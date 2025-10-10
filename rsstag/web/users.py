import json
import logging
import os
from typing import Optional, List
import asyncio
import aiohttp
from urllib.parse import urlencode, quote

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication
from rsstag.providers.bazqux import BazquxProvider
from rsstag.providers.providers import BAZQUX, TEXT_FILE, TELEGRAM, GMAIL
from rsstag.tasks import TASK_ALL, TASK_DOWNLOAD
from rsstag.users import TELEGRAM_CODE_FIELD, TELEGRAM_PASSWORD_FIELD

from werkzeug.wrappers import Request, Response
from werkzeug.utils import redirect


def on_login_get(
    app: "RSSTagApplication", request: Request, err: Optional[List[str]] = None
) -> Response:
    provider = request.cookies.get("provider")
    if provider in app.providers:
        # if (provider == 'bazqux') or (provider == 'inoreader') or (provider == 'telegram'):
        page = app.template_env.get_template("login.html")
        if not err:
            err = []
        google_auth_url = ""
        if provider == GMAIL:
            google_auth_url = app.routes.get_url_by_endpoint(
                endpoint="on_login_google_auth_get"
            )
        response = Response(
            page.render(
                err=err,
                login_url=app.routes.get_url_by_endpoint(endpoint="on_login_get"),
                version=app.config["settings"]["version"],
                support=app.config["settings"]["support"],
                provider=provider,
                google_auth_url=google_auth_url,
            ),
            mimetype="text/html",
        )
    else:
        page = app.template_env.get_template("error.html")
        response = Response(
            page.render(
                err=["Unknown provider"],
                version=app.config["settings"]["version"],
                support=app.config["settings"]["support"],
            ),
            mimetype="text/html",
        )

    return response


async def _exchange_code_for_token(app: "RSSTagApplication", code: str):
    """Exchange authorization code for access token and get user info."""
    token_url = "https://oauth2.googleapis.com/token"
    host_name = app.config["settings"]["host_name"]
    callback_path = app.routes.get_url_by_endpoint(endpoint="on_oauth2callback_get")
    redirect_uri = f"http://{host_name}{callback_path}"
    client_id = app.config["gmail"]["client_id"]
    client_secret = app.config["gmail"]["client_secret"]
    
    logging.info(f"Exchanging code for token with redirect_uri: {redirect_uri}")
    
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    
    async with aiohttp.ClientSession() as session:
        # Step 1: Exchange code for tokens
        try:
            async with session.post(token_url, data=payload) as resp:
                resp_text = await resp.text()
                if resp.status != 200:
                    logging.error(f"Failed to get token (status {resp.status}): {resp_text}")
                    return None, None
                token_data = await resp.json()
                logging.info(f"Token exchange successful. Token data keys: {list(token_data.keys())}")
        except aiohttp.ClientError as e:
            logging.error(f"Aiohttp client error during token exchange: {e}")
            return None, None
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse token response: {e}, Response: {resp_text}")
            return None, None
        
        access_token = token_data.get("access_token")
        if not access_token:
            logging.error("No access token in response")
            return None, None
        
        # Step 2: Get user info using the OpenID Connect UserInfo endpoint
        # This endpoint is part of the OpenID Connect standard and works with gmail.readonly + openid scopes
        userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        logging.info(f"Fetching user info from {userinfo_url}")
        
        try:
            async with session.get(userinfo_url, headers=headers) as resp:
                resp_text = await resp.text()
                if resp.status != 200:
                    logging.error(f"Failed to get user info (status {resp.status}): {resp_text}")
                    return token_data, None
                user_info = await resp.json()
                logging.info(f"User info retrieved successfully. Keys: {list(user_info.keys())}")
                return token_data, user_info
        except aiohttp.ClientError as e:
            logging.error(f"Aiohttp client error getting user info: {e}")
            return token_data, None
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse user info response: {e}, Response: {resp_text}")
            return token_data, None


