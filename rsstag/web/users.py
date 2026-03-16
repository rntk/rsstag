from datetime import datetime, timezone
import json
import logging
import os
import secrets
import hashlib
import base64
from typing import Optional, List
import asyncio
import aiohttp
import base64
import time
from urllib.parse import urlencode

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication
from rsstag.providers.bazqux import BazquxProvider
from rsstag.providers.providers import BAZQUX, TEXT_FILE, TELEGRAM, GMAIL, X
from rsstag.providers.x import XProvider
from rsstag.tasks import TASK_ALL, TASK_DOWNLOAD
from rsstag.users import TELEGRAM_CODE_FIELD, TELEGRAM_PASSWORD_FIELD

from werkzeug.wrappers import Request, Response
from werkzeug.utils import redirect


def _build_redirect_uri(app: "RSSTagApplication", endpoint: str) -> str:
    host_name = app.config["settings"]["host_name"]
    protocol = app.config["settings"].get("protocol", "http")
    callback_path = app.routes.get_url_by_endpoint(endpoint=endpoint)
    return f"{protocol}://{host_name}{callback_path}"


def _base64url_sha256(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def _clear_x_oauth_state(app: "RSSTagApplication", sid: str) -> None:
    app.users.update_by_sid(
        sid,
        {
            "x_oauth_state": "",
            "x_code_verifier": "",
        },
    )


def on_login_get(
    app: "RSSTagApplication", request: Request, err: Optional[List[str]] = None
) -> Response:
    page = app.template_env.get_template("login.html")
    if not err:
        err = []
    response = Response(
        page.render(
            err=err,
            login_url=app.routes.get_url_by_endpoint(endpoint="on_login_get"),
            register_url=app.routes.get_url_by_endpoint(endpoint="on_register_get"),
            version=app.config["settings"]["version"],
            support=app.config["settings"]["support"],
        ),
        mimetype="text/html",
    )

    return response


async def _exchange_code_for_token(app: "RSSTagApplication", code: str):
    """Exchange authorization code for access token and get user info."""
    token_url = "https://oauth2.googleapis.com/token"
    redirect_uri = _build_redirect_uri(app, "on_oauth2callback_get")
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
                    logging.error(
                        f"Failed to get token (status {resp.status}): {resp_text}"
                    )
                    return None, None
                token_data = await resp.json()
                logging.info(
                    f"Token exchange successful. Token data keys: {list(token_data.keys())}"
                )
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
                    logging.error(
                        f"Failed to get user info (status {resp.status}): {resp_text}"
                    )
                    return token_data, None
                user_info = await resp.json()
                logging.info(
                    f"User info retrieved successfully. Keys: {list(user_info.keys())}"
                )
                return token_data, user_info
        except aiohttp.ClientError as e:
            logging.error(f"Aiohttp client error getting user info: {e}")
            return token_data, None
        except json.JSONDecodeError as e:
            logging.error(
                f"Failed to parse user info response: {e}, Response: {resp_text}"
            )
            return token_data, None


def on_oauth2callback_get(
    app: "RSSTagApplication", user: Optional[dict], request: Request
) -> Response:
    """Handle OAuth callback from Google."""
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        logging.error(f"OAuth error from Google: {error}")
        return app.on_login_get(None, request, [f"Gmail login failed: {error}"])

    if not code:
        logging.error("OAuth callback received without code")
        return app.on_login_get(
            None, request, ["Gmail login failed: no code provided."]
        )

    logging.info(f"OAuth callback received with code: {code[:20]}...")

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    token_data, user_info = loop.run_until_complete(_exchange_code_for_token(app, code))

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

    if not user:
        return app.on_login_get(None, request, ["Please login before linking Gmail."])
    account_user = user
    existing_entry = app.users.get_provider_entry(account_user, GMAIL)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")

    provider_payload = {"login": email, "token": access_token, "retoken": False}
    if refresh_token:
        provider_payload["refresh_token"] = refresh_token

    set_active = not account_user.get("provider")
    if not existing_entry:
        logging.info("Linking Gmail provider for user: %s", account_user["sid"])
        app.users.add_provider(
            account_user["sid"], GMAIL, provider_payload, set_active=set_active
        )
    else:
        logging.info("Updating Gmail provider for user: %s", account_user["sid"])
        app.users.update_provider(account_user["sid"], GMAIL, provider_payload)
        if set_active:
            app.users.set_active_provider(account_user["sid"], GMAIL)

    response = redirect(
        app.routes.get_url_by_endpoint(
            endpoint="on_provider_detail_get", params={"provider": GMAIL}
        )
    )

    return response


def on_login_google_auth_get(
    app: "RSSTagApplication", user: Optional[dict], _: Request
) -> Response:
    """Initiate OAuth flow with Google."""
    if not user:
        return redirect(app.routes.get_url_by_endpoint(endpoint="on_login_get"))
    redirect_uri = _build_redirect_uri(app, "on_oauth2callback_get")
    client_id = app.config["gmail"]["client_id"]

    # Request OpenID Connect scopes which include email access
    # openid: Required for OpenID Connect
    # email: Access to user's email address
    # profile: Access to basic profile info
    # gmail.readonly: Read-only access to Gmail
    # gmail.modify: Allows adding/removing labels (needed for marking emails)
    scopes = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.labels",
    ]

    # Build OAuth URL with proper parameter encoding
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),  # Space-separated scopes
        "response_type": "code",
        "access_type": "offline",  # Request refresh token
        "prompt": "consent",  # Force consent screen to get refresh token
    }

    oauth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    logging.info(f"Redirecting to Google OAuth with scopes: {scopes}")
    logging.info(f"Redirect URI: {redirect_uri}")

    return redirect(oauth_url)


