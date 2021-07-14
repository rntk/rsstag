import logging
import time
from typing import Optional, List
from rsstag.users import RssTagUsers
from pymongo import MongoClient

TASK_ALL = -1
TASK_NOOP = 0
TASK_DOWNLOAD = 1
TASK_MARK = 2
TASK_TAGS = 3
TASK_WORDS = 4
TASK_LETTERS = 5
TASK_NER = 6
TASK_CLUSTERING = 7
TASK_W2V = 8
TASK_D2V = 9
TASK_TAGS_SENTIMENT = 10
TASK_TAGS_GROUP = 11
TASK_TAGS_COORDS = 12
TASK_BIGRAMS_RANK = 13

POST_NOT_IN_PROCESSING = 0
TASK_NOT_IN_PROCESSING = 0
TASK_FREEZED = -1
TAG_NOT_IN_PROCESSING = 0

class RssTagTasks:
    indexes = ['user', 'processing']
    _tasks_after = {
        TASK_DOWNLOAD: [TASK_TAGS],
        TASK_TAGS: [TASK_BIGRAMS_RANK, TASK_LETTERS, TASK_TAGS_SENTIMENT, TASK_NER, TASK_CLUSTERING], #TASK_TAGS_COORDS
        TASK_NER: [TASK_W2V],
        TASK_W2V: [TASK_TAGS_GROUP]
    }
    _delete_tasks = {
        TASK_LETTERS, TASK_TAGS_SENTIMENT, TASK_NER, TASK_CLUSTERING, TASK_TAGS_COORDS, TASK_W2V, TASK_TAGS_GROUP
    }
    def __init__(self, db: MongoClient) -> None:
        self._db = db
        self._log = logging.getLogger('tasks')
        self._bath_size = 200

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self._db.tasks.create_index(index)
            except Exception as e:
                self._log.warning('Can`t create index %s. May be already exists. Info: %s', index, e)

    def add_task(self, data: dict):
        result = True
        if data and 'type' in data:
            try:
                if data['type'] == TASK_DOWNLOAD:#TODO: check insertion results
                    self._db.tasks.update(
                        {'user': data['user']},
                        {'$set': {
                            'user': data['user'],
                            'type': TASK_DOWNLOAD,
                            'processing': TASK_NOT_IN_PROCESSING,
                            'host': data['host']
                        }},
                        upsert=True
                    )
                elif data['type'] == TASK_MARK:
                    if data['data']:
                        self._db.tasks.insert_many(data['data'])
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

    def add_next_tasks(self, user: str, task_type: int) -> Optional[bool]:
        result = False
        if task_type in self._tasks_after:
            for_insert = [{'user': user, 'type': task, 'processing': TASK_NOT_IN_PROCESSING} for task in self._tasks_after[task_type]]
            try:
                self._db.tasks.insert_many(for_insert)
                result = True
            except Exception as e:
                result = None
                self._log.warning('Can`t add tasks after %s for user %s. Info: %s', task_type, user, e)

        return result

    def get_task(self, users: RssTagUsers) -> dict:
        task = {
            'type': TASK_NOOP,
            'user': None,
            'data': None
        }
        try:
            user_task = self._db.tasks.find_one_and_update(
                {'$or': [{'processing': TASK_NOT_IN_PROCESSING}, {'type': TASK_TAGS}]},
                {'$set': {'processing': time.time()}}
            )
            if user_task:
                data = user_task
                task['user'] = users.get_by_sid(user_task['user'])
                if task['user']:
                    task['type'] = user_task['type']
                    if user_task['type'] == TASK_TAGS:
                        data = []
                        for i in range(self._bath_size):
                            p = self._db.posts.find_one_and_update(
                                {
                                    'owner': task['user']['sid'],
                                    'tags': [],
                                    'processing': POST_NOT_IN_PROCESSING
                                },
                                {'$set': {'processing': time.time()}}
                            )
                            if not p:
                                break
                            data.append(p)

                        if not data:
                            locked_task = self._db.tasks.find_one_and_update(
                                {'_id': user_task['_id'], 'remove': {'$exists': False}},
                                {'$set': {'remove': True}}
                            )
                            task['type'] = TASK_NOOP
                            if locked_task:
                                if self.add_next_tasks(task['user']['sid'], user_task['type']):
                                    self._db.tasks.remove({'_id': user_task['_id']})

                    '''if task_type == TASK_WORDS:
                        if task['type'] == TASK_NOOP:
                            data = db.tags.find_one_and_update(
                                {
                                    'processing': TASK_NOT_IN_PROCESSING,
                                    'worded': {'$exists': False}
                                },
                                {'$set': {'processing': time.time()}}
                            )
                            if data and (data['processing'] == TASK_NOT_IN_PROCESSING):
                                task['type'] = TASK_WORDS'''
                    task['data'] = data
        except Exception as e:
            task['type'] = TASK_NOOP
            self._log.error('Worker can`t get tasks: %s', e)

        #self._log.info('Get task: %s', task)
        return task

    def remove_task(self, _id: str) -> Optional[bool]:
        try:
            self._db.tasks.remove({'_id': _id})#TODO: check result?
            result = True
        except Exception as e:
            result = None
            self._log.error('Remove tasks: %s. Info: %s', _id, e)

        return result

    def finish_task(self, task: dict) -> bool:
        remove_task = True
        try:
            if task['type'] == TASK_TAGS:
                remove_task = False
                for post in task['data']:
                    self._db.posts.find_one_and_update(
                        {'_id': post['_id']},
                        {'$set': {'processing': POST_NOT_IN_PROCESSING}}
                    )
                '''elif task['type'] == TASK_WORDS:
                    self._db.tags.find_one_and_update(
                        {'_id': task['data']['_id']},
                        {'$set': {
                            'processing': POST_NOT_IN_PROCESSING,
                            'worded': True
                        }}
                    )'''

            if remove_task:
                removed = self.remove_task(task['data']['_id'])
                if removed and ((task['type'] == TASK_W2V) or (task['type'] == TASK_DOWNLOAD) or (task['type'] == TASK_NER)):
                    self.add_next_tasks(task['user']['sid'], task['type'])

            result = True
        except Exception as e:
            result = False
            self._log.error('Can`t finish task %s, type %s. Info: %s', task['data']['_id'], task['type'], e)

        return result

    def get_current_tasks_titles(self, user_id: str) -> Optional[List[str]]:
        try:
            curr = self._db.tasks.find({
                'user': user_id
            })
            task_types = set()
            result = []
            for task in curr:
                if task['type'] not in task_types:
                    task_types.add(task['type'])
                    result.append(self.get_task_title(task['type']))

        except Exception as e:
            result = None
            self._log.error('Can`t get user tasks state %s. Info: %s', user_id, e)

        return result

    def get_task_title(self, task_type: int) -> str:
        task_titles = {
            TASK_DOWNLOAD: 'Downloading posts from provider',
            TASK_MARK: 'Sync posts "read" state with provider',
            TASK_TAGS: 'Bulding posts tags',
            TASK_WORDS: '',
            TASK_LETTERS: 'Buildings first letters dictionary',
            TASK_NER: 'Named entity recognition',
            TASK_CLUSTERING: 'Posts clusterization',
            TASK_W2V: 'Learning Word2Vec',
            TASK_D2V: 'Learning Doc2Vec',
            TASK_TAGS_SENTIMENT: 'Tags sentiment',
            TASK_TAGS_GROUP: 'Tags groups searching',
            TASK_TAGS_COORDS: 'Searching geo objects in tags',
            TASK_BIGRAMS_RANK: 'Bi-grams ranking'
        }

        if task_type in task_titles:
            result = task_titles[task_type]
        else:
            result = ''
            self._log.error('Unknow task type "%s"', task_type)

        return result

    def freeze_tasks(self, user: dict, type: int) -> Optional[bool]:
        try:
            query = {'user': user['sid']}
            if type != TASK_ALL:
                query['type'] = type
            self._db.tasks.update_many(
                query,
                {'$set': {'processing': TASK_FREEZED}}
            )  # TODO: check result?
            result = True
        except Exception as e:
            result = None
            self._log.error('Can`t freeze tasks? user %s, type %s. Info: %s', user['sid'], type, e)

        return result

    def unfreeze_tasks(self, user: dict, type: int) -> Optional[bool]:
        try:
            query = {'user': user['sid']}
            if type != TASK_ALL:
                query['type'] = type
            self._db.tasks.update_many(
                query,
                {'$set': {'processing': TASK_NOT_IN_PROCESSING}}
            )  # TODO: check result?
            result = True
        except Exception as e:
            result = None
            self._log.error('Can`t freeze tasks? user %s, type %s. Info: %s', user['sid'], type, e)

        return result