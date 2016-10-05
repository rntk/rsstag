# -*- coding: UTF-8 -*-
import sys
from configparser import ConfigParser
import os, json, re
from urllib.parse import unquote_plus, quote_plus, urlencode, urlparse
from http import client
import html
import time
#import pickle
import gzip
import logging
from collections import OrderedDict
from datetime import date, datetime
from random import randint
from hashlib import md5, sha256
from xml.dom.minidom import parseString
from multiprocessing import Process, Pool, Manager
from werkzeug.wrappers import Response, Request
from werkzeug.routing import Map, Rule
from werkzeug.serving import run_simple
from werkzeug.exceptions import HTTPException, NotFound, InternalServerError
from werkzeug.utils import redirect
from werkzeug.wsgi import wrap_file
from jinja2 import Environment, PackageLoader
from pymongo import MongoClient, DESCENDING #, ASCENDING
from html_cleaner import HTMLCleaner
from tags_builder import TagsBuilder
#from bson.regex import Regex

class RSSCloudApplication(object):

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
    allow_not_logged = (
        'on_root_get',
        'on_login_get',
        'on_login_post',
        'on_select_provider_post',
        'on_select_provider_get',
        'on_static_get',
        'on_ready_get',
        'on_refresh_get_post',
        'on_favicon_get'
    )
    no_category_name = 'NotCategorized'

    def __init__(self, config_path=None):
        if self.setConfig(config_path):
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
                    'rss', os.path.join(os.path.dirname(__file__),
                    'templates',
                    self.config['settings']['templates'])
                )
            )
            self.providers = self.config['settings']['providers'].split(',')
            self.user_ttl = int(self.config['settings']['user_ttl'])
            cl = MongoClient(self.config['settings']['db_host'], int(self.config['settings']['db_port']))
            self.db = cl.rss
            self.prepareDB()
            routes = [
                {'url': '/', 'endpoint': 'on_root_get', 'methods': ['GET', 'HEAD']},
                {'url': '/login', 'endpoint': 'on_login_get', 'methods': ['GET', 'HEAD']},
                {'url': '/login', 'endpoint': 'on_login_post', 'methods': ['POST']},
                {'url': '/provider', 'endpoint': 'on_select_provider_get', 'methods': ['GET', 'HEAD']},
                {'url': '/provider', 'endpoint': 'on_select_provider_post', 'methods': ['POST']},
                {'url': '/group/tag/<int:page_number>', 'endpoint': 'on_group_by_tags_get', 'methods': ['GET', 'HEAD']},
                {'url': '/group/tag/startwith/<string(length: 1):letter>', 'endpoint': 'on_group_by_tags_startwith_get', 'methods': ['GET', 'HEAD']},
                {'url': '/group/category', 'endpoint': 'on_group_by_category_get', 'methods': ['GET', 'HEAD']},
                {'url': '/refresh', 'endpoint': 'on_refresh_get_post', 'methods': ['GET', 'HEAD', 'POST']},
                {'url': '/favicon.ico', 'endpoint': 'on_static_get', 'methods': ['GET', 'HEAD']},
                {'url': '/static/<string:directory>/<string:filename>', 'endpoint': 'on_static_get', 'methods': ['GET', 'HEAD']},
                {'url': '/static/<string:filename>', 'endpoint': 'on_static_get', 'methods': ['GET', 'HEAD']},
                {'url': '/tag/<string:quoted_tag>', 'endpoint': 'on_tag_get', 'methods': ['GET', 'HEAD']},
                {'url': '/category/<string:quoted_category>', 'endpoint': 'on_category_get', 'methods': ['GET', 'HEAD']},
                {'url': '/feed/<string:quoted_feed>', 'endpoint': 'on_feed_get', 'methods': ['GET', 'HEAD']},
                {'url': '/read/posts', 'endpoint': 'on_read_posts_post', 'methods': ['POST']},
                {'url': '/posts-content', 'endpoint': 'on_posts_content_post', 'methods': ['POST']},
                {'url': '/post-content', 'endpoint': 'on_post_content_post', 'methods': ['POST']},
                {'url': '/post-links', 'endpoint': 'on_post_links', 'methods': ['POST']},
                {'url': '/ready', 'endpoint': 'on_ready_get', 'methods': ['GET', 'HEAD']},
                {'url': '/settings', 'endpoint': 'on_settings_post', 'methods': ['POST']},
                {'url': '/all-tags', 'endpoint': 'on_get_all_tags', 'methods': ['GET', 'HEAD']},
                {'url': '/posts/with/tags/<string:s_tags>', 'endpoint': 'on_get_posts_with_tags', 'methods': ['GET', 'HEAD']},
                {'url': '/tag-siblings/<string:tag>', 'endpoint': 'on_get_tag_siblings', 'methods': ['GET', 'HEAD']},
                {'url': '/tags-search', 'endpoint': 'on_post_tags_search', 'methods': ['POST']},
                {'url': '/speech', 'endpoint': 'on_post_speech', 'methods': ['POST']}
            ]
            rules = []
            for route in routes:
                rules.append(Rule(route['url'], endpoint=route['endpoint'], methods=route['methods']))
            self.routes = Map(rules)
            self.updateEndpoints()
            if not self.workers_pool:
                for i in range(int(self.config['settings']['workers_count'])):
                    self.workers_pool.append(Process(target=worker, args=(self.config, routes)))
                    self.workers_pool[-1].start()
        else:
            logging.critical('Can`t load config file "{}"'.format(config_path))

    def prepareDB(self):
        self.db.posts.ensure_index([('owner', 1)])
        self.db.posts.ensure_index([('category_id', 1)])
        self.db.posts.ensure_index([('feed_id', 1)])
        self.db.posts.ensure_index([('read', 1)])
        self.db.posts.ensure_index([('tags', 1)])
        self.db.posts.ensure_index([('pid', 1)])
        #self.db.posts.ensure_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
        self.db.feeds.ensure_index([('owner', 1)])
        self.db.feeds.ensure_index([('feed_id', 1)])
        #self.db.feeds.ensure_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
        self.db.letters.ensure_index([('owner', 1)])
        #self.db.letters.ensure_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
        self.db.users.ensure_index([('sid', 1)])
        #self.db.users.ensure_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
        self.db.users.update_many({'in_queue': True}, {'$set': {'in_queue': False, 'ready_flag': True}})
        self.db.tags.ensure_index([('owner', 1)])
        self.db.tags.ensure_index([('tag', 1)])
        self.db.tags.ensure_index([('unread_count', 1)])
        self.db.tags.ensure_index([('posts_count', 1)])
        #self.db.tags.ensure_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
        self.db.download_queue.ensure_index([('locked', 1)])
        #self.db.download_queue.ensure_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
        self.db.mark_queue.ensure_index([('locked', 1)])
        #self.db.mark_queue.ensure_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)

    def close(self):
        if self.workers_pool:
            for p in self.workers_pool:
                p.terminate()
        logging.info('Goodbye!')

    def updateEndpoints(self):
        for i in self.routes.iter_rules():
            self.endpoints[i.endpoint] = getattr(self, i.endpoint)

    def prepareSession(self, user=None):
        if user == None:
            sid = self.request.cookies.get('sid')
            if sid:
                self.user = self.db.users.find_one({'sid': sid})
            else:
                self.user = None
        else:
            self.user = user

        if self.user:
            self.need_cookie_update = True
            return(True)
        else:
            self.need_cookie_update = False
            return(False)

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
            self.user['settings'] = settings;
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
        return(page_count)

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
                    self.response = redirect(self.getUrlByEndpoint('on_root_get'))
        except HTTPException as e:
            self.on_error(e)
        if self.need_cookie_update:
            self.response.set_cookie('sid', self.user['sid'], max_age=self.user_ttl, httponly=True)
            #self.response.set_cookie('sid', self.user['sid'])
        self.request.close()
        self.response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        logging.info('%s', time.time() - st)
        return(self.response(http_env, start_resp))

    def setConfig(self, config_name):
        result = False
        if config_name and os.path.exists(config_name):
            try:
                c = ConfigParser()
                c.read(config_name, encoding='utf-8')
                self.config = c
                result = True
            except Exception as e:
                logging.critical('Can`t load config: %s', e)
                result = False
        return(result)

    def getUrlByEndpoint(self, endpoint=None, params=None, full_url=False):
        url = None
        if endpoint:
            if not params:
                params = {}
            if full_url or params:
                all_urls = self.routes.bind(self.request.environ['HTTP_HOST'], '/')
                url = all_urls.build(endpoint, params, force_external=full_url)
            else:
                url = next(self.routes.iter_rules(endpoint=endpoint))
        return(url)

    def getSpeech(self, text):
        format = 'mp3'
        try:
            hash = md5(text.encode('utf-8')).hexdigest()
        except Exception as e:
            hash = ''
            logging.error('Can`t encode text to utf-8: {}'.format(e))
        path = self.config['settings']['speech_dir'] + os.sep + hash + '.' + format
        if (os.path.exists(path)):
            result = hash + '.' + format
        else:
            conn = client.HTTPSConnection(self.config['yandex']['speech_host'], 443)
            query = {
                'text': text,
                'format': format,
                'lang': 'ru‑RU',
                'speaker': 'jane', #jane, omazh, zahar, ermil
                'emotion': 'mixed', #mixed, good, neutral, evil
                #'robot': False,
                'key': self.config['yandex']['speech_key']
            }
            conn.request('GET', '/generate?' + urlencode(query))
            resp = conn.getresponse()
            if (resp.status == 200):
                speech = resp.read()
                try:
                    f = open(path, 'wb')
                    f.write(speech)
                    f.close()
                    result = hash + '.' + format
                except Exception as e:
                    result = None
                    logging.error('Can`t save speech in file: {}'.format(e))
            else:
                result = None
                logging.error('Can`t get response from yandex api: status: {}, reason: {}'.format(resp.status, resp.reason))
            conn.close()
        return(result)


    def on_select_provider_get(self):
        page = self.template_env.get_template('provider.html')
        self.response = Response(page.render(
            select_provider_url=self.getUrlByEndpoint(endpoint='on_select_provider_post'),
            version=self.config['settings']['version'],
            support=self.config['settings']['support']
        ), mimetype='text/html')

    def on_select_provider_post(self):
        provider = self.request.form.get('provider')
        if provider:
            self.response = redirect(self.getUrlByEndpoint(endpoint='on_login_get'))
            self.response.set_cookie('provider', provider, max_age=300, httponly=True)
        else:
            page = self.template_env.get_template('error.html')
            self.response = Response(page.render(err=['Unknown provider']), mimetype='text/html')

    def on_post_speech(self):
        try:
            post_id = int(self.request.form.get('post_id'))
        except Exception as e:
            post_id = None
        if (post_id):
            post = self.db.posts.find_one({'owner': self.user['sid'], 'pid': post_id})
            if (post):
                title = html.unescape(post['content']['title'])
                speech_file = self.getSpeech(title)
                if (speech_file):
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
                    login_url=self.getUrlByEndpoint(endpoint='on_login_get'),
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
        page = self.template_env.get_template('login.html')
        err = []
        if login and password:
            try:
                hash = sha256((login + password).encode('utf-8')).hexdigest()
                user = self.db.users.find_one({'lp': hash})
            except:
                err.append('Can`t login. Try later.')
            if user:
                self.prepareSession(user)
                self.response = redirect(self.getUrlByEndpoint(endpoint='on_root_get'))
                return ('')
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
            #self.response = redirect(self.getUrlByEndpoint(endpoint='on_root_get'))
            self.response = redirect(self.getUrlByEndpoint(endpoint='on_refresh_get_post'))
        else:
            self.response = Response('', mimetype='text/html')
            self.on_login_get(err)

    def on_refresh_get_post(self):
        if self.user:
            if not self.user['in_queue']:
                self.db.download_queue.insert_one({'user': self.user['_id'], 'locked': False, 'host': self.request.environ['HTTP_HOST']})
                self.db.users.update_one(
                    {'sid': self.user['sid']},
                    {'$set': {'ready_flag': False, 'in_queue': True, 'message': 'Downloading data, please wait'}}
                )
            else:
                self.db.users.update_one({'sid': self.user['sid']}, {'$set': {'message': 'You already in queue, please wait'}})
            self.response = redirect(self.getUrlByEndpoint(endpoint='on_root_get'))
        else:
            self.response = redirect(self.getUrlByEndpoint(endpoint='on_root_get'))
            #page = self.template_env.get_template('error.html')
            #self.response = Response(page.render(err=['No sid']), mimetype='text/html')

    def on_ready_get(self):
        result = {}
        if self.user:
            if self.user['ready_flag']:
                result = {'status': 'ready', 'reason': 'Ready'}
            else:
                result = {'status': 'not ready', 'reason': 'Not ready'}
            result['message'] = self.user['message']
        else:
            result = {'status': 'not logged', 'reason': 'Not logged', 'message': 'Click on "Select provider" to start work'}
        self.response = Response(json.dumps(result), mimetype='text/html')

    def on_settings_post(self):
        try:
            settings = json.loads(self.request.get_data(as_text=True))
        except Exception as e:
            logging.warning('Can`t json load settings. Cause: %s', e)
            settings = {}
        if (settings):
            result = {}
            if self.user:
                changed = False
                result = {'result': 'ok', 'reason': 'ok'}
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
                    result = {'result': 'error', 'reason': 'Bad settings'}
                    code = 400
                try:
                    if changed:
                        self.db.users.update_one(
                            {'sid': self.user['sid']},
                            {'$set': {'settings': self.user['settings']}}
                        )
                except Exception as e:
                    logging.error('Can`t save settings in db. Cause: %s', e)
                    result = {'result': 'error', 'reason': 'Server in trouble'}
                    code = 500
            else:
                result = {'result': 'error', 'reason': 'Not logged'}
                code = 401
            self.response = Response(json.dumps(result), mimetype='application/json')
        else:
            result = {'result': 'error', 'reason': 'Something wrong with settings'}
            code = 400
        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

    def on_error(self, e):
        page = self.template_env.get_template('error.html')
        self.response = Response(page.render(title='ERROR', body='Error: {0}, {1}'.format(e.code, e.description)), mimetype='text/html')
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
            ]);
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
            'url': self.getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': all_feeds}), 'feeds' : []
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
            data = {}
        page = self.template_env.get_template('group-by-category.html')
        self.response = Response(
            page.render(
                data=data,
                group_by_link=self.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number}),
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
            for f in cat_cursor:
                by_feed[f['feed_id']] = f
            if self.user['settings']['only_unread']:
                if cat == all_feeds:
                    cursor = self.db.posts.find({'owner': self.user['sid'], 'read': False}).sort([('feed_id', DESCENDING), ('unix_date', DESCENDING)])
                else:
                    cursor = self.db.posts.find({
                        'owner': self.user['sid'],
                        'read': False,
                        'category_id': f['category_id']
                    }).sort([('feed_id', DESCENDING), ('unix_date', DESCENDING)])
            else:
                if cat == all_feeds:
                    cursor = self.db.posts.find({'owner': self.user['sid']}).sort('unix_date', DESCENDING)
                else:
                    cursor = self.db.posts.find({'owner': self.user['sid'], 'category_id': f['category_id']}).sort('unix_date', DESCENDING)
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
                    back_link=self.getUrlByEndpoint(endpoint='on_group_by_category_get'),
                    group='category',
                    words='',
                    user_settings=self.user['settings'],
                    provider=self.user['provider']
                    # next_tag=self.getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': next_cat}),
                    # prev_tag=self.getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': prev_cat})),
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
            self.first_letters = {}
        if not page_number:
            page_number = 1
        if letter and letter in self.first_letters:
            back_link = self.getUrlByEndpoint(endpoint='on_group_by_tags_startwith_get', params={'letter': letter})
        else:
            back_link = self.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number})
        tag = unquote_plus(quoted_tag)
        current_tag = self.db.tags.find_one({'owner': self.user['sid'], 'tag': tag})
        if current_tag:
            posts = []
            if self.user['settings']['only_unread']:
                cursor = self.db.posts.find({
                    'owner': self.user['sid'],
                    'read': False,
                    'tags': {'$all': [tag]}
                }).sort([('feed_id', DESCENDING), ('unix_date', DESCENDING)])
            else:
                cursor = self.db.posts.find({'owner': self.user['sid'], 'tags': {'$all': [tag]}}).sort([('feed_id', DESCENDING), ('unix_date', DESCENDING)])
            by_feed = {}
            for post in cursor:
                if post['feed_id'] not in by_feed:
                    by_feed[post['feed_id']] = self.db.feeds.find_one({'owner': self.user['sid'], 'feed_id': post['feed_id']})
                posts.append({
                    'post': post,
                    'pos': post['pid'],
                    'category_title': by_feed[post['feed_id']]['category_title'],
                    'feed_title': by_feed[post['feed_id']]['title'],
                    'favicon': by_feed[post['feed_id']]['favicon']
                })
            #prev_tag, next_tag = self.getPrevNextTag(tag)
            self.response = Response(
                page.render(
                    posts=posts,
                    tag=tag,
                    back_link=back_link,
                    group='tag',
                    words=', '.join(current_tag['words']),
                    user_settings=self.user['settings'],
                    provider=self.user['provider']
                    # next_tag=self.getUrlByEndpoint(endpoint='on_tag_get', params={'quoted_tag': next_tag}) if next_tag else '/',
                    # prev_tag=self.getUrlByEndpoint(endpoint='on_tag_get', params={'quoted_tag': prev_tag}) if prev_tag else '/'),
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
                cursor = self.db.posts.find({'owner': self.user['sid'], 'read': False, 'feed_id': current_feed['feed_id']}).sort('unix_date', DESCENDING)
            else:
                cursor = self.db.posts.find({'owner': self.user['sid'], 'feed_id': current_feed['feed_id']}).sort('unix_date', DESCENDING)
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
                    back_link=self.getUrlByEndpoint(endpoint='on_group_by_category_get'),
                    group='feed',
                    words='',
                    user_settings=self.user['settings'],
                    provider=self.user['provider']
                    # next_tag=self.getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': next_cat}),
                    # prev_tag=self.getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': prev_cat})),
                ),
                mimetype='text/html'
            )
        else:
            self.on_error(NotFound())

    def on_static_get(self, directory=None, filename=None):
        mimetype = 'text/plain'
        if not directory:
            directory = ''
        elif directory == 'js':
            mimetype = 'application/javascript'
        elif directory == 'img':
            mimetype = 'image/gif'
        elif directory == 'css':
            mimetype = 'text/css'
        elif filename == 'favicon.ico':
            mimetype = 'image/x-icon'
        if filename:
            f_path = os.path.join('static', directory, filename)
            l_modify = datetime.fromtimestamp(os.path.getmtime(f_path)).strftime('%a, %d %b %Y %H:%m:%S %Z%z')
            if (self.request.if_modified_since) and (self.request.if_modified_since.strftime('%a, %d %b %Y %H:%m:%S %Z%z') == l_modify):
                self.response = Response('', mimetype=mimetype)
                self.response.status_code = 304
            else:
                f = open(f_path, 'rb')
                self.response = Response(wrap_file(self.request.environ, f), mimetype=mimetype, direct_passthrough=True)
                self.response.headers['Last-Modified'] = l_modify
        else:
            self.response = Response('', mimetype=mimetype)

    def on_read_posts_post(self):
        err = []
        many = False
        if 'pos' in self.request.form:
            many = False
            try:
                post_id = int(self.request.form['pos'])
                status = bool(int(self.request.form.get('status')))
            except Exception as e:
                err.append('Pos or Status wrong')
        elif 'posts[]' in self.request.form:
            many = True
            posts = []
            try:
                posts = [int(i) for i in self.request.form.getlist('posts[]')]
                status = bool(int(self.request.form.get('status')))
            except Exception as e:
                err.append('Posts or Status wrong')
        if not err:
            err.append('ok')
            st = time.time()
            tmp_letters = self.db.letters.find_one({'owner': self.user['sid']})
            if tmp_letters:
                first_letters = tmp_letters['letters']
            else:
                first_letters = {}
            if many:
                tags = {}
                current_data = None
                for_insert = []
                if (self.user['provider'] == 'bazqux') or (self.user['provider'] == 'inoreader'):
                    current_data = self.db.posts.find({'owner': self.user['sid'], 'read': not status, 'pid': {'$in': posts}}, projection=['id', 'tags'])
                    for d in current_data:
                        for_insert.append({'user': self.user['_id'], 'id': d['id'], 'status': status})
                        for t in d['tags']:
                            if t in tags:
                                tags[t] += 1
                            else:
                                tags[t] = 1
                try:
                    self.db.mark_queue.insert_many(for_insert)
                except Exception as e:
                    logging.error('Can`t push in mark queue: {}'.format(e))
                    err.append('Database error')
                bulk = self.db.tags.initialize_unordered_bulk_op()
                if tags:
                    if status:
                        for t in tags:
                            bulk.find({'owner': self.user['sid'], 'tag': t}).update_one({'$inc': {'unread_count': -tags[t]}})
                            first_letters[t[0]]['unread_count'] -= tags[t]
                    else:
                        for t in tags:
                            bulk.find({'owner': self.user['sid'], 'tag': t}).update_one({'$inc': {'unread_count': tags[t]}})
                            first_letters[t[0]]['unread_count'] += tags[t]
                    try:
                        bulk.execute()
                    except Exception as e:
                        logging.error('Bulk failed in on_read_posts_post: %s', e)
                        err.append('Database error')
                self.db.posts.update_many({'owner': self.user['sid'], 'read': not status, 'pid': {'$in': posts}}, {'$set': {'read': status}})
            else:
                if (self.user['provider'] == 'bazqux') or (self.user['provider'] == 'inoreader'):
                    current_post = self.db.posts.find_one({'owner': self.user['sid'], 'pid': post_id}, projection=['id', 'tags'])
                    self.db.mark_queue.insert_one({'user': self.user['_id'], 'id': current_post['id'], 'status': status})
                    self.db.posts.update_one({'owner': self.user['sid'], 'pid': post_id}, {'$set': {'read': status}})
                if status:
                    incr = -1
                else:
                    incr = 1
                for t in current_post['tags']:
                    first_letters[t[0]]['unread_count'] += incr
                self.db.tags.update_many({'owner': self.user['sid'], 'tag': {'$in': current_post['tags']}}, {'$inc': {'unread_count': incr}})
            self.db.letters.update_one({'owner': self.user['sid']}, {'$set': {'letters': first_letters}})
            logging.info('%s', time.time() - st)
        self.response = Response('{{"result": "{0}"}}'.format(''.join(err)), mimetype='application/json')

    def fillFirstLetters(self):
        tmp_letters = self.db.letters.find_one({'owner': self.user['sid']})
        if tmp_letters:
            self.first_letters = getSortedDictByAlphabet(tmp_letters['letters'])
        else:
            self.first_letters = {}

    def getLetters(self):
        letters = []
        if self.user['settings']['only_unread']:
            for s_let in self.first_letters:
                if self.first_letters[s_let]['unread_count'] > 0:
                    letters.append({'letter': self.first_letters[s_let]['letter'], 'local_url': self.first_letters[s_let]['local_url']})
        else:
            for s_let in self.first_letters:
                letters.append({'letter': self.first_letters[s_let]['letter'], 'local_url': self.first_letters[s_let]['local_url']})
        return(letters)

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
            pages_map['middle'] = [
                {'p': i, 'url': self.getUrlByEndpoint(endpoint=endpoint, params={'page_number': i})} for i in range(numbers_start_range, numbers_end_range)
            ]
            if numbers_start_range > 1:
                pages_map['start'] = [{'p': 'first', 'url': self.getUrlByEndpoint(endpoint=endpoint, params={'page_number': 1})}]
            if numbers_end_range <= (page_count):
                pages_map['end'] = [{'p': 'last', 'url': self.getUrlByEndpoint(endpoint=endpoint, params={'page_number': page_count})}]
        else:
            pages_map['start'] = [{'p': i, 'url': self.getUrlByEndpoint(endpoint=endpoint, params={'page_number': i})} for i in range(1, page_count + 1)]
        start_tags_range = round(((p_number - 1) * items_per_page) + items_per_page)
        end_tags_range = round(start_tags_range + items_per_page)
        return(pages_map, start_tags_range, end_tags_range)

    def on_group_by_tags_get(self, page_number):
        self.response = None
        page = self.template_env.get_template('group-by-tag.html')
        sort_data = []
        query = {'owner': self.user['sid']}
        if self.user['settings']['only_unread']:
            if (self.user['settings']['hot_tags']):
                sort_data = [('temperature', DESCENDING), ('unread_count', DESCENDING)]
            else:
                sort_data = [('unread_count', DESCENDING)]
            query['unread_count'] = {'$gt': 0}
        else:
            if (self.user['settings']['hot_tags']):
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
                self.response = redirect(self.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': p_number}))
                self.user['page'] = p_number
            else:
                p_number = page_number
            p_number -= 1
            if p_number < 0:
                p_number = 1
            new_cookie_page_value = p_number + 1
            if not self.response:
                pages_map, start_tags_range, end_tags_range = self.calcPagerData(p_number, page_count, self.user['settings']['tags_on_page'], 'on_group_by_tags_get')
                if end_tags_range > tags_count:
                    end_tags_range = tags_count
                sorted_tags = []
                load_tags = OrderedDict()
                if self.user['settings']['only_unread']:
                    for t in cursor[start_tags_range:end_tags_range]:
                        sorted_tags.append({'tag': t['tag'], 'url': t['local_url'], 'words': t['words'], 'count': t['unread_count']})
                else:
                    for t in cursor[start_tags_range:end_tags_range]:
                        sorted_tags.append({'tag': t['tag'], 'url': t['local_url'], 'words': t['words'], 'count': t['posts_count']})
                self.fillFirstLetters()
                letters = self.getLetters()
                self.response = Response(
                    page.render(
                        tags=sorted_tags,
                        sort_by_title = 'tags',
                        sort_by_link=self.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': new_cookie_page_value}),
                        group_by_link=self.getUrlByEndpoint(endpoint='on_group_by_category_get'),
                        pages_map=pages_map,
                        current_page=new_cookie_page_value,
                        letters=letters,
                        user_settings=self.user['settings'],
                        provider=self.user['provider']
                    ),
                    mimetype='text/html'
                )
                self.db.users.update_one({'sid': self.user['sid']}, {'$set': {'page': new_cookie_page_value, 'letter': ''}})
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
                #cursor = self.db.tags.find({'owner': self.user['sid'], 'unread_count': {'$gt': 0}, 'tag': {'$regex': '^{0}'.format(let)}}).sort([('unread_count', DESCENDING), ('tag', ASCENDING)])
                cursor = self.db.tags.find({
                    'owner': self.user['sid'],
                    'unread_count': {'$gt': 0},
                    'tag': {'$regex': '^{0}'.format(let)}
                }).sort([('unread_count', DESCENDING)])
                for t in cursor:
                    tags.append({'tag': t['tag'], 'url': t['local_url'], 'words': t['words'], 'count': t['unread_count']})
            else:
                #cursor = self.db.tags.find({'owner': self.user['sid'], 'tag': {'$regex': '^{0}'.format(let)}}).sort([('posts_count', DESCENDING), ('tag', ASCENDING)])
                cursor = self.db.tags.find({'owner': self.user['sid'], 'tag': {'$regex': '^{0}'.format(let)}}).sort([('posts_count', DESCENDING)])
                for t in cursor:
                    tags.append({'tag': t['tag'], 'url': t['local_url'], 'words': t['words'], 'count': t['posts_count']})
            '''if tags:
                tags = sorted(tags, key=lambda tag: tag['count'], reverse=True)'''
            self.response = Response(
                page.render(
                    tags=tags,
                    sort_by_title=let,
                    sort_by_link=self.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number}),
                    group_by_link=self.getUrlByEndpoint(endpoint='on_group_by_category_get'),
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
            self.response = redirect(self.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number}))

    def on_get_tag_siblings(self, tag=''):
        if tag:
            query = {
                'owner': self.user['sid'],
                'tags': tag
            }
            if self.user['settings']['only_unread']:
                query['read'] = False
            cur = self.db.posts.find(query, projection=['tags'])
            tags_set = set()
            for tags in cur:
                for tag in tags['tags']:
                    tags_set.add(tag)
            if tags_set:
                query = {
                    'owner': self.user['sid'],
                    'tag': {'$in': list(tags_set)}
                }
                if self.user['settings']['only_unread']:
                    query['read'] = False
                cur = self.db.tags.find(query, projection=['tag', 'posts_count', 'unread_count'])
                if self.user['settings']['only_unread']:
                    field = 'unread_count'
                else:
                    field = 'posts_count'
                all_tags = []
                for tag in cur:
                    all_tags.append({
                        't': tag['tag'],
                        'n': tag[field]
                    })


            self.response = Response(json.dumps(all_tags), mimetype='application/json')


    def on_posts_content_post(self):
        err = []
        wanted_posts = []
        if not err:
            if 'posts[]' in self.request.form:
                try:
                    wanted_posts = [int(i) for i in self.request.form.getlist('posts[]')]
                except Exception as e:
                    wanted_posts = []
                    err.append('Posts wrong')
                if (not wanted_posts):
                    err.append('Posts must be not empty or have correct value')
        if not err:
            posts = self.db.posts.find({'owner': self.user['sid'], 'pid': {'$in': wanted_posts}}, limit=round(self.user['settings']['posts_on_page']))
            if not err:
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
                result = {'result': 'ok', 'data': posts_content}
        if not err:
            self.response = Response(json.dumps(result), mimetype='application/json')
        else:
            self.response = Response('{{"result": "error", "data":"{0}"}}'.format(''.join(err)), mimetype='application/json')
            self.response.status_code = 404

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

    def on_post_links(self):
        err = []
        result = None
        try:
            post_id = int(self.request.form.get('postid'))
        except Exception as e:
            err.append('Post id must be int number')
        if not err:
            current_post = self.db.posts.find_one({'owner': self.user['sid'], 'pid': post_id}, projection=['tags', 'feed_id', 'url'])
            if current_post:
                feed = self.db.feeds.find_one({'feed_id': current_post['feed_id'], 'owner': self.user['sid']})
                if feed:
                    result = {
                        'result': 'ok',
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
                        result['data']['tags'].append({'url': self.getUrlByEndpoint(endpoint='on_tag_get', params={'quoted_tag': t}), 'tag': t})
                else:
                    err.append('Can`t find feed')
            else:
                err.append('Can`t find post')
        if not err:
            self.response = Response(json.dumps(result), mimetype='application/json')
        else:
            self.response = Response('{{"result": "error", "data":"{0}"}}'.format(''.join(err)), mimetype='application/json')
            self.response.status_code = 404

    def on_get_all_tags(self):
        err = []
        result = []
        if self.user['settings']['only_unread']:
            all_tags = self.db.tags.find({'owner': self.user['sid'], 'unread_count': {'$gt': 0}})
        else:
            all_tags = self.db.tags.find({'owner': self.user['sid']})
        for tag in all_tags:
            result.append({'t': tag['tag'], 'l': '/tag/{0}'.format(tag['local_url'])});
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
                    for id in posts:
                        if tag in posts[id]['tags']:
                            posts[id]['feed_title'] = feeds[posts[id]['feed_id']]['title']
                            posts[id]['category_title'] = feeds[posts[id]['feed_id']]['category_title']
                            result[tag]['posts'].append(posts[id])
                            posts_for_delete.append(id)
                    for id in posts_for_delete:
                        del(posts[id])
                    result[tag]['posts'] = sorted(result[tag]['posts'], key=lambda p: p['feed_id'])
                letter = self.user['letter']
                page_number = self.user['page']
                if letter:
                    back_link = self.getUrlByEndpoint(endpoint='on_group_by_tags_startwith_get', params={'letter': letter})
                elif self.user['settings']['hot_tags']:
                    back_link = self.getUrlByEndpoint(endpoint='on_group_by_hottags_get', params={'page_number': page_number})
                else:
                    back_link = self.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number})
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
            self.response = redirect(self.getUrlByEndpoint('on_root_get'))

    def on_post_tags_search(self):
        errors = []
        result = []
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
        if (not errors):
            result = {'result': 'ok', 'data': []}
            for tag in tags_cur:
                result['data'].append({
                    'tag': quote_plus(tag['tag']),
                    'cnt': tag[field_name],
                    'url': self.getUrlByEndpoint(endpoint='on_tag_get', params={'quoted_tag': quote_plus(tag['local_url'])})
                })
        else:
            result = {'result': 'error', 'data': ''.join(errors)}
        self.response = Response(json.dumps(result), mimetype='application/json')


