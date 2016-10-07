'''RSSTag downloaders'''
import json
import time
import gzip
import logging
import asyncio
import aiohttp
from hashlib import md5
from datetime import date, datetime
from random import randint
from urllib.parse import quote_plus, urlencode
from http import client
from typing import Tuple
from rsstag_routes import RSSTagRoutes

class BazquxProvider:
    '''rss downloader from bazqux.com'''

    def __init__(self, config: dict):
        self._config = config

    def get_headers(self, user: dict) -> dict:
        return {
            'Authorization': 'GoogleLogin auth={0}'.format(user['token']),
            'Content-type': 'application/x-www-form-urlencoded'
        }


    async def fetch(self, data: dict, loop: object) -> Tuple[dict, str]:
        posts = []
        max_repetitions = 5
        repetitions = 0
        again = True
        url = data['url']
        async with aiohttp.ClientSession(loop=loop) as session:
            while again:
                async with session.get(url, data['headers']) as resp:
                    if resp.status == 200:
                        downloaded = await resp.json()
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

        return (posts, data['category'])


    def download(self, user: dict) -> None:
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
            routes = RSSTagRoutes()
            by_category = {}
            loop = asyncio.get_event_loop()
            futures = []
            for i, feed in enumerate(subscriptions['subscriptions']):
                if len(feed['categories']) > 0:
                    category_name = feed['categories'][0]['label']
                else:
                    category_name = self.no_category_name
                    futures.append(self.fetch({
                        'headers': headers,
                        'url': '{}/reader/api/0/stream/contents?s={}&xt=user/-/state/com.google/read&n=5000&output=json'.format(
                            self._config[user['provider']]['api_host'],
                            quote_plus(feed['id'])
                        ),
                        'category': category_name
                    }))
                if category_name not in by_category:
                    by_category[category_name] = True
                    if category_name != self.no_category_name:
                        futures.append(self.fetch({
                            'headers': headers,
                            'url': '{}/reader/api/0/stream/contents?s=user/-/label/{}&xt=user/-/state/com.google/read&n=1000&output=json'.format(
                                self._config[user['provider']]['api_host'],
                                quote_plus(category_name)
                            ),
                            'category': category_name
                        }))
            future = asyncio.ensure_future(asyncio.wait(futures, loop=loop))
            loop.run_until_complete(future)
            loop.close()
            pid = 0
            for cat_data in future.result():
                cat_posts, category = cat_data
                for post in cat_posts:
                    if post['origin']['streamId'] not in feeds:
                        feeds[post['origin']['streamId']] = {
                            'createdAt': datetime.utcnow(),
                            'title': cat_posts['origin']['title'],
                            'owner': user['sid'],
                            'category_id': category,
                            'feed_id': post['origin']['streamId'],
                            'origin_feed_id': post['origin']['streamId'],
                            'category_title': category,
                            'category_local_url': routes.getUrlByEndpoint(endpoint='on_category_get', params={
                                'quoted_category': category}),
                            'local_url': routes.getUrlByEndpoint(endpoint='on_feed_get', params={
                                'quoted_feed': post['origin']['streamId']})
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
                        'feed_id': post['origin']['streamId'],
                        'id': post['id'],
                        'url': post['canonical'][0]['href'] if post['canonical'] else 'http://google.com',
                        'date': p_date,
                        'unix_date': pu_date,
                        'read': False,
                        'favorite': False,
                        'attachments': attachments_list,
                        'tags': [],
                        'pid': pid,
                        'owner': user['sid']
                    })
                    pid += 1

        return (posts, list(feeds.values()))

    def mark(self, data: dict, user: dict) -> None:
        status = data['status']
        data_id = data['id']
        headers = self.get_headers(user)
        counter = 0
        read_tag = 'user/-/state/com.google/read'
        if status:
            data = urlencode({'i': data_id, 'a': read_tag})
        else:
            data = urlencode({'i': data_id, 'r': read_tag})
        max_repetitions = 6
        while counter < max_repetitions:
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
                logging.warning('Can`t make request %s %s', e, counter)
            if not err:
                if resp_data.decode('utf-8').lower() == 'ok':
                    counter = max_repetitions
                else:
                    time.sleep(randint(2, 7))
                    if counter < max_repetitions:
                        logging.warning('try again')
                    else:
                        logging.warning('not marked %s', resp_data)
        connection.close()
