'''Build tags from text. Support languages: english, russian'''
import re
import pymorphy2
from nltk.stem import PorterStemmer

class TagsBuilder:
    '''Build tags from text. Support languages: english, russian'''
    def __init__(self, text_clean_re):
        self._text = ''
        self._tags = set()
        self._words = {}
        self.text_clearing = re.compile(text_clean_re)
        self.only_cyrillic = re.compile(r'^[а-яА-ЯёЁ]*$')
        self.only_latin = re.compile(r'^[a-zA-Z]*$')
        self.clear_html_esc = re.compile(r'&[#a-zA-Z0-9]*?;')
        self.latin = PorterStemmer()
        self.cyrillic = pymorphy2.MorphAnalyzer()

    def purge(self):
        '''Clear state'''
        self._text = ''
        self._tags = set()
        self._words = {}

    def get_tags(self):
        '''Get builded tags'''
        return list(self._tags)

    def get_words(self):
        '''Get words grouped by tag'''
        return self._words

    def build_tags(self, text):
        '''Build tags and words from text'''
        self._text = text
        text = self.clear_html_esc.sub(' ', text)
        text = self.text_clearing.sub(' ', text)
        text = text.strip()
        words = text.split()
        for current_word in words:
            current_word = current_word.strip().lower()
            word_length = len(current_word)
            tag = ''
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
            if tag:
                self._tags.add(tag)
                if tag not in self._words:
                    self._words[tag] = set()
                self._words[tag].add(current_word)
