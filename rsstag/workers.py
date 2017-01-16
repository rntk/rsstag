"""RSSTag workers"""
import logging
import time
import gzip
from random import randint
from multiprocessing import Process
from rsstag.tags_builder import TagsBuilder
from rsstag.html_cleaner import HTMLCleaner
from pymongo import MongoClient, UpdateOne
from rsstag.providers import BazquxProvider
from rsstag.utils import load_config
from rsstag.routes import RSSTagRoutes
from rsstag.users import RssTagUsers
from rsstag.tasks import TASK_NOOP, TASK_DOWNLOAD, TASK_MARK, TASK_TAGS, TASK_WORDS, TASK_TAGS_GROUP, \
    TAG_NOT_IN_PROCESSING, TASK_LETTERS, TASK_TAGS_SENTIMENT, TASK_W2V, TASK_NER, TASK_CLUSTERING
from rsstag.tasks import RssTagTasks
from rsstag.letters import RssTagLetters
from rsstag.tags import RssTagTags
from rsstag.sentiment import RuSentiLex, WordNetAffectRuRom, SentimentConverter

class RSSTagWorker:
    """Rsstag workers handler"""
    def __init__(self, config_path):
        self._config = load_config(config_path)
        self._workers_pool = []
        logging.basicConfig(
            filename=self._config['settings']['log_file'],
            filemode='a',
            level=getattr(logging, self._config['settings']['log_level'].upper())
        )

    def start(self):
        """Start worker"""
        for i in range(int(self._config['settings']['workers_count'])):
            self._workers_pool.append(Process(target=self.worker))
            self._workers_pool[-1].start()
        self._workers_pool[-1].join()

    def clear_user_data(self, db: object, user: dict):
        try:
            db.posts.remove({'owner': user['sid']})
            db.feeds.remove({'owner': user['sid']})
            db.tags.remove({'owner': user['sid']})
            db.bi_grams.remove({'owner': user['sid']})
            db.letters.remove({'owner': user['sid']})
            result = True
        except Exception as e:
            logging.error('Can`t clear user data %s. Info: %s', user['sid'], e)
            result = False

        return result

    def make_tags(self, db: MongoClient, post: dict, builder: TagsBuilder, cleaner: HTMLCleaner) -> bool:
        #logging.info('Start process %s', post['_id'])
        content = gzip.decompress(post['content']['content'])
        text = post['content']['title'] + ' '+ content.decode('utf-8')
        cleaner.purge()
        cleaner.feed(text)
        strings = cleaner.get_content()
        text = ' '.join(strings)
        builder.purge()
        builder.build_tags_and_bi_grams(text)
        tags = builder.get_tags()
        words = builder.get_words()
        bi_grams = builder.get_bi_grams()
        bi_words = builder.get_bi_grams_words()
        result = False
        tags_updates = []
        bi_grams_updates = []
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
                            params={'quoted_tag': tag}
                        ),
                        'processing': TAG_NOT_IN_PROCESSING
                    },
                    '$inc': {'posts_count': 1, 'unread_count': 1},
                    '$addToSet': {'words': {'$each': list(words[tag])}}
                },
                upsert=True
            ))
            first_letters.add(tag[0])

        for bi_gram, bi_value in bi_grams.items():
            bi_grams_updates.append(UpdateOne(
                {'owner': post['owner'], 'tag':bi_gram},
                {
                    '$set': {
                        'read': False,
                        'tag': bi_gram,
                        'owner': post['owner'],
                        'temperature': 0,
                        'local_url': routes.getUrlByEndpoint(
                            endpoint='on_bi_gram_get',
                            params={'bi_gram': bi_gram}
                        ),
                        'tags': list(bi_value),
                        'processing': TAG_NOT_IN_PROCESSING
                    },
                    '$inc': {'posts_count': 1, 'unread_count': 1},
                    '$addToSet': {'words': {'$each': list(bi_words[bi_gram])}}
                },
                upsert=True
            ))

        post_tags = {}
        if tags_updates:
            post_tags['tags'] = tags
        if bi_grams_updates:
            post_tags['bi_grams'] = list(bi_grams.keys())
        try:
            db.posts.update({'_id': post['_id']}, {'$set': post_tags})
            db.tags.bulk_write(tags_updates, ordered=False)
            db.bi_grams.bulk_write(bi_grams_updates, ordered=False)
            result = True
        except Exception as e:
            result = False
            logging.error('Can`t save tags/bi-grams for post %s. Info: %s', post['_id'], e)
        #logging.info('Processed %s', post['_id'])

        return result

    def process_words(self, db: MongoClient, tag: dict) -> bool:
        seconds_interval = 3600
        current_time = time.time()
        max_repeats = 5
        result = True
        word_query = {'word': tag['tag'], 'owner': tag['owner']}
        for i in range(0, max_repeats):
            try:
                word = db.words.find_one(word_query)
                if word:
                    old_mid = sum(word['numbers']) / len(word['numbers'])
                    time_delta = current_time - word['it']
                    if time_delta > seconds_interval:
                        update_query = {
                            '$set': {'it': current_time},
                            '$push': {'numbers': tag['posts_count']}
                        }
                        word['numbers'].append(tag['posts_count'])
                        new_mid = sum(word['numbers']) / len(word['numbers'])
                    else:
                        numbers_length = len(word['numbers']) - 1
                        key_name = 'numbers.' + str(numbers_length)
                        update_query = {
                            '$inc': {key_name: tag['posts_count']}
                        }
                        word['numbers'][-1] += tag['posts_count']
                        new_mid = sum(word['numbers']) / len(word['numbers'])
                    temperature = abs(new_mid - old_mid)
                    db.tags.find_one_and_update(
                        {'tag': tag['tag'], 'owner': tag['owner']},
                        {'$set': {'temperature': temperature}}
                    )
                    db.words.find_one_and_update(word_query, update_query)
                else:
                    db.words.insert({
                        'word': tag['tag'],
                        'owner': tag['owner'],
                        'numbers': [tag['posts_count']],
                        'it': current_time
                    })
            except Exception as e:
                result = False
                logging.error('Can`t process word %s for user %s. Info: %s', tag['tag'], tag['owner'], e)
            if result:
                break
            else:
                time.sleep(randint(3,10))

        return result

    def make_letters(self, db, owner: str, config: dict):
        router = RSSTagRoutes(config['settings']['host_name'])
        letters = RssTagLetters(db)
        tags = RssTagTags(db)
        all_tags = tags.get_all(owner, projection={'tag': True, 'unread_count': True})
        result = False
        if all_tags:
            result = letters.sync_with_tags(owner, all_tags, router)

        return result

    def worker(self):
        """Worker for bazqux.com"""
        cl = MongoClient(self._config['settings']['db_host'], int(self._config['settings']['db_port']))
        db = cl[self._config['settings']['db_name']]

        provider = BazquxProvider(self._config)
        builder = TagsBuilder(self._config['settings']['replacement'])
        cleaner = HTMLCleaner()
        users = RssTagUsers(db)
        tasks = RssTagTasks(db)
        letters = RssTagLetters(db)
        while True:
            task = tasks.get_task(users)
            if task['type'] == TASK_NOOP:
                time.sleep(randint(3, 8))
                continue
            if task['type'] == TASK_DOWNLOAD:
                logging.info('Start downloading for user')
                if self.clear_user_data(db, task['user']):
                    posts, feeds = provider.download(task['user'])
                    if posts:
                        logging.info('Try save data in db. Posts: %s. Feeds: %s', len(posts), len(feeds))
                        try:
                            db.feeds.insert_many(feeds)
                            db.posts.insert_many(posts)
                            task_done = True
                        except Exception as e:
                            task_done = False
                            logging.error('Can`t save in db for user %s. Info: %s', task['user']['sid'], e)
            elif task['type'] == TASK_MARK:
                task_done = provider.mark(task['data'], task['user'])
            elif task['type'] == TASK_TAGS:
                task_done = self.make_tags(db, task['data'], builder, cleaner)
            elif task['type'] == TASK_LETTERS:
                task_done = self.make_letters(db, task['user']['sid'], self._config)
            elif task['type'] == TASK_NER:
                task_done = True
            elif task['type'] == TASK_TAGS_SENTIMENT:
                task_done = True
            elif task['type'] == TASK_CLUSTERING:
                task_done = True
            elif task['type'] == TASK_TAGS_GROUP:
                task_done = True
            elif task['type'] == TASK_W2V:
                task_done = True
            '''elif task['type'] == TASK_WORDS:
                task_done = self.process_words(db, task['data'])'''

            if task_done:
                tasks.finish_task(task)
                if task['type'] == TASK_TAGS_GROUP:
                    users.update_by_sid(task['user']['sid'], {'ready': True, 'in_queue': False})
