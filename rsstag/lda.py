from typing import List
import logging

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from nltk.corpus import stopwords

class LDA:
    def __init__(self) -> None:
        self.log = logging.getLogger('LDA')

    def topics(self, texts: List[str], topics_n: int=10, top_k: int = 10) -> List[str]:
        stopw = set(stopwords.words('english') + stopwords.words('russian'))
        vectorizer = TfidfVectorizer(stop_words=stopw)
        vectors = vectorizer.fit_transform(texts)
        model = LatentDirichletAllocation(n_components=topics_n)
        model.fit(vectors)
        ftrs = vectorizer.get_feature_names()
        topics = set()
        for i in range(topics_n):
            indxs = model.components_[i].argsort()
            topics.update([ftrs[indx] for indx in indxs[-top_k:]])

        return list(topics)