# -*- coding: UTF-8 -*-
from configparser import ConfigParser
import os, json, re
from urllib.parse import unquote_plus, quote_plus, urlencode, urlparse
from http import client
import time
#import pickle
import gzip
from collections import OrderedDict
from datetime import date, datetime
from random import randint
from hashlib import md5, sha256
from xml.dom.minidom import parseString
from multiprocessing import Process, Queue, Pool, Lock
from werkzeug.wrappers import Response, Request
from werkzeug.routing import Map, Rule
from werkzeug.serving import run_simple
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.utils import redirect
from werkzeug.wsgi import wrap_file
from jinja2 import Environment, PackageLoader
import pymorphy2
from nltk.stem import PorterStemmer
from pymongo import MongoClient, DESCENDING #, ASCENDING
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
    firsts_queue = None
    seconds_queue = None
    workers_pool = []
    providers = []
    user_ttl = 0
    count_showed_nubmers = 4
    db = None
    allow_not_logged = ('on_root_get', 'on_login_get', 'on_login_post', 'on_code_get', 'on_select_provider_post', 'on_select_provider_get', 'on_static_get', 'on_ready_get', 'on_refresh_get_post', 'on_favicon_get')
    firsts_lock = None
    seconds_lock = None
    no_category_name = 'NotCategorized'

    def __init__(self, config_path=None):
        if self.setConfig(config_path):
            self.config_path = config_path
            self.template_env = Environment(loader=PackageLoader('rss', os.path.join(os.path.dirname(__file__), 'templates', self.config['settings']['templates'])))
            self.firsts_queue = Queue()
            self.seconds_queue = Queue()
            self.firsts_lock = Lock()
            self.seconds_lock = Lock()
            self.providers = self.config['settings']['providers'].split(',')
            self.user_ttl = int(self.config['settings']['user_ttl'])
            cl = MongoClient(self.config['settings']['db_host'], int(self.config['settings']['db_port']))
            self.db = cl.rss
            self.db.posts.ensure_index([('owner', 1)])
            self.db.posts.ensure_index([('category_id', 1)])
            self.db.posts.ensure_index([('feed_id', 1)])
            self.db.posts.ensure_index([('read', 1)])
            self.db.posts.ensure_index([('tags', 1)])
            self.db.posts.ensure_index([('pid', 1)])
            self.db.posts.ensure_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
            self.db.feeds.ensure_index([('owner', 1)])
            self.db.feeds.ensure_index([('feed_id', 1)])
            self.db.feeds.ensure_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
            self.db.letters.ensure_index([('owner', 1)])
            self.db.letters.ensure_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
            self.db.users.ensure_index([('sid', 1)])
            self.db.users.ensure_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
            self.db.tags.ensure_index([('owner', 1)])
            self.db.tags.ensure_index([('tag', 1)])
            self.db.tags.ensure_index([('unread_count', 1)])
            self.db.tags.ensure_index([('posts_count', 1)])
            self.db.tags.ensure_index([('createdAt', 1)], expireAfterSeconds=self.user_ttl)
            #self.favicon_url_re = re.compile(r'(?imu)<link.*?rel.*?href.{0,2}=.{0,2}"(.*favicon.*?)"')
            self.routes = Map([
                Rule('/', endpoint='on_root_get', methods=['GET', 'HEAD']),
                Rule('/favicon.ico', endpoint='on_favicon_get', methods=['GET', 'HEAD']),
                Rule('/code', endpoint='on_code_get', methods=['GET', 'HEAD']),
                Rule('/login', endpoint='on_login_get', methods=['GET', 'HEAD']),
                Rule('/login', endpoint='on_login_post', methods=['POST']),
                Rule('/provider', endpoint='on_select_provider_get', methods=['GET', 'HEAD']),
                Rule('/provider', endpoint='on_select_provider_post', methods=['POST']),
                Rule('/group/tag/<int:page_number>', endpoint='on_group_by_tags_get', methods=['GET', 'HEAD']),
                Rule('/group/tag/startwith/<string(length=1):letter>', endpoint='on_group_by_tags_startwith_get', methods=['GET', 'HEAD']),
                Rule('/group/category', endpoint='on_group_by_category_get', methods=['GET', 'HEAD']),
                Rule('/refresh', endpoint='on_refresh_get_post', methods=['GET', 'HEAD', 'POST']),
                Rule('/static/<string:directory>/<string:filename>', endpoint='on_static_get', methods=['GET', 'HEAD']),
                Rule('/static/<string:filename>', endpoint='on_static_get', methods=['GET', 'HEAD']),
                Rule('/tag/<string:quoted_tag>', endpoint='on_tag_get', methods=['GET', 'HEAD']),
                Rule('/category/<string:quoted_category>', endpoint='on_category_get', methods=['GET', 'HEAD']),
                Rule('/feed/<string:quoted_feed>', endpoint='on_feed_get', methods=['GET', 'HEAD']),
                Rule('/read/posts', endpoint='on_read_posts_post', methods=['POST']),
                Rule('/posts-content', endpoint='on_posts_content_post', methods=['POST']),
                Rule('/post-content', endpoint='on_post_content_post', methods=['POST']),
                Rule('/post-links', endpoint='on_post_links', methods=['POST']),
                Rule('/ready', endpoint='on_ready_get', methods=['GET', 'HEAD']),
                Rule('/only-unread', endpoint='on_only_unread_post', methods=['POST']),
                Rule('/all-tags', endpoint='on_get_all_tags', methods=['GET', 'HEAD']),
                Rule('/posts/with/tags/<string:s_tags>', endpoint='on_get_posts_with_tags', methods=['GET', 'HEAD'])
            ])
            self.updateEndpoints()
            if not self.workers_pool:
                for i in range(int(self.config['settings']['workers_count'])):
                    self.workers_pool.append(Process(target=worker, args=(self.firsts_queue, self.seconds_queue, self.firsts_lock, self.seconds_lock, self.config)))
                    self.workers_pool[-1].start()
        else:
            return None

    def close(self):
        if self.workers_pool:
            for p in self.workers_pool:
                p.terminate()

    def updateEndpoints(self):
        for i in self.routes.iter_rules():
            self.endpoints[i.endpoint] = getattr(self, i.endpoint)

    def prepareSession(self):
        sid = self.request.cookies.get('sid')
        if sid:
            self.user = self.db.users.find_one({'sid': sid})
        else:
            self.user = None
        if self.user:
            self.need_cookie_update = True
            return(True)
        else:
            self.need_cookie_update = False
            return(False)

    def createNewSession(self):
        self.need_cookie_update = True
        if self.user and 'sid' in self.user:
            user = self.db.users.find_one({'sid': self.user['sid']})
            if user:
                try:
                    self.db.users.update(
                        {'sid': self.user['sid']},
                        {'$set': {'ready_flag': False, 'provider': self.user['provider'], 'token': self.user['token'], 'message': 'Click on "Refresh posts" to start downloading data', 'in_queue': False, 'createdAt': datetime.utcnow()}})
                except Exception as e:
                    self.user = None
                    print(e, 'Can`t create new session')
        else:
            self.user['sid'] = sha256(os.urandom(randint(80, 200))).hexdigest()
            self.user['letter'] = ''
            self.user['page'] = '1'
            self.user['only_unread'] = True
            self.user['ready_flag'] = False
            self.user['cloud_items_on_page'] = 100
            self.user['posts_on_page'] = 30
            self.user['message'] = 'Click on "Refresh posts" to start downloading data'
            self.user['in_queue'] = False
            self.user['createdAt'] = datetime.utcnow()
            try:
                self.db.users.insert(self.user)
            except Exception as e:
                self.user = None
                print(e, 'Can`t create new session')
        self.user = self.db.users.find_one({'sid': self.user['sid']})

    def getPageCount(self, items_count, items_on_page_count):
        page_count = divmod(items_count, items_on_page_count)
        if page_count[1] == 0:
            page_count = page_count[0]
        elif (page_count[1] > 0) or (page_count[0] == 0):
            page_count = page_count[0] + 1
        return(page_count)

    def getFaviconUrl(self, url):
        parsed_url = urlparse(url)
        host = parsed_url.netloc
        url = '/favicon.ico'
        root_url = '/'
        favicon_url = None
        c = client.HTTPConnection(host)
        c.request('HEAD', url)
        r = c.getresponse()
        favicon_url = None
        new_host = None
        print(r.status, host)
        if r.status != 200:
            favicon_url = None
            print('try get from page', host)
            c.close()
            c = client.HTTPConnection(host)
            c.request('GET', root_url)
            r = c.getresponse()
            if r.status == 301:
                c.close()
                new_host = urlparse(r.getheader('Location')).netloc
                print('redirected', new_host)
                c = client.HTTPConnection(new_host)
                c.request('HEAD', url)
                r = c.getresponse()
                if r.status == 200:
                    print('found on redirect root')
                    favicon_url = 'http://{0}{1}'.format(new_host, url)
                else:
                    c.close()
                    print('try get from redirected page')
                    c = client.HTTPConnection(new_host)
                    c.request('GET', root_url)
                    r = c.getresponse()
            if not favicon_url:
                if r.status == 200:
                    page = r.read()
                    print('parse page')
                    result = self.favicon_url_re.search(page.decode('utf-8', 'ignore'))
                    print('page parsed')
                    if result:
                        favicon_url = result.group(1)
                        parsed_url = urlparse(favicon_url)
                        if (not parsed_url.scheme) or (not parsed_url.netloc):
                            if parsed_url.netloc:
                                h = parsed_url.netloc
                            elif new_host:
                                h = new_host
                            else:
                                h = host
                            favicon_url = 'http://{0}/{1}'.format(h, parsed_url.path)
                    else:
                        print('not found on page')
                        favicon_url = None
                else:
                    print('page not found')
                    favicon_url = None
        else:
            print('all ok')
            favicon_url = 'http://{0}{1}'.format(host, url)
        c.close()
        return(favicon_url)

    def setResponse(self, http_env, start_resp):
        self.request = Request(http_env)
        st = time.time()
        adapter = self.routes.bind_to_environ(self.request.environ)
        self.prepareSession()
        try:
            handler, values = adapter.match()
            print(handler, end=' - ')
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
            self.response.set_cookie('sid', self.user['sid'], max_age=self.user_ttl)
            #self.response.set_cookie('sid', self.user['sid'])
        self.request.close()
        self.response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        print(time.time() - st)
        return(self.response(http_env, start_resp))

    def setConfig(self, config_name):
        if config_name and os.path.exists(config_name):
            c = ConfigParser()
            c.read(config_name, encoding='utf-8')
            self.config = c
            return(True)
        else:
            return(False)

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

    def on_code_get(self):
        err = []
        if self.user:
            self.user['provider'] = self.request.cookies.get('provider')
        else:
            self.user = {'provider': self.request.cookies.get('provider')}
        if self.user['provider'] == 'yandex':
            connection = client.HTTPSConnection(self.config['yandex']['oauth_host'])
            body = 'grant_type=authorization_code&code={0}&client_id={1}&client_secret={2}'.format(self.request.args['code'], self.config['yandex']['id'], self.config['yandex']['secret'])
            try:
                connection.request('POST', '/token', body)
            except Exception as e:
                err.append('Can`t make request to Yandex. {0}'.format(e))
            resp = connection.getresponse()
            try:
                resp_dict = json.loads(resp.read().decode('utf-8'))
            except Exception as e:
                err.append('Can`t encode json. {0}'.format(e))
            connection.close()
            token = resp_dict.get('access_token')
            if token:
                self.user['token'] = token
                self.createNewSession()
                if not self.user:
                    err.append('Cant create session, try later')
            else:
                err.append('Can`t get token')
        if not err:
            #self.response = redirect(self.getUrlByEndpoint(endpoint='on_root_get'))
            self.response = redirect(self.getUrlByEndpoint(endpoint='on_refresh_get_post'))
        else:
            page = self.template_env.get_template('error.html')
            self.response = Response(page.render(err=err), mimetype='text/html')

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
            self.response.set_cookie('provider', provider, max_age=300)
        else:
            page = self.template_env.get_template('error.html')
            self.response = Response(page.render(err=['Unknown provider']), mimetype='text/html')

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
                    support=self.config['settings']['support']
                ), mimetype='text/html')
            elif provider == 'yandex':
                self.response = redirect(
                    'https://oauth.yandex.ru/authorize?response_type=code&client_id={0}&client_secret={1}&redirect_uri={2}'.format(
                        self.config['yandex']['id'],
                        self.config['yandex']['secret'],
                        self.getUrlByEndpoint(endpoint='on_code_get', full_url=True)
                    )
                )
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
            self.response = Response('', mimetype='text/html')
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
                        self.createNewSession()
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
            self.on_login_get(err)

    def on_refresh_get_post(self):
        if self.user:
            if not self.user['in_queue']:
                self.firsts_queue.put({'user': self.user, 'type': 'download', 'data': {'host' : self.request.environ['HTTP_HOST'], 'routes': self.routes}})
                '''self.user['ready_flag'] = False
                self.user['in_queue'] = True
                self.user['message'] = 'Downloading data, please wait'''
                self.db.users.update({'sid': self.user['sid']}, {'$set': {'ready_flag': False, 'in_queue': True, 'message': 'Downloading data, please wait'}})
            else:
                #self.user['message'] = 'You already in queue, please wait'
                self.db.users.update({'sid': self.user['sid']}, {'$set': {'message': 'You already in queue, please wait'}})
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

    def on_only_unread_post(self):
        status = bool(int(self.request.form.get('status')))
        result = {}
        if self.user:
            #self.user['only_unread'] = status
            self.db.users.update({'sid': self.user['sid']}, {'$set': {'only_unread': status}})
            result = {'result': 'ok', 'reason': 'ok'}
        else:
            result = {'result': 'error', 'reason': 'Not logged'}
        self.response = Response(json.dumps(result), mimetype='text/html')

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
            if cursor and cursor['result']:
                for result in cursor['result']:
                    if result['_id']:
                        posts['read'] = result['counter']
                    else:
                        posts['unread'] = result['counter']
            page = self.template_env.get_template('root-logged.html')
            self.response = Response(page.render(
                err=err,
                support=self.config['settings']['support'],
                version=self.config['settings']['version'],
                only_unread=self.user['only_unread'],
                provider=self.user['provider'],
                posts_per_page=self.user['posts_on_page'],
                tags_per_page=self.user['cloud_items_on_page'],
                posts=posts),
            mimetype='text/html')
        else:
            provider = 'Not selected'
            page = self.template_env.get_template('root.html')
            self.response = Response(page.render(err=err, only_unread=only_unread, provider=provider, support=self.config['settings']['support'], version=self.config['settings']['version']), mimetype='text/html')

    def on_group_by_category_get(self):
        page_number = self.user['page']
        if not page_number:
            page_number = 1
        by_feed = {}
        for f in self.db.feeds.find({'owner': self.user['sid']}):
            by_feed[f['feed_id']] = f
        if self.user['only_unread']:
            match = {'owner': self.user['sid'], 'read':False}
        else:
            match = {'owner': self.user['sid']}
        grouped = self.db.posts.aggregate([
            {'$match': match},
            {'$group': {'_id': '$feed_id', 'category_id': {'$first': '$category_id'}, 'count': {'$sum': 1}}}
        ])
        all_feeds = 'All'
        by_category = {all_feeds: {'unread_count' : 0, 'title': all_feeds, 'url': self.getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': all_feeds}), 'feeds' : []}}
        for g in grouped['result']:
            if g['count'] > 0:
                if g['category_id'] not in by_category:
                    by_category[g['category_id']] = {'unread_count' : 0, 'title': by_feed[g['_id']]['category_title'], 'url': by_feed[g['_id']]['category_local_url'], 'feeds' : []}
                by_category[g['category_id']]['unread_count'] += g['count']
                by_category[all_feeds]['unread_count'] += g['count']
                by_category[g['category_id']]['feeds'].append({'unread_count': g['count'], 'url': by_feed[g['_id']]['local_url'], 'title': by_feed[g['_id']]['title']})
        if len(by_category) > 1:
            data = getSortedDictByAlphabet(by_category)
            if self.no_category_name in data:
                data.move_to_end(self.no_category_name)
        else:
            data = {}
        page = self.template_env.get_template('group-by-category.html')
        self.response = Response(page.render(
            data=data,
            group_by_link=self.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number}),
            only_unread=self.user['only_unread'],
            provider=self.user['provider'],
            posts_per_page=self.user['posts_on_page'],
            tags_per_page=self.user['cloud_items_on_page']),
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
            if self.user['only_unread']:
                if cat == all_feeds:
                    cursor = self.db.posts.find({'owner': self.user['sid'], 'read': False}).sort([('feed_id', DESCENDING), ('unix_date', DESCENDING)])
                else:
                    cursor = self.db.posts.find({'owner': self.user['sid'], 'read': False, 'category_id': f['category_id']}).sort([('feed_id', DESCENDING), ('unix_date', DESCENDING)])
            else:
                if cat == all_feeds:
                    cursor = self.db.posts.find({'owner': self.user['sid']}).sort('unix_date', DESCENDING)
                else:
                    cursor = self.db.posts.find({'owner': self.user['sid'], 'category_id': f['category_id']}).sort('unix_date', DESCENDING)
            posts = []
            for post in cursor:
                posts.append({'post': post, 'pos': post['pid'], 'category_title': by_feed[post['feed_id']]['category_title'], 'feed_title': by_feed[post['feed_id']]['title'], 'favicon': by_feed[post['feed_id']]['favicon']})
            self.response = Response(
                page.render(
                    posts=posts,
                    tag=cat,
                    back_link=self.getUrlByEndpoint(endpoint='on_group_by_category_get'),
                    group='category',
                    words='',
                    only_unread=self.user['only_unread'],
                    provider=self.user['provider'],
                    posts_per_page=self.user['posts_on_page'],
                    tags_per_page=self.user['cloud_items_on_page']),
                    #next_tag=self.getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': next_cat}),
                    #prev_tag=self.getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': prev_cat})),
                mimetype='text/html')
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
            if self.user['only_unread']:
                cursor = self.db.posts.find({'owner': self.user['sid'], 'read': False, 'tags': {'$all': [tag]}}).sort([('feed_id', DESCENDING), ('unix_date', DESCENDING)])
            else:
                cursor = self.db.posts.find({'owner': self.user['sid'], 'tags': {'$all': [tag]}}).sort([('feed_id', DESCENDING), ('unix_date', DESCENDING)])
            by_feed = {}
            for post in cursor:
                if post['feed_id'] not in by_feed:
                    by_feed[post['feed_id']] = self.db.feeds.find_one({'owner': self.user['sid'], 'feed_id': post['feed_id']})
                posts.append({'post': post, 'pos': post['pid'], 'category_title': by_feed[post['feed_id']]['category_title'], 'feed_title': by_feed[post['feed_id']]['title'], 'favicon': by_feed[post['feed_id']]['favicon']})
            #prev_tag, next_tag = self.getPrevNextTag(tag)
            self.response = Response(
                page.render(
                    posts=posts,
                    tag=tag,
                    back_link=back_link,
                    group='tag',
                    words=', '.join(current_tag['words']),
                    only_unread=self.user['only_unread'],
                    provider=self.user['provider'],
                    posts_per_page=self.user['posts_on_page'],
                    tags_per_page=self.user['cloud_items_on_page']),
                    #next_tag=self.getUrlByEndpoint(endpoint='on_tag_get', params={'quoted_tag': next_tag}) if next_tag else '/',
                    #prev_tag=self.getUrlByEndpoint(endpoint='on_tag_get', params={'quoted_tag': prev_tag}) if prev_tag else '/'),
                mimetype='text/html')
        else:
            self.on_error(NotFound())

    def on_feed_get(self, quoted_feed=None):
        page = self.template_env.get_template('posts.html')
        feed = unquote_plus(quoted_feed)
        current_feed = self.db.feeds.find_one({'owner': self.user['sid'], 'feed_id': feed})
        if feed:
            if self.user['only_unread']:
                cursor = self.db.posts.find({'owner': self.user['sid'], 'read': False, 'feed_id': current_feed['feed_id']}).sort('unix_date', DESCENDING)
            else:
                cursor = self.db.posts.find({'owner': self.user['sid'], 'feed_id': current_feed['feed_id']}).sort('unix_date', DESCENDING)
            posts = []
            for post in cursor:
                posts.append({'post': post, 'category_title': current_feed['category_title'], 'pos': post['pid'], 'feed_title': current_feed['title'], 'favicon': current_feed['favicon']})
            self.response = Response(
                page.render(
                    posts=posts,
                    tag=current_feed['title'],
                    back_link=self.getUrlByEndpoint(endpoint='on_group_by_category_get'),
                    group='feed',
                    words='',
                    only_unread=self.user['only_unread'],
                    provider=self.user['provider'],
                    posts_per_page=self.user['posts_on_page'],
                    tags_per_page=self.user['cloud_items_on_page']),
                    #next_tag=self.getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': next_cat}),
                    #prev_tag=self.getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': prev_cat})),
                mimetype='text/html')
        else:
            self.on_error(NotFound())

    def on_favicon_get(self):
        mimetype = 'image/x-icon'
        f_path = 'favicon.ico'
        l_modify = datetime.fromtimestamp(os.path.getmtime(f_path)).strftime('%a, %d %b %Y %H:%m:%S %Z%z')
        if (self.request.if_modified_since) and (self.request.if_modified_since.strftime('%a, %d %b %Y %H:%m:%S %Z%z') == l_modify):
            self.response = Response('', mimetype=mimetype)
            self.response.status_code = 304
        else:
            f = open(f_path, 'rb')
            self.response = Response(wrap_file(self.request.environ, f), mimetype=mimetype, direct_passthrough=True)
            self.response.headers['Last-Modified'] = l_modify

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
                if self.user['provider'] == 'yandex':
                    current_data = self.db.posts.find({'owner': self.user['sid'], 'read': not status, 'pid': {'$in': posts}}, fields=['links', 'tags'])
                    for d in current_data:
                        self.seconds_queue.put({'user': self.user, 'type': 'mark', 'data': {'url': d['links']['meta'], 'status': status}})
                        for t in d['tags']:
                            if t in tags:
                                tags[t] += 1
                            else:
                                tags[t] = 1
                elif (self.user['provider'] == 'bazqux') or (self.user['provider'] == 'inoreader'):
                    current_data = self.db.posts.find({'owner': self.user['sid'], 'read': not status, 'pid': {'$in': posts}}, fields=['id', 'tags'])
                    for d in current_data:
                        self.seconds_queue.put({'user': self.user, 'type': 'mark', 'data': {'id': d['id'], 'status': status}})
                        for t in d['tags']:
                            if t in tags:
                                tags[t] += 1
                            else:
                                tags[t] = 1
                bulk = self.db.tags.initialize_unordered_bulk_op()
                if status:
                    for t in tags:
                        bulk.find({'owner': self.user['sid'], 'tag': t}).update({'$inc': {'unread_count': -tags[t]}})
                        first_letters[t[0]]['unread_count'] -= tags[t]
                else:
                    for t in tags:
                        bulk.find({'owner': self.user['sid'], 'tag': t}).update({'$inc': {'unread_count': tags[t]}})
                        first_letters[t[0]]['unread_count'] += tags[t]
                try:
                    bulk.execute()
                except Exception as e:
                    print(e, 'Bulk failed')
                self.db.posts.update({'owner': self.user['sid'], 'read': not status, 'pid': {'$in': posts}}, {'$set': {'read': status}}, multi=True)
            else:
                if self.user['provider'] == 'yandex':
                    current_post = self.db.posts.find_one({'owner': self.user['sid'], 'pid': post_id}, fields=['links', 'tags'])
                    self.seconds_queue.put({'user': self.user, 'type': 'mark', 'data': {'url': current_post['links']['meta'], 'status': status}})
                elif (self.user['provider'] == 'bazqux') or (self.user['provider'] == 'inoreader'):
                    current_post = self.db.posts.find_one({'owner': self.user['sid'], 'pid': post_id}, fields=['id', 'tags'])
                    self.seconds_queue.put({'user': self.user, 'type': 'mark', 'data': {'id': current_post['id'], 'status': status}})
                    self.db.posts.update({'owner': self.user['sid'], 'pid': post_id}, {'$set': {'read': status}})
                if status:
                    incr = -1
                else:
                    incr = 1
                for t in current_post['tags']:
                    first_letters[t[0]]['unread_count'] += incr
                self.db.tags.update({'owner': self.user['sid'], 'tag': {'$in': current_post['tags']}}, {'$inc': {'unread_count': incr}}, multi=True)
            self.db.letters.update({'owner': self.user['sid']}, {'$set': {'letters': first_letters}})
            print(time.time() - st)
        self.response = Response('{{"result": "{0}"}}'.format(''.join(err)), mimetype='application/json')

    def fillFirstLetters(self):
        tmp_letters = self.db.letters.find_one({'owner': self.user['sid']})
        if tmp_letters:
            self.first_letters = getSortedDictByAlphabet(tmp_letters['letters'])
        else:
            self.first_letters = {}

    def getLetters(self):
        letters = []
        if self.user['only_unread']:
            for s_let in self.first_letters:
                if self.first_letters[s_let]['unread_count'] > 0:
                    letters.append({'letter': self.first_letters[s_let]['letter'], 'local_url': self.first_letters[s_let]['local_url']})
        else:
            for s_let in self.first_letters:
                letters.append({'letter': self.first_letters[s_let]['letter'], 'local_url': self.first_letters[s_let]['local_url']})
        return(letters)

    def calcPagerData(self, p_number, page_count, items_per_page, endpoint):
        pages_map = {}
        numbers_start_range = p_number - self.count_showed_nubmers + 1
        numbers_end_range = p_number + self.count_showed_nubmers + 1
        if numbers_start_range <= 0:
            numbers_start_range = 1
        if numbers_end_range > page_count:
            numbers_end_range = page_count + 1
        if page_count > 11:
            pages_map['middle'] = [{'p': i, 'url': self.getUrlByEndpoint(endpoint=endpoint, params={'page_number': i})} for i in range(numbers_start_range, numbers_end_range)]
            if numbers_start_range > 1:
                pages_map['start'] = [{'p': 'first', 'url': self.getUrlByEndpoint(endpoint=endpoint, params={'page_number': 1})}]
            if numbers_end_range <= (page_count):
                pages_map['end'] = [{'p': 'last', 'url': self.getUrlByEndpoint(endpoint=endpoint, params={'page_number': page_count})}]
        else:
            pages_map['start'] = [{'p': i, 'url': self.getUrlByEndpoint(endpoint=endpoint, params={'page_number': i})} for i in range(1, page_count + 1)]
        start_tags_range = ((p_number - 1) * items_per_page) + items_per_page
        end_tags_range = start_tags_range + items_per_page
        return(pages_map, start_tags_range, end_tags_range)

    def on_group_by_tags_get(self, page_number):
        self.response = None
        page = self.template_env.get_template('group-by-tag.html')
        if self.user['only_unread']:
            #cursor = self.db.tags.find({'owner': self.user['sid'], 'unread_count': {'$gt': 0}}).sort([('unread_count', DESCENDING), ('tag', ASCENDING)])
            cursor = self.db.tags.find({'owner': self.user['sid'], 'unread_count': {'$gt': 0}}).sort([('unread_count', DESCENDING)])
        else:
            #cursor = self.db.tags.find({'owner': self.user['sid']}).sort([('posts_count', DESCENDING), ('tag', ASCENDING)])
            cursor = self.db.tags.find({'owner': self.user['sid']}).sort([('posts_count', DESCENDING)])
        tags_count = cursor.count()
        page_count = self.getPageCount(tags_count, self.user['cloud_items_on_page'])

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
            pages_map, start_tags_range, end_tags_range = self.calcPagerData(p_number, page_count, self.user['cloud_items_on_page'], 'on_group_by_tags_get')
            if end_tags_range > tags_count:
                end_tags_range = tags_count
            sorted_tags = []
            load_tags = OrderedDict()
            if self.user['only_unread']:
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
                    only_unread=self.user['only_unread'],
                    provider=self.user['provider'],
                    posts_per_page=self.user['posts_on_page'],
                    tags_per_page=self.user['cloud_items_on_page']),
                mimetype='text/html'
                )
            self.db.users.update({'sid': self.user['sid']}, {'$set': {'page': new_cookie_page_value, 'letter': ''}})
        else:
            if not self.response:
                self.on_error(NotFound())

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
            if self.user['only_unread']:
                #cursor = self.db.tags.find({'owner': self.user['sid'], 'unread_count': {'$gt': 0}, 'tag': {'$regex': '^{0}'.format(let)}}).sort([('unread_count', DESCENDING), ('tag', ASCENDING)])
                cursor = self.db.tags.find({'owner': self.user['sid'], 'unread_count': {'$gt': 0}, 'tag': {'$regex': '^{0}'.format(let)}}).sort([('unread_count', DESCENDING)])
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
                    only_unread=self.user['only_unread'],
                    provider=self.user['provider'],
                    posts_per_page=self.user['posts_on_page'],
                    tags_per_page=self.user['cloud_items_on_page']),
                mimetype='text/html'
            )
            self.db.users.update({'sid': self.user['sid']}, {'$set': {'letter': let}})
        else:
            self.response = redirect(self.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number}))

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
            posts = self.db.posts.find({'owner': self.user['sid'], 'pid': {'$in': wanted_posts}}, limit=self.user['posts_on_page'])
            if not err:
                posts_content = []
                for post in posts:
                    posts_content.append({'pos': post['pid'], 'content': gzip.decompress(post['content']['content']).decode('utf-8', 'replace')})
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
            if current_post:
                result = {'result': 'ok', 'data': {'pos': post_id, 'content': gzip.decompress(current_post['content']['content']).decode('utf-8', 'replace')}}
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
            current_post = self.db.posts.find_one({'owner': self.user['sid'], 'pid': post_id}, fields=['tags', 'feed_id'])
            if current_post:
                feed = self.db.feeds.find_one({'feed_id': current_post['feed_id'], 'owner': self.user['sid']})
                if feed:
                    result = {'result': 'ok', 'data': {'c_url': feed['category_local_url'], 'c_title': feed['category_title'], 'f_url': feed['local_url'], 'f_title': feed['title'], 'tags': []}}
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
        if self.user['only_unread']:
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
            tags = s_tags.split('+')
            if tags:
                result = {}
                query = {'owner': self.user['sid'], 'tag': {'$in': tags}}
                tags_cursor = self.db.tags.find(query, {'_id': 0, 'tag': 1, 'words': 1})
                for tag in tags_cursor:
                    result[tag['tag']] = {'words': ','.join(tag['words']), 'posts': []}

                query = {'owner': self.user['sid'], 'tags': {'$in': tags}}
                if self.user['only_unread']:
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
                else:
                    back_link = self.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number})
                page = self.template_env.get_template('tags-posts.html')
                self.response = Response(page.render(
                    tags=result,
                    selected_tags=','.join(tags),
                    back_link=back_link, group='tag',
                    only_unread=self.user['only_unread'],
                    provider=self.user['provider'],
                    posts_per_page=self.user['posts_on_page'],
                    tags_per_page=self.user['cloud_items_on_page']),
                mimetype='text/html')
        else:
            self.response = redirect(self.getUrlByEndpoint('on_root_get'))

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
        print('Start downloading, ', data['category'])
    except Exception as e:
        print('Start downloading, category with strange symbols')
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
            tmp_result = json.loads(json_data.decode('utf-8'))
            if 'continuation' not in tmp_result:
                again = False
                result['items'].extend(tmp_result['items'])
            else:
                result['items'].extend(tmp_result['items'])
                url = data['url'] + '&c={0}'.format(tmp_result['continuation'])
        except Exception as e:
            print(e, data['category'], counter_for_downloads, url)
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
        print('Downloaded, ', data['category'])
    except Exception as e:
        print('Downloaded, category with strange symbols')
    return(result, data['category'])