async def _exchange_x_code_for_token(
    app: "RSSTagApplication", code: str, code_verifier: str
) -> Optional[dict]:
    x_config = app.config.get("x", {})
    token_url = f"{x_config.get('api_base', 'https://api.x.com')}/2/oauth2/token"
    payload = {
        "code": code,
        "grant_type": "authorization_code",
        "client_id": x_config.get("client_id", ""),
        "redirect_uri": _build_redirect_uri(app, "on_x_oauth2callback_get"),
        "code_verifier": code_verifier,
    }
    client_secret = x_config.get("client_secret", "")
    if client_secret:
        payload["client_secret"] = client_secret

    headers: dict[str, str] = {}
    if payload["client_id"] and client_secret:
        credentials = f"{payload['client_id']}:{client_secret}".encode("utf-8")
        headers["Authorization"] = (
            f"Basic {base64.b64encode(credentials).decode('ascii')}"
        )

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(token_url, data=payload, headers=headers) as resp:
                if resp.status != 200:
                    logging.error("Failed to get X token (status %s): %s", resp.status, await resp.text())
                    return None
                return await resp.json()
        except aiohttp.ClientError as exc:
            logging.error("X OAuth token exchange failed: %s", exc)
            return None


async def _get_x_user_info(app: "RSSTagApplication", access_token: str) -> Optional[dict]:
    api_base = app.config.get("x", {}).get("api_base", "https://api.x.com")
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"user.fields": "username,name,profile_image_url"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{api_base}/2/users/me", headers=headers, params=params
            ) as resp:
                if resp.status != 200:
                    logging.error("Failed to get X user info (status %s): %s", resp.status, await resp.text())
                    return None
                payload = await resp.json()
        except aiohttp.ClientError as exc:
            logging.error("Failed to request X user info: %s", exc)
            return None

    return payload.get("data")


def on_login_x_auth_get(
    app: "RSSTagApplication", user: Optional[dict], _: Request
) -> Response:
    if not user:
        return redirect(app.routes.get_url_by_endpoint(endpoint="on_login_get"))
    provider_h = XProvider(app.config)
    state = secrets.token_urlsafe(24)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _base64url_sha256(code_verifier)
    app.users.update_by_sid(
        user["sid"],
        {
            "x_oauth_state": state,
            "x_code_verifier": code_verifier,
        },
    )
    oauth_url = provider_h.get_authorization_url(
        _build_redirect_uri(app, "on_x_oauth2callback_get"),
        state,
        code_challenge,
    )
    return redirect(oauth_url)


