import logging
from collections import defaultdict
from typing import Optional, List, Iterable
from pymongo import MongoClient, DESCENDING, UpdateOne

class RssTagTags:
    indexes = ['owner', 'tag', 'unread_count', 'posts_count', 'processing']
    def __init__(self, db: MongoClient) -> None:
        self._db = db
        self._log = logging.getLogger('tags')

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self._db.tags.create_index(index)
            except Exception as e:
                self._log.warning('Can`t create index %s. May be already exists. Info: %s', index, e)

    def get_by_tag(self, owner: str, tag: str) -> Optional[dict]:
        query = {'owner': owner, 'tag': tag}
        try:
            db_tag = self._db.tags.find_one(query)
            if db_tag:
                result = db_tag
            else:
                result = {}
        except Exception as e:
            self._log.error('Can`t get tag %s. User %s. Info: %s', tag, owner, e)
            result = None

        return result

    def get_by_tags(self, owner: str, tags: list, only_unread: Optional[bool]=None, projection: dict={}) -> Optional[list]:
        query = {
            'owner': owner,
            'tag': {'$in': tags}
        }
        if only_unread:
            query['unread_count'] = {'$gt': 0}
        try:
            if projection:
                cursor = self._db.tags.find(query, projection=projection)
            else:
                cursor = self._db.tags.find(query)
            result = list(cursor)
        except Exception as e:
            self._log.error('Can`t get tagby tag %s. User %s. Info: %s', tags, owner, e)
            result = None

        return result

    def get_all(self, owner: str, only_unread: Optional[bool]=None, hot_tags: bool=False,
                opts: dict=[], projection: dict={}) -> Optional[list]:
        query = {'owner': owner}
        if 'regexp' in opts:
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
        if 'offset' in opts:
            params['skip'] = opts['offset']
        if 'limit' in opts:
            params['limit'] = opts['limit']
        if projection:
            params['projection'] = projection
        try:
            cursor = self._db.tags.find(query, **params).sort(sort_data)
            result = list(cursor)
        except Exception as e:
            self._log.error('Can`t get all tags user %s. Info: %s', owner, e)
            result = None

        return result

    def count(self, owner: str, only_unread: Optional[bool]=None, regexp: str='', sentiments: List[str]=[], groups: List[str]=[]) -> Optional[int]:
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
            result = self._db.tags.count(query)
        except Exception as e:
            self._log.error('Can`t get tags number for user %s. Info: e', owner, e)
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
                bulk_result = self._db.tags.bulk_write(updates, ordered=False)
                result = (bulk_result.matched_count > 0)
            except Exception as e:
                result = None
                self._log.error('Can`t change unread_count for tags. User %s. info: %s', owner, e)

        return result

    def get_city_tags(self, owner: str, only_unread: bool=None, projection: dict=None) -> Optional[dict]:
        query = {
            'owner': owner,
            'city': {'$exists': True}
        }
        if only_unread:
            query['unread_count'] = {'$gt': 0}
        try:
            if projection:
                cursor = self._db.tags.find(query, projection=projection)
            else:
                cursor = self._db.tags.find(query)
            result = list(cursor)
        except Exception as e:
            self._log.error('Can`t get city tags. User %s. Info: %s', owner, e)
            result = None

        return result


    def get_country_tags(self, owner: str, only_unread: bool=None, projection: dict=None) -> Optional[dict]:
        query = {
            'owner': owner,
            'country': {'$exists': True}
        }
        if only_unread:
            query['unread_count'] = {'$gt': 0}
        try:
            if projection:
                cursor = self._db.tags.find(query, projection=projection)
            else:
                cursor = self._db.tags.find(query)
            result = list(cursor)
        except Exception as e:
            self._log.error('Can`t get country tags. User %s. Info: %s', owner, e)
            result = None

        return result

    def add_sentiment(self, owner: str, tag: str, sentiment: List[str]) -> Optional[bool]:
        try:
            self._db.tags.update({'owner': owner, 'tag': tag}, {'$set': {'sentiment': sentiment}})#TODO: check result
            result = True
        except Exception as e:
            result = None
            self._log.error('Can`t get country tags. User %s. Info: %s', owner, e)

        return result

    def get_sentiments(self, owner: str, only_unread: bool) -> Optional[tuple]:
        query = {
            'owner': owner,
            'sentiment': {'$exists': True}
        }
        if only_unread:
            query['unread_count'] = {'$gt': 0}
        try:
            cur = self._db.tags.aggregate([
                {'$match': query},
                {'$group': {'_id': '$sentiment', 'counter': {'$sum': 1}}}
            ])
            sentiments = set()
            for sents in cur:
                for sent in sents['_id']:
                    sentiments.add(sent)
            result = tuple(sentiments)
        except Exception as e:
            self._log.error('Can`t get tags sentiments. User %s. Info: %s', owner, e)
            result = None

        return result

    def get_by_sentiment(self, owner: str, sentiments: List[str], only_unread: Optional[bool] = None, hot_tags: bool = False,
                opts: dict = [], projection: dict = {}) -> Optional[list]:
        query = {
            'owner': owner,
            '$and': [{'sentiment': {'$exists': True}}, {'sentiment': {'$all': sentiments}}]
        }
        if 'regexp' in opts:
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
        if 'offset' in opts:
            params['skip'] = opts['offset']
        if 'limit' in opts:
            params['limit'] = opts['limit']
        if projection:
            params['projection'] = projection
        try:
            cursor = self._db.tags.find(query, **params).sort(sort_data)
            result = list(cursor)
        except Exception as e:
            self._log.error('Can`t get tags by sentiments user %s. Info: %s', owner, e)
            result = None

        return result

    def get_by_group(self, owner: str, groups: List[str], only_unread: Optional[bool] = None, hot_tags: bool = False,
                opts: dict = [], projection: dict = {}) -> Optional[list]:
        query = {
            'owner': owner,
            '$and': [{'groups': {'$exists': True}}, {'groups': {'$all': groups}}]
        }
        if 'regexp' in opts:
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
        if 'offset' in opts:
            params['skip'] = opts['offset']
        if 'limit' in opts:
            params['limit'] = opts['limit']
        if projection:
            params['projection'] = projection
        try:
            cursor = self._db.tags.find(query, **params).sort(sort_data)
            result = list(cursor)
        except Exception as e:
            self._log.error('Can`t get tags by group user %s. Info: %s', owner, e)
            result = None

        return result

    def add_groups(self, owner: str, tags_groups: dict) -> Optional[bool]:
        updates = []
        result = False
        for tag, groups in tags_groups.items():
            updates.append(UpdateOne(
                {'owner': owner, 'tag': tag},
                {'$set': {'groups': list(groups)}}
            ))
        if updates:
            try:
                self._db.tags.bulk_write(updates) #add check bulk write results
                result = True
            except Exception as e:
                self._log.error('Can`t update tags gruops, user %s. Info: %s', owner, e)
                result = None

        return result

    def get_groups(self, owner: str, only_unread: bool=False) -> Optional[dict]:
        query = {
            'owner': owner,
            'groups': {'$exists': True}
        }
        if only_unread:
            query['unread_count'] = {'$gt': 0}
        try:
            aggr = self._db.tags.aggregate([
                {'$match': query},
                {'$group': {'_id': '$groups', 'counter': {'$sum': 1}}}
            ])
            groups = defaultdict(int)
            for agg in aggr:
                for group in agg['_id']:
                    groups[group] += 1
            result = groups
        except Exception as e:
            self._log.error('Can`t get tags groups, user %s. Info: %s', owner, e)
            result = None

        return result

    def add_entities(self, owner: str, entities: dict, replace: bool=False) -> Optional[bool]:
        if replace:
            operator = '$set'
        else:
            operator = '$inc'
        updates = [
            UpdateOne(
                {'owner': owner, 'tag': entity},
                {operator: {'temperature': number, 'ner': number}}
            )
            for entity, number in entities.items()
        ]
        try:
            self._db.tags.bulk_write(updates)#add bulk write result checking
            result = True
        except Exception as e:
            self._log.error('Can`t add entities, user %s. Info: %s', owner, e)
            result = None

        return result