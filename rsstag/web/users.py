import json
import logging
from typing import Optional, List

from rsstag.web.app import RSSTagApplication
from rsstag.providers import BazquxProvider
from rsstag.tasks import TASK_ALL, TASK_DOWNLOAD

from werkzeug.wrappers import Request, Response
from werkzeug.utils import redirect

def on_login_get(app: RSSTagApplication, request: Request, err: Optional[List[str]]=None) -> Response:
    provider = request.cookies.get('provider')
    if provider in app.providers:
        # if (provider == 'bazqux') or (provider == 'inoreader') or (provider == 'telegram'):
        page = app.template_env.get_template('login.html')
        if not err:
            err = []
        response = Response(page.render(
            err=err,
            login_url=app.routes.getUrlByEndpoint(endpoint='on_login_get'),
            version=app.config['settings']['version'],
            support=app.config['settings']['support'],
            provider=provider
        ), mimetype='text/html')
    else:
        page = app.template_env.get_template('error.html')
        response = Response(page.render(
            err=['Unknown provider'],
            version=app.config['settings']['version'],
            support=app.config['settings']['support']
        ), mimetype='text/html')

    return response

def on_login_post(app: RSSTagApplication, request: Request) -> Response:
    login = request.form.get('login')
    password = request.form.get('password')

    if not login or not password:
        return app.on_login_get(None, request, ["Login or Password can`t be empty"])

    user = app.users.get_by_login_password(login, password)
    err = []
    if user and user["provider"] == "bazqux":
        # login as baszqux user and check token
        err = []
        provider = BazquxProvider(app.config)
        is_valid = provider.is_valid_user(user)
        if is_valid == False:
            token = provider.get_token(login, password)
            if token:
                updated = app.users.update_by_sid(user['sid'], {'token': token, 'retoken': False})
                if updated:
                    user['token'] = token
                    app.tasks.unfreeze_tasks(user, TASK_ALL)
                else:
                    err.append('Can`t safe new token. Try later.')
            else:
                err.append('Can`t refresh token. Try later.')
        elif is_valid == None:
            err.append('Can`t check token status. Try later.')
    elif not user:
        # create new user
        provider = request.cookies.get("provider")
        if (provider == 'bazqux') or (provider == 'inoreader'):
            provider_h = BazquxProvider(app.config)
            token = provider_h.get_token(login, password)
            if token:
                user = app.createNewSession(login, password, token, provider)
            elif token == '':
                err.append('Wrong login or password')
            else:
                err.append('Cant` create session. Try later')
        elif provider == "telegram":
            user = app.createNewSession(login, password, "", provider)

    if err:
        return app.on_login_get(None, request, err)

    response = redirect(app.routes.getUrlByEndpoint(endpoint='on_root_get'))
    if user:
        response.set_cookie('sid', user['sid'], max_age=app.user_ttl, httponly=True)

    return response

def on_settings_post(app: RSSTagApplication, user: dict, request: Request) -> Response:
    try:
        settings = json.loads(request.get_data(as_text=True))
    except Exception as e:
        logging.warning('Can`t json load settings. Cause: %s', e)
        settings = {}
    if settings:
        settings = app.users.get_validated_settings(settings)
        if settings:
            updated = app.users.update_settings(user['sid'], settings)
            if updated:
                result = {'data': 'ok'}
                code = 200
            elif updated is None:
                result = {'error': 'Server in trouble'}
                code = 500
            else:
                result = {'error': 'User not found'}
                code = 404
        else:
            result = {'error': 'Something wrong with settings'}
            code = 400
    else:
        result = {'error': 'Something wrong with settings'}
        code = 400

    return Response(
        json.dumps(result),
        mimetype="application/json",
        status=code
    )

def on_refresh_get_post(app: RSSTagApplication, user: dict, request: Request) -> Response:
    if user:
        try:
            updated = False
            if not user['in_queue']:
                added = app.tasks.add_task({
                    'type': TASK_DOWNLOAD,
                    'user': user['sid'],
                    'host': request.environ['HTTP_HOST']
                })
                if added:
                    updated = app.users.update_by_sid(
                        user['sid'],
                        {'ready': False, 'in_queue': True, 'message': 'Downloading data, please wait'}
                    )
            else:
                updated = app.users.update_by_sid(
                    user['sid'],
                    {'message': 'You already in queue, please wait'}
                )
            if not updated:
                logging.error('Cant update data of user %s while create "posts update" task', user['sid'])
        except Exception as e:
            logging.error('Can`t create refresh task for user %s. Info: %s', user['sid'], e)

    return redirect(app.routes.getUrlByEndpoint(endpoint="on_root_get"))

def on_status_get(app: RSSTagApplication, user: Optional[dict]) -> Response:
    if user:
        if user['retoken']:
            result = {'data': {
                'is_ok': False,
                'msgs': ['Need refresh token. Click me for relogin']
            }}
        else :
            task_titles = app.tasks.get_current_tasks_titles(user['sid'])
            result = {'data': {
                'is_ok': True,
                'msgs': task_titles
            }}
    else:
        result = {'data': {
            'is_ok': False,
            'msgs': ['Looks like you are not logged in']
        }}

    return Response(
        json.dumps(result),
        mimetype="text/html",
        headers={"Pragma": "no-cache"}
    )

def on_select_provider_get(app: RSSTagApplication) -> Response:
    page = app.template_env.get_template('provider.html')
    return Response(page.render(
        select_provider_url=app.routes.getUrlByEndpoint(endpoint='on_select_provider_post'),
        version=app.config['settings']['version'],
        support=app.config['settings']['support']
    ), mimetype='text/html')

def on_select_provider_post(app: RSSTagApplication, request: Request) -> Response:
    provider = request.form.get('provider')
    if provider:
        response = redirect(app.routes.getUrlByEndpoint(endpoint='on_login_get'))
        response.set_cookie('provider', provider, max_age=300, httponly=True)
    else:
        page = app.template_env.get_template('error.html')
        response = Response(page.render(err=['Unknown provider']), mimetype='text/html')

    return response

def on_root_get(app: RSSTagApplication, user: Optional[dict], err: Optional[List[str]]=None) -> Response:
    if not err:
        err = []
    only_unread = True
    if user and 'provider' in user:
        posts = app.posts.get_stat(user['sid'])
        sentiments = app.tags.get_sentiments(user['sid'], user['settings']['only_unread'])
        page = app.template_env.get_template('root-logged.html')
        response = Response(
            page.render(
                err=err,
                support=app.config['settings']['support'],
                version=app.config['settings']['version'],
                user_settings=user['settings'],
                provider=user['provider'],
                posts=posts,
                sentiments=sentiments
            ),
            mimetype='text/html'
        )
    else:
        provider = 'Not selected'
        page = app.template_env.get_template('root.html')
        response = Response(
            page.render(
                err=err,
                only_unread=only_unread,
                provider=provider,
                support=app.config['settings']['support'],
                version=app.config['settings']['version']
            ),
            mimetype='text/html'
        )

    return response
