import logging
from typing import Optional, List, Union
from pymongo import MongoClient, DESCENDING, UpdateOne, CursorType

class RssTagBiGrams:
    indexes = ['owner', 'tag', 'tags', 'unread_count', 'posts_count', 'temperature']
    def __init__(self, db: MongoClient) -> None:
        self.db = db

        self.log = logging.getLogger('bi_grams')

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self.db.bi_grams.create_index(index)
            except Exception as e:
                self.log.warning('Can`t create index %s. May be already exists. Info: %s', index, e)

    def get_by_bi_gram(self, owner: str, bi_gram: str) -> Optional[dict]:
        query = {'owner': owner, 'tag': bi_gram}
        try:
            db_bi_gram = self.db.bi_grams.find_one(query)
            if db_bi_gram:
                result = db_bi_gram
            else:
                result = {}
        except Exception as e:
            self.log.error('Can`t get bi-gram %s. User %s. Info: %s', bi_gram, owner, e)
            result = None

        return result

    def get_by_tags(self, owner: str, tags: list, only_unread: Optional[bool]=None, projection: dict={}) -> Optional[list]:
        query = {
            'owner': owner,
            'tags': {'$all': tags}
        }
        sort_data = []
        if only_unread:
            query['unread_count'] = {'$gt': 0}
            sort_data.append(('unread_count', DESCENDING))
        else:
            sort_data.append(('posts_count', DESCENDING))
        try:
            if projection:
                cursor = self.db.bi_grams.find(query, projection=projection).sort(sort_data)
            else:
                cursor = self.db.bi_grams.find(query).sort(sort_data)
            result = list(cursor)
        except Exception as e:
            self.log.error('Can`t get tagby tag %s. User %s. Info: %s', tags, owner, e)
            result = None

        return result


    def change_unread(self, owner: str, tags: dict, readed: bool) -> Optional[bool]:
        updates = []
        result = False
        for tag in tags:
            updates.append(UpdateOne(
                {
                    'owner': owner,
                    'tag': tag
                },
                {
                    '$inc': {
                        'unread_count': -tags[tag] if readed else tags[tag]
                    }
                }
            ))
        if updates:
            try:
                bulk_result = self.db.bi_grams.bulk_write(updates, ordered=False)
                result = (bulk_result.matched_count > 0)
            except Exception as e:
                result = None
                self.log.error('Can`t change unread_count for bi-grams. User %s. info: %s', owner, e)

        return result

    def count(self, owner: str, only_unread: bool=False, regexp: str='', sentiments: List[str]=None, groups: List[str]=None) -> Optional[int]:
        query = {'owner': owner}
        if regexp:
            query['tag'] = {'$regex': regexp, '$options': 'i'}
        if only_unread:
            query['unread_count'] = {'$gt': 0}
        if sentiments:
            query['$and'] = [{'sentiment': {'$exists': True}}, {'sentiment': {'$all': sentiments}}]
        if groups:
            query['$and'] = [{'groups': {'$exists': True}}, {'groups': {'$all': groups}}]
        try:
            result = self.db.bi_grams.count(query)
        except Exception as e:
            self.log.error('Can`t get tags number for user %s. Info: e', owner, e)
            result = None

        return result

    def get_all(self, owner: str, only_unread: bool=False, hot_tags: bool=False,
                opts: dict=None, projection: dict=None, get_cursor: bool=False) -> Optional[Union[list, CursorType]]:
        query = {'owner': owner}
        if opts and 'regexp' in opts:
            query['tag'] = {'$regex': opts['regexp'], '$options': 'i'}
        sort_data = []
        if hot_tags:
            sort_data.append(('temperature', DESCENDING))
        if only_unread:
            sort_data.append(('unread_count', DESCENDING))
            query['unread_count'] = {'$gt': 0}
        else:
            sort_data.append(('posts_count', DESCENDING))
        params = {}
        if opts and 'offset' in opts:
            params['skip'] = opts['offset']
        if opts and 'limit' in opts:
            params['limit'] = opts['limit']
        if projection:
            params['projection'] = projection
        try:
            cursor = self.db.bi_grams.find(query, **params).sort(sort_data)
            if get_cursor:
                result = cursor
            else:
                result = list(cursor)
        except Exception as e:
            self.log.error('Can`t get all tags user %s. Info: %s', owner, e)
            result = None

        return result

    def set_temperature(self, owner: str, bi_gram: str, temperature: float) -> Optional[bool]:
        try:
            resp = self.db.bi_grams.update_one(
                {
                    'owner': owner,
                    'tag': bi_gram
                },
                {"$set": {"temperature": temperature}}
            )
            return resp.matched_count > 0
        except Exception as e:
            self.log.error('Can`t change unread_count for bi-grams. User %s. info: %s', owner, e)
            return None
