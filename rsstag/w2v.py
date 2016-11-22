import os
import gzip
from collections import defaultdict
from pymongo import MongoClient
from rsstag.tags_builder import TagsBuilder
from rsstag.html_cleaner import HTMLCleaner
from gensim.models.word2vec import Word2Vec

class W2VLearn:
    _tagged_texts = []

    def __init__(self, db, config: dict) -> None:
        self._config = config
        self._db = db
        if os.path.exists(self._config['settings']['w2v_model']):
            self._model = Word2Vec.load(self._config['settings']['w2v_model'])
        else:
            self._model = None

    def fetch_texts(self) -> None:
        cursor = self._db.posts.find({})
        builder = TagsBuilder(self._config['settings']['replacement'])
        cleaner = HTMLCleaner()
        for post in cursor:
            text = post['content']['title'] + ' ' + gzip.decompress(post['content']['content']).decode('utf-8', 'replace')
            cleaner.purge()
            cleaner.feed(text)
            strings = cleaner.get_content()
            text = ' '.join(strings)
            builder.purge()
            builder.prepare_text(text)
            #tag = 'post_'.format(post['pid'])
            tag = post['pid']
            self._tagged_texts.append((builder.get_prepared_text(), tag))

    def learn(self):
        words = []
        for i, tagged_text in enumerate(self._tagged_texts):
            words.append(tagged_text[0].split())

        if self._model:
            self._model.train(words)
        else:
            self._model = Word2Vec(words, window=15, iter=30, sample=1e-5, workers=os.cpu_count())
        self._model.save(self._config['settings']['w2v_model'])

    def make_groups(self, top_n: int=10, koef: float=0.3):
        groups = defaultdict(lambda: set())
        if self._model:
            tags_cur = self._db.tags.find({}, {'tag': True})
            for tag in tags_cur:
                try:
                    similar_tags = self._model.similar_by_word(tag['tag'], topn=top_n)
                    for sim_tag, val in similar_tags:
                        if val >= koef:
                            groups[sim_tag].add(tag['tag'])
                except Exception as e:
                    pass

        return groups

    def reduce_groups(self, groups: dict, top_n: int=10, koef: float=0.3) -> dict:
        reduced = {}
        new_groups = defaultdict(lambda: set())
        if self._model:
            for tag, tags in groups.items():
                try:
                    similar_tags = self._model.similar_by_word(tag, topn=top_n)
                    for sim_tag, val in similar_tags:
                        if (val >= koef) and (sim_tag in groups):
                            new_groups[sim_tag].add(tag)
                except Exception as e:
                    pass

        for tag, tags_set in new_groups.items():
            s = set()
            for st in tags_set:
                s.update(st)
            reduced['tag'] = s

        return reduced