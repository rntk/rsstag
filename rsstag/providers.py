"""RSSTag downloaders"""
import json
import time
import gzip
import logging
import asyncio
from hashlib import md5
from datetime import date, datetime
from random import randint
from urllib.parse import quote_plus, urlencode
from http import client
from typing import Tuple, List, Optional

from rsstag.tasks import POST_NOT_IN_PROCESSING
from rsstag.routes import RSSTagRoutes

import aiohttp

from telegram.client import Telegram

NOT_CATEGORIZED = "NotCategorized"

class BazquxProvider:
    """rss downloader from bazqux.com"""

    def __init__(self, config: dict):
        self._config = config
        if self._config['settings']['no_category_name']:
            self.no_category_name = self._config['settings']['no_category_name']
        else:
            self.no_category_name = NOT_CATEGORIZED

    def get_headers(self, user: dict) -> dict:
        return {
            'Authorization': 'GoogleLogin auth={0}'.format(user['token']),
            'Content-type': 'application/x-www-form-urlencoded'
        }


    async def fetch(self, data: dict, loop: Optional[asyncio.AbstractEventLoop]) -> Tuple[dict, str]:
        posts = []
        max_repetitions = 5
        repetitions = 0
        again = True
        url = data['url']
        async with aiohttp.ClientSession(loop=loop) as session:
            while again:
                try:
                    async with session.get(url, headers=data['headers']) as resp:
                        if resp.status == 200:
                            raw_json = await resp.text()
                            try:
                                downloaded = json.loads(raw_json)
                            except Exception as e:
                                logging.error('Get strange json from %s. Info: %s', url, e)
                                downloaded = {}
                            if 'continuation' in downloaded:
                                again = True
                                url = '{}&c={}'.format(data['url'], downloaded['continuation'])
                                repetitions = 0
                            else:
                                again = False
                            if 'items' in downloaded:
                                posts = posts + downloaded['items']
                        else:
                            repetitions += 1
                            again = (repetitions < max_repetitions)
                except Exception as e:
                    logging.error('Request failed %s. Repeat: %s. Error: %s', url, repetitions, e)
                    repetitions += 1
                    again = (repetitions < max_repetitions)
            logging.info('Loaded posts %s for category "%s"', len(posts), data['category'])
            return (posts, data['category'])


    def download(self, user: dict) -> Tuple[List, List]:
        posts = []
        feeds = {}
        connection = client.HTTPSConnection(self._config[user['provider']]['api_host'])
        headers = self.get_headers(user)
        connection.request('GET', '/reader/api/0/subscription/list?output=json', '', headers)
        resp = connection.getresponse()
        json_data = resp.read()
        try:
            subscriptions = json.loads(json_data.decode('utf-8'))
        except Exception as e:
            subscriptions = None
            logging.error('Can`t decode subscriptions %s', e)
        if subscriptions:
            routes = RSSTagRoutes(self._config['settings']['host_name'])
            by_category = {}
            loop = asyncio.new_event_loop()
            futures = []
            for feed in subscriptions['subscriptions']:
                if len(feed['categories']) > 0:
                    category_name = feed['categories'][0]['label']
                else:
                    category_name = self.no_category_name
                    futures.append(self.fetch(
                        {
                            'headers': headers,
                            'url': 'https://{}/reader/api/0/stream/contents?s={}&xt=user/-/state/com.google/read&n=5000&output=json'.format(
                                self._config[user['provider']]['api_host'],
                                quote_plus(feed['id'])
                            ),
                            'category': category_name
                        },
                        loop
                    ))
                if category_name not in by_category:
                    by_category[category_name] = True
                    if category_name != self.no_category_name:
                        futures.append(self.fetch(
                            {
                                'headers': headers,
                                'url': 'https://{}/reader/api/0/stream/contents?s=user/-/label/{}&xt=user/-/state/com.google/read&n=1000&output=json'.format(
                                    self._config[user['provider']]['api_host'],
                                    quote_plus(category_name)
                                ),
                                'category': category_name
                            },
                            loop
                        ))
            future = asyncio.gather(*futures, loop=loop)
            loop.run_until_complete(future)
            cats_data = future.result()
            loop.close()
            pid = 0
            logging.info('Was loaded %s categories', len(cats_data))
            for cat_data in cats_data:
                cat_posts, category = cat_data
                logging.info('Fetched %s posts for category "%s"', len(cat_posts), category)
                for post in cat_posts:
                    stream_id = md5(post['origin']['streamId'].encode('utf-8')).hexdigest()
                    if stream_id not in feeds:
                        feeds[stream_id] = {
                            'createdAt': datetime.utcnow(),
                            'title': post['origin']['title'],
                            'owner': user['sid'],
                            'category_id': category,
                            'feed_id': stream_id,
                            'origin_feed_id': post['origin']['streamId'],
                            'category_title': category,
                            'category_local_url': routes.getUrlByEndpoint(
                                endpoint='on_category_get',
                                params={'quoted_category': category}
                            ),
                            'local_url': routes.getUrlByEndpoint(
                                endpoint='on_feed_get',
                                params={'quoted_feed': stream_id}
                            ),
                            'favicon': ''
                        }
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
                    posts.append({
                        'content': {
                            'title': post['title'],
                            'content': gzip.compress(post['summary']['content'].encode('utf-8', 'replace'))
                        },
                        'feed_id': stream_id,
                        'category_id': category,
                        'id': post['id'],
                        'url': post['canonical'][0]['href'] if post['canonical'] else 'http://google.com',
                        'date': p_date,
                        'unix_date': pu_date,
                        'read': False,
                        'favorite': False,
                        'attachments': attachments_list,
                        'tags': [],
                        'bi_grams': [],
                        'pid': pid,
                        'owner': user['sid'],
                        'processing': POST_NOT_IN_PROCESSING
                    })
                    pid += 1

        return (posts, list(feeds.values()))

    def mark(self, data: dict, user: dict) -> Optional[bool]:
        status = data['status']
        data_id = data['id']
        headers = self.get_headers(user)
        read_tag = 'user/-/state/com.google/read'
        result = False
        if status:
            data = urlencode({'i': data_id, 'a': read_tag})
        else:
            data = urlencode({'i': data_id, 'r': read_tag})
        max_repetitions = 10
        for i in range(max_repetitions):
            try:
                connection = client.HTTPSConnection(self._config[user['provider']]['api_host'])
                connection.request('POST', '/reader/api/0/edit-tag?output=json', data, headers)
                resp = connection.getresponse()
                resp_data = resp.read()
                connection.close()
            except Exception as e:
                result = False
                resp_data = None
                logging.warning('Can`t make request %s %s', e, i)

            if resp_data and (resp_data.decode('utf-8').lower() == 'ok'):
                result = True
                break
            else:
                logging.warning('Can`t mark. Resp: %s', resp_data)
                if not self.is_valid_user(user):
                    return None

            time.sleep(randint(2, 7))

        return result

    def get_token(self, login: str, password: str) -> Optional[str]:
        connection = client.HTTPSConnection(self._config['bazqux']['api_host'])
        headers = {'Content-type': 'application/x-www-form-urlencoded'}
        data = urlencode({'Email': login, 'Passwd': password})
        try:
            connection.request('POST', '/accounts/ClientLogin', data, headers)
            resp = connection.getresponse().read().splitlines()
            if resp and resp[0].decode('utf-8').split('=')[0] != 'Error':
                token = resp[-1].decode('utf-8').split('=')[-1]
                result = token
            else:
                result = ''
                logging.error('Wrong Login or Password')
        except Exception as e:
            result = None
            logging.error('Can`t get token from bazqux server. Info: %', e)

        return result

    def is_valid_user(self, user: dict) -> Optional[bool]:
        headers = self.get_headers(user)
        try:
            connection = client.HTTPSConnection(self._config['bazqux']['api_host'])
            connection.request('GET', '/reader/ping', None, headers)
            if connection.getresponse().read().strip() == "OK":
                result= True
            else:
                result = False
                logging.error('Unauthorized user')
            connection.close()
        except Exception as e:
            result = None
            logging.error('Can`t ping bazqux server. Info: %s', e)

        return result

