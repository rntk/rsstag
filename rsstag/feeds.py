import logging
from typing import Optional
from pymongo import MongoClient, DESCENDING

class RssTagFeeds:
    indexes = ['owner', 'feed_id']
    all_feeds = 'All'

    def __init__(self, db: MongoClient):
        self.db = db
        self.log = logging.getLogger('feeds')

    def get_by_category(self, owner: str, category: str, projection: dict={}) -> Optional[list]:
        query = {'owner': owner}
        if category != self.all_feeds:
            query['category_id'] = category
        try:
            if projection:
                cursor = self.db.feeds.find(query, projection=projection)
            else:
                cursor = self.db.feeds.find(query)
            result = list(cursor)
        except Exception as e:
            self.log.error('Can`t get feeds for user %s. Info: %s', owner, e)
            result = None

        return result

    def get_all(self, owner: str, projection: dict={}) -> Optional[list]:
        query = {'owner': owner}
        try:
            if projection:
                cursor = self.db.feeds.find(query, projection=projection)
            else:
                cursor = self.db.feeds.find(query)
            result = list(cursor)
        except Exception as e:
            self.log.error('Can`t get feeds for user %s. Info: %s', owner, e)
            result = None

        return result

    def prepare(self):
        for index in self.indexes:
            try:
                self.db.feeds.create_index(index)
            except Exception as e:
                self.log.warning('Can`t create index %s. May be already exists. Info: %s', e)