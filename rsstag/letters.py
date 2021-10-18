import logging
from collections import defaultdict
from typing import Optional, List
from rsstag.web.routes import RSSTagRoutes
from rsstag.utils import getSortedDictByAlphabet
from pymongo import MongoClient

class RssTagLetters:
    indexes = ['owner']
    def __init__(self, db: MongoClient) -> None:
        self._db = db
        self._log = logging.getLogger('letters')

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self._db.letters.create_index(index)
            except Exception as e:
                self._log.warning('Can`t create index %s. May be already exists. Info: %s', index, e)

    def get(self, owner: str, make_sort: bool=False) -> Optional[dict]:
        query = {'owner': owner}
        letters = self._db.letters.find_one(query)
        if letters:
            if make_sort:
                letters['letters'] = getSortedDictByAlphabet(letters['letters'])
            result = letters
        else:
            result = {}

        return result

    def to_list(self, letters: dict, only_unread: Optional[bool]=None) -> list:
        if only_unread:
            letters_list = [letter for letter in letters['letters'].values() if letter['unread_count'] > 0]
        else:
            letters_list = list(letters['letters'].values())

        return letters_list

    def change_unread(self, owner: str, letters: dict, readed: bool):
        find_query = {'owner': owner}
        inc_query = {}
        for letter in letters:
            key = 'letters.{}.unread_count'.format(letter)
            inc_query[key] = -letters[letter] if readed else letters[letter]
        if find_query:
            self._db.letters.update_one(find_query, {'$inc': inc_query})

    def sync_with_tags(self, owner: str, tags: List[dict], router: RSSTagRoutes):
        letters = defaultdict(lambda: {'unread_count': 0, 'letter': ''})
        for tag in tags:
            letter = tag['tag'][0]
            if letter not in letters:
                letters[letter]['letter'] = letter
                letters[letter]['local_url'] = router.getUrlByEndpoint(
                    endpoint = 'on_group_by_tags_startwith_get',
                    params = {'letter': letter, 'page_number': 1}
                )
            letters[letter]['unread_count'] += tag['unread_count']

        self._db.letters.update_one(
            {'owner': owner},
            {'$set': {'owner': owner, 'letters': letters}},
            upsert=True
        )