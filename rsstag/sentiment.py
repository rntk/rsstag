"""
Determine words sentiment
"""
from collections import defaultdict
from typing import Tuple

class RuSentiLex:
    """
    Wrapper for determine russian words sentiment. Use dictionary from http://www.labinform.ru/pub/rusentilex/index.htm
    """
    def __init__(self, file_path: str, splitter:str=',', comment_symbol: str='!') -> None:
        self._path = file_path
        self._sentiments = defaultdict(lambda: set())
        self._splitter = splitter
        self._comment_symbol = comment_symbol
        self._positions = {
            'word': 0,
            'pos': 1, #part of speech
            'lemma': 2,
            'sentiment': 3,
            'source': 4,
            'meaning': 5 #optional, only for words with few meanings
        }
        self.load_file(self._path, self._splitter, self._comment_symbol)


    def load_file(self, path: str, splitter: str, comment_symbol: str) -> None:
        f = open(path, 'r', encoding='utf-8')
        strings = f.read().splitlines()
        f.close()
        if strings:
            for s in strings:
                if s.strip() == '':
                    continue
                if s[0] == comment_symbol:
                    continue
                data = s.split(splitter)
                if data:
                    word = data[self._positions['word']].strip()
                    sentiment = data[self._positions['sentiment']].strip()
                    self._sentiments[word].add(sentiment)

    def get_sentiment(self, word: str) -> Tuple[str]:
        return tuple(self._sentiments[word])
