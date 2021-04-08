"""Build tags from text. Support languages: english, russian"""
import re
import logging
from collections import defaultdict
from typing import List, Dict
import pymorphy2
from nltk.stem import PorterStemmer
from nltk.corpus import stopwords

class TagsBuilder:
    """Build tags from text. Support languages: english, russian"""
    def __init__(self, text_clean_re: str="[^\w\d ]") -> None:
        self.purge()
        '''self._text = ''
        self._prepared_text = ''
        self._words = {}
        self._bi_grams = {}
        self._bi_grams_words = defaultdict(set)'''
        self.text_clearing = re.compile(text_clean_re)
        self.only_cyrillic = re.compile(r'^[а-яА-ЯёЁ]*$')
        self.only_latin = re.compile(r'^[a-zA-Z]*$')
        self.clear_html_esc = re.compile(r'&[#a-zA-Z0-9]*?;')
        self.latin = PorterStemmer()
        self.cyrillic = pymorphy2.MorphAnalyzer()
        self._stopwords = None
        self._log = logging.getLogger('TagsBuilder')
        self._window = 2

    def purge(self) -> None:
        """Clear state"""
        self._text = ''
        self._tags: defaultdict = defaultdict(int)
        self._words = defaultdict(set)
        self._prepared_text = ''
        self._bi_grams = {}
        self._bi_grams_words = defaultdict(set)

    def text2words(self, text: str) -> List[str]:
        """Make words list from text"""
        text = self.clear_html_esc.sub(' ', text)
        text = self.text_clearing.sub(' ', text)
        text = text.strip().casefold()
        words = text.split()

        return words

    def process_word(self, current_word: str) -> str:
        """Make tag/token from gven word"""
        tag = ''
        try:
            current_word = current_word.strip().casefold()
            word_length = len(current_word)
            if self.only_cyrillic.match(current_word):
                temp = self.cyrillic.parse(current_word)
                if temp:
                    tag = temp[0].normal_form
                else:
                    tag = current_word
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
        except Exception as e:
            self._log.error('Can`t add to stat word: "%s". Info: %s', current_word, e)

        return tag

    def get_tags(self) -> defaultdict:
        """Get builded tags"""
        return self._tags

    def get_words(self) -> Dict[str, set]:
        """Get words grouped by tag"""
        return self._words

    def get_bi_grams(self) -> dict:
        """Get bi-grams"""
        return self._bi_grams

    def get_bi_grams_words(self) -> dict:
        """Return words for bi-grams"""
        return self._bi_grams_words

    def build_tags(self, text: str) -> None:
        """Build tags and words from text"""
        self._text = text
        words = self.text2words(text)
        for current_word in words:
            tag = self.process_word(current_word)
            if tag:
                self._tags[tag] += 1
                self._words[tag].add(current_word)

    def build_bi_grams(self, text: str) -> None:
        words = self.text2words(text)
        if words:
            prev_word = words[0]
            prev_tag = self.process_word(prev_word)
            for current_word in words[1:]:
                current_tag = self.process_word(current_word)
                if current_tag:
                    bi_gram = prev_tag + ' ' + current_tag
                    if bi_gram not in self._bi_grams:
                        self._bi_grams[bi_gram] = {prev_tag, current_tag}
                    self._bi_grams_words[bi_gram].add(prev_word)
                    self._bi_grams_words[bi_gram].add(current_word)
                    prev_word = current_word
                    prev_tag = current_tag

    def build_tags_and_bi_grams(self, text: str) -> None:
        """Build tags and words from text"""
        self._text = text
        words = self.text2words(text)
        if not words:
            return
        post_bis = set()
        lemmas = []
        for word_pos, word in enumerate(words):
            tag = self.process_word(word)
            if not tag:
                continue
            lemmas.append(tag)
            self._tags[tag] += 1
            self._words[tag].add(word)
            for i in range(self._window):
                i += 1
                bi_words = []
                prev_pos = word_pos - i
                if prev_pos >= 0:
                    bi_words.append(words[prev_pos])
                next_pos = word_pos + i
                if next_pos < len(words):
                    bi_words.append(words[next_pos])
                for bi_word in bi_words:
                    bi_tag = self.process_word(bi_word)
                    bi_grams_l = [tag, bi_tag]
                    bi_grams_l.sort()
                    bi_gram = " ".join(bi_grams_l)
                    if bi_gram in post_bis:
                        continue
                    post_bis.add(bi_gram)
                    if bi_gram not in self._bi_grams:
                        self._bi_grams[bi_gram] = {tag, bi_tag}
                    self._bi_grams_words[bi_gram].add(word)
                    self._bi_grams_words[bi_gram].add(bi_word)
        self._prepared_text = " ".join(lemmas)

    def get_prepared_text(self) -> str:
        """Get text prepared for Doc2Vec"""
        return self._prepared_text

    def prepare_text(self, text: str, ignore_stopwords: bool=False) -> None:
        """Prepare text for Doc2vec"""
        self._text = text
        words = self.text2words(text)
        self._prepared_text = ''
        tags = []
        self._stopwords = set(stopwords.words('english') + stopwords.words('russian'))
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
        self._prepared_text = ' '.join(tags)
