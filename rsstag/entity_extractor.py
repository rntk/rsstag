from typing import List, Iterator
from unicodedata import category as get_letter_category
import nltk

class RssTagEntityExtractor:
    def __init__(self):
        self._stopwords = set(nltk.corpus.stopwords.words('english') + nltk.corpus.stopwords.words('russian'))
        pass

    def find_geo_entities(self, entities: List[str]) -> List[str]:
        pass

    def tokenize_text(self, text: str) -> Iterator:
        token = ''
        sign = ''
        delimiter = False
        add_to_token = False
        for letter in text:
            letter_category = get_letter_category(letter)
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

    def extract_entities(self, text: str, delimiter='_') -> List[str]:
        entities = []
        entity = []
        add_to_entity = False
        initial = ''
        for word in self.tokenize_text(text):
            if word.casefold() in self._stopwords:
                continue

            if word.istitle():
                if len(word) == 1:
                    initial = word
                add_to_entity = True
            elif (word == '.') and entity and initial:
                add_to_entity = True
                initial = ''
            elif entity:
                entities.append(' '.join(entity))
                entity = []

            if add_to_entity:
                entity.append(word)
                add_to_entity = False

        if entity:
            entities.append(' '.join(entity))

        return entities
