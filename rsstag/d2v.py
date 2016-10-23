import os
import gzip
from rsstag.utils import load_config
from pymongo import MongoClient
from rsstag.tags_builder import TagsBuilder
from rsstag.html_cleaner import HTMLCleaner
from gensim.models.doc2vec import Doc2Vec, TaggedDocument

class D2VLearn:
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
        tagged_docs = []
        for i, tagged_text in enumerate(self._tagged_texts):
            tagged_docs.append(TaggedDocument(tagged_text[0].split(), [tagged_text[1]]))

        if os.path.exists(self._config['settings']['d2v_model']):
            model = Doc2Vec.load(self._config['settings']['d2v_model'])
            model.train(tagged_docs)
        else:
            model = Doc2Vec(tagged_docs, iter=30, sample=1e-5, min_count=2, workers=os.cpu_count())
        model.save(self._config['settings']['d2v_model'])
