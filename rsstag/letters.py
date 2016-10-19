import logging
from typing import Optional
from rsstag.utils import getSortedDictByAlphabet
from pymongo import MongoClient

class RssTagLetters:
    indexes = ['owner']
    def __init__(self, db: MongoClient) -> None:
        self.db = db
        self.log = logging.getLogger('letters')

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self.db.posts.create_index(index)
            except Exception as e:
                self.log.warning('Can`t create index %s. May be already exists. Info: %s', e)

    def get(self, owner: str, make_sort: bool=False) -> Optional[dict]:
        query = {'owner': owner}
        try:
            letters = self.db.letters.find_one(query)
            if letters:
                if make_sort:
                    letters['letters'] = getSortedDictByAlphabet(letters['letters'])
                result = letters
            else:
                result = {}
        except Exception as e:
            self.log.error('Can`t get letters for user %s. Info: %s', owner, e)
            result = None

        return result

    def to_list(self, letters: dict, only_unread: Optional[bool]=None) -> list:
        if only_unread:
            letters_list = [letter for letter in letters['letters'].values() if letter['unread_count'] > 0]
        else:
            letters_list = list(letters['letters'].values())

        return letters_list