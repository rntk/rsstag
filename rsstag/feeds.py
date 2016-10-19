import logging
from typing import Optional
from pymongo import MongoClient, DESCENDING

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
                self.log.warning('Can`t create index %s. May be already exists. Info: %s', e)

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


    def get_by_feed_id(self, owner: str, feed_id: str) -> Optional[dict]:
        query = {
            'owner': owner,
            'feed_id': feed_id
        }
        try:
            feed = self.db.feeds.find_one(query)
            if feed:
                result = feed
            else:
                result = {}
        except Exception as e:
            self.log.error('Can`t get feed by id %s for user %s. Info: %s', feed_id, owner, e)
            result = None

        return result
