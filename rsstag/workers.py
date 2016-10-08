'''RSSTag workers'''
import logging
import time
from typing import Tuple
from random import randint
from multiprocessing import Process
from rsstag.html_cleaner import HTMLCleaner
from rsstag.tags_builder import TagsBuilder
from pymongo import MongoClient
from rsstag.providers import BazquxProvider
from rsstag.utils import load_config

ACTION_NOOP = 0
ACTION_DOWNLOAD = 1
ACTION_MARK = 2
ACTION_TAGS = 3

POST_NOT_IN_PROCESSING = 0
TASK_NOT_IN_PROCESSING = 0

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

    def make_tags(self, builder: TagsBuilder, cleaner: HTMLCleaner) -> bool:
        pass

    def get_task(self, db: MongoClient) -> dict:
        task = {
            'action': ACTION_NOOP,
            'user': None,
            'data': None
        }
        try:
            data = db.download_queue.find_one_and_update({
                {'processing': TASK_NOT_IN_PROCESSING},
                {'$set': {'processing': time.time()}}
            })
            if data:
                task['action'] = ACTION_DOWNLOAD
        except Exception as e:
            data = None
            logging.error('Worker can`t get data from queue: %s', e)

        if task['action'] == ACTION_NOOP:
            try:
                data = db.mark_queue.find_one_and_update({
                    {'processing': TASK_NOT_IN_PROCESSING},
                    {'$set': {'processing': time.time()}}
                })
                if data:
                    task['action'] = ACTION_MARK
            except Exception as e:
                data = None
                logging.error('Worker can`t get data from queue: %s', e)

        if task['action'] == ACTION_NOOP:
            try:
                data = db.posts.find_one_and_update(
                    {
                        'tags': [],
                        'processing': POST_NOT_IN_PROCESSING
                    },
                    {'$set': {'processing': time.time()}}
                )
                if data:
                    task['action'] = ACTION_MARK
            except Exception as e:
                data = None
                logging.error('Worker can`t get data from queue: %s', e)

        user = None
        if data:
            try:
                user_id = None
                if 'user_id' in data:
                    user_id = data['user_id']
                    user = db.users.find_one({'sid': user_id})
                '''elif 'owner' in data:
                    user_id = data['owner']'''
            except Exception as e:
                user = None
                logging.error(
                    'Cant`t get user %s for task %s, type %s. Info: %e',
                    user_id,
                    data['_id'],
                    task['action'],
                    e
                )
                task['action'] = ACTION_NOOP

        task['data'] = data
        task['user'] = user

        return task

    def finish_task(self, db: MongoClient, task: dict) -> bool:
        max_repeats = 5
        for i in range(max_repeats):
            try:
                if task['action'] == ACTION_DOWNLOAD:
                    db.download_queue.remove({'_id': task['_id']})
                elif task['action'] == ACTION_MARK:
                    db.mark_queue.remove({'_id': task['_id']})
                elif task['action'] == ACTION_TAGS:
                    db.posts.find_one_and_update(
                        {'_id': task['_id']},
                        {'$set': {'processing': POST_NOT_IN_PROCESSING}}
                    )
                result = True
                break
            except Exception as e:
                result = False
                logging.error('Can`t finish task %s, type %s. Info: %s', task['id'], task['action'], e)

        return result

    def worker(self, *args, **kwargs):
        '''Worker for bazqux.com'''
        cl = MongoClient(self._config['settings']['db_host'], int(self._config['settings']['db_port']))
        db = cl.rss

        provider = BazquxProvider(self._config)
        cleaner = HTMLCleaner()
        builder = TagsBuilder(self._config['settings']['replacement'])
        while True:
            task = self.get_task(db)
            if task['action'] == ACTION_NOOP:
                time.sleep(randint(3, 8))
                continue
            if task['action'] == ACTION_DOWNLOAD:
                if self.clear_user_data(db, task['user']):
                    posts, feeds = provider.download(task['user'])
                    if posts:
                        logging.info('Try save data in db. Posts: %s. Feeds: %s', len(posts), len(feeds))
                        try:
                            db.feeds.insert_many(feeds)
                            db.posts.insert_many(posts)
                            db.users.update_one({'sid': task['user']['sid']}, {'$set': {'ready_flag': True}})
                            task_done = True
                        except Exception as e:
                            task_done = False
                            logging.error('Can`t save in db for user %s. Info: %s', task['user']['sid'], e)
            elif task['action'] == ACTION_MARK:
                task_done = provider.mark(task['data'], task['user'])

            elif task['action'] == ACTION_TAGS:
                task_done = self.make_tags(task['data'], builder, cleaner)

            if task_done:
                self.finish_task(db, task)