def getSortedDictByAlphabet(dct, type=None):
    if not type or type == 'k':
        sorted_keys = sorted(dct.keys())
    elif type == 'c':
        sorted_keys = sorted(dct.keys(), key=lambda d:dct[d]['title'])
    temp_dct = dct
    sorted_dct = OrderedDict()
    for key in sorted_keys:
        sorted_dct[key] = temp_dct[key]
    return(sorted_dct)

def downloader_bazqux(data):
    try:
        logging.info('Start downloading, %s', data['category'])
    except Exception as e:
        logging.warning('Start downloading, category with strange symbols')
    counter_for_downloads = 0
    result = {'items': []}
    again = True;
    url = data['url']
    while again:
        try:
            connection = client.HTTPSConnection(data['host'])
            connection.request('GET', url, '', data['headers'])
            resp = connection.getresponse()
            json_data = resp.read()
            tmp_result = {}
            if json_data:
                tmp_result = json.loads(json_data.decode('utf-8'))
            else:
                logging.error('json_data is empty - %s', json_data)
            if tmp_result:
                if 'continuation' not in tmp_result:
                    again = False
                else:
                    url = data['url'] + '&c={0}'.format(tmp_result['continuation'])
                result['items'].extend(tmp_result['items'])
            else:
                if counter_for_downloads == 5:
                    logging.error('enough downloading')
                    again = False
                logging.error('tmp_result is empty - %s', tmp_result)
        except Exception as e:
            logging.error('%s: %s %s %s yoyoyo', e, data['category'], counter_for_downloads, url)
            if counter_for_downloads == 5:
                again = False
            else:
                counter_for_downloads += 1
                time.sleep(2)
            result = None
            f = open('log/{0}'.format(data['category']), 'w')
            f.write(json_data.decode('utf-8'))
            f.close()
    try:
        logging.info('Downloaded, %s', data['category'])
    except Exception as e:
        logging.warning('Downloaded, category with strange symbols')
    return(result, data['category'])

