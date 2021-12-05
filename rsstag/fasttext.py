import os
import logging
from collections import defaultdict
from typing import List, Tuple
from gensim.models.fasttext import FastText


class FastTextLearn:
    def __init__(self, path: str) -> None:
        self._log = logging.getLogger("FastTextLearn")
        self._path = path
        if os.path.exists(self._path):
            self._model = FastText.load(self._path)
        else:
            self._model = None

    def learn(self, texts: List[Tuple[str, int]]):
        words = []
        n_epochs = 30
        for i, tagged_text in enumerate(texts):
            words.append(tagged_text[0].split())

        if self._model:
            self._model.build_vocab(sentences=words)
            self._model.train(sentences=words, total_examples=len(words), epochs=n_epochs)
        else:
            self._model = FastText(
                sentences=words,
                window=5,
                epochs=n_epochs,
                min_count=1,
                workers=os.cpu_count(),
            )
        self._model.save(self._path)
