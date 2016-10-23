"""
Class for work with WordNet-Affect data from http://lilu.fcim.utm.md/resourcesRoRuWNA_ru.html
"""

import os
import logging
import textwrap
from typing import Iterable, List

class WordNetAffectRuRomVer2:
    def __init__(self, lang: str='en', grams_n: int=3) -> None:
        """
        Initializing internal structures
        """
        self._langs = {
            'en': 2,
            'ru': 3,
            'rom': 4
        }
        if lang in self._langs:
            self._lang = lang
            self._lang_pos = self._langs[lang]
        else:
            raise Exception('Not support langugage "{}"'.format(lang))
        self._grams_n = grams_n
        self._by_affect = {}
        self._by_word = {}
        self._all_by_id = {}
        self._search_index = {}
        self.log = logging.getLogger('WordNetAffectRuRomVer2')
        self._affects_list = ['anger', 'disgust', 'fear', 'joy', 'sadness', 'surprise']
        self._ids_key = '_'

    def load_dicts_from_dir(self, dir: str) -> None:
        self._dir = dir
        for affect in self._affects_list:
            file_name = os.path.abspath('{}{}{}.txt'.format(self._dir, os.sep, affect))
            if os.path.exists(file_name):
                f = open(file_name, 'r', encoding='utf-8')
                self.build_vocab(affect, f)
                f.close()
            else:
                self.log.warning('Can`t load %s', affect)

    def build_vocab(self, affect: str, data: Iterable) -> None:
        """
        Build internal representation of data from sequence of strings.
        Description of string format: http://lilu.fcim.utm.md/resourcesRoRuWNA_ru.html
        """
        if affect not in self._by_affect:
            self._by_affect[affect] = set()
        for data_line in data:
            info = data_line.strip().split('\t')
            if info and len(info) >= 5:
                words_list = info[self._lang_pos].split()
                self._all_by_id[info[0]] = {
                    'id': info[0],
                    'words': words_list,
                    'affect': affect,
                    'descr': info[1]
                }
                self._by_affect[affect].add(info[0])
                for word in words_list:
                    if word not in self._by_word:
                        self._by_word[word] = set()
                    self._by_word[word].add(info[0])
                self._add_word_in_index(word, info[0])

    def _add_word_in_index(self, word: str, word_id: str) -> None:
        search_keys = self._get_search_keys(word, self._grams_n)
        current_node = self._search_index
        for key in search_keys:
            if key != self._ids_key:
                if key not in current_node:
                    current_node[key] = {self._ids_key: set()}
                current_node[key][self._ids_key].add(word_id)
                current_node = current_node[key]

    def _get_search_keys(self, word: str, n: int=3):
        return textwrap.wrap(word, n)

    def search_affects_by_word(self, word: str) -> List[str]:
        affects = set()
        search_keys = self._get_search_keys(word, self._grams_n)
        last_ids = set()
        current_node = self._search_index
        for key in search_keys:
            if key != self._ids_key:
                if key in current_node:
                    last_ids = current_node[key][self._ids_key]
                    current_node = current_node[key]
                else:
                    break
        for _id in last_ids:
            affects.add(self._all_by_id[_id]['affect'])

        return list(affects)

    def get_affects_by_word(self, word: str) -> List[str]:
        """Return list of affects for given word"""
        affects = set()
        if word in self._by_word:
            for _id in self._by_word[word]:
                affects.add(self._all_by_id[_id]['affect'])

        return list(affects)


    def get_info_by_word(self, word: str) -> List[dict]:
        """Return all info about given word"""
        info = []
        if word in self._by_word:
            for _id in self._by_word[word]:
                info.append(self._all_by_id[_id])

        return info