def on_oauth2callback_get(app: "RSSTagApplication", request: Request) -> Response:
    """Handle OAuth callback from Google."""
    code = request.args.get("code")
    error = request.args.get("error")
    
    if error:
        logging.error(f"OAuth error from Google: {error}")
        return app.on_login_get(None, request, [f"Gmail login failed: {error}"])
    
    if not code:
        logging.error("OAuth callback received without code")
        return app.on_login_get(None, request, ["Gmail login failed: no code provided."])
    
    logging.info(f"OAuth callback received with code: {code[:20]}...")
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    token_data, user_info = loop.run_until_complete(
        _exchange_code_for_token(app, code)
    )
    
    if not token_data:
        logging.error("Failed to exchange code for token")
        return app.on_login_get(
            None, request, ["Failed to authenticate with Google. Please try again."]
        )
    
    if not user_info:
        logging.error("Failed to get user info from Google")
        return app.on_login_get(
            None, request, ["Failed to get user information from Google."]
        )
    
    email = user_info.get("email")
    if not email:
        logging.error(f"No email in user info. Keys: {list(user_info.keys())}")
        return app.on_login_get(None, request, ["Failed to get email from Google."])
    
    logging.info(f"Successfully authenticated user: {email}")
    
    user = app.users.get_by_login(email)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    
    if not user:
        logging.info(f"Creating new user for email: {email}")
        # create_user returns sid (string), not user object
        sid = app.users.create_user(
            login=email, password="", token=access_token, provider=GMAIL
        )
        if refresh_token:
            app.users.update_by_sid(sid, {"refresh_token": refresh_token})
        # Fetch the created user object
        user = app.users.get_by_sid(sid)
    else:
        logging.info(f"Updating existing user: {email}")
        update_data = {"token": access_token}
        if refresh_token:
            update_data["refresh_token"] = refresh_token
        app.users.update_by_sid(user["sid"], update_data)
        # Refresh user object with updated data
        user = app.users.get_by_sid(user["sid"])

    response = redirect(app.routes.get_url_by_endpoint(endpoint="on_root_get"))
    response.set_cookie("sid", user["sid"], max_age=app.user_ttl, httponly=True)

    return response


def on_login_google_auth_get(app: "RSSTagApplication", _: Request) -> Response:
    """Initiate OAuth flow with Google."""
    host_name = app.config["settings"]["host_name"]
    callback_path = app.routes.get_url_by_endpoint(endpoint="on_oauth2callback_get")
    redirect_uri = f"http://{host_name}{callback_path}"
    client_id = app.config["gmail"]["client_id"]
    
    # Request OpenID Connect scopes which include email access
    # openid: Required for OpenID Connect
    # email: Access to user's email address  
    # profile: Access to basic profile info
    # gmail.readonly: Read-only access to Gmail
    scopes = [
        "openid",
        "email", 
        "profile",
        "https://www.googleapis.com/auth/gmail.readonly"
    ]
    
    # Build OAuth URL with proper parameter encoding
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),  # Space-separated scopes
        "response_type": "code",
        "access_type": "offline",  # Request refresh token
        "prompt": "consent"  # Force consent screen to get refresh token
    }
    
    oauth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    
    logging.info(f"Redirecting to Google OAuth with scopes: {scopes}")
    logging.info(f"Redirect URI: {redirect_uri}")
    
    return redirect(oauth_url)




def on_login_post(app: "RSSTagApplication", request: Request) -> Response:
    login = request.form.get("login")
    password = request.form.get("password")

    if not login or not password:
        return app.on_login_get(None, request, ["Login or Password can`t be empty"])

    user = app.users.get_by_login_password(login, password)
    err = []
    if user and user["provider"] == BAZQUX:
        # login as baszqux user and check token
        err = []
        provider = BazquxProvider(app.config)
        is_valid = provider.is_valid_user(user)
        if is_valid is False:
            token = provider.get_token(login, password)
            if token:
                updated = app.users.update_by_sid(
                    user["sid"], {"token": token, "retoken": False}
                )
                if updated:
                    user["token"] = token
                    app.tasks.unfreeze_tasks(user, TASK_ALL)
                else:
                    err.append("Can`t safe new token. Try later.")
            else:
                err.append("Can`t refresh token. Try later.")
        elif is_valid is None:
            err.append("Can`t check token status. Try later.")
    elif not user:
        # create new user
        provider = request.cookies.get("provider")
        if provider == BAZQUX:
            provider_h = BazquxProvider(app.config)
            token = provider_h.get_token(login, password)
            if token:
                user = app.create_new_session(login, password, token, provider)
            elif token == "":
                err.append("Wrong login or password")
            else:
                err.append("Cant` create session. Try later")
        elif provider == TELEGRAM:
            user = app.create_new_session(login, password, "", provider)
        elif provider == TEXT_FILE:
            if os.path.exists(login):
                user = app.create_new_session(login, password, "", provider)
            else:
                err.append("File not exists")

    if err:
        return app.on_login_get(None, request, err)

    response = redirect(app.routes.get_url_by_endpoint(endpoint="on_root_get"))
    if user:
        response.set_cookie("sid", user["sid"], max_age=app.user_ttl, httponly=True)

    return response


