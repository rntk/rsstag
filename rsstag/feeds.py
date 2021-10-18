import logging
from typing import Optional, Iterable
from pymongo import MongoClient

class RssTagFeeds:
    indexes = ['owner', 'feed_id']
    all_feeds = 'All'

    def __init__(self, db: MongoClient) -> None:
        self.db = db
        self.log = logging.getLogger('feeds')

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self.db.feeds.create_index(index)
            except Exception as e:
                self.log.warning('Can`t create index %s. May be already exists. Info: %s', index, e)

    def get_by_category(self, owner: str, category: str, projection: Optional[dict]=None) -> Iterable:
        query = {'owner': owner}
        if category != self.all_feeds:
            query['category_id'] = category

        return self.db.feeds.find(query, projection=projection)

    def get_all(self, owner: str, projection: Optional[dict]=None) -> Iterable:
        query = {'owner': owner}

        return self.db.feeds.find(query, projection=projection)


    def get_by_feed_id(self, owner: str, feed_id: str) -> Optional[dict]:
        query = {
            'owner': owner,
            'feed_id': feed_id
        }

        return self.db.feeds.find_one(query)
