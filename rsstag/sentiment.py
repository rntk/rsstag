"""
Determine words sentiment
"""
import os
import logging
import textwrap
from collections import defaultdict
from typing import List, Iterable

class SentimentConverter:
    """
    Map different sentiment/affects label to "standart" labels (positive, negative, neutral, positive/negative)
    """
    def __init__(self):
        self._map = {
            'anger': 'negative',
            'disgust': 'negative',
            'fear': 'negative',
            'joy': 'positive',
            'sadness': 'negative',
            'surprise': 'positive'
        }

    def convert_sentiment(self, sentiments: Iterable[str]) -> List[str]:
        return [self._map[sentiment] for sentiment in sentiments if sentiment in self._map]


class RuSentiLex:
    """
    Wrapper for determine russian words sentiment. Use dictionary from http://www.labinform.ru/pub/rusentilex/index.htm
    """
    def __init__(self, strings: List[str], splitter:str=',', comment_symbol: str='!') -> None:
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
        self.load(strings, self._splitter, self._comment_symbol)


    def load(self, strings: List[str], splitter: str, comment_symbol: str) -> None:
        if strings:
            for s in strings:
                if s.strip() == '':
                    continue
                if s[0] == comment_symbol:
                    continue
                data = s.split(splitter)
                if data:
                    words = [data[self._positions['word']].strip()]
                    sentiment = data[self._positions['sentiment']].strip()
                    words += data[self._positions['lemma']].strip().split('/')
                    for word in words:
                        self._sentiments[word].add(sentiment)

    def get_sentiment(self, word: str) -> List[str]:
        return list(self._sentiments[word])