def on_settings_post(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    try:
        settings = json.loads(request.get_data(as_text=True))
    except Exception as e:
        logging.warning("Can`t json load settings. Cause: %s", e)
        settings = {}
    if settings:
        settings = app.users.get_validated_settings(settings)
        if settings:
            updated = app.users.update_settings(user["sid"], settings)
            if updated:
                result = {"data": "ok"}
                code = 200
            elif updated is None:
                result = {"error": "Server in trouble"}
                code = 500
            else:
                result = {"error": "User not found"}
                code = 404
        else:
            result = {"error": "Something wrong with settings"}
            code = 400
    else:
        result = {"error": "Something wrong with settings"}
        code = 400

    return Response(json.dumps(result), mimetype="application/json", status=code)


def on_refresh_get_post(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    if user:
        try:
            updated = False
            if not user["in_queue"]:
                added = app.tasks.add_task(
                    {
                        "type": TASK_DOWNLOAD,
                        "user": user["sid"],
                        "host": request.environ["HTTP_HOST"],
                    }
                )
                if added:
                    updated = app.users.update_by_sid(
                        user["sid"],
                        {
                            "ready": False,
                            "in_queue": True,
                            "message": "Downloading data, please wait",
                        },
                    )
            else:
                updated = app.users.update_by_sid(
                    user["sid"], {"message": "You already in queue, please wait"}
                )
            if not updated:
                logging.error(
                    'Cant update data of user %s while create "posts update" task',
                    user["sid"],
                )
        except Exception as e:
            logging.error(
                "Can`t create refresh task for user %s. Info: %s", user["sid"], e
            )

    return redirect(app.routes.get_url_by_endpoint(endpoint="on_root_get"))


def on_status_get(app: "RSSTagApplication", user: Optional[dict]) -> Response:
    if user:
        if user["retoken"]:
            result = {
                "data": {
                    "is_ok": False,
                    "msgs": ["Need refresh token. Click me for relogin"],
                }
            }
        else:
            task_titles = app.tasks.get_current_tasks_titles(user["sid"])
            result = {"data": {"is_ok": True, "msgs": task_titles}}
            if (TELEGRAM_CODE_FIELD in user) and (user[TELEGRAM_CODE_FIELD] == ""):
                result["data"][TELEGRAM_CODE_FIELD] = True
            if (TELEGRAM_PASSWORD_FIELD in user) and (user[TELEGRAM_PASSWORD_FIELD] == ""):
                result["data"][TELEGRAM_PASSWORD_FIELD] = True
    else:
        result = {
            "data": {"is_ok": False, "msgs": ["Looks like you are not logged in"]}
        }

    return Response(
        json.dumps(result), mimetype="text/html", headers={"Pragma": "no-cache"}
    )


def on_select_provider_get(app: "RSSTagApplication") -> Response:
    page = app.template_env.get_template("provider.html")
    return Response(
        page.render(
            select_provider_url=app.routes.get_url_by_endpoint(
                endpoint="on_select_provider_post"
            ),
            version=app.config["settings"]["version"],
            support=app.config["settings"]["support"],
        ),
        mimetype="text/html",
    )


def on_select_provider_post(app: "RSSTagApplication", request: Request) -> Response:
    provider = request.form.get("provider")
    if provider:
        response = redirect(app.routes.get_url_by_endpoint(endpoint="on_login_get"))
        response.set_cookie("provider", provider, max_age=300, httponly=True)
    else:
        page = app.template_env.get_template("error.html")
        response = Response(page.render(err=["Unknown provider"]), mimetype="text/html")

    return response


def on_root_get(
    app: "RSSTagApplication", user: Optional[dict], err: Optional[List[str]] = None
) -> Response:
    if not err:
        err = []
    only_unread = True
    if user and "provider" in user:
        posts = app.posts.get_stat(user["sid"])
        sentiments = app.tags.get_sentiments(
            user["sid"], user["settings"]["only_unread"]
        )
        page = app.template_env.get_template("root-logged.html")
        response = Response(
            page.render(
                err=err,
                support=app.config["settings"]["support"],
                version=app.config["settings"]["version"],
                user_settings=user["settings"],
                provider=user["provider"],
                posts=posts,
                sentiments=sentiments,
            ),
            mimetype="text/html",
        )
    else:
        provider = "Not selected"
        page = app.template_env.get_template("root.html")
        response = Response(
            page.render(
                err=err,
                only_unread=only_unread,
                provider=provider,
                support=app.config["settings"]["support"],
                version=app.config["settings"]["version"],
            ),
            mimetype="text/html",
        )

    return response

def on_telegram_auth_post(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    tlg_data = json.loads(request.get_data(as_text=True))
    result = {"error": "Something wrong with telegram auth"}
    code = 400
    if tlg_data:
        set_data = {}
        if TELEGRAM_CODE_FIELD in tlg_data and tlg_data[TELEGRAM_CODE_FIELD]:
            set_data[TELEGRAM_CODE_FIELD] = tlg_data[TELEGRAM_CODE_FIELD]
        if TELEGRAM_PASSWORD_FIELD in tlg_data and tlg_data[TELEGRAM_PASSWORD_FIELD]:
            set_data[TELEGRAM_PASSWORD_FIELD] = tlg_data[TELEGRAM_PASSWORD_FIELD]
        if set_data:
            app.users.update_by_sid(user["sid"], set_data)
            result = {"data": "ok"}
            code = 200

    return Response(json.dumps(result), mimetype="application/json", status=code)