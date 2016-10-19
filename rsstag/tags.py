import logging
from typing import Optional
from pymongo import MongoClient, DESCENDING

class RssTagTags:
    indexes = ['owner', 'tag', 'unread_count', 'posts_count', 'processing']
    def __init__(self, db: MongoClient) -> None:
        self.db = db
        self.log = logging.getLogger('tags')

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self.db.posts.create_index(index)
            except Exception as e:
                self.log.warning('Can`t create index %s. May be already exists. Info: %s', e)

    def get_by_tag(self, owner: str, tag: str) -> Optional[dict]:
        query = {'owner': owner, 'tag': tag}
        try:
            tag = self.db.tags.find_one(query)
            if tag:
                result = tag
            else:
                result = {}
        except Exception as e:
            self.log.error('Can`t get tagby tag %s. User %s. Info: %s', tag, owner, e)
            result = None

        return result