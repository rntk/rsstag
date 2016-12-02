from typing import List, Iterator
import re
import unicodedata
from collections import defaultdict
from rsstag.html_cleaner import HTMLCleaner
import pymorphy2
import nltk

class RssTagEntityExtractor:
    """
    Simple NER. Word is entity if istitle() == True
    """
    def __init__(self):
        self._html_cleaner = HTMLCleaner()
        self._lemmer_ru = pymorphy2.MorphAnalyzer()
        self._stemmer_ru = nltk.stem.snowball.RussianStemmer()
        self._stemmer_en = nltk.stem.PorterStemmer()
        self._only_cyrillic = re.compile('^[А-яЁё_-]*$')
        self._only_latin = re.compile('^[A-z_-]*$')
        self._delimiter = ' '
        self._stopwords = set(nltk.corpus.stopwords.words('english') + nltk.corpus.stopwords.words('russian'))
        self._words_stat = defaultdict(lambda: {'u': 0, 'l': 0})

    def find_geo_entities(self, entities: List[str]) -> List[str]:
        pass

    def tokenize_text(self, text: str) -> Iterator:
        self._html_cleaner.purge()
        self._html_cleaner.feed(text)
        text = ' '.join(self._html_cleaner.get_content())
        token = ''
        sign = ''
        delimiter = False
        add_to_token = False
        for letter in text:
            letter_category = unicodedata.category(letter)
            if (letter_category == 'Ll') or (letter_category == 'Lu') or (letter_category == 'Nd'):
                add_to_token = True
            elif letter.isspace():
                delimiter = True
            elif (letter == '-') and token:
                add_to_token = True
            else:
                delimiter = True
                sign = letter
            if add_to_token:
                token += letter
                add_to_token = False
            if delimiter:
                delimiter = False
                if token:
                    yield token
                    token = ''
                if sign:
                    yield sign
                    sign = ''

    def treat_entities(self, entities: List[list]) -> List[str]:
        new_entities = []
        for entity in entities:
            new_entity = []
            for word in entity:
                word = word.casefold()
                new_word = ''
                if len(word) > 2:
                    if self._only_cyrillic.match(word):
                        morphy = self._lemmer_ru.parse(word)
                        if morphy:
                            if (morphy[0].tag.POS == 'NOUN') and (morphy[0].tag.number == 'sing'):
                                new_word = morphy[0].normal_form
                    elif self._only_latin.match(word):
                        new_word = self._stemmer_en.stem(word)
                    else:
                        new_word = word
                else:
                    new_word = word
                if new_word:
                    new_entity.append(new_word)
            if new_entity:
                new_entities.append(new_entity)

        return new_entities

    def clean_entity(self, entity: List[str]) -> List[str]:
        new_entity = []
        for word in entity:
            add_entity = True
            if len(word) > 1:
                if self._only_cyrillic.match(word):
                    s_word = self._stemmer_ru.stem(word)
                elif self._only_latin.match(word):
                    s_word = self._stemmer_en.stem(word)
                else:
                    s_word = word
                if s_word in self._words_stat:
                    add_entity = self._words_stat[s_word]['l'] > 1

            if add_entity:
                new_entity.append(word)

        return new_entity

    def add_to_stat(self, word: str):
        if self._only_cyrillic.match(word):
            s_word = self._stemmer_ru.stem(word)
        elif self._only_latin.match(word):
            s_word = self._stemmer_en.stem(word)
        else:
            s_word = word

        print(word, s_word)
        if s_word.istitle():
            letter_case = 'u'
        else:
            letter_case = 'l'
        self._words_stat[word.casefold()][letter_case] += 1

    def extract_entities(self, text: str) -> List[str]:
        entities = []
        entity = []
        add_to_entity = False
        initial = ''
        for word in self.tokenize_text(text):
            if word.casefold() in self._stopwords:
                continue

            self.add_to_stat(word)
            if word.istitle():
                if len(word) == 1:
                    initial = word
                add_to_entity = True
            elif (word == '.') and entity and initial:
                add_to_entity = True
                initial = ''
            elif entity:
                if entity[-1] != '.':
                    entities.append(entity)
                else:
                    entities.append(entity[:-1])
                entity = []

            if add_to_entity:
                entity.append(word)
                add_to_entity = False

        if entity:
            if entity[-1] != '.':
                entities.append(entity)
            else:
                entities.append(entity[:-1])

        return self.treat_entities(entities)
