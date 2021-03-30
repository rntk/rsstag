"""RSSTag workers"""
import logging
import time
import gzip
from _collections import defaultdict
from typing import Optional
from random import randint
from multiprocessing import Process
from rsstag.tags_builder import TagsBuilder
from rsstag.html_cleaner import HTMLCleaner
from pymongo import MongoClient, UpdateOne
from rsstag.providers import BazquxProvider, TelegramProvider
from rsstag.utils import load_config
from rsstag.routes import RSSTagRoutes
from rsstag.users import RssTagUsers
from rsstag.tasks import TASK_NOOP, TASK_DOWNLOAD, TASK_MARK, TASK_TAGS, TASK_WORDS, TASK_TAGS_GROUP, \
    TAG_NOT_IN_PROCESSING, TASK_LETTERS, TASK_TAGS_SENTIMENT, TASK_W2V, TASK_NER, TASK_CLUSTERING
from rsstag.tasks import RssTagTasks
from rsstag.letters import RssTagLetters
from rsstag.tags import RssTagTags
from rsstag.posts import RssTagPosts
from rsstag.entity_extractor import RssTagEntityExtractor
from rsstag.w2v import W2VLearn
from rsstag.sentiment import RuSentiLex, WordNetAffectRuRom, SentimentConverter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
from nltk.corpus import stopwords


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
        post_tags = {"lemmas": gzip.compress(builder.get_prepared_text().encode('utf-8', 'replace'))}
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

    def make_ner(self, db, owner: str) -> Optional[bool]:
        result = False
        posts = RssTagPosts(db)
        all_posts = posts.get_all(owner, projection={'content': True, 'pid': True})
        count_ent = defaultdict(int)
        if all_posts:
            ent_ex = RssTagEntityExtractor()
            for post in all_posts:
                text = post['content']['title'] + ' ' + gzip.decompress(post['content']['content']).decode('utf-8', 'ignore')
                if not text:
                    continue
                entities = ent_ex.extract_entities(text)
                for e_i, entity in enumerate(entities):
                    cl_entity = ent_ex.clean_entity(entity)
                    if not cl_entity:
                        continue
                    for word in entity:
                        if len(word) > 1:
                            count_ent[word] += 1

        if count_ent:
            logging.info('Found %s entities for user %s', len(count_ent), owner)
            tags = RssTagTags(db)
            result = tags.add_entities(owner, count_ent, replace=True)

        return result

    def make_clustering(self, db, owner: str) -> Optional[bool]:
        result = False
        posts = RssTagPosts(db)
        all_posts = posts.get_all(owner, projection={'lemmas': True, 'pid': True})
        clusters = None
        texts_for_vec = []
        post_pids = []
        if all_posts:
            for post in all_posts:
                post_pids.append(post['pid'])
                text = gzip.decompress(post["lemmas"]).decode('utf-8', 'ignore')
                texts_for_vec.append(text)

        if texts_for_vec:
            vectorizer = TfidfVectorizer(stop_words=set(stopwords.words('english') + stopwords.words('russian')))
            dbs = DBSCAN(eps=0.9, min_samples=2, n_jobs=1)
            dbs.fit(vectorizer.fit_transform(texts_for_vec))
            clusters = defaultdict(set)
            for i, cluster in enumerate(dbs.labels_):
                clusters[int(cluster)].add(post_pids[i])

            if clusters and -1 in clusters:
                del clusters[-1]

        if clusters:
            logging.info('Posts: %s. Clusters: %s. User: %s', len(all_posts), len(clusters), owner)
            result = posts.set_clusters(owner, clusters)

        return result

    def make_w2v(self, db, owner: str, config: dict) -> Optional[bool]:
        result = False
        posts = RssTagPosts(db)
        all_posts = posts.get_all(owner, projection={'lemmas': True, 'pid': True})
        tagged_texts = []
        if all_posts:
            for post in all_posts:
                text = gzip.decompress(post["lemmas"]).decode('utf-8', 'replace')
                tag = post['pid']
                tagged_texts.append((text, tag))
        if tagged_texts:
            try:
                learn = W2VLearn(db, config)
                learn._tagged_texts = tagged_texts
                learn.learn()
                result = True
            except Exception as e:
                result = None
                logging.error('Can`t W2V. Info: %s', e)

        return result

    def make_tags_groups(self, db, owner: str, config: dict) -> Optional[bool]:
        result = False
        tags_h = RssTagTags(db)
        all_tags = tags_h.get_all(owner, projection={'tag': True})
        if all_tags:
            try:
                learn = W2VLearn(db, config)
                koef = 0.6
                top_n = 10
                groups = learn.make_groups([tag['tag'] for tag in all_tags], top_n, koef)
                tag_groups = defaultdict(list)
                for group, tags in groups.items():
                    if len(tags) > 3:
                        for tag in tags:
                            tag_groups[tag].append(group)
                if tag_groups:
                    tags_h.add_groups(owner, tag_groups)
                result = True
            except Exception as e:
                result = None
                logging.error('Can`t group tags. Info: %s', e)

        return result

    def make_tags_sentiment(self, db, owner: str, config: dict) -> Optional[bool]:
        """
            TODO: may be will be need RuSentiLex and WordNetAffectRuRom caching
        """
        result = True
        tags = RssTagTags(db)
        all_tags = tags.get_all(owner, projection={'tag': True})
        if all_tags:
            try:
                f = open(config['settings']['sentilex'], 'r', encoding='utf-8')
                strings = f.read().splitlines()
                ru_sent = RuSentiLex()
                wrong = ru_sent.sentiment_validation(strings, ',', '!')
                i = 0
                if not wrong:
                    ru_sent.load(strings, ',', '!')
                    all_tags = db.tags.find({}, {'tag': True})
                    wna_dir = config['settings']['lilu_wordnet']
                    wn_en = WordNetAffectRuRom('en', 4)
                    wn_en.load_dicts_from_dir(wna_dir)
                    wn_ru = WordNetAffectRuRom('ru', 4)
                    wn_ru.load_dicts_from_dir(wna_dir)
                    conv = SentimentConverter()
                    for tag in all_tags:
                        sentiment = ru_sent.get_sentiment(tag['tag'])
                        if not sentiment:
                            affects = wn_en.get_affects_by_word(tag['tag'])
                            '''if not affects:
                                affects = wn_en.search_affects_by_word(tag['tag'])'''
                            if not affects:
                                affects = wn_ru.get_affects_by_word(tag['tag'])
                            '''if not affects:
                                affects = wn_ru.search_affects_by_word(tag['tag'])'''
                            if affects:
                                sentiment = conv.convert_sentiment(affects)

                        if sentiment:
                            i += 1
                            sentiment = sorted(sentiment)
                            tags.add_sentiment(owner, tag['tag'], sentiment)
                    result = True
            except Exception as e:
                logging.error('Can`t make tags santiment. Info: %s', e)

        return result #Always True. TODO: refactor or replace by somethin

    def worker(self):
        """Worker for bazqux.com"""
        cl = MongoClient(self._config['settings']['db_host'], int(self._config['settings']['db_port']))
        db = cl[self._config['settings']['db_name']]

        providers = {
            "bazqux": BazquxProvider(self._config),
            "telegram": TelegramProvider(self._config)
        }
        builder = TagsBuilder(self._config['settings']['replacement'])
        cleaner = HTMLCleaner()
        users = RssTagUsers(db)
        tasks = RssTagTasks(db)
        while True:
            task = tasks.get_task(users)
            if task['type'] == TASK_NOOP:
                time.sleep(randint(3, 8))
                continue
            if task['type'] == TASK_DOWNLOAD:
                logging.info('Start downloading for user')
                if self.clear_user_data(db, task['user']):
                    provider = providers[task["user"]["provider"]]
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
                provider = providers[task["user"]["provider"]]
                marked = provider.mark(task['data'], task['user'])
                if marked is None:
                    tasks.freeze_tasks(task['user'], task['type'])
                    users.update_by_sid(task['user']['sid'], {'retoken': True})
                    task_done = False
                else:
                    task_done = marked
            elif task['type'] == TASK_TAGS:
                if task['data']:
                    task_done = self.make_tags(db, task['data'], builder, cleaner)
                else:
                    task_done = True
                    logging.warning('Error while make tags: %s', task)
            elif task['type'] == TASK_LETTERS:
                task_done = self.make_letters(db, task['user']['sid'], self._config)
            elif task['type'] == TASK_NER:
                task_done = self.make_ner(db, task['user']['sid'])
            elif task['type'] == TASK_TAGS_SENTIMENT:
                task_done = self.make_tags_sentiment(db, task['user']['sid'], self._config)
            elif task['type'] == TASK_CLUSTERING:
                task_done = self.make_clustering(db, task['user']['sid'])
            elif task['type'] == TASK_W2V:
                task_done = self.make_w2v(db, task['user']['sid'], self._config)
            elif task['type'] == TASK_TAGS_GROUP:
                task_done = self.make_tags_groups(db, task['user']['sid'], self._config)
            '''elif task['type'] == TASK_WORDS:
                task_done = self.process_words(db, task['data'])'''
            #TODO: add tags_coords, add D2V?
            if task_done:
                tasks.finish_task(task)
                if task['type'] == TASK_TAGS_GROUP:
                    users.update_by_sid(task['user']['sid'], {'ready': True, 'in_queue': False})
