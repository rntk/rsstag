'''RSSTag workers'''
import logging
import gzip
import time
import json
import sys
from hashlib import md5
from random import randint
from http import client
from multiprocessing import Process, Pool
from urllib.parse import quote_plus, urlencode, urlparse
from datetime import date, datetime
from collections import OrderedDict
from html_cleaner import HTMLCleaner
from tags_builder import TagsBuilder
from pymongo import MongoClient
from rsstag_downloaders import BazquxDownloader
from rsstag_utils import getSortedDictByAlphabet, load_config
from rsstag_routes import RSSTagRoutes

class RSSTagWorker:
    '''Rsstag workers handler'''
    def __init__(self, config_path):
        self._config = load_config(config_path)
        self.routes = RSSTagRoutes(self._config['settings']['host_name'])
        self._workers_pool = []
        logging.basicConfig(
            filename=self._config['settings']['log_file'],
            filemode='a',
            level=getattr(logging, self._config['settings']['log_level'].upper())
        )
        self.log = logging

    def start(self):
        '''Start worker'''
        for i in range(int(self._config['settings']['workers_count'])):
            self._workers_pool.append(Process(target=self.worker))
            self._workers_pool[-1].start()

    def worker(self):
        '''Worker for bazqux.com'''
        no_category_name = 'NotCategorized'
        tags_builder = TagsBuilder(self._config['settings']['replacement'])
        html_clnr = HTMLCleaner()
        by_category = {}
        by_feed = {}
        by_tag = OrderedDict({'tags': {}})
        first_letters = {}
        user = None
        all_posts = []

        cl = MongoClient(self._config['settings']['db_host'], int(self._config['settings']['db_port']))
        db = cl.rss

        def treatPosts(category=None, p_range=None):
            try:
                self.log.info('treating %s', category)
            except Exception as e:
                self.log.warning('treating category with strange symbols')
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
                words = tags_builder.get_words()
                for tag in tags:
                    if tag[0] not in first_letters:
                        first_letters[tag[0]] = {
                            'letter': tag[0],
                            'local_url': self.routes.getUrlByEndpoint(
                                endpoint='on_group_by_tags_startwith_get',
                                params={'letter': tag[0]}
                            ),
                            'unread_count': 0
                        }
                    if tag not in by_tag['tags']:
                        by_tag['unread_count'] += 1
                        by_tag['tags'][tag] = {'words': [], 'local_url': tag, 'read': False, 'tag': tag,
                                               'owner': user['sid'], 'posts': set(),
                                               'temperature': 0}  # 'posts': set(), 'read_posts': set(),
                    by_tag['tags'][tag]['words'] = list(words[tag])
                    by_tag['tags'][tag]['posts'].add(pos)
                    if tag not in all_posts[pos]['tags']:
                        all_posts[pos]['tags'].append(tag)

            try:
                self.log.info('treated %s', category)
            except Exception as e:
                self.log.warning('treated category with strange symbols')
            return p_range

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
                    db.letters.insert_one(
                        {'owner': user['sid'], 'letters': first_letters, 'createdAt': datetime.utcnow()})
                    db.users.update_one(
                        {'sid': user['sid']},
                        {'$set': {
                            'ready_flag': True,
                            'in_queue': False,
                            'message': 'You can start reading',
                            'createdAt': datetime.utcnow()
                        }}
                    )
                except Exception as e:
                    self.log.error('Can`t save all data: %s', e)
                    db.users.update_one(
                        {'sid': user['sid']},
                        {'$set': {
                            'ready_flag': False,
                            'in_queue': False,
                            'message': 'Can`t save to database, please try later',
                            'createdAt': datetime.utcnow()
                        }}
                    )
                self.log.info('saved all-%s %s %s %s', time.time() - st, len(tags_list), len(all_posts), len(by_feed))
            else:
                db.users.update_one(
                    {'sid': user['sid']},
                    {'$set': {'ready_flag': True, 'in_queue': False, 'message': 'You can start reading'}}
                )
                self.log.warning('Nothing to save')

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
                    upsert=True
                )

        while True:
            user_id = None
            user = None
            # st = time.time()
            try:
                data = db.download_queue.find_one_and_delete({})
            except Exception as e:
                data = None
                self.log.error('Worker can`t get data from queue: %s', e)
            if data:
                user_id = data['user']
                action_type = 'download'
            else:
                try:
                    data = db.mark_queue.find_one_and_delete({})
                except Exception as e:
                    data = None
                    self.log.error('Worker can`t get data from queue: %s', e)
                if data:
                    user_id = data['user']
                    action_type = 'mark'
            if user_id:
                user = db.users.find_one({'_id': user_id})
            if not user:
                time.sleep(randint(3, 8))
                continue
            # print(name, 'lock wait', time.time() - st)
            if action_type == 'download':
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
                if (user['provider'] == 'bazqux') or (user['provider'] == 'inoreader'):
                    connection = client.HTTPSConnection(self._config[user['provider']]['api_host'])
                    headers = {'Authorization': 'GoogleLogin auth={0}'.format(user['token'])}
                    connection.request('GET', '/reader/api/0/subscription/list?output=json', '', headers)
                    resp = connection.getresponse()
                    json_data = resp.read()
                    try:
                        subscriptions = json.loads(json_data.decode('utf-8'))
                    except Exception as e:
                        subscriptions = None
                        self.log.error('Can`t decode subscriptions %s', e)
                    if subscriptions:
                        works = []
                        i = 0
                        feed = None
                        for i, feed in enumerate(subscriptions['subscriptions']):
                            if len(feed['categories']) > 0:
                                category_name = feed['categories'][0]['label']
                            else:
                                category_name = no_category_name
                                works.append({
                                    'headers': headers,
                                    'host': self._config[user['provider']]['api_host'],
                                    'url': '/reader/api/0/stream/contents?s={0}&xt=user/-/state/com.google/read&n=5000&output=json'.format(
                                        quote_plus(feed['id'])),
                                    'category': category_name
                                })
                            if category_name not in by_category:
                                by_category[category_name] = True
                                if category_name != no_category_name:
                                    works.append({
                                        'headers': headers,
                                        'host': self._config[user['provider']]['api_host'],
                                        'url': '/reader/api/0/stream/contents?s=user/-/label/{0}&xt=user/-/state/com.google/read&n=1000&output=json'.format(
                                            quote_plus(category_name)
                                        ),
                                        'category': category_name
                                    })
                        workers_downloader_pool = Pool(int(self._config['settings']['workers_count']))
                        downloader = BazquxDownloader(self.log)
                        for posts, category in workers_downloader_pool.imap(downloader.start, works, 1):
                            if posts and posts['items']:
                                old_posts_count = len(all_posts)
                                posts_count = len(posts['items'])
                                p_range = (old_posts_count, old_posts_count + posts_count)
                                for post in posts['items']:
                                    origin_feed_id = post['origin']['streamId']
                                    post['origin']['streamId'] = md5(
                                        post['origin']['streamId'].encode('utf-8')).hexdigest()
                                    if post['origin']['streamId'] not in by_feed:
                                        by_feed[post['origin']['streamId']] = {
                                            'createdAt': datetime.utcnow(),
                                            'title': post['origin']['title'],
                                            'owner': user['sid'],
                                            'category_id': category,
                                            'feed_id': post['origin']['streamId'],
                                            'origin_feed_id': origin_feed_id,
                                            'category_title': category,
                                            'category_local_url': self.routes.getUrlByEndpoint(endpoint='on_category_get', params={
                                                'quoted_category': category}),
                                            'local_url': self.routes.getUrlByEndpoint(endpoint='on_feed_get', params={
                                                'quoted_feed': post['origin']['streamId']})
                                        }
                                    p_date = None
                                    if 'published' in post:
                                        p_date = date.fromtimestamp(int(post['published'])).strftime('%x')
                                        pu_date = float(post['published'])
                                    else:
                                        p_date = -1
                                        pu_date = -1.0
                                    attachments_list = []
                                    if 'enclosure' in post:
                                        for attachments in post['enclosure']:
                                            if ('href' in attachments) and attachments['href']:
                                                attachments_list.append(attachments['href'])
                                    all_posts.append({
                                        'content': {'title': post['title'], 'content': gzip.compress(
                                            post['summary']['content'].encode('utf-8', 'replace'))},
                                        'feed_id': post['origin']['streamId'],
                                        'id': post['id'],
                                        'url': post['canonical'][0]['href'] if post['canonical'] else 'http://ya.ru',
                                        'date': p_date,
                                        'unix_date': pu_date,
                                        'read': False,
                                        'favorite': False,
                                        'attachments': attachments_list
                                    })
                                    if 'favicon' not in by_feed[post['origin']['streamId']]:
                                        if all_posts[-1]['url']:
                                            # by_feed[post['origin']['streamId']]['favicon'] = all_posts[-1]['url']
                                            parsed_url = urlparse(all_posts[-1]['url'])
                                            by_feed[post['origin']['streamId']]['favicon'] = '{0}://{1}/favicon.ico'\
                                                .format(
                                                    parsed_url.scheme if parsed_url.scheme else 'http',
                                                    parsed_url.netloc
                                                )
                                treatPosts(category, p_range)
                        workers_downloader_pool.terminate()
                        by_tag = getSortedDictByAlphabet(by_tag)
                        saveAllData()
                        processWords()
            elif action_type == 'mark':
                status = data['status']
                if (user['provider'] == 'bazqux') or (user['provider'] == 'inoreader'):
                    data_id = data['id']
                    headers = {'Authorization': 'GoogleLogin auth={0}'.format(user['token']),
                               'Content-type': 'application/x-www-form-urlencoded'}
                    err = []
                    counter = 0
                    read_tag = 'user/-/state/com.google/read'
                    if status:
                        data = urlencode({'i': data_id, 'a': read_tag})
                    else:
                        data = urlencode({'i': data_id, 'r': read_tag})
                    while counter < 6:
                        connection = client.HTTPSConnection(self._config[user['provider']]['api_host'])
                        counter += 1
                        err = []
                        try:
                            connection.request('POST', '/reader/api/0/edit-tag?output=json', data, headers)
                            resp = connection.getresponse()
                            resp_data = resp.read()
                        except Exception as e:
                            err.append(str(e))
                            connection.close()
                            self.log.warning('Can`t make request %s %s', e, counter)
                        if not err:
                            if resp_data.decode('utf-8').lower() == 'ok':
                                counter = 6
                            else:
                                time.sleep(randint(2, 7))
                                if counter < 6:
                                    self.log.warning('try again')
                                else:
                                    self.log.warning('not marked %s', resp_data)
                    connection.close()

if __name__ == '__main__':
    config_path = 'rsscloud.conf'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    worker = RSSTagWorker(config_path)
    worker.start()
