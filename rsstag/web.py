import os
import json
from urllib.parse import unquote_plus, urlencode, unquote, quote_plus
from http import client
import html
import time
import gzip
import logging
from collections import OrderedDict, defaultdict
from hashlib import md5
from werkzeug.wrappers import Response, Request
from werkzeug.exceptions import HTTPException, NotFound, InternalServerError
from werkzeug.utils import redirect
from jinja2 import Environment, PackageLoader
from pymongo import MongoClient
from gensim.models.doc2vec import Doc2Vec
from gensim.models.word2vec import Word2Vec
from rsstag import TASK_NOT_IN_PROCESSING
from rsstag.routes import RSSTagRoutes
from rsstag.utils import getSortedDictByAlphabet, load_config, to_dot_format
from rsstag.posts import RssTagPosts
from rsstag.feeds import RssTagFeeds
from rsstag.tags import RssTagTags
from rsstag.letters import RssTagLetters
from rsstag.bi_grams import RssTagBiGrams
from rsstag.users import RssTagUsers
from rsstag.providers import BazquxProvider

class RSSTagApplication(object):
    request = None
    response = None
    template_env = None
    routes = None
    endpoints = {}
    user = {}
    config = None
    config_path = None
    providers = []
    user_ttl = 0
    count_showed_numbers = 4
    need_cookie_update = False
    d2v = None
    w2v = None
    models = {'d2v': 'd2v', 'w2v': 'w2v'}
    allow_not_logged = (
        'on_root_get',
        'on_login_get',
        'on_login_post',
        'on_select_provider_post',
        'on_select_provider_get',
        'on_ready_get',
        'on_refresh_get_post'
    )
    no_category_name = 'NotCategorized'

    def __init__(self, config_path=None):
        self.config = load_config(config_path)
        if self.config['settings']['no_category_name']:
            self.no_category_name = self.config['settings']['no_category_name']
        if os.path.exists(self.config['settings']['d2v_model']):
            self.d2v = Doc2Vec.load(self.config['settings']['d2v_model'])
        if os.path.exists(self.config['settings']['w2v_model']):
            self.w2v = Word2Vec.load(self.config['settings']['w2v_model'])

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
        self.template_env.filters['url_encode'] = quote_plus
        self.providers = self.config['settings']['providers'].split(',')
        self.user_ttl = int(self.config['settings']['user_ttl'])
        cl = MongoClient(self.config['settings']['db_host'], int(self.config['settings']['db_port']))
        self.db = cl[self.config['settings']['db_name']]
        self.posts = RssTagPosts(self.db)
        self.posts.prepare()
        self.feeds = RssTagFeeds(self.db)
        self.feeds.prepare()
        self.tags = RssTagTags(self.db)
        self.tags.prepare()
        self.letters = RssTagLetters(self.db)
        self.letters.prepare()
        self.bi_grams = RssTagBiGrams(self.db)
        self.bi_grams.prepare()
        self.users = RssTagUsers(self.db)
        self.users.prepare()
        self.routes = RSSTagRoutes(self.config['settings']['host_name'])
        self.updateEndpoints()

    def prepareDB(self):
        try:
            self.db.download_queue.create_index('processing')
            self.db.mark_queue.create_index('processing')
            self.db.words.create_index('word')
        except Exception as e:
            logging.warning('Indexes not created. May be already exists.')

    def close(self):
        logging.info('Goodbye!')

    def updateEndpoints(self):
        routes = self.routes.get_werkzeug_routes()
        for i in routes.iter_rules():
            self.endpoints[i.endpoint] = getattr(self, i.endpoint)

    def prepareSession(self, user=None):
        if user is None:
            sid = self.request.cookies.get('sid')
            if sid:
                self.user = self.users.get_by_sid(sid)
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

    def createNewSession(self, login: str, password: str, token: str, provider: str):
        self.need_cookie_update = True
        sid = self.users.create_user(login, password, token, provider)
        self.user = self.users.get_by_sid(sid)

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
            if self.user and self.user['ready']:
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
            post = self.posts.get_by_pid(self.user['sid'], post_id)
            if post:
                title = html.unescape(post['content']['title'])
                speech_file = self.getSpeech(title)
                if speech_file:
                    result = {'data': '/static/speech/{}'.format(speech_file)}
                else:
                    result = {'error': 'Can`t get speech file'}
                    code = 503
            elif post is None:
                result = {'error': 'Database trouble'}
                code = 500
            else:
                result = {'error': 'Post not found'}
                code = 404
        else:
            result = {'error': 'No post id'}
            code = 400

        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

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
            user = self.users.get_by_login_password(login, password)
            if user:
                self.prepareSession(user)
                self.response = redirect(self.routes.getUrlByEndpoint(endpoint='on_root_get'))
                return ''
            elif user is not None:
                if self.user:
                    self.user['provider'] = self.request.cookies.get('provider')
                else:
                    self.user = {'provider': self.request.cookies.get('provider')}
                if (self.user['provider'] == 'bazqux') or (self.user['provider'] == 'inoreader'):
                    provider = BazquxProvider(self.config)
                    token = provider.get_token(login, password)
                    if token:
                        self.user['token'] = token
                        self.createNewSession(login, password, token, self.user['provider'])
                    elif token == '':
                        err.append('Wrong login or password')
                    else:
                        err.append('Cant` create session. Try later')
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
            try:
                if not self.user['in_queue']:
                    self.db.download_queue.insert_one(
                        {'user': self.user['_id'], 'processing': TASK_NOT_IN_PROCESSING, 'host': self.request.environ['HTTP_HOST']}
                    )
                    updated = self.users.update_by_sid(
                        self.user['sid'],
                        {'ready': False, 'in_queue': True, 'message': 'Downloading data, please wait'}
                    )
                else:
                    updated = self.users.update_by_sid(
                        self.user['sid'],
                        {'message': 'You already in queue, please wait'}
                    )
                if not updated:
                    logging.error('Cant update data of user %s while create "posts update" task', self.user['_id'])
            except Exception as e:
                logging.error('Can`t create refresh task for user %s. Info: %s', self.user['_id'], e)
            self.response = redirect(self.routes.getUrlByEndpoint(endpoint='on_root_get'))
        else:
            self.response = redirect(self.routes.getUrlByEndpoint(endpoint='on_root_get'))

    def on_ready_get(self):
        if self.user:
            result = {
                'ready': self.user['ready'],
                'message': self.user['message']
            }
        else:
            result = {
                'ready': False,
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
                settings = self.users.get_validated_settings(settings)
                if settings:
                    updated = self.users.update_settings(self.user['sid'], settings)
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
                result = {'error': 'Not logged'}
                code = 401
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
            stat = self.posts.get_stat(self.user['sid'])
            if stat:
                posts = stat
            else:
                posts = {'unread': 0, 'read': 0}
            sentiments = self.tags.get_sentiments(self.user['sid'], self.user['settings']['only_unread'])
            if sentiments is None:
                sentiments = tuple()
            page = self.template_env.get_template('root-logged.html')
            self.response = Response(
                page.render(
                    err=err,
                    support=self.config['settings']['support'],
                    version=self.config['settings']['version'],
                    user_settings=self.user['settings'],
                    provider=self.user['provider'],
                    posts=posts,
                    sentiments=sentiments
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
        db_feeds = self.feeds.get_all(self.user['sid'])
        if db_feeds is not None:
            for f in db_feeds:
                by_feed[f['feed_id']] = f
            if self.user['settings']['only_unread']:
                only_unread = self.user['settings']['only_unread']
            else:
                only_unread = None
            grouped = self.posts.get_grouped_stat(self.user['sid'], only_unread)
            if grouped is not None:
                by_category = {self.feeds.all_feeds: {
                    'unread_count': 0,
                    'title': self.feeds.all_feeds,
                    'url': self.routes.getUrlByEndpoint(
                        endpoint='on_category_get',
                        params={'quoted_category': self.feeds.all_feeds}
                    ),
                    'feeds': []
                }}
                for g in grouped:
                    if g['count'] > 0:
                        if g['category_id'] not in by_category:
                            by_category[g['category_id']] = {
                                'unread_count': 0,
                                'title': by_feed[g['_id']]['category_title'],
                                'url': by_feed[g['_id']]['category_local_url'], 'feeds': []
                            }
                        by_category[g['category_id']]['unread_count'] += g['count']
                        by_category[self.feeds.all_feeds]['unread_count'] += g['count']
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
                        group_by_link=self.routes.getUrlByEndpoint(endpoint='on_group_by_tags_get',
                                                                   params={'page_number': page_number}),
                        user_settings=self.user['settings'],
                        provider=self.user['provider'],
                    ),
                    mimetype='text/html'
                )
            else:
                self.on_error(InternalServerError())
        else:
            self.on_error(InternalServerError())

    def on_category_get(self, quoted_category=None):
        cat = unquote_plus(quoted_category)
        db_feeds = self.feeds.get_by_category(self.user['sid'], cat)
        if db_feeds:
            by_feed = {}
            for f in db_feeds:
                by_feed[f['feed_id']] = f
            projection = {'_id': False, 'content.content': False}
            if self.user['settings']['only_unread']:
                only_unread = self.user['settings']['only_unread']
            else:
                only_unread = None
            if cat != self.feeds.all_feeds:
                db_posts = self.posts.get_by_category(self.user['sid'], only_unread, cat, projection)
            else:
                db_posts = self.posts.get_all(self.user['sid'], only_unread, projection)
            if db_posts is not None:
                if self.user['settings']['similar_posts']:
                    clusters = self.posts.get_clusters(db_posts)
                    if clusters:
                        cl_posts = self.posts.get_by_clusters(self.user['sid'], list(clusters), only_unread, projection)
                        if cl_posts:
                            for post in cl_posts:
                                if post['feed_id'] not in by_feed:
                                    feed = self.feeds.get_by_feed_id(self.user['sid'], post['feed_id'])
                                    if feed:
                                        by_feed[post['feed_id']] = feed
                            db_posts.extend(cl_posts)
                posts = []
                pids = set()
                for post in db_posts:
                    if post['pid'] not in pids:
                        pids.add(post['pid'])
                        if post['feed_id'] in by_feed:
                            posts.append({
                                'post': post,
                                'pos': post['pid'],
                                'category_title': by_feed[post['feed_id']]['category_title'],
                                'feed_title': by_feed[post['feed_id']]['title'],
                                'favicon': by_feed[post['feed_id']]['favicon']
                            })
                page = self.template_env.get_template('posts.html')
                self.response = Response(
                    page.render(
                        posts=posts,
                        tag=cat,
                        back_link=self.routes.getUrlByEndpoint(endpoint='on_group_by_category_get'),
                        group='category',
                        words=[],
                        user_settings=self.user['settings'],
                        provider=self.user['provider']
                    ),
                    mimetype='text/html'
                )
            else:
                self.on_error(InternalServerError())
        elif db_feeds is None:
            self.on_error(InternalServerError())
        else:
            self.on_error(NotFound())

    def on_tag_get(self, quoted_tag=None):
        page_number = self.user['page']
        letter = self.user['letter']
        tmp_letters = self.letters.get(self.user['sid'])
        if not page_number:
            page_number = 1
        if tmp_letters and letter and letter in tmp_letters['letters']:
            back_link = self.routes.getUrlByEndpoint(
                endpoint='on_group_by_tags_startwith_get',
                params={'letter': letter, 'page_number': page_number}
            )
        else:
            back_link = self.routes.getUrlByEndpoint(endpoint='on_group_by_tags_get', params={'page_number': page_number})
        tag = unquote(quoted_tag)
        current_tag = self.tags.get_by_tag(self.user['sid'], tag)
        if current_tag:
            projection = {'_id': False, 'content.content': False}
            if self.user['settings']['only_unread']:
                only_unread = self.user['settings']['only_unread']
            else:
                only_unread = None
            db_posts = self.posts.get_by_tags(self.user['sid'], [tag], only_unread, projection)
            if db_posts is not None:
                if self.user['settings']['similar_posts']:
                    clusters = self.posts.get_clusters(db_posts)
                    if clusters:
                        cl_posts = self.posts.get_by_clusters(self.user['sid'], list(clusters), only_unread, projection)
                        if cl_posts:
                            db_posts.extend(cl_posts)
                posts = []
                by_feed = {}
                pids = set()
                for post in db_posts:
                    if post['pid'] not in pids:
                        pids.add(post['pid'])
                        if post['feed_id'] not in by_feed:
                            feed = self.feeds.get_by_feed_id(self.user['sid'], post['feed_id'])
                            if feed:
                                by_feed[post['feed_id']] = feed
                        if post['feed_id']in by_feed:
                            posts.append({
                                'post': post,
                                'pos': post['pid'],
                                'category_title': by_feed[post['feed_id']]['category_title'],
                                'feed_title': by_feed[post['feed_id']]['title'],
                                'favicon': by_feed[post['feed_id']]['favicon']
                            })
                page = self.template_env.get_template('posts.html')
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
                self.on_error(InternalServerError())
        elif current_tag is None:
            self.on_error(InternalServerError())
        else:
            self.on_error(NotFound())

    def on_bi_gram_get(self, bi_gram=''):
        current_bi_gram = self.bi_grams.get_by_bi_gram(self.user['sid'], bi_gram)
        if current_bi_gram:
            projection = {'_id': False, 'content.content': False}
            if self.user['settings']['only_unread']:
                only_unread = self.user['settings']['only_unread']
            else:
                only_unread = None
            db_posts = self.posts.get_by_bi_grams(self.user['sid'], [bi_gram], only_unread, projection)
            if db_posts is not None:
                if self.user['settings']['similar_posts']:
                    clusters = self.posts.get_clusters(db_posts)
                    if clusters:
                        cl_posts = self.posts.get_by_clusters(self.user['sid'], list(clusters), only_unread, projection)
                        if cl_posts:
                            db_posts.extend(cl_posts)
                posts = []
                by_feed = {}
                pids = set()
                for post in db_posts:
                    if post['pid'] not in pids:
                        pids.add(post['pid'])
                        if post['feed_id'] not in by_feed:
                            feed = self.feeds.get_by_feed_id(self.user['sid'], post['feed_id'])
                            if feed:
                                by_feed[post['feed_id']] = feed
                        if post['feed_id'] in by_feed:
                            posts.append({
                                'post': post,
                                'pos': post['pid'],
                                'category_title': by_feed[post['feed_id']]['category_title'],
                                'feed_title': by_feed[post['feed_id']]['title'],
                                'favicon': by_feed[post['feed_id']]['favicon']
                            })
                page = self.template_env.get_template('posts.html')
                if self.request.referrer:
                    back_link = self.request.referrer
                else:
                    back_link = '/'
                self.response = Response(
                    page.render(
                        posts=posts,
                        tag=bi_gram,
                        back_link=back_link,
                        group='tag',
                        words=current_bi_gram['words'],
                        user_settings=self.user['settings'],
                        provider=self.user['provider']
                    ),
                    mimetype='text/html'
                )
            else:
                self.on_error(InternalServerError())
        elif current_bi_gram is None:
            self.on_error(InternalServerError())
        else:
            self.on_error(NotFound())

    def on_feed_get(self, quoted_feed=None):
        feed = unquote_plus(quoted_feed)
        current_feed = self.feeds.get_by_feed_id(self.user['sid'], feed)
        projection = {'_id': False, 'content.content': False}
        if current_feed is not None:
            if self.user['settings']['only_unread']:
                only_unread = self.user['settings']['only_unread']
            else:
                only_unread = None
            db_posts = self.posts.get_by_feed_id(
                self.user['sid'],
                current_feed['feed_id'],
                only_unread,
                projection
            )
            if db_posts is not None:
                posts = []
                if self.user['settings']['similar_posts']:
                    clusters = self.posts.get_clusters(db_posts)
                    if clusters:
                        cl_posts = self.posts.get_by_clusters(self.user['sid'], list(clusters), only_unread, projection)
                        if cl_posts:
                            db_posts.extend(cl_posts)
                pids = set()
                for post in db_posts:
                    if post['pid'] not in pids:
                        pids.add(post['pid'])
                        posts.append({
                            'post': post,
                            'category_title': current_feed['category_title'],
                            'pos': post['pid'],
                            'feed_title': current_feed['title'],
                            'favicon': current_feed['favicon']
                        })
                page = self.template_env.get_template('posts.html')
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
                self.on_error(InternalServerError())
        elif current_feed is None:
            self.on_error(InternalServerError())
        else:
            self.on_error(NotFound())

    def on_read_posts_post(self):
        try:
            data = json.loads(self.request.get_data(as_text=True))
            if data['ids'] and isinstance(data['ids'], list):
                post_ids = data['ids']
            else:
                raise Exception('Bad ids for posts status')
            readed = bool(data['readed'])
        except Exception as e:
            logging.warning('Send wrond data for read posts. Cause: %s', e)
            post_ids = None
            result = {'error': 'Bad ids or status'}
            code = 400

        if post_ids:
            tags = {}
            bi_grams = {}
            letters = {}
            for_insert = []
            db_posts = self.posts.get_by_pids(
                self.user['sid'],
                post_ids,
                {'id': True, 'tags': True, 'bi_grams': True, 'read': True}
            )
            if db_posts is not None:
                for d in db_posts:
                    if d['read'] != readed:
                        for_insert.append({
                            'user': self.user['_id'],
                            'id': d['id'],
                            'status': readed,
                            'processing': TASK_NOT_IN_PROCESSING
                        })
                        for t in d['tags']:
                            if t not in tags:
                                tags[t] = 0
                            tags[t] += 1
                            if t[0] not in letters:
                                letters[t[0]] = 0
                            letters[t[0]] += 1
                        for bi_g in d['bi_grams']:
                            if bi_g not in bi_grams:
                                bi_grams[bi_g] = 0
                            bi_grams[bi_g] += 1
            else:
                code = 500
                result = {'error': 'Database error'}
            if for_insert:
                try:
                    self.db.mark_queue.insert_many(for_insert)
                    changed = self.posts.change_status(self.user['sid'], post_ids, readed)
                    if changed and tags:
                        changed = self.tags.change_unread(self.user['sid'], tags, readed)
                    if changed and bi_grams:
                        changed = self.bi_grams.change_unread(self.user['sid'], bi_grams, readed)
                    if changed and letters:
                        changed = self.letters.change_unread(self.user['sid'], letters, readed)
                    if changed:
                        code = 200
                        result = {'data': 'ok'}
                    else:
                        code = 500
                        result = {'error': 'Database error'}
                except Exception as e:
                    result = {'error': 'Database queue error'}
                    logging.error('Can`t push in mark queue: %s', e)
                    code = 500

        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

    def calcPagerData(self, p_number, page_count, items_per_page, endpoint, sentiment='', group=''):
        pages_map = {}
        page_count = round(page_count)
        numbers_start_range = p_number - self.count_showed_numbers + 1
        numbers_end_range = p_number + self.count_showed_numbers + 1
        if numbers_start_range <= 0:
            numbers_start_range = 1
        if numbers_end_range > page_count:
            numbers_end_range = page_count + 1
        params = {}
        if sentiment:
            params['sentiment'] = sentiment
        if group:
            params['group'] = group
        if page_count > 11:
            pages_map['middle'] = []
            for i in range(numbers_start_range, numbers_end_range):
                params['page_number'] = i
                pages_map['middle'].append({
                    'p': i,
                    'url': self.routes.getUrlByEndpoint(endpoint=endpoint, params=params)
                })
            if numbers_start_range > 1:
                params['page_number'] = 1
                pages_map['start'] = [{
                    'p': 'first',
                    'url': self.routes.getUrlByEndpoint(endpoint=endpoint, params=params)
                }]
            if numbers_end_range <= (page_count):
                params['page_number'] = page_count
                pages_map['end'] = [{
                    'p': 'last',
                    'url': self.routes.getUrlByEndpoint(endpoint=endpoint, params=params)
                }]
        else:
            pages_map['start'] = []
            for i in range(1, page_count + 1):
                params['page_number'] = i
                pages_map['start'].append({
                    'p': i,
                    'url': self.routes.getUrlByEndpoint(endpoint=endpoint, params=params)
                })
        start_tags_range = round(((p_number - 1) * items_per_page) + items_per_page)
        end_tags_range = round(start_tags_range + items_per_page)
        return (pages_map, start_tags_range, end_tags_range)

    def on_get_tag_page(self, tag=''):
        tag_data = self.tags.get_by_tag(self.user['sid'], tag)
        if tag_data is not None:
            del tag_data['_id']
            page = self.template_env.get_template('tag-info.html')
            self.response = Response(
                page.render(
                    tag=tag_data,
                    sort_by_title='tags',
                    sort_by_link=self.routes.getUrlByEndpoint(
                        endpoint='on_group_by_tags_get',
                        params={'page_number': 1}
                    ),
                    group_by_link=self.routes.getUrlByEndpoint(endpoint='on_group_by_category_get'),
                    user_settings=self.user['settings'],
                    provider=self.user['provider']
                ),
                mimetype='text/html'
            )
        elif tag_data is None:
            self.on_error(InternalServerError())
        else:
            self.on_error(NotFound())

    def on_group_by_tags_get(self, page_number: int=1) -> None:
        tags_count = self.tags.count(self.user['sid'], self.user['settings']['only_unread'])
        if tags_count is not None:
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
            pages_map, start_tags_range, end_tags_range = self.calcPagerData(
                p_number,
                page_count,
                self.user['settings']['tags_on_page'],
                'on_group_by_tags_get'
            )
            sorted_tags = []
            tags = self.tags.get_all(
                self.user['sid'],
                self.user['settings']['only_unread'],
                self.user['settings']['hot_tags'],
                opts={
                    'offset': start_tags_range,
                    'limit': self.user['settings']['tags_on_page']
                }
            )
            if tags is not None:
                for t in tags:
                    sorted_tags.append({
                        'tag': t['tag'],
                        'url': t['local_url'],
                        'words': t['words'],
                        'count': t['unread_count'] if self.user['settings']['only_unread'] else t['posts_count'],
                        'sentiment': t['sentiment'] if 'sentiment' in t else []
                    })
                db_letters = self.letters.get(self.user['sid'], make_sort=True)
                if db_letters:
                    letters = self.letters.to_list(db_letters, self.user['settings']['only_unread'])
                else:
                    letters = []
                page = self.template_env.get_template('group-by-tag.html')
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
            else:
                self.on_error(InternalServerError())
            self.users.update_by_sid(
                self.user['sid'],
                {'page': new_cookie_page_value, 'letter': ''}
            )
        else:
            self.on_error(InternalServerError())

    def on_group_by_tags_sentiment(self, sentiment:str, page_number: int=1) -> None:
        sentiment = sentiment.replace('|', '/')
        tags_count = self.tags.count(self.user['sid'], self.user['settings']['only_unread'], sentiments=[sentiment])
        if tags_count is not None:
            page_count = self.getPageCount(tags_count, self.user['settings']['tags_on_page'])
            if page_number <= 0:
                p_number = 1
                self.user['page'] = p_number
            elif page_number > page_count:
                p_number = page_count
                self.response = redirect(
                    self.routes.getUrlByEndpoint(
                        endpoint='on_group_by_tags_sentiment',
                        params={'sentiment': sentiment, 'page_number': p_number}
                    )
                )
                self.user['page'] = p_number
            else:
                p_number = page_number
            p_number -= 1
            if p_number < 0:
                p_number = 1
            new_cookie_page_value = p_number + 1
            pages_map, start_tags_range, end_tags_range = self.calcPagerData(
                p_number,
                page_count,
                self.user['settings']['tags_on_page'],
                'on_group_by_tags_sentiment',
                sentiment=sentiment
            )
            sorted_tags = []
            tags = self.tags.get_by_sentiment(
                self.user['sid'],
                [sentiment],
                self.user['settings']['only_unread'],
                self.user['settings']['hot_tags'],
                opts={
                    'offset': start_tags_range,
                    'limit': self.user['settings']['tags_on_page']
                }
            )
            if tags is not None:
                for t in tags:
                    sorted_tags.append({
                        'tag': t['tag'],
                        'url': t['local_url'],
                        'words': t['words'],
                        'count': t['unread_count'] if self.user['settings']['only_unread'] else t['posts_count'],
                        'sentiment': t['sentiment'] if 'sentiment' in t else []
                    })
                db_letters = self.letters.get(self.user['sid'], make_sort=True)
                if db_letters:
                    letters = self.letters.to_list(db_letters, self.user['settings']['only_unread'])
                else:
                    letters = []
                page = self.template_env.get_template('group-by-tag.html')
                self.response = Response(
                    page.render(
                        tags=sorted_tags,
                        sort_by_title='tags',
                        sort_by_link=self.routes.getUrlByEndpoint(
                            endpoint='on_group_by_tags_sentiment',
                            params={'sentiment': sentiment, 'page_number': new_cookie_page_value}
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
            else:
                self.on_error(InternalServerError())
            self.users.update_by_sid(
                self.user['sid'],
                {'page': new_cookie_page_value, 'letter': ''}
            )
        else:
            self.on_error(InternalServerError())

    def on_group_by_tags_startwith_get(self, letter='', page_number=1):
        db_letters = self.letters.get(self.user['sid'], make_sort=True)
        if (db_letters is not None) and (letter in db_letters['letters']):
            tags_count = self.tags.count(self.user['sid'], self.user['settings']['only_unread'], '^{}'.format(letter))
            if tags_count is not None:
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
                pages_map, start_tags_range, end_tags_range = self.calcPagerData(
                    p_number,
                    page_count,
                    self.user['settings']['tags_on_page'],
                    'on_group_by_tags_get'
                )
                sorted_tags = []
                tags = self.tags.get_all(
                    self.user['sid'],
                    self.user['settings']['only_unread'],
                    self.user['settings']['hot_tags'],
                    opts={
                        'offset': start_tags_range,
                        'limit': self.user['settings']['tags_on_page'],
                        'regexp': '^{}'.format(letter)
                    }
                )
                if tags is not None:
                    for t in tags:
                        sorted_tags.append({
                            'tag': t['tag'],
                            'url': t['local_url'],
                            'words': t['words'],
                            'count': t['unread_count'] if self.user['settings']['only_unread'] else t['posts_count'],
                            'sentiment': t['sentiment'] if 'sentiment' in t else []
                        })
                    if db_letters:
                        letters = self.letters.to_list(db_letters, self.user['settings']['only_unread'])
                    else:
                        letters = []
                    page = self.template_env.get_template('group-by-tag.html')
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
                else:
                    self.on_error(InternalServerError())
                self.users.update_by_sid(self.user['sid'], {'letter': letter})
            else:
                self.on_error(InternalServerError())
        elif db_letters is None:
            self.on_error(InternalServerError())
        else:
            self.on_error(NotFound())

    def on_group_by_tags_group(self, group='', page_number=1):
        tags_count = self.tags.count(self.user['sid'], self.user['settings']['only_unread'], groups=[group])
        if tags_count is not None:
            page_count = self.getPageCount(tags_count, self.user['settings']['tags_on_page'])
            if page_number <= 0:
                p_number = 1
                self.user['page'] = p_number
            elif page_number > page_count:
                p_number = page_count
                self.response = redirect(
                    self.routes.getUrlByEndpoint(
                        endpoint='on_group_by_tags_group',
                        params={'group': group, 'page_number': p_number}
                    )
                )
                self.user['page'] = p_number
            else:
                p_number = page_number
            p_number -= 1
            if p_number < 0:
                p_number = 1
            new_cookie_page_value = p_number + 1
            pages_map, start_tags_range, end_tags_range = self.calcPagerData(
                p_number,
                page_count,
                self.user['settings']['tags_on_page'],
                'on_group_by_tags_group',
                group=group
            )
            sorted_tags = []
            tags = self.tags.get_by_group(
                self.user['sid'],
                [group],
                self.user['settings']['only_unread'],
                self.user['settings']['hot_tags'],
                opts={
                    'offset': start_tags_range,
                    'limit': self.user['settings']['tags_on_page']
                }
            )
            if tags is not None:
                for t in tags:
                    sorted_tags.append({
                        'tag': t['tag'],
                        'url': t['local_url'],
                        'words': t['words'],
                        'count': t['unread_count'] if self.user['settings']['only_unread'] else t['posts_count'],
                        'sentiment': t['sentiment'] if 'sentiment' in t else []
                    })
                db_letters = self.letters.get(self.user['sid'], make_sort=True)
                if db_letters:
                    letters = self.letters.to_list(db_letters, self.user['settings']['only_unread'])
                else:
                    letters = []
                page = self.template_env.get_template('group-by-tag.html')
                self.response = Response(
                    page.render(
                        tags=sorted_tags,
                        sort_by_title='tags',
                        sort_by_link=self.routes.getUrlByEndpoint(
                            endpoint='on_group_by_tags_group',
                            params={'group': group, 'page_number': new_cookie_page_value}
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
            else:
                self.on_error(InternalServerError())
            self.users.update_by_sid(
                self.user['sid'],
                {'page': new_cookie_page_value, 'letter': ''}
            )
        else:
            self.on_error(InternalServerError())


    def on_get_tag_similar(self, model='', tag=''):
        tags_set = set()
        all_tags = []
        if model in self.models:
            if (model == self.models['d2v']) and self.d2v:
                try:
                    siblings = self.d2v.similar_by_word(tag, topn=30)
                    for sibling in siblings:
                        tags_set.add(sibling[0])
                except Exception as e:
                    logging.warning('In %s not found tag %s', self.config['settings']['d2v_model'], tag)
            elif (model == self.models['w2v']) and self.w2v:
                try:
                    siblings = self.w2v.similar_by_word(tag, topn=30)
                    for sibling in siblings:
                        tags_set.add(sibling[0])
                except Exception as e:
                    logging.warning('In %s not found tag %s', self.config['settings']['w2v_model'], tag)

            if tags_set:
                db_tags = self.tags.get_by_tags(self.user['sid'], list(tags_set), self.user['settings']['only_unread'])
                if db_tags is not None:
                    for tag in db_tags:
                        all_tags.append({
                            'tag': tag['tag'],
                            'url': tag['local_url'],
                            'words': tag['words'],
                            'count': tag['unread_count'] if self.user['settings']['only_unread'] else tag['posts_count'],
                            'sentiment': tag['sentiment'] if 'sentiment' in tag else []
                        })
                    code = 200
                    result = {'data': all_tags}
                else:
                    code = 500
                    result = {'error': 'Database trouble'}

            else:
                code = 200
                result = {'data': all_tags}
        else:
            code = 404
            result = {'error': 'Unknown model'}

        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

    def on_get_tag_siblings(self, tag=''):
        all_tags = []
        if self.user['settings']['only_unread']:
            only_unread = self.user['settings']['only_unread']
        else:
            only_unread = None
        posts = self.posts.get_by_tags(self.user['sid'], [tag], only_unread, {'tags': True})
        if posts is not None:
            tags_set = set()
            for post in posts:
                for tag in post['tags']:
                    tags_set.add(tag)

            if tags_set:
                db_tags = self.tags.get_by_tags(self.user['sid'], list(tags_set), self.user['settings']['only_unread'])
                if db_tags is not None:
                    for tag in db_tags:
                        all_tags.append({
                            'tag': tag['tag'],
                            'url': tag['local_url'],
                            'words': tag['words'],
                            'count': tag['unread_count'] if self.user['settings']['only_unread'] else tag['posts_count'],
                            'sentiment': tag['sentiment'] if 'sentiment' in tag else []
                        })
                    code = 200
                    result = {'data': all_tags}
                else:
                    code = 500
                    result = {'error': 'Database trouble'}
            else:
                code = 200
                result = {'data': all_tags}
        else:
            code = 500
            result = {'error': 'Database trouble'}

        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

    def on_get_tag_bi_grams(self, tag=''):
        bi_grams = self.bi_grams.get_by_tags(self.user['sid'], [tag], self.user['settings']['only_unread'])
        if bi_grams is not None:
            all_bi_grams = []
            for tag in bi_grams:
                all_bi_grams.append({
                    'tag': tag['tag'],
                    'url': tag['local_url'],
                    'words': tag['words'],
                    'count': tag['unread_count'] if self.user['settings']['only_unread'] else tag['posts_count'],
                    'sentiment': tag['sentiment'] if 'sentiment' in tag else []
                })
            code = 200
            result = {'data': all_bi_grams}
        else:
            code = 500
            result = {'error': 'Database trouble'}

        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

    def on_posts_content_post(self):
        try:
            wanted_posts = json.loads(self.request.get_data(as_text=True))
            if not (isinstance(wanted_posts, list) and wanted_posts):
                raise Exception('Empty list of ids for post content')
        except Exception as e:
            logging.warning('Send bad posts ids for posts content. Cause: %s', e)
            wanted_posts = []
            result = {'error': 'Bad posts ids'}
            code = 400
        if wanted_posts:
            projection = {
                'pid': True,
                'content': True,
                'attachments': True
            }
            posts = self.posts.get_by_pids(self.user['sid'], wanted_posts, projection)
            if posts:
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
                code = 200
            elif posts is None:
                code = 500
                result = {'error': 'Database trouble'}
            else:
                code = 404
                result = {'error': 'Not found'}

        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

    def on_post_links_get(self, post_id: int) -> None:
        projection = {
            'tags': True,
            'feed_id': True,
            'url': True
        }
        current_post = self.posts.get_by_pid(self.user['sid'], post_id, projection)
        if current_post:
            feed = self.feeds.get_by_feed_id(self.user['sid'], current_post['feed_id'])
            if feed:
                code = 200
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
                        'url': self.routes.getUrlByEndpoint(endpoint='on_get_tag_page', params={'tag': t}),
                        'tag': t
                    })
            else:
                code = 500
                result = {'error': 'Server trouble'}
        elif current_post is None:
            code = 500
            result = {'error': 'Database trouble'}
        else:
            code = 404
            result = {'error': 'Not found'}

        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

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
                    back_link = self.routes.getUrlByEndpoint(
                        endpoint='on_group_by_tags_startwith_get',
                        params={'letter': letter, 'page_number': page_number}
                    )
                elif self.user['settings']['hot_tags']:
                    back_link = self.routes.getUrlByEndpoint(
                        endpoint='on_group_by_hottags_get',
                        params={'page_number': page_number}
                    )
                else:
                    back_link = self.routes.getUrlByEndpoint(
                        endpoint='on_group_by_tags_get',
                        params={'page_number': page_number}
                    )
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
        s_request = unquote_plus(self.request.form.get('req'))
        if s_request:
            search_result = self.tags.get_all(
                self.user['sid'],
                only_unread=self.user['settings']['only_unread'],
                opts={
                    'regexp': '^{}.*'.format(s_request),
                    'limit': 10
                }
            )
            if search_result is not None:
                code = 200
                result = {'data': []}
                for tag in search_result:
                    result['data'].append({
                        'tag': tag['tag'],
                        'unread': tag['unread_count'],
                        'all': tag['posts_count'],
                        'url': tag['local_url'],
                        'info_url': self.routes.getUrlByEndpoint('on_get_tag_page', {'tag': tag['tag']})
                    })
            else:
                code = 500
                result = {'error': 'Database trouble'}
        else:
            code = 400
            result = {'error': 'Request can`t be empty'}

        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

    def on_get_map(self):
        projection = {'_id': False}
        cities = self.tags.get_city_tags(self.user['sid'], self.user['settings']['only_unread'], projection)
        countries = self.tags.get_country_tags(self.user['sid'], self.user['settings']['only_unread'], projection)
        if cities is None:
            cities = []
        if countries is None:
            countries = []
        page = self.template_env.get_template('map.html')
        self.response = Response(
            page.render(
                support=self.config['settings']['support'],
                version=self.config['settings']['version'],
                user_settings=self.user['settings'],
                provider=self.user['provider'],
                cities=cities,
                countries=countries
            ),
            mimetype='text/html'
        )

    def on_get_tag_net(self, tag=''):
        all_tags = []
        edges = defaultdict(lambda: set())
        if self.user['settings']['only_unread']:
            only_unread = self.user['settings']['only_unread']
        else:
            only_unread = None
        posts = self.posts.get_by_tags(self.user['sid'], [tag], only_unread, {'tags': True})
        if posts is not None:
            tags_set = set()
            for post in posts:
                for tag in post['tags']:
                    tags_set.add(tag)
                    for tg in post['tags']:
                        edges[tag].add(tg)

            if tags_set:
                db_tags = self.tags.get_by_tags(self.user['sid'], list(tags_set), self.user['settings']['only_unread'])
                if db_tags is not None:
                    for tag in db_tags:
                        edges[tag['tag']].remove(tag['tag'])
                        all_tags.append({
                            'tag': tag['tag'],
                            'url': tag['local_url'],
                            'words': tag['words'],
                            'count': tag['unread_count'] if self.user['settings']['only_unread'] else tag['posts_count'],
                            'edges': list(edges[tag['tag']])[:5],
                            'sentiment': tag['sentiment'] if 'sentiment' in tag else []
                        })
                    code = 200
                    result = {'data': all_tags}
                else:
                    code = 500
                    result = {'error': 'Database trouble'}
            else:
                code = 200
                result = {'data': all_tags}
        else:
            code = 500
            result = {'error': 'Database trouble'}

        self.response = Response(json.dumps(result), mimetype='application/json')
        self.response.status_code = code

    def on_get_tag_net_page(self):
        page = self.template_env.get_template('tags-net.html')
        self.response = Response(
            page.render(
                support=self.config['settings']['support'],
                version=self.config['settings']['version'],
                user_settings=self.user['settings'],
                provider=self.user['provider']
            ),
            mimetype='text/html'
        )

    def on_get_groups(self, page_number=1):
        groups = self.tags.get_groups(self.user['sid'], self.user['settings']['only_unread'])
        if groups:
            groups_count = len(groups)
            page_count = self.getPageCount(groups_count, self.user['settings']['tags_on_page'])
            if page_number <= 0:
                p_number = 1
                self.user['page'] = p_number
            elif page_number > page_count:
                p_number = page_count
                self.response = redirect(
                    self.routes.getUrlByEndpoint(
                        endpoint='on_get_groups',
                        params={'page_number': p_number}
                    )
                )
                self.user['page'] = p_number
            else:
                p_number = page_number
            p_number -= 1
            if p_number < 0:
                p_number = 1
            new_cookie_page_value = p_number + 1
            pages_map, start_tags_range, end_tags_range = self.calcPagerData(
                p_number,
                page_count,
                self.user['settings']['tags_on_page'],
                'on_get_groups',
            )
            page = self.template_env.get_template('tags-groups.html')
            page_groups = sorted(groups.items(), key=lambda el: el[1], reverse=True)
            self.response = Response(
                page.render(
                    support=self.config['settings']['support'],
                    version=self.config['settings']['version'],
                    user_settings=self.user['settings'],
                    provider=self.user['provider'],
                    pages_map=pages_map,
                    groups=page_groups[start_tags_range:end_tags_range]
                ),
                mimetype='text/html'
            )
            self.users.update_by_sid(
                self.user['sid'],
                {'page': new_cookie_page_value, 'letter': ''}
            )
        else:
            self.on_error(InternalServerError())