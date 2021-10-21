import os
import logging
from collections import defaultdict
from typing import List, Tuple
from gensim.models.word2vec import Word2Vec


class W2VLearn:
    def __init__(self, path: str) -> None:
        self._log = logging.getLogger("W2VLearn")
        self._path = path
        if os.path.exists(self._path):
            self._model = Word2Vec.load(self._path)
        else:
            self._model = None

    def learn(self, texts: List[Tuple[str, int]]):
        words = []
        n_epochs = 30
        for i, tagged_text in enumerate(texts):
            words.append(tagged_text[0].split())

        if self._model:
            self._model.train(words, total_examples=len(words), epochs=n_epochs)
        else:
            self._model = Word2Vec(
                words,
                window=15,
                epochs=n_epochs,
                sample=1e-5,
                min_count=0,
                workers=os.cpu_count(),
            )
        self._model.save(self._path)

    def make_groups(self, tags: List[str], top_n: int = 10, koef: float = 0.3):
        groups = defaultdict(set)
        if self._model:
            for tag in tags:
                try:
                    similar_tags = self._model.wv.similar_by_word(tag, topn=top_n)
                    for sim_tag, val in similar_tags:
                        if val >= koef:
                            groups[sim_tag].add(tag)
                except Exception as e:
                    self._log.warning("Error in w2v.make_groups. Info: %s", e)

        return groups

    def reduce_groups(self, groups: dict, top_n: int = 10, koef: float = 0.3) -> dict:
        reduced = {}
        new_groups = defaultdict(set)
        if self._model:
            for tag, tags in groups.items():
                try:
                    similar_tags = self._model.wv.similar_by_word(tag, topn=top_n)
                    for sim_tag, val in similar_tags:
                        if (val >= koef) and (sim_tag in groups):
                            new_groups[sim_tag].add(tag)
                except Exception as e:
                    self._log.warning("Error in w2v.reduce_groups. Info: %s", e)

        for tag, tags_set in new_groups.items():
            s = set()
            for st in tags_set:
                s.update(st)
            reduced["tag"] = s

        return reduced