def downloader_yandex(data):
    try:
        print('Start downloading, ', data['title'])
    except Exception as e:
        print('Start downloading, category with strange symbols')
    result = {'posts' : []}
    connection = client.HTTPSConnection(data['host'])
    '''if data['title'] == 'Kz':
        posts = {'navigation': {'next' : ''.join([data['url'], '&format=json'])}}
    else:'''
    posts = {'navigation': {'next' : data['url']}}
    counter_for_downloads = 0
    counter_for_parse = 0
    while posts['navigation'].get('next') is not None:
        try:
            '''f = open('log/{0}_urls'.format(data['title']), 'a')
            f.write(''.join([posts['navigation']['next'], '&format=json', '\n']))
            f.close()'''
            '''if data['title'] == 'Kz':
                connection.request('GET', posts['navigation']['next'], '', data['headers'])
            else:    '''
            connection.request('GET', ''.join([posts['navigation']['next'], '&format=json']), '', data['headers'])
            resp = connection.getresponse()
            json_data = resp.read()
            if data['title'] == 'Kz':
                f = open('log/{0}_urlsy'.format(data['title']), 'a')
                f.write('{0}\r\n{1}\r\n'.format(posts['navigation']['next'], json_data.decode('utf-8', 'ignore')))
                f.close()
        except Exception as e:
            if counter_for_downloads >= 10:
                posts = {'navigation': {'next' : None}}
                counter_for_downloads = 0
            else:
                counter_for_downloads += 1
            print(e, data['title'], posts['navigation'].get('next'), counter_for_downloads)
            time.sleep(2)
            continue
        try:
            posts = json.loads(json_data.decode('utf-8', 'ignore'))
        except Exception as e:
            if counter_for_parse >= 5:
                posts = {'navigation': {'next' : None}}
                counter_for_parse = 0
            else:
                counter_for_parse += 1
            f = open('log/{0}_jsonfuckedup'.format(data['title']), 'a')
            f.write(json_data.decode('utf-8', 'ignore'))
            f.close()
            f = open('log/{0}_urls'.format(data['title']), 'a')
            f.write(json_data.decode('utf-8', 'ignore'))
            f.close()
            print(e, data['title'], 'parse error', counter_for_parse, posts['navigation'].get('next'))
            time.sleep(2)
            continue
        result['posts'].extend(posts['posts'])
    connection.close()
    if not result['posts']:
        result = None
    try:
        print('Downloaded, ', data['title'])
    except Exception as e:
        print('Downloaded, category with strange symbols')
    return(result, data['title'])

