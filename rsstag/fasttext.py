import os
import logging
from typing import List, Tuple, Union

from gensim.models.fasttext import FastText
from .posts import PostLemmaSentence


class FastTextLearn:
    def __init__(self, path: str) -> None:
        self._log = logging.getLogger("FastTextLearn")
        self._path = path
        if os.path.exists(self._path):
            self._model = FastText.load(self._path)
        else:
            self._model = None

        self.__n_epochs = 30
        self.__window = 5

    def learn(self, texts: Union[List[Tuple[str, int]], PostLemmaSentence]):
        if isinstance(texts, PostLemmaSentence):
            words = texts
            total = texts.count()
        else:
            words = []
            for i, tagged_text in enumerate(texts):
                words.append(tagged_text[0].split())
            total = len(words)

        if self._model:
            self._model.build_vocab(sentences=words)
            self._model.train(sentences=words, total_examples=total, epochs=self.__n_epochs)
        else:
            self._model = FastText(
                sentences=words,
                window=self.__window,
                epochs=self.__n_epochs,
                min_count=1,
                workers=os.cpu_count(),
            )
        self._model.save(self._path)
