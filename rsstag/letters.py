import logging
from typing import Optional
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

    def get(self, owner: str) -> Optional[dict]:
        query = {'owner': owner}
        try:
            letters = self.db.letters.find_one(query)
            if letters:
                result = letters
            else:
                result = {}
        except Exception as e:
            self.log.error('Can`t get letters for user %s. Info: %s', owner, e)
            result = None

        return result