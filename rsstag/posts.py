import logging
from typing import Optional
from pymongo import MongoClient, DESCENDING

class RssTagPosts:
    indexes = ['owner', 'category_id', 'feed_id', 'read', 'tags', 'pid']
    def __init__(self, db: MongoClient):
        self.db = db
        self.log = logging.getLogger('posts')

    def get_by_category(self, owner: str, only_unread: Optional[bool]=None, category: str='', projection: dict= {}) -> Optional[list]:
        query = {'owner': owner}
        if category:
            query['category_id'] = category
        try:
            if only_unread is not None:
                query['read'] = not only_unread
                sort = [('feed_id', DESCENDING), ('unix_date', DESCENDING)]
            else:
                sort = [('unix_date', DESCENDING)]
            if projection:
                cursor = self.db.posts.find(query, projection=projection).sort(sort)
            else:
                cursor = self.db.posts.find(query).sort(sort)
            result = list(cursor)
        except Exception as e:
            self.log.error('Can`t get posts by category %s, user %s. Info: %s', category, owner, e)
            result = None

        return result

    def get_all(self, owner: str, only_unread: Optional[bool]=None, projection: dict={}) -> Optional[list]:
        query = {'owner': owner}
        try:
            if only_unread is not None:
                query['read'] = not only_unread
            if projection:
                cursor = self.db.posts.find(query, projection=projection)
            else:
                cursor = self.db.posts.find(query)
            result = list(cursor)
        except Exception as e:
            self.log.error('Can`t get posts for user %s. Info: %s', owner, e)
            result = None

        return result

    def prepare(self):
        for index in self.indexes:
            try:
                self.db.posts.create_index(index)
            except Exception as e:
                self.log.warning('Can`t create index %s. May be already exists. Info: %s', e)

    def get_grouped_stat(self, owner: str, only_unread: Optional[bool]=None) -> Optional[list]:
        query = {'owner': owner}
        if only_unread is not None:
            query['read'] = not only_unread
        try:
            grouped = self.db.posts.aggregate([
                {'$match': query},
                {'$group': {'_id': '$feed_id', 'category_id': {'$first': '$category_id'}, 'count': {'$sum': 1}}}
            ])
            result = list(grouped)
        except Exception as e:
            self.log.error('Can`t get gtouped stat for user %s. Info: %s', owner, e)
            result = None

        return result