class TelegramProvider:
    def __init__(self, config: dict):
        self._config = config
        if self._config['settings']['no_category_name']:
            self.no_category_name = self._config['settings']['no_category_name']
        else:
            self.no_category_name = NOT_CATEGORIZED

    def download(self, user: dict) -> Tuple[List, List]:
        provider = user["provider"]
        telegram_channel = user["telegram_channel"]
        self._tlg: Telegram = Telegram(
            api_id=self._config[provider]["app_id"],
            api_hash=self._config[provider]["app_hash"],
            phone=user["phone"],
            database_encryption_key='tlg123456',
        )
        self._tlg.login(blocking=True)
        channel_req = self._tlg.search_channel(telegram_channel)
        channel_req.wait()
        if not channel_req:
            logging.warning("No channel: %s", telegram_channel)
            self._tlg.stop()
            return ([], [])
        channel = channel_req.update
        has_posts = True
        from_id = 0
        max_limit = user["telegram_limit"]
        limit = max_limit
        posts = []
        feeds = {}
        routes = RSSTagRoutes(self._config['settings']['host_name'])
        pid = 0
        stream_id = str(channel["id"])
        if stream_id not in feeds:
            feeds[stream_id] = {
                'createdAt': datetime.utcnow(),
                'title': channel['title'],
                'owner': user['sid'],
                'category_id': self.no_category_name,
                'feed_id': stream_id,
                'origin_feed_id': channel["id"],
                'category_title': self.no_category_name,
                'category_local_url': routes.getUrlByEndpoint(
                    endpoint='on_category_get',
                    params={'quoted_category': self.no_category_name}
                ),
                'local_url': routes.getUrlByEndpoint(
                    endpoint='on_feed_get',
                    params={'quoted_feed': stream_id}
                ),
                'favicon': ''
            }
        while has_posts and len(posts) < max_limit:
            posts_req = self._tlg.get_chat_history(channel["id"], limit=limit, from_message_id=from_id)
            posts_req.wait()
            posts_data = posts_req.update
            if (not posts_req.update) or (len(posts_data["messages"]) == 0):
                self._tlg.stop()
                has_posts = False
                continue
            logging.info("Batch loaded %s. Channel %s from %s. Posts - %s, ", telegram_channel, from_id, len(posts_data["messages"]), len(posts))
            if len(posts_data["messages"]) > 0:
                from_id = posts_data["messages"][-1]["id"]
                limit -= len(posts_data["messages"])
            for post in posts_data["messages"]:
                p_date = date.fromtimestamp(int(post["date"])).strftime('%x')
                pu_date = post["date"]

                attachments_list = []
                entities = []
                post_text = ""
                if "caption" in post["content"]:
                    entities = post["content"]["caption"]["entities"]
                    post_text = post['content']["caption"]["text"]
                elif "text" in post["content"]:
                    entities = post["content"]["text"]["entities"]
                    post_text = post["content"]["text"]["text"]
                for entity in entities:
                    if "type" in entity and "url" in entity["type"]:
                        attachments_list.append(entity["type"]["url"])
                resp = self._tlg.get_message_link(post["chat_id"], post["id"])
                resp.wait()
                t_link = resp.update["link"]
                posts.append({
                    'content': {
                        'title': "",
                        'content': gzip.compress(post_text.encode('utf-8', 'replace'))
                    },
                    'feed_id': stream_id,
                    'category_id': self.no_category_name,
                    'id': post['id'],
                    'url': t_link,
                    'date': p_date,
                    'unix_date': pu_date,
                    'read': False,
                    'favorite': False,
                    'attachments': attachments_list,
                    'tags': [],
                    'bi_grams': [],
                    'pid': pid,
                    'owner': user['sid'],
                    'processing': POST_NOT_IN_PROCESSING
                })
                pid += 1
        logging.info("Downloaded: %s - %s", telegram_channel, len(posts))

        self._tlg.stop()

        return (posts, list(feeds.values()))

    def mark(self, data: dict, user: dict) -> Optional[bool]:
        return True