def on_x_oauth2callback_get(
    app: "RSSTagApplication", user: Optional[dict], request: Request
) -> Response:
    if not user:
        return app.on_login_get(None, request, ["Please login before linking X."])

    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")
    if error:
        logging.error("OAuth error from X: %s", error)
        _clear_x_oauth_state(app, user["sid"])
        return app.on_login_get(None, request, [f"X login failed: {error}"])

    current_user = app.users.get_by_sid(user["sid"])
    if not current_user:
        return app.on_login_get(None, request, ["User not found during X login."])
    expected_state = current_user.get("x_oauth_state", "")
    code_verifier = current_user.get("x_code_verifier", "")
    if not code or not state or state != expected_state or not code_verifier:
        _clear_x_oauth_state(app, user["sid"])
        return app.on_login_get(None, request, ["X login failed: invalid OAuth state."])

    async def fetch_x_data():
        t_data = await _exchange_x_code_for_token(app, code, code_verifier)
        if not t_data or "access_token" not in t_data:
            return t_data, None
        u_info = await _get_x_user_info(app, t_data["access_token"])
        return t_data, u_info

    token_data, user_info = asyncio.run(fetch_x_data())
    if not token_data or "access_token" not in token_data:
        _clear_x_oauth_state(app, user["sid"])
        return app.on_login_get(None, request, ["Failed to authenticate with X. Please try again."])

    if not user_info:
        _clear_x_oauth_state(app, user["sid"])
        return app.on_login_get(None, request, ["Failed to get X account information."])

    existing_entry = app.users.get_provider_entry(current_user, X)
    refresh_token = token_data.get("refresh_token")
    if not refresh_token and existing_entry:
        refresh_token = existing_entry.get("refresh_token", "")

    provider_payload = {
        "login": user_info.get("username", ""),
        "token": token_data["access_token"],
        "access_token": token_data["access_token"],
        "retoken": False,
        "x_user_id": user_info.get("id", ""),
        "x_username": user_info.get("username", ""),
        "x_home_enabled": True,
        "x_selected_feeds": [],
        "x_follow_since_ids": {},
        "x_home_since_id": "",
        "x_fetch_mode": "unread",
        "x_max_results_per_sync": int(
            app.config.get("x", {}).get("max_results", user["settings"].get("x_max_results", 50))
        ),
        "x_exclude_replies": False,
        "x_exclude_reposts": False,
    }
    if refresh_token:
        provider_payload["refresh_token"] = refresh_token
    if token_data.get("expires_in"):
        provider_payload["token_expires_at"] = int(time.time()) + int(token_data["expires_in"])

    set_active = not current_user.get("provider")
    if not existing_entry:
        app.users.add_provider(user["sid"], X, provider_payload, set_active=set_active)
    else:
        app.users.update_provider(user["sid"], X, provider_payload)
        if set_active:
            app.users.set_active_provider(user["sid"], X)

    _clear_x_oauth_state(app, user["sid"])
    return redirect(
        app.routes.get_url_by_endpoint(
            endpoint="on_provider_detail_get", params={"provider": X}
        )
    )


def on_login_post(app: "RSSTagApplication", request: Request) -> Response:
    login = request.form.get("login")
    password = request.form.get("password")

    if not login or not password:
        return app.on_login_get(None, request, ["Login or Password can`t be empty"])

    user = app.users.get_by_login_password(login, password)
    if not user:
        return app.on_login_get(None, request, ["Wrong login or password"])

    response = redirect(app.routes.get_url_by_endpoint(endpoint="on_root_get"))
    response.set_cookie("sid", user["sid"], max_age=app.user_ttl, httponly=True)

    return response


def on_register_get(
    app: "RSSTagApplication", _: Request, err: Optional[List[str]] = None
) -> Response:
    page = app.template_env.get_template("register.html")
    return Response(
        page.render(
            err=err or [],
            register_url=app.routes.get_url_by_endpoint(endpoint="on_register_post"),
            login_url=app.routes.get_url_by_endpoint(endpoint="on_login_get"),
            version=app.config["settings"]["version"],
            support=app.config["settings"]["support"],
        ),
        mimetype="text/html",
    )


def on_register_post(app: "RSSTagApplication", request: Request) -> Response:
    username = request.form.get("login")
    password = request.form.get("password")
    confirm = request.form.get("password_confirm")

    if not username or not password:
        return on_register_get(app, request, ["Login or Password can`t be empty"])
    if password != confirm:
        return on_register_get(app, request, ["Passwords do not match"])
    if app.users.get_by_username(username):
        return on_register_get(app, request, ["User already exists"])

    sid = app.users.create_account(username, password)
    response = redirect(app.routes.get_url_by_endpoint(endpoint="on_data_sources_get"))
    response.set_cookie("sid", sid, max_age=app.user_ttl, httponly=True)

    return response


