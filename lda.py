import os
import gzip
from rsstag.utils import load_config
from pymongo import MongoClient
from rsstag.tags_builder import TagsBuilder
from rsstag.html_cleaner import HTMLCleaner
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation


class LDATopics:
    def __init__(self, config_path: str) -> None:
        self._config = load_config(config_path)
        cl = MongoClient(
            self._config["settings"]["db_host"],
            int(self._config["settings"]["db_port"]),
        )
        self.db = cl[self._config["settings"]["db_name"]]
        self._texts = []
        self._n_features = 200
        self._n_topics = 500

    def print_top_words(self, model, feature_names, n_top_words):
        all_topics = set()
        for topic_idx, topic in enumerate(model.components_):
            current_topics = []
            print("Topic #{}:".format(topic_idx))
            for i in topic.argsort()[: -n_top_words - 1 : -1]:
                current_topics.append(feature_names[i])
                all_topics.add(feature_names[i])
            print(" ".join(current_topics))

        print(all_topics)
        print()

    def fetch_texts(self) -> None:
        cursor = self.db.posts.find({})
        builder = TagsBuilder(self._config["settings"]["replacement"])
        cleaner = HTMLCleaner()
        for post in cursor:
            # self._texts.append(post['content']['title'] + ' ' + gzip.decompress(post['content']['content']).decode('utf-8', 'replace'))
            text = (
                post["content"]["title"]
                + " "
                + gzip.decompress(post["content"]["content"]).decode("utf-8", "replace")
            )
            cleaner.purge()
            cleaner.feed(text)
            strings = cleaner.get_content()
            text = " ".join(strings)
            builder.purge()
            builder.prepare_text(text, ignore_stopwords=True)
            self._texts.append(builder.get_prepared_text())

    def learn(self):
        vectorizer = TfidfVectorizer(
            max_df=7000, min_df=2000, max_features=self._n_features
        )
        # vectorizer = CountVectorizer(max_df=0.9, min_df=2, max_features=self._n_features)
        vectors = vectorizer.fit_transform(open("lda_data.txt", "r"))
        print(vectorizer.get_feature_names())
        exit()
        # vectors = vectorizer.fit_transform(self._texts)
        lda = LatentDirichletAllocation(
            n_topics=self._n_topics,
            max_iter=5,
            learning_method="online",
            learning_offset=20.0,
            random_state=0,
        )
        lda.fit(vectors)
        tf_feature_names = vectorizer.get_feature_names()
        self.print_top_words(lda, tf_feature_names, 100)


if __name__ == "__main__":
    lda = LDATopics("./rsscloud.conf")
    # lda.fetch_texts()
    """f = open('lda_data_stop.txt', 'w')
    f.write('\n'.join(lda._texts))
    f.close()"""
    lda.learn()
