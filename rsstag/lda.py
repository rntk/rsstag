from typing import List
import logging

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from nltk.corpus import stopwords


class LDA:
    def __init__(self) -> None:
        self.log = logging.getLogger("LDA")
        stopw = ["это"]
        self._stopwords = set(
            stopwords.words("english") + stopwords.words("russian") + stopw
        )

    def topics(
        self, texts: List[str], topics_n: int = 10, top_k: int = 10
    ) -> List[str]:
        vectorizer = TfidfVectorizer(stop_words=list(self._stopwords))
        vectors = vectorizer.fit_transform(texts)
        model = LatentDirichletAllocation(n_components=topics_n)
        model.fit(vectors)
        ftrs = vectorizer.get_feature_names_out()
        topics = set()
        for i in range(topics_n):
            indxs = model.components_[i].argsort()
            topics.update([ftrs[indx] for indx in indxs[-top_k:]])

        return list(topics)