def worker(config, routes_list):
    try:
        logging.basicConfig(
            filename=config['settings']['log_file'],
            filemode='a',
            level=getattr(logging, config['settings']['log_level'].upper())
        )
    except Exception as e:
        logging.critical('Error in logging configuration: %s', e)
    rules = []
    for route in routes_list:
        rules.append(Rule(route['url'], endpoint=route['endpoint'], methods=route['methods']))
    routes = Map(rules)
    name = str(randint(0, 10000))
    no_category_name = 'NotCategorized'
    tags_builder = TagsBuilder(config['settings']['replacement'])
    html_clnr = HTMLCleaner()
    by_category = {}
    by_feed = {}
    by_tag = {'tags': {}}
    first_letters = {}
    user = None
    all_posts = []

    user_ttl = int(config['settings']['user_ttl'])
    #all_posts_content = []
    cl = MongoClient(config['settings']['db_host'], int(config['settings']['db_port']))
    db = cl.rss

    def treatPosts(category=None, p_range=None):
        try:
            logging.info('treating %s', category)
        except Exception as e:
            logging.warning('treating category with strange symbols')
        for pos in range(p_range[0], p_range[1]):
            if not all_posts[pos]['content']['title']:
                all_posts[pos]['content']['title'] = 'Notitle'
            all_posts[pos]['owner'] = user['sid']
            all_posts[pos]['category_id'] = category
            all_posts[pos]['tags'] = []
            all_posts[pos]['pid'] = pos
            all_posts[pos]['createdAt'] = datetime.utcnow()
            title = all_posts[pos]['content']['title']
            content = gzip.decompress(all_posts[pos]['content']['content'])
            content = content.decode('utf-8')
            if content:
                html_clnr.purge()
                html_clnr.feed(content)
                strings = html_clnr.get_content()
                if strings:
                    content = ' '.join(strings)

            content = title + ' ' + content
            tags_builder.purge()
            tags_builder.build_tags(content)
            tags = tags_builder.get_tags()
            words = tags_builder.get_words();
            for tag in tags:
                if tag[0] not in first_letters:
                    first_letters[tag[0]] = {
                        'letter': tag[0],
                        'local_url': getUrlByEndpoint(endpoint='on_group_by_tags_startwith_get',
                                                      params={'letter': tag[0]}),
                        'unread_count': 0
                    }
                if tag not in by_tag['tags']:
                    by_tag['unread_count'] += 1
                    by_tag['tags'][tag] = {'words': [], 'local_url': tag, 'read': False, 'tag': tag,
                                           'owner': user['sid'], 'posts': set(),
                                           'temperature': 0}  # 'posts': set(), 'read_posts': set(),
                by_tag['tags'][tag]['words'] = words[tag]
                by_tag['tags'][tag]['posts'].add(pos)
                if tag not in all_posts[pos]['tags']:
                    all_posts[pos]['tags'].append(tag)

        try:
            logging.info('treated %s', category)
        except Exception as e:
            logging.warning('treated category with strange symbols')
        return(p_range)

    def saveAllData():
        if all_posts:
            st = time.time()
            tags_list = []
            for t in by_tag['tags']:
                by_tag['tags'][t]['createdAt'] = datetime.utcnow()
                by_tag['tags'][t]['unread_count'] = len(by_tag['tags'][t]['posts'])
                by_tag['tags'][t]['posts_count'] = by_tag['tags'][t]['unread_count']
                first_letters[t[0]]['unread_count'] += by_tag['tags'][t]['posts_count']
                del by_tag['tags'][t]['posts']
                tags_list.append(by_tag['tags'][t])
            try:
                db.posts.insert_many(all_posts)
                db.feeds.insert_many(list(by_feed.values()))
                db.tags.insert_many(tags_list)
                db.letters.insert_one({'owner': user['sid'], 'letters': first_letters, 'createdAt': datetime.utcnow()})
                db.users.update_one(
                    {'sid': user['sid']},
                    {'$set': {'ready_flag': True, 'in_queue': False, 'message': 'You can start reading', 'createdAt': datetime.utcnow()}}
                )
            except Exception as e:
                logging.error('Can`t save all data: %s', e)
                db.users.update_one(
                    {'sid': user['sid']},
                    {'$set': {'ready_flag': False, 'in_queue': False, 'message': 'Can`t save to database, please try later', 'createdAt': datetime.utcnow()}}
                )
            logging.info('saved all-%s %s %s %s', time.time() - st, len(tags_list), len(all_posts), len(by_feed))
        else:
            db.users.update_one({'sid': user['sid']}, {'$set': {'ready_flag': True, 'in_queue': False, 'message': 'You can start reading'}})
            logging.warning('Nothing to save')

    def processWords():
        cur = db.tags.find({'owner': user['sid']})
        for tag in cur:
            word = db.words.find_one({'word': tag['tag']})
            if word:
                old_mid = sum(word['numbers']) / len(word['numbers'])
                word['numbers'].append(tag['posts_count'])
                new_mid = sum(word['numbers']) / len(word['numbers'])
                temperature = abs(new_mid - old_mid)
                db.tags.find_one_and_update(
                    {'tag': tag['tag']},
                    {'$set': {'temperature': temperature}}
                )
            db.words.find_one_and_update(
                {'word': tag['tag']},
                {'$push': {'numbers': tag['posts_count']}},
                upsert = True
            )


    def getUrlByEndpoint(endpoint=None, params=None, full_url=False):
        url = None
        if endpoint:
            url = next(routes.iter_rules(endpoint=endpoint))
            if params:
                all_urls = routes.bind(host, '/')
                url = all_urls.build(endpoint, params, force_external=full_url)
        return(url)

    while True:
        data = None
        user_id = None
        user = None
        #st = time.time()
        try:
            data = db.download_queue.find_one_and_delete({})
        except Exception as e:
            data = None
            logging.error('Worker can`t get data from queue: {}'.format(e))
        if data:
            user_id = data['user']
            type = 'download'
        else:
            try:
                data = db.mark_queue.find_one_and_delete({})
            except Exception as e:
                data = None
                logging.error('Worker can`t get data from queue: {}'.format(e))
            if data:
                user_id = data['user']
                type = 'mark'
        if user_id:
            user = db.users.find_one({'_id': user_id})
        if not user:
            #print('Tasks list is empty.', name, 'going sleep')
            time.sleep(randint(3, 8))
            continue
        #print(name, 'lock wait', time.time() - st)
        if type == 'download':
            by_category.clear()
            by_tag['tags'].clear()
            by_tag.clear()
            by_tag['tags'] = {}
            by_tag['unread_count'] = 0
            by_feed.clear()
            all_posts = []
            first_letters.clear()
            user['ready_flag'] = False
            db.feeds.remove({'owner': user['sid']})
            db.posts.remove({'owner': user['sid']})
            db.tags.remove({'owner': user['sid']})
            db.letters.remove({'owner': user['sid']})
            host = data['host']
            if (user['provider'] == 'bazqux') or (user['provider'] == 'inoreader'):
                connection = client.HTTPSConnection(config[user['provider']]['api_host'])
                headers = {'Authorization': 'GoogleLogin auth={0}'.format(user['token'])}
                connection.request('GET', '/reader/api/0/subscription/list?output=json', '', headers)
                resp = connection.getresponse()
                json_data = resp.read()
                try:
                    subscriptions = json.loads(json_data.decode('utf-8'))
                except Exception as e:
                    subscriptions = None
                    logging.error('Can`t decode subscriptions %s', e);
                if subscriptions:
                    works = []
                    i = 0
                    feed = None
                    for i, feed in enumerate(subscriptions['subscriptions']):
                        '''if i >= 4:
                            break'''
                        if len(feed['categories']) > 0:
                            category_name = feed['categories'][0]['label']
                        else:
                            category_name = no_category_name
                            works.append({
                                'headers': headers,
                                'host': config[user['provider']]['api_host'],
                                'url': '/reader/api/0/stream/contents?s={0}&xt=user/-/state/com.google/read&n=5000&output=json'.format(quote_plus(feed['id'])),
                                'category': category_name
                            })
                        if category_name not in by_category:
                            by_category[category_name] = True
                            if category_name != no_category_name:
                                works.append({
                                    'headers': headers,
                                    'host': config[user['provider']]['api_host'],
                                    'url': '/reader/api/0/stream/contents?s=user/-/label/{0}&xt=user/-/state/com.google/read&n=1000&output=json'.format(
                                        quote_plus(category_name)
                                    ),
                                    'category': category_name
                                })
                    workers_downloader_pool = Pool(int(config['settings']['workers_count']))
                    posts = None
                    category = None
                    for posts, category in workers_downloader_pool.imap(downloader_bazqux, works, 1):
                        if posts and posts['items']:
                            old_posts_count = len(all_posts)
                            posts_count = len(posts['items'])
                            p_range = (old_posts_count, old_posts_count + posts_count)
                            for post in posts['items']:
                                origin_feed_id = post['origin']['streamId']
                                post['origin']['streamId'] = md5(post['origin']['streamId'].encode('utf-8')).hexdigest()
                                if post['origin']['streamId'] not in by_feed:
                                    by_feed[post['origin']['streamId']] = {
                                        'createdAt': datetime.utcnow(),
                                        'title': post['origin']['title'],
                                        'owner': user['sid'],
                                        'category_id': category,
                                        'feed_id': post['origin']['streamId'],
                                        'origin_feed_id': origin_feed_id,
                                        'category_title': category,
                                        'category_local_url': getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': category}),
                                        'local_url': getUrlByEndpoint(endpoint='on_feed_get', params={'quoted_feed': post['origin']['streamId']})
                                    }
                                p_date = None
                                if 'published' in post:
                                    p_date = date.fromtimestamp(int(post['published'])).strftime('%x')
                                    pu_date = float(post['published'])
                                else:
                                    p_date = -1
                                    pu_date = -1
                                attachments_list = []
                                if 'enclosure' in post:
                                    for attachments in post['enclosure']:
                                        if ('href' in attachments) and attachments['href']:
                                            attachments_list.append(attachments['href'])
                                all_posts.append({
                                    #'category_id': category,
                                    'content': {'title': post['title'], 'content': gzip.compress(post['summary']['content'].encode('utf-8', 'replace'))},
                                    'feed_id': post['origin']['streamId'],
                                    'id': post['id'],
                                    'url': post['canonical'][0]['href'] if post['canonical'] else 'http://ya.ru',
                                    'date': p_date,
                                    'unix_date': pu_date,
                                    'read': False,
                                    'favorite': False,
                                    'attachments': attachments_list
                                    #'meta': '/reader/api/0/edit-tag?output=json&i={0}'.format(post['id'])
                                })
                                if 'favicon' not in by_feed[post['origin']['streamId']]:
                                    if all_posts[-1]['url']:
                                        #by_feed[post['origin']['streamId']]['favicon'] = all_posts[-1]['url']
                                        parsed_url = urlparse(all_posts[-1]['url'])
                                        by_feed[post['origin']['streamId']]['favicon'] = '{0}://{1}/favicon.ico'.format(
                                            parsed_url.scheme if parsed_url.scheme else 'http',
                                            parsed_url.netloc
                                        )
                            treatPosts(category, p_range)
                    workers_downloader_pool.terminate()
                    by_tag = getSortedDictByAlphabet(by_tag)
                    #first_letters = getSortedDictByAlphabet(first_letters)
                    '''user['ready_flag'] = True
                    user['in_queue'] = False
                    user['message'] = 'You can start reading'''
                    saveAllData()
                    processWords()
        elif type == 'mark':
            status = data['status']
            if (user['provider'] == 'bazqux') or (user['provider'] == 'inoreader'):
                id = data['id']
                headers = {'Authorization': 'GoogleLogin auth={0}'.format(user['token']), 'Content-type': 'application/x-www-form-urlencoded'}
                err = []
                counter = 0
                read_tag = 'user/-/state/com.google/read'
                if status:
                    data = urlencode({'i' : id, 'a': read_tag})
                else:
                    data = urlencode({'i' : id, 'r': read_tag})
                while (counter < 6):
                    connection = client.HTTPSConnection(config[user['provider']]['api_host'])
                    counter += 1
                    err = []
                    try:
                        connection.request('POST', '/reader/api/0/edit-tag?output=json', data, headers)
                        resp = connection.getresponse()
                        resp_data = resp.read()
                    except Exception as e:
                        err.append(str(e))
                        connection.close()
                        logging.warning('Can`t make request %s %s', e, counter)
                    if not err:
                        if resp_data.decode('utf-8').lower() == 'ok':
                            #print('marked')
                            counter = 6
                        else:
                            time.sleep(randint(2, 7))
                            if counter < 6 :
                                logging.warning('try again')
                            else:
                                logging.warning('not marked %s', resp_data)
                connection.close()

if __name__ == '__main__':
    config_path = 'rsscloud.conf'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    app = RSSCloudApplication(config_path)
    if app:
        try:
            run_simple(app.config['settings']['host'], int(app.config['settings']['port']), app.setResponse)
        except Exception as e:
            logging.error(e)
            app.close()
    else:
        logging.critical('Can`t start server')