def on_logout_get(app: "RSSTagApplication") -> Response:
    response = redirect(app.routes.get_url_by_endpoint(endpoint="on_root_get"))
    response.delete_cookie("sid")
    response.delete_cookie("provider")
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
        configured = list(user.get("providers", {}).keys())
        if not configured:
            return redirect(
                app.routes.get_url_by_endpoint(endpoint="on_data_sources_get")
            )
        try:
            any_added = False
            for prov in configured:
                added = app.tasks.add_task(
                    {
                        "type": TASK_DOWNLOAD,
                        "user": user["sid"],
                        "provider": prov,
                        "host": request.environ["HTTP_HOST"],
                    }
                )
                if added:
                    any_added = True
            if any_added:
                app.users.update_by_sid(
                    user["sid"],
                    {
                        "in_queue": True,
                        "message": "Downloading data, please wait",
                    },
                )
            else:
                app.users.update_by_sid(
                    user["sid"], {"message": "You already in queue, please wait"}
                )
        except Exception as e:
            logging.error(
                "Can`t create refresh task for user %s. Info: %s", user["sid"], e
            )

    return redirect(app.routes.get_url_by_endpoint(endpoint="on_root_get"))


def on_status_get(app: "RSSTagApplication", user: Optional[dict]) -> Response:
    if user:
        retoken = False
        for prov_name, prov_entry in user.get("providers", {}).items():
            if isinstance(prov_entry, dict) and prov_entry.get("retoken"):
                retoken = True
                break
        if not retoken:
            retoken = user.get("retoken", False)
        if retoken:
            result = {
                "data": {
                    "is_ok": False,
                    "msgs": ["Need refresh token. Click me for relogin"],
                }
            }
        else:
            task_titles = app.tasks.get_tasks_status(user["sid"])
            result = {"data": {"is_ok": True, "msgs": task_titles}}
            if TELEGRAM in user.get("providers", {}):
                if (TELEGRAM_CODE_FIELD in user) and (user[TELEGRAM_CODE_FIELD] == ""):
                    result["data"][TELEGRAM_CODE_FIELD] = True
                if (TELEGRAM_PASSWORD_FIELD in user) and (
                    user[TELEGRAM_PASSWORD_FIELD] == ""
                ):
                    result["data"][TELEGRAM_PASSWORD_FIELD] = True
    else:
        result = {
            "data": {"is_ok": False, "msgs": ["Looks like you are not logged in"]}
        }

    return Response(
        json.dumps(result), mimetype="text/html", headers={"Pragma": "no-cache"}
    )


def on_select_provider_get(app: "RSSTagApplication") -> Response:
    return redirect(app.routes.get_url_by_endpoint(endpoint="on_data_sources_get"))