def worker(firsts, seconds, firsts_lock, seconds_lock, config):
    name = str(randint(0, 10000))
    no_category_name = 'NotCategorized'
    workers_downloader_pool = []
    title_clearing = re.compile(config['settings']['replacement'])
    only_cyrillic = re.compile(r'^[а-яА-ЯёЁ]*$')
    only_latin = re.compile(r'^[a-zA-Z]*$')
    clear_html_esc = re.compile(r'&[#a-zA-Z0-9]*?;')
    latin = PorterStemmer()
    cyrillic = pymorphy2.MorphAnalyzer()
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
            print('treating', category)
        except Exception as e:
            print('treating category with strange symbols')
        for pos in range(p_range[0], p_range[1]):
            if not all_posts[pos]['content']['title']:
                all_posts[pos]['content']['title'] = 'Notitle'
            all_posts[pos]['owner'] = user['sid']
            all_posts[pos]['category_id'] = category
            all_posts[pos]['tags'] = []
            all_posts[pos]['pid'] = pos
            all_posts[pos]['createdAt'] = datetime.utcnow()
            title = all_posts[pos]['content']['title']
            title = clear_html_esc.sub(' ', title)
            title = title_clearing.sub(' ', title)
            title = title.strip()
            words = title.split()
            for current_word in words:
                current_word = current_word.strip().lower()
                word_length = len(current_word)
                tag = ''
                if only_cyrillic.match(current_word):
                    temp = cyrillic.parse(current_word)
                    if temp:
                        for pw in temp:
                            if pw.normal_form in by_tag['tags']:
                                tag = pw.normal_form
                                break
                        if tag == '':
                            tag = temp[0].normal_form
                    else:
                        tag = current_word
                elif only_latin.match(current_word):
                    tag = latin.stem(current_word)
                elif current_word.isnumeric or word_length < 4:
                    tag = current_word
                elif word_length == 4 or word_length == 5:
                    tag = current_word[:-1]
                elif word_length == 6:
                    tag = current_word[:-2]
                else:
                    tag = current_word[:-3]
                if tag:
                    if tag[0] not in first_letters:
                        first_letters[tag[0]] = {'letter': tag[0], 'local_url': getUrlByEndpoint(endpoint='on_group_by_tags_startwith_get', params={'letter': tag[0]}), 'unread_count': 0}
                    if tag not in by_tag['tags']:
                        by_tag['unread_count'] += 1
                        by_tag['tags'][tag] =  {'words': [], 'local_url': tag, 'read': False, 'tag': tag, 'owner': user['sid'], 'posts': set()} #'posts': set(), 'read_posts': set(),
                    if current_word not in by_tag['tags'][tag]['words']:
                        by_tag['tags'][tag]['words'].append(current_word)
                    by_tag['tags'][tag]['posts'].add(pos)
                    if tag not in all_posts[pos]['tags']:
                        all_posts[pos]['tags'].append(tag)
        try:
            print('treated', category)
        except Exception as e:
            print('treated category with strange symbols')
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
                db.posts.insert(all_posts)
                db.feeds.insert(by_feed.values())
                db.tags.insert(tags_list)
                db.letters.insert({'owner': user['sid'], 'letters': first_letters, 'createdAt': datetime.utcnow()})
                db.users.update({'sid': user['sid']}, {'$set': {'ready_flag': True, 'in_queue': False, 'message': 'You can start reading', 'createdAt': datetime.utcnow()}})
            except Exception as e:
                print(e, 'Can`t save all data')
                db.users.update({'sid': user['sid']}, {'$set': {'ready_flag': False, 'in_queue': False, 'message': 'Can`t save to database, please try later', 'createdAt': datetime.utcnow()}})
            print('saved all-', time.time() - st, len(tags_list), len(all_posts), len(by_feed))
        else:
            db.users.update({'sid': user['sid']}, {'$set': {'ready_flag': True, 'in_queue': False, 'message': 'You can start reading'}})
            print('Nothing to save')

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
        #st = time.time()
        firsts_lock.acquire()
        try:
            if not firsts.empty():
                data = firsts.get()
        finally:
            firsts_lock.release()
        if not data:
            seconds_lock.acquire()
            try:
                if not seconds.empty():
                    data = seconds.get()
            finally:
                seconds_lock.release()
        if data:
            user = data['user']
            type = data['type']
        else:
            #print('Tasks list is empy.', name, 'going sleep')
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
            routes = data['data']['routes']
            host = data['data']['host']
            if user['provider'] == 'yandex':
                headers = {'AUTHORIZATION': 'OAuth {0}'.format(user['token'])}
                connection = client.HTTPSConnection(config['yandex']['api_host'])
                connection.request('GET', '/subscriptions?format=json', '', headers)
                resp = connection.getresponse()
                json_data = resp.read()
                connection.close()
                subscriptions = json.loads(json_data.decode('utf-8'))
                works = []
                for i, g in enumerate(subscriptions['groups']):
                    if int(g['unread_count']) > 0:
                        '''if i == 3:
                            break'''
                        for f in g['feeds']:
                            if int(f['unread_count']) > 0:
                                by_feed[f['md5']] = {}
                                by_feed[f['md5']]['category_title'] = g['title']
                                by_feed[f['md5']]['category_id'] = g['title']
                                by_feed[f['md5']]['category_local_url'] = getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': g['title']})
                                by_feed[f['md5']]['feed_id'] = f['md5']
                                by_feed[f['md5']]['title'] = f['title']
                                by_feed[f['md5']]['owner'] = user['sid']
                                by_feed[f['md5']]['favicon'] = f['links']['links']['favicon'] if f['links']['links'].get('favicon') else None
                                by_feed[f['md5']]['local_url'] = getUrlByEndpoint(endpoint='on_feed_get', params={'quoted_feed': f['md5']})
                        works.append({'host': config['yandex']['api_host'], 'url': '/posts?items_per_page=100&read_status=unread&group_id={0}'.format(g['group_id']), 'headers': headers, 'title': g['title']})
                if subscriptions['feeds']:
                    for f in subscriptions['feeds']:
                        if int(f['unread_count']) > 0:
                            by_feed[f['md5']] = {}
                            by_feed[f['md5']]['createdAt'] = datetime.utcnow()
                            by_feed[f['md5']]['category_title'] = no_category_name
                            by_feed[f['md5']]['category_id'] = no_category_name
                            by_feed[f['md5']]['category_local_url'] = getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': no_category_name})
                            by_feed[f['md5']]['feed_id'] = f['md5']
                            by_feed[f['md5']]['title'] = f['title']
                            by_feed[f['md5']]['owner'] = user['sid']
                            by_feed[f['md5']]['favicon'] =  f['links']['links']['favicon'] if f['links']['links'].get('favicon') else None
                            by_feed[f['md5']]['local_url'] = getUrlByEndpoint(endpoint='on_feed_get', params={'quoted_feed': f['md5']})
                            works.append({'host': config['yandex']['api_host'], 'url': '/posts?items_per_page=100&read_status=unread&md5={0}'.format(f['md5']), 'headers': headers, 'title': no_category_name})
                workers_downloader_pool = Pool(int(config['settings']['workers_count']))
                posts = None
                cateegory = None
                for posts, category in workers_downloader_pool.imap(downloader_yandex, works, 1):
                    if posts:
                        old_count = len(all_posts)
                        p_range = (old_count, old_count + len(posts['posts']))
                        for i, p in enumerate(posts['posts']):
                            posts['posts'][i]['content']['content'] = gzip.compress(posts['posts'][i]['content']['content'].encode('utf-8', 'replace'))
                            if p.get('issued'):
                                dt = datetime.strptime(p['issued'], '%Y-%m-%dT%XZ')
                                posts['posts'][i]['date'] = dt.strftime('%x %X')
                                posts['posts'][i]['unix_date'] = dt.timestamp()
                            else:
                                posts['posts'][i]['date'] = -1
                                posts['posts'][i]['unix_date'] = -1
                        all_posts.extend(posts['posts'])
                        start = p_range[0]
                        st = time.strftime('%X', time.localtime())
                        treatPosts(category, p_range)
                        print(p_range, st, time.strftime('%X', time.localtime()), category)
                workers_downloader_pool.terminate()
            elif (user['provider'] == 'bazqux') or (user['provider'] == 'inoreader'):
                connection = client.HTTPSConnection(config[user['provider']]['api_host'])
                headers = {'Authorization': 'GoogleLogin auth={0}'.format(user['token'])}
                connection.request('GET', '/reader/api/0/subscription/list?output=json', '', headers)
                resp = connection.getresponse()
                json_data = resp.read()
                subscriptions = json.loads(json_data.decode('utf-8'))
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
                        works.append({'headers': headers, 'host': config[user['provider']]['api_host'], 'url': '/reader/api/0/stream/contents?s={0}&xt=user/-/state/com.google/read&n=5000&output=json'.format(quote_plus(feed['id'])), 'category': category_name})
                    if category_name not in by_category:
                        by_category[category_name] = True
                        if category_name != no_category_name:
                            works.append({'headers': headers, 'host': config[user['provider']]['api_host'], 'url': '/reader/api/0/stream/contents?s=user/-/label/{0}&xt=user/-/state/com.google/read&n=1000&output=json'.format(quote_plus(category_name)), 'category': category_name})
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
                                by_feed[post['origin']['streamId']] = {}
                                by_feed[post['origin']['streamId']]['createdAt'] = datetime.utcnow()
                                by_feed[post['origin']['streamId']]['title'] = post['origin']['title']
                                by_feed[post['origin']['streamId']]['owner'] = user['sid']
                                by_feed[post['origin']['streamId']]['category_id'] = category
                                #by_feed[post['origin']['streamId']]['timestamp'] =
                                by_feed[post['origin']['streamId']]['feed_id'] = post['origin']['streamId']
                                by_feed[post['origin']['streamId']]['origin_feed_id'] = origin_feed_id
                                by_feed[post['origin']['streamId']]['category_title'] = category
                                by_feed[post['origin']['streamId']]['category_local_url'] = getUrlByEndpoint(endpoint='on_category_get', params={'quoted_category': category})
                                by_feed[post['origin']['streamId']]['local_url'] = getUrlByEndpoint(endpoint='on_feed_get', params={'quoted_feed': post['origin']['streamId']})
                            p_date = None
                            if 'published' in post:
                                p_date = date.fromtimestamp(int(post['published'])).strftime('%x')
                                pu_date = float(post['published'])
                            else:
                                p_date = -1
                                pu_date = -1
                            all_posts.append({
                                #'category_id': category,
                                'content': {'title': post['title'], 'content': gzip.compress(post['summary']['content'].encode('utf-8', 'replace'))},
                                'feed_id': post['origin']['streamId'],
                                'id': post['id'],
                                'url': post['canonical'][0]['href'] if post['canonical'] else 'http://ya.ru',
                                'date': p_date,
                                'unix_date': pu_date,
                                'read': False,
                                'favorite': False
                                #'meta': '/reader/api/0/edit-tag?output=json&i={0}'.format(post['id'])
                            })
                            if 'favicon' not in by_feed[post['origin']['streamId']]:
                                if all_posts[-1]['url']:
                                    #by_feed[post['origin']['streamId']]['favicon'] = all_posts[-1]['url']
                                    #favicon_works.append((all_posts[-1]['url'], post['origin']['streamId'], favicon_url_re))'''
                                    parsed_url = urlparse(all_posts[-1]['url'])
                                    by_feed[post['origin']['streamId']]['favicon'] = '{0}://{1}/favicon.ico'.format(parsed_url.scheme if parsed_url.scheme else 'http', parsed_url.netloc)
                                    #by_feed[post['origin']['streamId']]['favicon'] = getFaviconUrl(all_posts[-1]['url'])
                        treatPosts(category, p_range)
                workers_downloader_pool.terminate()
                #loaded_data = workers_downloader_pool.map(getFaviconUrl, favicon_works)
                '''favicon_works = []
                for f in by_feed:
                    favicon_works.append((by_feed[f]['favicon'], f, favicon_url_re))
                for url, feed_id in workers_downloader_pool.imap(getFaviconUrl, favicon_works, 2):
                    if url:
                        by_feed[feed_id]['favicon'] = url
                    else:
                        by_feed[feed_id]['favicon'] = 'http://ya.ru/favicon.ico'
                #del favicon_works
                workers_downloader_pool.terminate()'''
            by_tag = getSortedDictByAlphabet(by_tag)
            #first_letters = getSortedDictByAlphabet(first_letters)
            '''user['ready_flag'] = True
            user['in_queue'] = False
            user['message'] = 'You can start reading'''
            saveAllData()
        elif type == 'mark':
            status = data['data']['status']
            if user['provider'] == 'yandex':
                headers = {'AUTHORIZATION': 'OAuth {0}'.format(user['token'])}
                err = []
                url = data['data']['url']
                counter = 0
                while (counter < 6):
                    connection = client.HTTPSConnection(config[user['provider']]['api_host'])
                    counter += 1
                    try:
                        xml_data = None
                        connection.request('GET', url, '', headers)
                        resp = connection.getresponse()
                        xml_data = resp.read()
                    except Exception as e:
                        connection.close()
                        connection = client.HTTPSConnection(config[user['provider']]['api_host'])
                        print(e, 'can not GET meta info', url, xml_data, e.args)
                        err.append(str(e))
                    if not err:
                        try:
                            post_meta = parseString(xml_data)
                        except Exception as e:
                            print(e, 'can not parse data')
                            err.append(str(e))
                        if not err:
                            try:
                                if status and (len(post_meta.getElementsByTagName('read')) == 0):
                                    r = post_meta.createElement('read')
                                    post_meta.getElementsByTagName('post')[0].appendChild(r)
                                elif not status and (len(post_meta.getElementsByTagName('read')) > 0):
                                    post_meta.getElementsByTagName('post')[0].removeChild(post_meta.getElementsByTagName('read')[0])
                            except Exception as e:
                                print(e, 'can not working with xml')
                                err.append(str(e))
                            if not err:
                                try:
                                    connection.close()
                                    connection = client.HTTPSConnection(config[user['provider']]['api_host'])
                                    connection.request('PUT', url, post_meta.toxml(), headers)
                                    resp = connection.getresponse()
                                    xml_data = resp.read()
                                except Exception as e:
                                    print(e, 'can not put meta info to server')
                                    err.append(str(e))
                                if not err:
                                    try:
                                        result_dom = parseString(xml_data)
                                    except Exception as e:
                                        print(e, 'can not parse response after putting data')
                                        err.append(str(e))
                                    if not err:
                                        if len(result_dom.getElementsByTagName('ok')) == 0:
                                            err.append(xml_data.decode('utf-8', 'ignore'))
                                            print(err, 'try again', counter)
                                            time.sleep(randint(2, 7))
                                        else:
                                            counter = 6
                                            #print('marked', name)
                                            post_meta.unlink()
                                            result_dom.unlink()
                connection.close()
            elif (user['provider'] == 'bazqux') or (user['provider'] == 'inoreader'):
                id = data['data']['id']
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
                        print('Can`t make request', e, counter)
                    if not err:
                        if resp_data.decode('utf-8').lower() == 'ok':
                            #print('marked')
                            counter = 6
                        else:
                            time.sleep(randint(2, 7))
                            if counter < 6 :
                                print('try again')
                            else:
                                print('not marked', resp_data)
                connection.close()

