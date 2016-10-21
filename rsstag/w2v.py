import os
import gzip
from rsstag.utils import load_config
from pymongo import MongoClient
from rsstag.tags_builder import TagsBuilder
from rsstag.html_cleaner import HTMLCleaner
from gensim.models.word2vec import Word2Vec

class W2VLearn:
    _tagged_texts = []

    def __init__(self, config_path: str) -> None:
        self._config = load_config(config_path)
        cl = MongoClient(self._config['settings']['db_host'], int(self._config['settings']['db_port']))
        self.db = cl.rss

    def fetch_texts(self) -> None:
        cursor = self.db.posts.find({})
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

        if os.path.exists(self._config['settings']['w2v_model']):
            model = Word2Vec.load(self._config['settings']['w2v_model'])
            model.train(words)
        else:
            model = Word2Vec(words, iter=30, sample=1e-5, workers=os.cpu_count())
        model.save(self._config['settings']['w2v_model'])