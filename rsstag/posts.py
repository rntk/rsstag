import logging
from typing import Optional, List, Iterator
from pymongo import MongoClient, DESCENDING, UpdateMany

class RssTagPosts:
    indexes = ['owner', 'category_id', 'feed_id', 'read', 'tags', 'pid']
    def __init__(self, db: MongoClient) -> None:
        self._db: MongoClient  = db
        self._log = logging.getLogger('posts')

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self._db.posts.create_index(index)
            except Exception as e:
                self._log.warning('Can`t create index %s. May be already exists. Info: %s', index, e)

    def get_by_category(self, owner: str, only_unread: Optional[bool]=None, category: str='', projection: Optional[dict]=None) -> Iterator[dict]:
        query = {'owner': owner}
        if category:
            query['category_id'] = category

        if only_unread is not None:
            query['read'] = not only_unread
            sort = [('feed_id', DESCENDING), ('unix_date', DESCENDING)]
        else:
            sort = [('unix_date', DESCENDING)]

        return self._db.posts.find(query, projection=projection).sort(sort)

    def get_all(self, owner: str, only_unread: Optional[bool]=None, projection: Optional[dict]=None) -> Iterator[dict]:
        query = {'owner': owner}
        if only_unread is not None:
            query['read'] = not only_unread

        return self._db.posts.find(query, projection=projection)

    def get_grouped_stat(self, owner: str, only_unread: Optional[bool]=None) -> Iterator[dict]:
        query = {'owner': owner}
        if only_unread is not None:
            query['read'] = not only_unread

        return self._db.posts.aggregate([
            {'$match': query},
            {'$group': {'_id': '$feed_id', 'category_id': {'$first': '$category_id'}, 'count': {'$sum': 1}}}
        ])

    def get_by_tags(self, owner: str, tags: list, only_unread: Optional[bool]=None, projection: Optional[dict]=None) -> Iterator[dict]:
        """
        TODO: may be need change condition from 'tags': {'$all': tags} to 'tags': {'$elemMAtch': {'$in': tags}}
        """
        query = {
            'owner': owner,
            'tags': {'$all': tags}
        }
        if only_unread is not None:
            query['read'] = not only_unread
        sort_data = [('feed_id', DESCENDING), ('unix_date', DESCENDING)]

        return self._db.posts.find(query, projection=projection).sort(sort_data)

    def get_by_bi_grams(self, owner: str, tags: list, only_unread: Optional[bool]=None, projection: Optional[dict]=None) -> Iterator[dict]:
        query = {
            'owner': owner,
            'bi_grams': {'$all': tags}
        }
        if only_unread is not None:
            query['read'] = not only_unread
        sort_data = [('feed_id', DESCENDING), ('unix_date', DESCENDING)]

        return self._db.posts.find(query, projection=projection).sort(sort_data)

    def get_by_feed_id(self, owner: str, feed_id: str, only_unread: Optional[bool]=None, projection: Optional[dict]=None) -> Iterator[dict]:
        query = {
            'owner': owner,
            'feed_id': feed_id
        }
        if only_unread is not None:
            query['read'] = not only_unread
            sort = [('feed_id', DESCENDING), ('unix_date', DESCENDING)]
        else:
            sort = [('unix_date', DESCENDING)]

        return self._db.posts.find(query, projection=projection).sort(sort)

    def get_by_pid(self, owner: str, pid: int, projection: Optional[dict]=None) -> Optional[dict]:
        query = {
            'owner': owner,
            'pid': pid
        }

        return self._db.posts.find_one(query, projection=projection)

    def get_by_pids(self, owner: str, pids: List[int], projection: Optional[dict]=None) -> Iterator[dict]:
        query = {
            'owner': owner,
            'pid': {'$in': pids}
        }

        return self._db.posts.find(query, projection=projection)

    def change_status(self, owner: str, pids: List[int], readed: bool) -> bool:
        query = {
            'owner': owner,
            'pid': {'$in': pids}
        }
        self._db.posts.update_many(query, {'$set': {'read': readed}})

        return True

    def get_stat(self, owner: str) -> dict:
        result = {'unread': 0, 'read': 0, 'tags': 0}
        cursor = self._db.posts.aggregate([
            {'$match': {'owner': owner}},
            {'$group': {'_id': '$read', 'counter': {'$sum': 1}}}
        ])
        for dt in cursor:
            if dt['_id']:
                result['read'] = dt['counter']
            else:
                result['unread'] = dt['counter']
        result["tags"] = self._db.tags.count_documents({'owner': owner})

        return result

    def set_clusters(self, owner: str, similars: dict) -> bool:
        updates = [
            UpdateMany(
                {'owner': owner, 'pid': {'$in': list(ids)}},
                {'$addToSet': {'clusters': cluster}}
            )
            for cluster, ids in similars.items()
        ]

        if updates:
            self._db.posts.bulk_write(updates)

        return True

    def get_by_clusters(self, owner: str, clusters: list, only_unread: Optional[bool]=None, projection: Optional[dict]=None) -> Iterator[dict]:
        query = {
            'owner': owner,
            'clusters': {'$exists': True, '$elemMatch': {'$in': clusters}}
        }
        if only_unread is not None:
            query['read'] = not only_unread
        sort_data = [('feed_id', DESCENDING), ('unix_date', DESCENDING)]

        return self._db.posts.find(query, projection=projection).sort(sort_data)

    def get_clusters(self, posts: List[dict]) -> set:
        result = set()
        field = 'clusters'
        for post in posts:
            if (field in post) and post[field]:
                result.update(post[field])

        return result

    def count(self, owner: str) -> int:
        return self._db.posts.count_documents({'owner': owner})