def on_select_provider_post(app: "RSSTagApplication", request: Request) -> Response:
    provider = request.form.get("provider")
    if provider:
        response = redirect(
            app.routes.get_url_by_endpoint(
                endpoint="on_provider_detail_get", params={"provider": provider}
            )
        )
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
    if user:
        provider = user.get("provider", "")
        if provider:
            posts = app.posts.get_stat(user["sid"])
            sentiments = app.tags.get_sentiments(
                user["sid"], user["settings"]["only_unread"]
            )
        else:
            posts = {"tags": 0, "unread": 0, "read": 0}
            sentiments = []
        page = app.template_env.get_template("root-logged.html")
        response = Response(
            page.render(
                err=err,
                support=app.config["settings"]["support"],
                version=app.config["settings"]["version"],
                user_settings=user["settings"],
                provider=provider,
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


def on_telegram_auth_post(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
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


def on_data_sources_get(app: "RSSTagApplication", user: dict) -> Response:
    page = app.template_env.get_template("data-sources.html")
    sources = []
    for provider in app.providers:
        entry = app.users.get_provider_entry(user, provider)
        sources.append(
            {
                "id": provider,
                "connected": entry is not None,
                "login": entry.get("login") if entry else "",
                "retoken": entry.get("retoken", False) if entry else False,
                "detail_url": app.routes.get_url_by_endpoint(
                    endpoint="on_provider_detail_get", params={"provider": provider}
                ),
            }
        )
    return Response(
        page.render(
            sources=sources,
            active_provider=user.get("provider", ""),
            version=app.config["settings"]["version"],
            support=app.config["settings"]["support"],
            user_settings=user["settings"],
        ),
        mimetype="text/html",
    )


def on_provider_detail_get(
    app: "RSSTagApplication",
    user: dict,
    provider: str,
    err: Optional[List[str]] = None,
) -> Response:
    if provider not in app.providers:
        return redirect(app.routes.get_url_by_endpoint(endpoint="on_data_sources_get"))
    page = app.template_env.get_template("provider-detail.html")
    entry = app.users.get_provider_entry(user, provider)
    return Response(
        page.render(
            err=err or [],
            provider=provider,
            entry=entry,
            active_provider=user.get("provider", ""),
            login_url=app.routes.get_url_by_endpoint(
                endpoint="on_provider_detail_post", params={"provider": provider}
            ),
            google_auth_url=app.routes.get_url_by_endpoint(
                endpoint="on_login_google_auth_get"
            ),
            x_auth_url=app.routes.get_url_by_endpoint(
                endpoint="on_login_x_auth_get"
            ),
            feeds_url=app.routes.get_url_by_endpoint(
                endpoint="on_provider_feeds_get_post", params={"provider": provider}
            ),
            data_sources_url=app.routes.get_url_by_endpoint(
                endpoint="on_data_sources_get"
            ),
            version=app.config["settings"]["version"],
            support=app.config["settings"]["support"],
            user_settings=user["settings"],
        ),
        mimetype="text/html",
    )


def on_provider_detail_post(
    app: "RSSTagApplication", user: dict, provider: str, request: Request
) -> Response:
    action = request.form.get("action")
    if action == "activate":
        if app.users.get_provider_entry(user, provider):
            app.users.set_active_provider(user["sid"], provider)
        return redirect(
            app.routes.get_url_by_endpoint(
                endpoint="on_provider_detail_get", params={"provider": provider}
            )
        )

    if action == "download":
        if not user["in_queue"]:
            added = app.tasks.add_task(
                {
                    "type": TASK_DOWNLOAD,
                    "user": user["sid"],
                    "host": request.environ["HTTP_HOST"],
                    "provider": provider,
                    "selection": {"channels": [], "feeds": [], "categories": []},
                }
            )
            if added:
                updated = app.users.update_by_sid(
                    user["sid"],
                    {
                        "in_queue": True,
                        "message": "Downloading from provider, please wait",
                    },
                )
                if not updated:
                    logging.error(
                        "Cant update data of user %s while create download task",
                        user["sid"],
                    )
        else:
            app.users.update_by_sid(
                user["sid"], {"message": "You already in queue, please wait"}
            )
        return redirect(app.routes.get_url_by_endpoint(endpoint="on_root_get"))

    login = request.form.get("login")
    password = request.form.get("password")
    err = []

    if provider == BAZQUX:
        if not login or not password:
            err.append("Login or Password can`t be empty")
        else:
            provider_h = BazquxProvider(app.config)
            token = provider_h.get_token(login, password)
            if token:
                app.users.add_provider(
                    user["sid"],
                    provider,
                    app.users.build_provider_data(login, password, token, provider),
                    set_active=True,
                )
                app.tasks.unfreeze_tasks(user, TASK_ALL)
            elif token == "":
                err.append("Wrong login or password")
            else:
                err.append("Cant` create session. Try later")
    elif provider == TELEGRAM:
        if not login or not password:
            err.append("Login or Password can`t be empty")
        else:
            app.users.add_provider(
                user["sid"],
                provider,
                app.users.build_provider_data(login, password, "", provider),
                set_active=True,
            )
            app.users.update_by_sid(
                user["sid"], {TELEGRAM_CODE_FIELD: "", TELEGRAM_PASSWORD_FIELD: ""}
            )
    elif provider == TEXT_FILE:
        if not login or not password:
            err.append("Login or Password can`t be empty")
        elif os.path.exists(login):
            app.users.add_provider(
                user["sid"],
                provider,
                app.users.build_provider_data(login, password, "", provider),
                set_active=True,
            )
        else:
            err.append("File not exists")
    elif provider == GMAIL:
        return redirect(
            app.routes.get_url_by_endpoint(endpoint="on_login_google_auth_get")
        )
    elif provider == X:
        return redirect(
            app.routes.get_url_by_endpoint(endpoint="on_login_x_auth_get")
        )

    if err:
        return on_provider_detail_get(app, user, provider, err)

    return redirect(
        app.routes.get_url_by_endpoint(
            endpoint="on_provider_detail_get", params={"provider": provider}
        )
    )
