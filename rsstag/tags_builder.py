"""Build tags from text. Support languages: english, russian"""

import re
import logging
from collections import defaultdict
from typing import List
from nltk.stem import SnowballStemmer
from rsstag.stopwords import stopwords
from functools import lru_cache


class TagsBuilder:
    """Build tags from text. Support languages: english, russian"""

    def __init__(self, text_clean_re: str = r"[^\w\d ]") -> None:
        self.purge()
        self.text_clearing = re.compile(text_clean_re)
        self.only_cyrillic = re.compile(r"^[а-яА-ЯёЁ]*$")
        self.only_latin = re.compile(r"^[a-zA-Z]*$")
        # self.clear_html_esc = re.compile(r"&[#a-zA-Z0-9]*?;")
        self.latin = SnowballStemmer("english")
        self.cyrillic = SnowballStemmer("russian")
        self._stopwords = None
        self._log = logging.getLogger("TagsBuilder")

    def purge(self) -> None:
        """Clear state"""
        self._text = ""
        self._tags: defaultdict[str, int] = defaultdict(int)
        self._words: defaultdict[str, set[str]] = defaultdict(set)
        self._prepared_text = ""

    def text2words(self, text: str) -> List[str]:
        """Make words list from text"""
        # text = self.clear_html_esc.sub(" ", text)
        text = self.text_clearing.sub(" ", text)
        text = text.strip().casefold()
        words = text.split()

        return words

    def process_word(self, current_word: str) -> str:
        return self.process_word_(current_word.strip().casefold())

    @lru_cache(maxsize=5128)
    def process_word_(self, current_word: str) -> str:
        """Make tag/token from gven word"""
        tag = ""
        try:
            word_length = len(current_word)
            if self.only_cyrillic.match(current_word):
                tag = self.cyrillic.stem(current_word)
            elif self.only_latin.match(current_word):
                tag = self.latin.stem(current_word)
            elif current_word.isnumeric or word_length < 4:
                tag = current_word
            elif word_length == 4 or word_length == 5:
                tag = current_word[:-1]
            elif word_length == 6:
                tag = current_word[:-2]
            else:
                tag = current_word[:-3]

            if not tag:
                tag = current_word
        except Exception as e:
            self._log.error('Can`t add to stat word: "%s". Info: %s', current_word, e)

        return tag

    def get_tags(self) -> defaultdict[str, int]:
        """Get builded tags"""
        return self._tags

    def get_words(self) -> dict[str, set[str]]:
        """Get words grouped by tag"""
        return self._words

    def build_tags(self, text: str) -> None:
        """Build tags and words from text"""
        self._text = text
        words: list[str] = self.text2words(text)
        lemmas: list[str] = []
        for current_word in words:
            tag: str = self.process_word(current_word)
            if tag:
                lemmas.append(tag)
                self._tags[tag] += 1
                self._words[tag].add(current_word)
        self._prepared_text = " ".join(lemmas)

    def get_prepared_text(self) -> str:
        """Get text prepared for Doc2Vec"""
        return self._prepared_text

    def prepare_text(self, text: str, ignore_stopwords: bool = False) -> None:
        """Prepare text for Doc2vec"""
        self._text = text
        words = self.text2words(text)
        self._prepared_text = ""
        tags = []
        self._stopwords = set(stopwords.words("english") + stopwords.words("russian"))
        if ignore_stopwords:
            for current_word in words:
                tag = self.process_word(current_word)
                if tag and tag not in self._stopwords:
                    tags.append(tag)
        else:
            for current_word in words:
                tag = self.process_word(current_word)
                if tag:
                    tags.append(tag)
        self._prepared_text = " ".join(tags)
