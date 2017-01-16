import logging
import time
from rsstag import TASK_NOOP, TASK_NOT_IN_PROCESSING, TASK_DOWNLOAD, TASK_MARK, TASK_TAGS, TASK_WORDS, POST_NOT_IN_PROCESSING
from rsstag.users import RssTagUsers
from pymongo import MongoClient

class RssTagTasks:
    indexes = ['owner']
    def __init__(self, db: MongoClient) -> None:
        self._db = db
        self._log = logging.getLogger('tasks')

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self._db.tasks.create_index(index)
            except Exception as e:
                self._log.warning('Can`t create index %s. May be already exists. Info: %s', index, e)
        index = 'processing'
        try:
            self.db.download_queue.create_index(index)
        except Exception as e:
            self._log.warning('Can`t create index %s. May be already exists. Info: %s', index, e)
        try:
            self.db.mark_queue.create_index(index)
        except Exception as e:
            self._log.warning('Can`t create index %s. May be already exists. Info: %s', index, e)

    def add_task(self, data: dict):
        result = True
        if data and 'type' in data:
            try:
                if data['type'] == TASK_DOWNLOAD:#TODO: check insertion results
                    self.db.download_queue.insert_one(
                        {'user': data['user'], 'processing': TASK_NOT_IN_PROCESSING, 'host': data['host']}
                    )
                elif data['type'] == TASK_MARK:
                    if data['data']:
                        self.db.mark_queue.insert_many(data['data'])
                    else:
                        result = False
                else:
                    result = False
            except Exception as e:
                result = None
                self._log.warning('Can`t add task %s for user %s. Info: %s', data['type'], data['user'], e)
        else:
            result = False
            self._log.warning('Can`t add task. Bad task data: %s', data)

        return result

    def get_task(self, db: MongoClient, users: RssTagUsers) -> dict:
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
            if data and (data['processing'] == TASK_NOT_IN_PROCESSING):
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
                if data and (data['processing'] == TASK_NOT_IN_PROCESSING):
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
                if data and (data['processing'] == TASK_NOT_IN_PROCESSING):
                    task['type'] = TASK_TAGS
            except Exception as e:
                data = None
                logging.error('Worker can`t get data from posts: %s', e)

        """if task['type'] == TASK_NOOP:
            try:
                data = db.tags.find_one_and_update(
                    {
                        'processing': TASK_NOT_IN_PROCESSING,
                        'worded': {'$exists': False}
                    },
                    {'$set': {'processing': time.time()}}
                )
                if data and (data['processing'] == TASK_NOT_IN_PROCESSING):
                    task['type'] = TASK_WORDS
            except Exception as e:
                data = None
                logging.error('Worker can`t get data from words queue: %s', e)"""

        user = None
        if data:
            try:
                user_id = None
                if 'user' in data:
                    user_id = data['user']
                    user = users.get_by_id(user_id)
                    if not user:
                        task['type'] = TASK_NOOP
                """elif 'owner' in data:
                    user_id = data['owner']"""
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
                elif task['type'] == TASK_WORDS:
                    db.tags.find_one_and_update(
                        {'_id': task['data']['_id']},
                        {'$set': {
                            'processing': POST_NOT_IN_PROCESSING,
                            'worded': True
                        }}
                    )
                result = True
                break
            except Exception as e:
                result = False
                logging.error('Can`t finish task %s, type %s. Info: %s', task['data']['_id'], task['type'], e)

        return result
