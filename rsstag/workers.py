'''RSSTag workers'''
import logging
import time
import gzip
from urllib.parse import quote
from random import randint
from multiprocessing import Process
from rsstag.tags_builder import TagsBuilder
from pymongo import MongoClient, UpdateOne
from rsstag.providers import BazquxProvider
from rsstag.utils import load_config
from rsstag.routes import RSSTagRoutes
from rsstag import TASK_NOOP, TASK_DOWNLOAD, TASK_MARK, TASK_TAGS, POST_NOT_IN_PROCESSING, TASK_NOT_IN_PROCESSING

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

    def make_tags(self, db: MongoClient, post: dict, builder: TagsBuilder) -> bool:
        #logging.info('Start process %s', post['_id'])
        content = gzip.decompress(post['content']['content'])
        text = post['content']['title'] + content.decode('utf-8')
        builder.purge()
        builder.build_tags(text)
        tags = builder.get_tags()
        words = builder.get_words()
        result = False
        tags_updates = []
        first_letters = set()
        routes = RSSTagRoutes(self._config['settings']['host_name'])
        if tags == []:
            tag = 'notitle'
            tags = [tag]
            words[tag] = set(tags)
        for tag in tags:
            tags_updates.append(UpdateOne(
                {'owner': post['owner'], 'tag': tag},
                {
                    '$set': {
                        'read': False,
                        'tag': tag,
                        'owner': post['owner'],
                        'temperature': 0,
                        'local_url': routes.getUrlByEndpoint(
                            endpoint='on_tag_get',
                            params={'quoted_tag': quote(tag)}
                        )
                    },
                    '$inc': {'posts_count': 1, 'unread_count': 1},
                    '$addToSet': {'words': {'$each': list(words[tag])}}
                },
                upsert=True
            ))
            first_letters.add(tag[0])

        letters_updates = []
        for letter in first_letters:
            key = 'letters.' + letter
            letters_updates.append(UpdateOne(
                {'owner': post['owner']},
                {'$set': {
                    key + '.letter': letter,
                    key + '.local_url': routes.getUrlByEndpoint(
                            endpoint='on_group_by_tags_startwith_get',
                            params={'letter': letter}
                        )
                }},
                upsert=True
            ))
            letters_updates.append(UpdateOne(
                {'owner': post['owner']},
                {'$inc': {
                    key + '.unread_count': 1
                }},
                upsert=True
            ))

        if tags_updates:
            try:
                db.tags.bulk_write(tags_updates, ordered=False)
                db.letters.bulk_write(letters_updates)
                db.posts.update({'_id': post['_id']}, {'$set': {'tags': tags}})
                result = True
            except Exception as e:
                result = False
                logging.error('Can`t make tags for post %s. Info: %s', post['_id'], e)

        #logging.info('Processed %s', post['_id'])

        return result

    def get_task(self, db: MongoClient) -> dict:
        task = {
            'type': TASK_NOOP,
            'user': None,
            'data': None
        }
        try:
            data = db.download_queue.find_one_and_update(
                {'processing': TASK_NOT_IN_PROCESSING},
                {'$set': {'processing': time.time()}}
            )
            if data:
                task['type'] = TASK_DOWNLOAD
        except Exception as e:
            data = None
            logging.error('Worker can`t get data from queue: %s', e)

        if task['type'] == TASK_NOOP:
            try:
                data = db.mark_queue.find_one_and_update(
                    {'processing': TASK_NOT_IN_PROCESSING},
                    {'$set': {'processing': time.time()}}
                )
                if data:
                    task['type'] = TASK_MARK
            except Exception as e:
                data = None
                logging.error('Worker can`t get data from queue: %s', e)

        if task['type'] == TASK_NOOP:
            try:
                data = db.posts.find_one_and_update(
                    {
                        'tags': [],
                        'processing': POST_NOT_IN_PROCESSING
                    },
                    {'$set': {'processing': time.time()}}
                )
                if data:
                    task['type'] = TASK_TAGS
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
                    if not user:
                        task['type'] = TASK_NOOP
                '''elif 'owner' in data:
                    user_id = data['owner']'''
            except Exception as e:
                user = None
                logging.error(
                    'Cant`t get user %s for task %s, type %s. Info: %e',
                    user_id,
                    data['_id'],
                    task['type'],
                    e
                )
                task['type'] = TASK_NOOP

        task['data'] = data
        task['user'] = user

        return task

    def finish_task(self, db: MongoClient, task: dict) -> bool:
        max_repeats = 5
        for i in range(max_repeats):
            try:
                if task['type'] == TASK_DOWNLOAD:
                    db.download_queue.remove({'_id': task['data']['_id']})
                elif task['type'] == TASK_MARK:
                    db.mark_queue.remove({'_id': task['data']['_id']})
                elif task['type'] == TASK_TAGS:
                    db.posts.find_one_and_update(
                        {'_id': task['data']['_id']},
                        {'$set': {'processing': POST_NOT_IN_PROCESSING}}
                    )
                result = True
                break
            except Exception as e:
                result = False
                logging.error('Can`t finish task %s, type %s. Info: %s', task['data']['_id'], task['type'], e)

        return result

    def worker(self):
        '''Worker for bazqux.com'''
        cl = MongoClient(self._config['settings']['db_host'], int(self._config['settings']['db_port']))
        db = cl.rss

        provider = BazquxProvider(self._config)
        builder = TagsBuilder(self._config['settings']['replacement'])
        while True:
            task = self.get_task(db)
            if task['type'] == TASK_NOOP:
                time.sleep(randint(3, 8))
                continue
            if task['type'] == TASK_DOWNLOAD:
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
            elif task['type'] == TASK_MARK:
                task_done = provider.mark(task['data'], task['user'])

            elif task['type'] == TASK_TAGS:
                task_done = self.make_tags(db, task['data'], builder)

            if task_done:
                self.finish_task(db, task)
