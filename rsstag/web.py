import os
import json
from urllib.parse import unquote_plus, quote_plus, urlencode, unquote, quote
from http import client
import html
import time
import gzip
import logging
from collections import OrderedDict
from datetime import datetime
from random import randint
from hashlib import md5, sha256
from werkzeug.wrappers import Response, Request
from werkzeug.exceptions import HTTPException, NotFound, InternalServerError
from werkzeug.utils import redirect
from jinja2 import Environment, PackageLoader
from pymongo import MongoClient, DESCENDING
from rsstag.routes import RSSTagRoutes
from rsstag.utils import getSortedDictByAlphabet, load_config
from rsstag import TASK_NOT_IN_PROCESSING
from gensim.models.doc2vec import Doc2Vec

class RSSTagApplication(object):
    request = None
    response = None
    template_env = None
    routes = None
    endpoints = {}
    user = {}
    config = None
    config_path = None
    workers_pool = []
    providers = []
    user_ttl = 0
    count_showed_numbers = 4
    db = None
    need_cookie_update = False
    first_letters = None
    d2v = None
    allow_not_logged = (
        'on_root_get',
        'on_login_get',
        'on_login_post',
        'on_select_provider_post',
        'on_select_provider_get',
        'on_ready_get',
        'on_refresh_get_post',
        'on_favicon_get'
    )
    no_category_name = 'NotCategorized'

    def __init__(self, config_path=None):
        self.config = load_config(config_path)
        if self.config['settings']['no_category_name']:
            self.no_category_name = self.config['settings']['no_category_name']
        if os.path.exists(self.config['settings']['model']):
            self.d2v = Doc2Vec.load(self.config['settings']['model'])

        try:
            logging.basicConfig(
                filename=self.config['settings']['log_file'],
                filemode='a',
                level=getattr(logging, self.config['settings']['log_level'].upper())
            )
        except Exception as e:
            logging.critical('Error in logging configuration: %s', e)
        self.config_path = config_path
        self.template_env = Environment(
            loader=PackageLoader(
                'web',
                os.path.join(
                    'templates',
                    self.config['settings']['templates']
                )
            )
        )
        self.template_env.filters['json'] = json.dumps
        self.providers = self.config['settings']['providers'].split(',')
        self.user_ttl = int(self.config['settings']['user_ttl'])
        cl = MongoClient(self.config['settings']['db_host'], int(self.config['settings']['db_port']))
        self.db = cl.rss
        self.prepareDB()
        self.routes = RSSTagRoutes(self.config['settings']['host_name'])
        self.updateEndpoints()

    def prepareDB(self):
        try:
            self.db.posts.create_index('owner')
            self.db.posts.create_index('category_id')
            self.db.posts.create_index('feed_id')
            self.db.posts.create_index('read')
            self.db.posts.create_index('tags')
            self.db.posts.create_index('pid')
            #self.db.posts.create_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
            self.db.feeds.create_index('owner')
            self.db.feeds.create_index('feed_id')
            #self.db.feeds.create_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
            self.db.letters.create_index('owner', unique=True)
            #self.db.letters.create_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
            self.db.users.create_index('sid')
            #self.db.users.create_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
            #self.db.users.update_many({'in_queue': True}, {'$set': {'in_queue': False, 'ready_flag': True}})
            self.db.tags.create_index('owner')
            self.db.tags.create_index('tag')
            self.db.tags.create_index('unread_count')
            self.db.tags.create_index('posts_count')
            self.db.tags.create_index('processing')
            #self.db.tags.create_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
            self.db.download_queue.create_index('processing')
            #self.db.download_queue.create_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
            self.db.mark_queue.create_index('processing')
            self.db.words.create_index('word')
            #self.db.mark_queue.create_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
        except Exception as e:
            logging.warning('Indexses not created. May be already exists.')

    def close(self):
        if self.workers_pool:
            for p in self.workers_pool:
                p.terminate()
        logging.info('Goodbye!')

    def updateEndpoints(self):
        routes = self.routes.get_werkzeug_routes()
        for i in routes.iter_rules():
            self.endpoints[i.endpoint] = getattr(self, i.endpoint)

    def prepareSession(self, user=None):
        if user is None:
            sid = self.request.cookies.get('sid')
            if sid:
                self.user = self.db.users.find_one({'sid': sid})
            else:
                self.user = None
        else:
            self.user = user

        if self.user:
            self.need_cookie_update = True
            return True
        else:
            self.need_cookie_update = False
            return False

    def createNewSession(self, login, password):
        self.need_cookie_update = True
        if self.user and 'sid' in self.user:
            user = self.db.users.find_one({'sid': self.user['sid']})
            if user:
                try:
                    self.db.users.update_one(
                        {'sid': self.user['sid']},
                        {'$set': {
                            'ready_flag': False,
                            'provider': self.user['provider'],
                            'token': self.user['token'],
                            'message': 'Click on "Refresh posts" to start downloading data',
                            'in_queue': False,
                            'createdAt': datetime.utcnow()
                        }}
                    )
                except Exception as e:
                    self.user = None
                    logging.error('Can`t create new session: %s', e)
        else:
            settings = {
                'only_unread': True,
                'tags_on_page': 100,
                'posts_on_page': 30,
                'hot_tags' : False
            }
            self.user['sid'] = sha256(os.urandom(randint(80, 200))).hexdigest()
            self.user['letter'] = ''
            self.user['page'] = '1'
            self.user['settings'] = settings
            self.user['ready_flag'] = False
            self.user['message'] = 'Click on "Refresh posts" to start downloading data'
            self.user['in_queue'] = False
            self.user['createdAt'] = datetime.utcnow()
            self.user['lp'] = sha256((login + password).encode('utf-8')).hexdigest()
            try:
                self.db.users.insert_one(self.user)
            except Exception as e:
                self.user = None
                logging.error('Can`t create new session: %s', e)
        self.user = self.db.users.find_one({'sid': self.user['sid']})

    def getPageCount(self, items_count, items_on_page_count):
        page_count = divmod(items_count, items_on_page_count)
        if page_count[1] == 0:
            page_count = page_count[0]
        elif (page_count[1] > 0) or (page_count[0] == 0):
            page_count = page_count[0] + 1
        return page_count

    def setResponse(self, http_env, start_resp):
        self.request = Request(http_env)
        st = time.time()
        adapter = self.routes.bind_to_environ(self.request.environ)
        self.prepareSession()
        try:
            handler, values = adapter.match()
            logging.info('%s', handler)
            if self.user and self.user['ready_flag']:
                self.endpoints[handler](**values)
            else:
                if handler in self.allow_not_logged:
                    self.endpoints[handler](**values)
                else:
                    self.response = redirect(self.routes.getUrlByEndpoint('on_root_get'))
        except HTTPException as e:
            self.on_error(e)
        if self.need_cookie_update:
            self.response.set_cookie('sid', self.user['sid'], max_age=self.user_ttl, httponly=True)
            #self.response.set_cookie('sid', self.user['sid'])
        self.request.close()
        self.response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        logging.info('%s', time.time() - st)
        return self.response(http_env, start_resp)

    def getSpeech(self, text):
        file_format = 'mp3'
        try:
            txt_hash = md5(text.encode('utf-8')).hexdigest()
        except Exception as e:
            txt_hash = ''
            logging.error('Can`t encode text to utf-8: %s', e)
        path = self.config['settings']['speech_dir'] + os.sep + txt_hash + '.' + file_format
        if os.path.exists(path):
            result = txt_hash + '.' + file_format
        else:
            conn = client.HTTPSConnection(self.config['yandex']['speech_host'], 443)
            query = {
                'text': text,
                'format': file_format,
                'lang': 'ru‑RU',
                'speaker': 'jane', #jane, omazh, zahar, ermil
                'emotion': 'mixed', #mixed, good, neutral, evil
                #'robot': False,
                'key': self.config['yandex']['speech_key']
            }
            conn.request('GET', '/generate?' + urlencode(query))
            resp = conn.getresponse()
            if resp.status == 200:
                speech = resp.read()
                try:
                    f = open(path, 'wb')
                    f.write(speech)
                    f.close()
                    result = txt_hash + '.' + file_format
                except Exception as e:
                    result = None
                    logging.error('Can`t save speech in file: %s', e)
            else:
                result = None
                logging.error('Can`t get response from yandex api: status: %s, reason: %s', resp.status, resp.reason)
            conn.close()
        return result


    def on_select_provider_get(self):
        page = self.template_env.get_template('provider.html')
        self.response = Response(page.render(
            select_provider_url=self.routes.getUrlByEndpoint(endpoint='on_select_provider_post'),
            version=self.config['settings']['version'],
            support=self.config['settings']['support']
        ), mimetype='text/html')

    def on_select_provider_post(self):
        provider = self.request.form.get('provider')
        if provider:
            self.response = redirect(self.routes.getUrlByEndpoint(endpoint='on_login_get'))
            self.response.set_cookie('provider', provider, max_age=300, httponly=True)
        else:
            page = self.template_env.get_template('error.html')
            self.response = Response(page.render(err=['Unknown provider']), mimetype='text/html')

    def on_post_speech(self):
        try:
            post_id = int(self.request.form.get('post_id'))
        except Exception as e:
            post_id = None
        if post_id:
            post = self.db.posts.find_one({'owner': self.user['sid'], 'pid': post_id})
            if post:
                title = html.unescape(post['content']['title'])
                speech_file = self.getSpeech(title)
                if speech_file:
                    result = {'result': 'ok', 'data': '/static/speech/{}'.format(speech_file)}
                else:
                    result = {'result': 'error', 'reason': 'can`t get speech file'}
            else:
                result = {'result': 'error', 'reason': 'post not found'}
        else:
            result = {'result': 'error', 'reason': 'no post id'}
        self.response = Response(json.dumps(result), mimetype='application/json')

    def on_login_get(self, err=None):
        provider = self.request.cookies.get('provider')
        if provider in self.providers:
            if (provider == 'bazqux') or (provider == 'inoreader'):
                page = self.template_env.get_template('login.html')
                if not err:
                    err = []
                self.response = Response(page.render(
                    err=err,
                    login_url=self.routes.getUrlByEndpoint(endpoint='on_login_get'),
                    version=self.config['settings']['version'],
                    support=self.config['settings']['support'],
                    provider=provider
                ), mimetype='text/html')
        else:
            page = self.template_env.get_template('error.html')
            self.response = Response(page.render(
                err=['Unknown provider'],
                version=self.config['settings']['version'],
                support=self.config['settings']['support']
            ), mimetype='text/html')

    def on_login_post(self):
        login = self.request.form.get('login')
        password = self.request.form.get('password')
        err = []
        if login and password:
            try:
                lp_hash = sha256((login + password).encode('utf-8')).hexdigest()
                user = self.db.users.find_one({'lp': lp_hash})
            except Exception as e:
                logging.error('Can`t find user by hash. %s', e)
                err.append('Can`t login. Try later.')
            if user:
                self.prepareSession(user)
                self.response = redirect(self.routes.getUrlByEndpoint(endpoint='on_root_get'))
                return ''
            elif not err:
                if self.user:
                    self.user['provider'] = self.request.cookies.get('provider')
                else:
                    self.user = {'provider': self.request.cookies.get('provider')}
                if (self.user['provider'] == 'bazqux') or (self.user['provider'] == 'inoreader'):
                    connection = client.HTTPSConnection(self.config[self.user['provider']]['api_host'])
                    headers = {'Content-type': 'application/x-www-form-urlencoded'}
                    data = urlencode({'Email': login, 'Passwd': password})
                    try:
                        connection.request('POST', '/accounts/ClientLogin', data, headers)
                    except Exception as e:
                        err.append('Can`t request to server. {0}'.format(e))
                    if not err:
                        resp = connection.getresponse().read().splitlines()
                        if resp and resp[0].decode('utf-8').split('=')[0] != 'Error':
                            token = resp[-1].decode('utf-8').split('=')[-1]
                            self.user['token'] = token
                            self.createNewSession(login, password)
                            if not self.user:
                                err.append('Can`t create session, try later')
                        else:
                            err.append('Wrong Login or Password')
        else:
            err.append('Login or Password can`t be empty')
        if not err:
            #self.response = redirect(self.routes.getUrlByEndpoint(endpoint='on_root_get'))
            self.response = redirect(self.routes.getUrlByEndpoint(endpoint='on_refresh_get_post'))
        else:
            self.response = Response('', mimetype='text/html')
            self.on_login_get(err)

    def on_refresh_get_post(self):
        if self.user:
            if not self.user['in_queue']:
                self.db.download_queue.insert_one(
                    {'user': self.user['_id'], 'processing': TASK_NOT_IN_PROCESSING, 'host': self.request.environ['HTTP_HOST']}
                )
                self.db.users.update_one(
                    {'sid': self.user['sid']},
                    {'$set': {'ready_flag': False, 'in_queue': True, 'message': 'Downloading data, please wait'}}
                )
            else:
                self.db.users.update_one(
                    {'sid': self.user['sid']}, {'$set': {'message': 'You already in queue, please wait'}}
                )
            self.response = redirect(self.routes.getUrlByEndpoint(endpoint='on_root_get'))
        else:
            self.response = redirect(self.routes.getUrlByEndpoint(endpoint='on_root_get'))

    def on_ready_get(self):
        result = {}
        if self.user:
            if self.user['ready_flag']:
                result = {'status': 'ready', 'reason': 'Ready'}
            else:
                result = {'status': 'not ready', 'reason': 'Not ready'}
            result['message'] = self.user['message']
        else:
            result = {
                'status': 'not logged',
                'reason': 'Not logged',
                'message': 'Click on "Select provider" to start work'
            }
        self.response = Response(json.dumps(result), mimetype='text/html')

    def on_settings_post(self):
        try:
            settings = json.loads(self.request.get_data(as_text=True))
        except Exception as e:
            logging.warning('Can`t json load settings. Cause: %s', e)
            settings = {}
        if settings:
            if self.user:
                changed = False
                result = {'data': 'ok'}
                code = 200
                try:
                    for k, v in settings.items():
                        if (k in self.user['settings']) and (self.user['settings'][k] != v):
                            old_value = self.user['settings'][k]
                            if isinstance(old_value, int):
                                self.user['settings'][k] = int(v)
                            elif isinstance(old_value, float):
                                self.user['settings'][k] = float(v)
                            elif isinstance(old_value, bool):
                                self.user['settings'][k] = bool(v)
                            else:
                                raise ValueError('bad settings value')
                            changed = True
                except Exception as e:
                    changed = False
                    logging.warning('Wrong settings value. Cause: %s', e)
                    result = {'error': 'Bad settings'}
                    code = 400
                if changed:
                    try:
                        self.db.users.update_one(
                            {'sid': self.user['sid']},
                            {'$set': {'settings': self.user['settings']}}
                        )
                    except Exception as e:
                        logging.error('Can`t save settings in db. Cause: %s', e)
                        result = {'error': 'Server in trouble'}
                        code = 500
            else:
                result = {'error': 'Not logged'}
                code = 401
            self.response = Response(json.dumps(result), mimetype='application/json')
        else:
            result = {'error': 'Something wrong with settings'}
            code = 400

        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

    def on_error(self, e):
        page = self.template_env.get_template('error.html')
        self.response = Response(
            page.render(title='ERROR', body='Error: {0}, {1}'.format(e.code, e.description)),
            mimetype='text/html'
        )
        self.response.status_code = e.code

    def on_root_get(self, err=None):
        if not err:
            err = []
        only_unread = True
        if self.user and 'provider' in self.user:
            match = {'owner': self.user['sid']}
            cursor = self.db.posts.aggregate([
                {'$match': match},
                {'$group': {'_id': '$read', 'counter': {'$sum': 1}}}
            ])
            posts = {'unread': 0, 'read': 0}
            if cursor and cursor.alive:
                for result in cursor:
                    if result['_id']:
                        posts['read'] = result['counter']
                    else:
                        posts['unread'] = result['counter']
            page = self.template_env.get_template('root-logged.html')
            self.response = Response(
                page.render(
                    err=err,
                    support=self.config['settings']['support'],
                    version=self.config['settings']['version'],
                    user_settings=self.user['settings'],
                    provider=self.user['provider'],
                    posts=posts
                ),
                mimetype='text/html'
            )
        else:
            provider = 'Not selected'
            page = self.template_env.get_template('root.html')
            self.response = Response(
                page.render(
                    err=err,
                    only_unread=only_unread,
                    provider=provider,
                    support=self.config['settings']['support'],
                    version=self.config['settings']['version']
                ),
                mimetype='text/html'
            )

    def on_group_by_category_get(self):
        page_number = self.user['page']
        if not page_number:
            page_number = 1
        by_feed = {}
        for f in self.db.feeds.find({'owner': self.user['sid']}):
            by_feed[f['feed_id']] = f
        if self.user['settings']['only_unread']:
            match = {'owner': self.user['sid'], 'read':False}
        else:
            match = {'owner': self.user['sid']}
        grouped = self.db.posts.aggregate([
            {'$match': match},
            {'$group': {'_id': '$feed_id', 'category_id': {'$first': '$category_id'}, 'count': {'$sum': 1}}}
        ])
        all_feeds = 'All'
        by_category = {all_feeds: {
            'unread_count' : 0,
            'title': all_feeds,
            'url': self.routes.getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': all_feeds}),
            'feeds' : []
        }}
        for g in grouped:
            if g['count'] > 0:
                if g['category_id'] not in by_category:
                    by_category[g['category_id']] = {
                        'unread_count' : 0,
                        'title': by_feed[g['_id']]['category_title'],
                        'url': by_feed[g['_id']]['category_local_url'], 'feeds' : []
                    }
                by_category[g['category_id']]['unread_count'] += g['count']
                by_category[all_feeds]['unread_count'] += g['count']
                by_category[g['category_id']]['feeds'].append({
                    'unread_count': g['count'],
                    'url': by_feed[g['_id']]['local_url'],
                    'title': by_feed[g['_id']]['title']
                })
        if len(by_category) > 1:
            data = getSortedDictByAlphabet(by_category)
            if self.no_category_name in data:
                data.move_to_end(self.no_category_name)
        else:
            data = OrderedDict()
        page = self.template_env.get_template('group-by-category.html')
        self.response = Response(
            page.render(
                data=data,
                group_by_link=self.routes.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number}),
                user_settings=self.user['settings'],
                provider=self.user['provider'],
            ),
            mimetype='text/html'
        )

    def on_category_get(self, quoted_category=None):
        page = self.template_env.get_template('posts.html')
        if quoted_category:
            cat = unquote_plus(quoted_category)
        else:
            cat = ''
        all_feeds = 'All'
        if cat == all_feeds:
            cat_cursor = self.db.feeds.find({'owner': self.user['sid']})
        else:
            cat_cursor = self.db.feeds.find({'owner': self.user['sid'], 'category_id': cat})
        if cat_cursor.count() > 0:
            by_feed = {}
            cat_id = ''
            for f in cat_cursor:
                by_feed[f['feed_id']] = f
                cat_id = f['category_id']
            projection = {'_id': False, 'content.content': False}
            if self.user['settings']['only_unread']:
                if cat == all_feeds:
                    cursor = self.db.posts\
                        .find({'owner': self.user['sid'], 'read': False}, projection=projection)\
                        .sort([('feed_id', DESCENDING), ('unix_date', DESCENDING)])
                else:
                    cursor = self.db.posts.find(
                        {
                            'owner': self.user['sid'],
                            'read': False,
                            'category_id': cat_id
                        },
                        projection = projection
                    ).sort([('feed_id', DESCENDING), ('unix_date', DESCENDING)])
            else:
                if cat == all_feeds:
                    cursor = self.db.posts\
                        .find({'owner': self.user['sid']}, projection=projection)\
                        .sort('unix_date', DESCENDING)
                else:
                    cursor = self.db.posts\
                        .find({'owner': self.user['sid'], 'category_id': cat_id}, projection=projection)\
                        .sort('unix_date', DESCENDING)
            posts = []
            for post in cursor:
                posts.append({
                    'post': post,
                    'pos': post['pid'],
                    'category_title': by_feed[post['feed_id']]['category_title'],
                    'feed_title': by_feed[post['feed_id']]['title'],
                    'favicon': by_feed[post['feed_id']]['favicon']
                })
            self.response = Response(
                page.render(
                    posts=posts,
                    tag=cat,
                    back_link=self.routes.getUrlByEndpoint(endpoint='on_group_by_category_get'),
                    group='category',
                    words=[],
                    user_settings=self.user['settings'],
                    provider=self.user['provider']
                    # next_tag=self.routes.getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': next_cat}),
                    # prev_tag=self.routes.getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': prev_cat})),
                ),
                mimetype='text/html'
            )
        else:
            self.on_error(NotFound())

    def on_tag_get(self, quoted_tag=None):
        page = self.template_env.get_template('posts.html')
        page_number = self.user['page']
        letter = self.user['letter']
        tmp_letters = self.db.letters.find_one({'owner': self.user['sid']})
        if tmp_letters:
            self.first_letters = getSortedDictByAlphabet(tmp_letters['letters'])
        else:
            self.first_letters = OrderedDict()
        if not page_number:
            page_number = 1
        if letter and letter in self.first_letters:
            back_link = self.routes.getUrlByEndpoint(endpoint='on_group_by_tags_startwith_get', params={'letter': letter})
        else:
            back_link = self.routes.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number})
        tag = unquote(quoted_tag)
        current_tag = self.db.tags.find_one({'owner': self.user['sid'], 'tag': tag})
        if current_tag:
            projection = {'_id': False, 'content.content': False}
            posts = []
            if self.user['settings']['only_unread']:
                cursor = self.db.posts.find(
                    {
                        'owner': self.user['sid'],
                        'read': False,
                        'tags': {'$all': [tag]}
                    },
                    projection=projection
                ).sort([('feed_id', DESCENDING), ('unix_date', DESCENDING)])
            else:
                cursor = self.db.posts\
                    .find({'owner': self.user['sid'], 'tags': {'$all': [tag]}}, projection=projection)\
                    .sort([('feed_id', DESCENDING), ('unix_date', DESCENDING)])
            by_feed = {}
            for post in cursor:
                if post['feed_id'] not in by_feed:
                    by_feed[post['feed_id']] = self.db.feeds.find_one(
                        {'owner': self.user['sid'], 'feed_id': post['feed_id']}
                    )
                posts.append({
                    'post': post,
                    'pos': post['pid'],
                    'category_title': by_feed[post['feed_id']]['category_title'],
                    'feed_title': by_feed[post['feed_id']]['title'],
                    'favicon': by_feed[post['feed_id']]['favicon']
                })
            self.response = Response(
                page.render(
                    posts=posts,
                    tag=tag,
                    back_link=back_link,
                    group='tag',
                    words=current_tag['words'],
                    user_settings=self.user['settings'],
                    provider=self.user['provider']
                ),
                mimetype='text/html'
            )
        else:
            self.on_error(NotFound())

    def on_feed_get(self, quoted_feed=None):
        page = self.template_env.get_template('posts.html')
        feed = unquote_plus(quoted_feed)
        current_feed = self.db.feeds.find_one({'owner': self.user['sid'], 'feed_id': feed})
        if feed:
            if self.user['settings']['only_unread']:
                cursor = self.db.posts\
                    .find({'owner': self.user['sid'], 'read': False, 'feed_id': current_feed['feed_id']})\
                    .sort('unix_date', DESCENDING)
            else:
                cursor = self.db.posts\
                    .find({'owner': self.user['sid'], 'feed_id': current_feed['feed_id']})\
                    .sort('unix_date', DESCENDING)
            posts = []
            for post in cursor:
                posts.append({
                    'post': post,
                    'category_title': current_feed['category_title'],
                    'pos': post['pid'],
                    'feed_title': current_feed['title'],
                    'favicon': current_feed['favicon']
                })
            self.response = Response(
                page.render(
                    posts=posts,
                    tag=current_feed['title'],
                    back_link=self.routes.getUrlByEndpoint(endpoint='on_group_by_category_get'),
                    group='feed',
                    words=[],
                    user_settings=self.user['settings'],
                    provider=self.user['provider']
                ),
                mimetype='text/html'
            )
        else:
            self.on_error(NotFound())

    def on_read_posts_post(self):
        code = 200
        try:
            data = json.loads(self.request.get_data(as_text=True))
            if (data['ids'] and isinstance(data['ids'], list)):
                post_ids = data['ids']
            else:
                raise Exception('Bad ids for posts status');
            readed = bool(data['readed'])
            result = None
        except Exception as e:
            logging.warning('Send wrond data for read posts. Cause: %s', e)
            post_ids = None
            result = {'error': 'Bad ids or status'}
            code = 400

        if result is None:
            #st = time.time()
            tmp_letters = self.db.letters.find_one({'owner': self.user['sid']})
            if tmp_letters:
                first_letters = tmp_letters['letters']
            else:
                first_letters = {}
            tags = {}
            for_insert = []
            if (self.user['provider'] == 'bazqux') or (self.user['provider'] == 'inoreader'):
                current_data = self.db.posts.find(
                    {
                        'owner': self.user['sid'],
                        'read': not readed,
                        'pid': {'$in': post_ids}
                    },
                    projection=['id', 'tags']
                )
                for d in current_data:
                    for_insert.append({
                        'user': self.user['_id'],
                        'id': d['id'],
                        'status': readed,
                        'processing': TASK_NOT_IN_PROCESSING
                    })
                    for t in d['tags']:
                        if t in tags:
                            tags[t] += 1
                        else:
                            tags[t] = 1
            if for_insert:
                try:
                    self.db.mark_queue.insert_many(for_insert)
                except Exception as e:
                    result = {'error': 'Database queue error'}
                    logging.error('Can`t push in mark queue: %s', e)
                    code = 500

        if result is None:
            bulk = self.db.tags.initialize_unordered_bulk_op()
            if tags:
                if readed:
                    for t in tags:
                        bulk.find({'owner': self.user['sid'], 'tag': t})\
                            .update_one({'$inc': {'unread_count': -tags[t]}})
                        first_letters[t[0]]['unread_count'] -= tags[t]
                else:
                    for t in tags:
                        bulk.find({'owner': self.user['sid'], 'tag': t})\
                            .update_one({'$inc': {'unread_count': tags[t]}})
                        first_letters[t[0]]['unread_count'] += tags[t]
                try:
                    bulk.execute()
                except Exception as e:
                    result = {'error': 'Database error'}
                    logging.error('Bulk failed in on_read_posts_post: %s', e)
                    code = 500
            try:
                self.db.posts.update_many(
                    {'owner': self.user['sid'], 'read': not readed, 'pid': {'$in': post_ids}},
                    {'$set': {'read': readed}}
                )
                self.db.letters.update_one({'owner': self.user['sid']}, {'$set': {'letters': first_letters}})
                result = {'data': 'ok'}
            except Exception as e:
                result = {'error': 'Database error'}
                logging.error('Can`t mark posts or on_read_posts_post: %s', e)
                code = 500

            #logging.info('%s', time.time() - st)
        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

    def fillFirstLetters(self):
        tmp_letters = self.db.letters.find_one({'owner': self.user['sid']})
        if tmp_letters:
            self.first_letters = getSortedDictByAlphabet(tmp_letters['letters'])
        else:
            self.first_letters = OrderedDict()

    def getLetters(self):
        letters = []
        if self.user['settings']['only_unread']:
            for s_let in self.first_letters:
                if self.first_letters[s_let]['unread_count'] > 0:
                    letters.append({
                        'letter': self.first_letters[s_let]['letter'],
                        'local_url': self.first_letters[s_let]['local_url']
                    })
        else:
            for s_let in self.first_letters:
                letters.append({
                    'letter': self.first_letters[s_let]['letter'],
                    'local_url': self.first_letters[s_let]['local_url']
                })
        return letters

    def calcPagerData(self, p_number, page_count, items_per_page, endpoint):
        pages_map = {}
        page_count = round(page_count)
        numbers_start_range = p_number - self.count_showed_numbers + 1
        numbers_end_range = p_number + self.count_showed_numbers + 1
        if numbers_start_range <= 0:
            numbers_start_range = 1
        if numbers_end_range > page_count:
            numbers_end_range = page_count + 1
        if page_count > 11:
            pages_map['middle'] = []
            for i in range(numbers_start_range, numbers_end_range):
                pages_map['middle'].append({
                    'p': i,
                    'url': self.routes.getUrlByEndpoint(endpoint=endpoint, params={'page_number': i})
                })
            if numbers_start_range > 1:
                pages_map['start'] = [{
                    'p': 'first',
                    'url': self.routes.getUrlByEndpoint(endpoint=endpoint, params={'page_number': 1})
                }]
            if numbers_end_range <= (page_count):
                pages_map['end'] = [{
                    'p': 'last',
                    'url': self.routes.getUrlByEndpoint(endpoint=endpoint, params={'page_number': page_count})
                }]
        else:
            pages_map['start'] = []
            for i in range(1, page_count + 1):
                pages_map['start'].append({
                    'p': i,
                    'url': self.routes.getUrlByEndpoint(endpoint=endpoint, params={'page_number': i})
                })
        start_tags_range = round(((p_number - 1) * items_per_page) + items_per_page)
        end_tags_range = round(start_tags_range + items_per_page)
        return (pages_map, start_tags_range, end_tags_range)

    def on_group_by_tags_get(self, page_number):
        self.response = None
        page = self.template_env.get_template('group-by-tag.html')
        sort_data = []
        query = {'owner': self.user['sid']}
        if self.user['settings']['only_unread']:
            if self.user['settings']['hot_tags']:
                sort_data = [('temperature', DESCENDING), ('unread_count', DESCENDING)]
            else:
                sort_data = [('unread_count', DESCENDING)]
            query['unread_count'] = {'$gt': 0}
        else:
            if self.user['settings']['hot_tags']:
                sort_data = [('temperature', DESCENDING), ('posts_count', DESCENDING)]
            else:
                sort_data = [('posts_count', DESCENDING)]
        try:
            cursor = self.db.tags.find(query).sort(sort_data)
            tags_count = cursor.count()
        except Exception as e:
            cursor = None
            logging.error('Can`t get tags. Cause: %s', e)
        if cursor:
            page_count = self.getPageCount(tags_count, self.user['settings']['tags_on_page'])
            if page_number <= 0:
                p_number = 1
                self.user['page'] = p_number
            elif page_number > page_count:
                p_number = page_count
                self.response = redirect(
                    self.routes.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': p_number})
                )
                self.user['page'] = p_number
            else:
                p_number = page_number
            p_number -= 1
            if p_number < 0:
                p_number = 1
            new_cookie_page_value = p_number + 1
            if not self.response:
                pages_map, start_tags_range, end_tags_range = self.calcPagerData(
                    p_number,
                    page_count,
                    self.user['settings']['tags_on_page'],
                    'on_group_by_tags_get'
                )
                if end_tags_range > tags_count:
                    end_tags_range = tags_count
                sorted_tags = []
                if self.user['settings']['only_unread']:
                    field = 'unread_count'
                else:
                    field = 'posts_count'
                for t in cursor[start_tags_range:end_tags_range]:
                    sorted_tags.append({
                        'tag': t['tag'],
                        'url': t['local_url'],
                        'words': t['words'],
                        'count': t[field]
                    })
                self.fillFirstLetters()
                letters = self.getLetters()
                self.response = Response(
                    page.render(
                        tags=sorted_tags,
                        sort_by_title='tags',
                        sort_by_link=self.routes.getUrlByEndpoint(
                            endpoint='on_group_by_tags_get',
                            params={'page_number': new_cookie_page_value}
                        ),
                        group_by_link=self.routes.getUrlByEndpoint(endpoint='on_group_by_category_get'),
                        pages_map=pages_map,
                        current_page=new_cookie_page_value,
                        letters=letters,
                        user_settings=self.user['settings'],
                        provider=self.user['provider']
                    ),
                    mimetype='text/html'
                )
                self.db.users.update_one(
                    {'sid': self.user['sid']},
                    {'$set': {'page': new_cookie_page_value, 'letter': ''}}
                )
            else:
                if not self.response:
                    self.on_error(NotFound())
        else:
            raise InternalServerError()

    def on_group_by_tags_startwith_get(self, letter=None):
        self.response = None
        page_number = self.user['page']
        if not page_number:
            page_number = 1
        let = unquote_plus(letter)
        self.fillFirstLetters()
        if let and (let in self.first_letters):
            letters = self.getLetters()
            page = self.template_env.get_template('group-by-tag.html')
            tags = []
            if self.user['settings']['only_unread']:
                cursor = self.db.tags.find({
                    'owner': self.user['sid'],
                    'unread_count': {'$gt': 0},
                    'tag': {'$regex': '^{0}'.format(let)}
                }).sort([('unread_count', DESCENDING)])
                for t in cursor:
                    tags.append({'tag': t['tag'], 'url': t['local_url'], 'words': t['words'], 'count': t['unread_count']})
            else:
                cursor = self.db.tags\
                    .find({'owner': self.user['sid'], 'tag': {'$regex': '^{0}'.format(let)}})\
                    .sort([('posts_count', DESCENDING)])
                for t in cursor:
                    tags.append({'tag': t['tag'], 'url': t['local_url'], 'words': t['words'], 'count': t['posts_count']})
            self.response = Response(
                page.render(
                    tags=tags,
                    sort_by_title=let,
                    sort_by_link=self.routes.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number}),
                    group_by_link=self.routes.getUrlByEndpoint(endpoint='on_group_by_category_get'),
                    pages_map={},
                    current_page=1,
                    letters=letters,
                    provider=self.user['provider'],
                    user_settings=self.user['settings']
                ),
                mimetype='text/html'
            )
            self.db.users.update_one({'sid': self.user['sid']}, {'$set': {'letter': let}})
        else:
            self.response = redirect(self.routes.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number}))

    def on_get_tag_siblings(self, tag=''):
        code = 200
        all_tags = []
        result = None
        if tag:
            tags_set = set()
            if self.d2v:
                try:
                    siblings = self.d2v.similar_by_word(tag, topn=30)
                except Exception as e:
                    logging.error('In %s not found tag %s', self.config['settings']['model'], tag)
                    siblings = []
                for sibling in siblings:
                    tags_set.add(sibling[0])

            if not siblings:
                query = {
                    'owner': self.user['sid'],
                    'tags': tag
                }
                if self.user['settings']['only_unread']:
                    query['read'] = False
                try:
                    cur = self.db.posts.find(query, projection=['tags'])
                except Exception as e:
                    logging.error('Can`t get tag siblings %s. Info: %s', tag, e)
                    result = {'error': 'Database error'}
                    code = 500
                    cur = []
                tags_set = set()
                for tags in cur:
                    for tag in tags['tags']:
                        tags_set.add(tag)

        if result is None:
            if tags_set:
                if self.user['settings']['only_unread']:
                    field = 'unread_count'
                else:
                    field = 'posts_count'
                query = {
                    'owner': self.user['sid'],
                    'tag': {'$in': list(tags_set)},
                    field: {'$gt': 0}
                }
                if self.user['settings']['only_unread']:
                    query['read'] = False
                try:
                    cur = self.db.tags.find(query, projection={'_id': False})
                except Exception as e:
                    logging.error('Can`t fetch tags siblings for %s. Info: %s', tag, e)
                    cur = []

                all_tags = []
                for tag in cur:
                    all_tags.append({
                        'tag': tag['tag'],
                        'url': tag['local_url'],
                        'words': tag['words'],
                        'count': tag[field]
                    })

            result = {'data': all_tags}

        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code


    def on_posts_content_post(self):
        code = 200
        try:
            wanted_posts = json.loads(self.request.get_data(as_text=True))
            if isinstance(wanted_posts, list) and wanted_posts:
                result = None
            else:
                raise Exception('Empty list of ids for post content')
        except Exception as e:
            logging.warning('Send bad posts ids for posts content. Cause: %s', e)
            wanted_posts = []
            result = {'error': 'Bad posts ids'}
            code = 400
        if result is None:
            try:
                #posts = self.db.posts.find({'owner': self.user['sid'], 'pid': {'$in': wanted_posts}}, limit=round(self.user['settings']['posts_on_page']))
                posts = self.db.posts.find(
                    {
                        'owner': self.user['sid'],
                        'pid': {'$in': wanted_posts}
                    },
                    projection = ['pid', 'content', 'attachments']
                )
            except Exception as e:
                logging.warning('Can`t get posts content. Cause: %s', e)
                wanted_posts = []
                result = {'error': 'Database error'}
                code = 500

        if result is None:
            posts_content = []
            for post in posts:
                attachments = ''
                if post['attachments']:
                    for href in post['attachments']:
                        attachments += '<a href="{0}">{0}</a><br />'.format(href)
                content = gzip.decompress(post['content']['content']).decode('utf-8', 'replace')
                if attachments:
                    content += '<p>Attachments:<br />{0}<p>'.format(attachments)
                posts_content.append({'pos': post['pid'], 'content': content})
            result = {'data': posts_content}
        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

    def on_post_content_post(self):
        err = []
        try:
            post_id = int(self.request.form.get('postid'))
        except Exception as e:
            err.append('Post id must be int number')
        if not err:
            current_post = self.db.posts.find_one({'owner': self.user['sid'], 'pid': post_id})
            attachments = ''
            if current_post['attachments']:
                for href in current_post['attachments']:
                    attachments += '<a href="{0}">{0}</a><br />'.format(href)
            if current_post:
                content = gzip.decompress(current_post['content']['content']).decode('utf-8', 'replace')
                if attachments:
                    content += '<p>Attachments:<br />{0}<p>'.format(attachments)
                result = {'result': 'ok', 'data': {'pos': post_id, 'content': content}}
            else:
                err.append('Not found post content')
        if not err:
            self.response = Response(json.dumps(result), mimetype='application/json')
        else:
            self.response = Response('{{"result": "error", "data":"{0}"}}'.format(''.join(err)), mimetype='application/json')
            self.response.status_code = 404

    def on_post_links_get(self, post_id: int) -> None:
        code = 200
        result = None
        try:
            current_post = self.db.posts.find_one(
                {'owner': self.user['sid'], 'pid': post_id},
                projection=['tags', 'feed_id', 'url']
            )
            if not current_post:
                result = {'error': 'Post not found'}
                code = 404
        except Exception as e:
            logging.error('Can`t find post by id %s. Info: %s', post_id, e)
            result = {'error': 'Database error'}
            code = 500
        if result is None:
            try:
                feed = self.db.feeds.find_one({'feed_id': current_post['feed_id'], 'owner': self.user['sid']})
                if not feed:
                    result = {'error': 'Feed not found'}
                    code = 500
            except Exception as e:
                logging.error('Can`t find feed. Post %s, feed id %s. Info: %s', post_id, current_post['feed_id'], e)
                result = {'error': 'Database error'}
                code = 500

        if result is None:
            result = {
                'data': {
                    'c_url': feed['category_local_url'],
                    'c_title': feed['category_title'],
                    'f_url': feed['local_url'],
                    'f_title': feed['title'],
                    'p_url': current_post['url'],
                    'tags': []
                }
            }
            for t in current_post['tags']:
                result['data']['tags'].append({
                    'url': self.routes.getUrlByEndpoint(endpoint='on_tag_get', params={'quoted_tag': t}),
                    'tag': t
                })
        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

    def on_get_all_tags(self):
        err = []
        result = []
        if self.user['settings']['only_unread']:
            all_tags = self.db.tags.find({'owner': self.user['sid'], 'unread_count': {'$gt': 0}})
        else:
            all_tags = self.db.tags.find({'owner': self.user['sid']})
        for tag in all_tags:
            result.append({'t': tag['tag'], 'l': '/tag/{0}'.format(tag['local_url'])})
        if not err:
            self.response = Response(json.dumps(result), mimetype='application/json')
        else:
            self.response = Response('{{"result": "error", "data":"{0}"}}'.format(''.join(err)), mimetype='application/json')
            self.response.status_code = 404

    def on_get_posts_with_tags(self, s_tags):
        if s_tags:
            tags = s_tags.split('-')
            if tags:
                result = {}
                query = {'owner': self.user['sid'], 'tag': {'$in': tags}}
                tags_cursor = self.db.tags.find(query, {'_id': 0, 'tag': 1, 'words': 1})
                for tag in tags_cursor:
                    result[tag['tag']] = {'words': ', '.join(tag['words']), 'posts': []}

                query = {'owner': self.user['sid'], 'tags': {'$in': tags}}
                if self.user['settings']['only_unread']:
                    query['read'] = False
                posts_cursor = self.db.posts.find(query, {'content.content': 0})
                feeds = {}
                posts = {}
                for post in posts_cursor:
                    posts[post['id']] = post
                    if post['feed_id'] not in feeds:
                        feeds[post['feed_id']] = {}
                feeds_cursor = self.db.feeds.find({'owner': self.user['sid'], 'feed_id': {'$in': list(feeds.keys())}})
                for feed in feeds_cursor:
                    feeds[feed['feed_id']] = feed
                for tag in tags:
                    posts_for_delete = []
                    for p_id in posts:
                        if tag in posts[p_id]['tags']:
                            posts[p_id]['feed_title'] = feeds[posts[p_id]['feed_id']]['title']
                            posts[p_id]['category_title'] = feeds[posts[p_id]['feed_id']]['category_title']
                            result[tag]['posts'].append(posts[p_id])
                            posts_for_delete.append(p_id)
                    for p_id in posts_for_delete:
                        del posts[p_id]
                    result[tag]['posts'] = sorted(result[tag]['posts'], key=lambda p: p['feed_id'])
                letter = self.user['letter']
                page_number = self.user['page']
                if letter:
                    back_link = self.routes.getUrlByEndpoint(endpoint='on_group_by_tags_startwith_get', params={'letter': letter})
                elif self.user['settings']['hot_tags']:
                    back_link = self.routes.getUrlByEndpoint(endpoint='on_group_by_hottags_get', params={'page_number': page_number})
                else:
                    back_link = self.routes.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number})
                page = self.template_env.get_template('tags-posts.html')
                self.response = Response(
                    page.render(
                        tags=result,
                        selected_tags=','.join(tags),
                        back_link=back_link, group='tag',
                        user_settings=self.user['settings'],
                        provider=self.user['provider']
                    ),
                    mimetype='text/html'
                )
        else:
            self.response = redirect(self.routes.getUrlByEndpoint('on_root_get'))

    def on_post_tags_search(self):
        errors = []
        s_request = unquote_plus(self.request.form.get('req'))
        if s_request:
            field_name = ''
            if self.user['settings']['only_unread']:
                field_name = 'unread_count'
            else:
                field_name = 'posts_count'
            try:
                tags_cur = self.db.tags.find({
                    'owner': self.user['sid'],
                    field_name: {'$gt': 0},
                    'read': not self.user['settings']['only_unread'],
                    'tag': {'$regex': '^{}.*'.format(s_request), '$options': 'i'}
                }, {
                    'tag': 1,
                    'local_url': 1,
                    field_name: 1,
                    '_id': 0
                }, limit=100)
            except Exception as e:
                errors.append('{}'.format(e))
        else:
            errors.append('Request can`t be empty')
        if not errors:
            result = {'result': 'ok', 'data': []}
            for tag in tags_cur:
                result['data'].append({
                    'tag': tag['tag'],
                    'cnt': tag[field_name],
                    'url': tag['local_url']
                })
        else:
            result = {'result': 'error', 'data': ''.join(errors)}
        self.response = Response(json.dumps(result), mimetype='application/json')