def getFaviconUrl(data):
    parsed_url = urlparse(data[0])
    host = parsed_url.netloc
    url = '/favicon.ico'
    root_url = '/'
    favicon_url = None
    c = client.HTTPConnection(host, timeout=3)
    c.request('HEAD', url)
    r = c.getresponse()
    favicon_url = None
    new_host = None
    #print(r.status, host)
    #print('search favicon for', host)
    if r.status != 200:
        favicon_url = None
        #print('try get from page', host)
        c.close()
        c = client.HTTPConnection(host, timeout=3)
        c.request('GET', root_url)
        r = c.getresponse()
        if r.status == 301:
            c.close()
            new_host = urlparse(r.getheader('Location')).netloc
            #print('redirected', new_host)
            c = client.HTTPConnection(new_host, timeout=3)
            c.request('HEAD', url)
            r = c.getresponse()
            if r.status == 200:
                #print('found on redirect root')
                favicon_url = 'http://{0}{1}'.format(new_host, url)
            else:
                c.close()
                #print('try get from redirected page')
                c = client.HTTPConnection(new_host, timeout=3)
                c.request('GET', root_url)
                r = c.getresponse()
        if not favicon_url:
            if r.status == 200:
                page = r.read()
                #print('parse page')
                result = data[2].search(page.decode('utf-8', 'ignore'))
                #print('page parsed')
                if result:
                    favicon_url = result.group(1)
                    parsed_url = urlparse(favicon_url)
                    if (not parsed_url.scheme) or (not parsed_url.netloc):
                        if parsed_url.netloc:
                            h = parsed_url.netloc
                        elif new_host:
                            h = new_host
                        else:
                            h = host
                        favicon_url = 'http://{0}/{1}'.format(h, parsed_url.path)
                else:
                    #print('not found on page')
                    favicon_url = None
            else:
                #print('page not found')
                favicon_url = None
    else:
        #print('all ok')
        favicon_url = 'http://{0}{1}'.format(host, url)
    c.close()
    '''if favicon_url:
        print('Found', favicon_url)
    else:
        print('Not found', url)'''
    return(favicon_url, data[1])

if __name__ == '__main__':
    app = RSSCloudApplication('rsscloud.conf')
    run_simple(app.config['settings']['host'], int(app.config['settings']['port']), app.setResponse)
    app.close()
    print('Goodbye!')
    '''TODO
        offline mode
        settings: posts on page, tags on page, provider
        mark as read page, feed, category
        reader.aol.com
        feedly
        digg.com
    '''