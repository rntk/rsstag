'''RSSTag workers'''
import logging
import time
import sys
from random import randint
from multiprocessing import Process
'''from collections import OrderedDict
from html_cleaner import HTMLCleaner
from tags_builder import TagsBuilder'''
from pymongo import MongoClient
from rsstag_providers import BazquxProvider
from rsstag_utils import load_config

class RSSTagWorker:
    '''Rsstag workers handler'''
    def __init__(self, config_path):
        self._config = load_config(config_path)
        self._workers_pool = []
        logging.basicConfig(
            filename=self._config['settings']['log_file'],
            filemode='a',
            level=getattr(logging, self._config['settings']['log_level'].upper())
        )

    def start(self):
        '''Start worker'''
        for i in range(int(self._config['settings']['workers_count'])):
            self._workers_pool.append(Process(target=self.worker))
            self._workers_pool[-1].start()
        self._workers_pool[-1].join()

    def clear_user_data(self, db: object, user: dict):
        try:
            db.posts.remove({'owner': user['sid']})
            db.feeds.remove({'owner': user['sid']})
            db.tags.remove({'owner': user['sid']})
            db.letters.remove({'owner': user['sid']})
            result = True
        except Exception as e:
            logging.error('Can`t clear user data %s. Info: %s', user['sid'], e)
            result = False

        return result

    def worker(self, *args, **kwargs):
        '''Worker for bazqux.com'''
        cl = MongoClient(self._config['settings']['db_host'], int(self._config['settings']['db_port']))
        db = cl.rss

        provider = BazquxProvider(self._config)
        while True:
            user_id = None
            user = None
            try:
                data = db.download_queue.find_one_and_delete({})
            except Exception as e:
                data = None
                logging.error('Worker can`t get data from queue: %s', e)
            if data:
                user_id = data['user']
                action_type = 'download'
            else:
                try:
                    data = db.mark_queue.find_one_and_delete({})
                except Exception as e:
                    data = None
                    logging.error('Worker can`t get data from queue: %s', e)
                if data:
                    user_id = data['user']
                    action_type = 'mark'
            if user_id:
                user = db.users.find_one({'_id': user_id})
            if not user:
                time.sleep(randint(3, 8))
                continue
            if action_type == 'download':
                if self.clear_user_data(db, user):
                    posts, feeds = provider.download(user)
                    if posts:
                        try:
                            db.feeds.insert_many(feeds)
                            db.posts.insert_many(posts)
                            db.users.update_one({'sid': user['sid']}, {'$set': {'ready_flag': True}})
                        except Exception as e:
                            logging.error('Can`t save in db for user %s. Info: %s', user['sid'], e)
            elif action_type == 'mark':
                provider.mark(data, user)

if __name__ == '__main__':
    config_path = 'rsscloud.conf'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    worker = RSSTagWorker(config_path)
    worker.start()
