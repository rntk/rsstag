import os
import gzip
from rsstag.utils import load_config
from pymongo import MongoClient
from rsstag.tags_builder import TagsBuilder
from gensim.models.doc2vec import Doc2Vec, TaggedDocument

class D2VLearn:
    _texts = []

    def __init__(self, config_path: str) -> None:
        self._config = load_config(config_path)
        cl = MongoClient(self._config['settings']['db_host'], int(self._config['settings']['db_port']))
        self.db = cl.rss

    def fetch_texts(self) -> None:
        cursor = self.db.posts.find({})
        builder = TagsBuilder(self._config['settings']['replacement'])
        for post in cursor:
            text = post['content']['title'] + ' ' + gzip.decompress(post['content']['content']).decode('utf-8', 'replace')
            builder.purge()
            builder.prepare_text(text)
            self._texts.append(builder.get_prepared_text())

    def learn(self):
        tagged_docs = []
        for i, text in enumerate(self._texts):
            tagged_docs.append(TaggedDocument(text.split(), [i]))

        if os.path.exists(self._config['settings']['model']):
            model = Doc2Vec.load(self._config['settings']['model'])
            model.train(tagged_docs)
        else:
            model = Doc2Vec(tagged_docs, iter=30, sample=1e-5, workers=os.cpu_count())
        model.save(self._config['settings']['model'])
