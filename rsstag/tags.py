import logging
from collections import defaultdict
from typing import Optional, List, Iterator
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

        return self._db.tags.find_one(query)

    def get_by_tags(self, owner: str, tags: list, only_unread: Optional[bool]=None, projection: Optional[dict]=None) -> Iterator[dict]:
        query = {
            'owner': owner,
            'tag': {'$in': tags}
        }
        if only_unread:
            query['unread_count'] = {'$gt': 0}

        return self._db.tags.find(query, projection=projection)

    def get_all(self, owner: str, only_unread: Optional[bool]=None, hot_tags: bool=False,
                opts: Optional[dict]=None, projection: Optional[dict]=None) -> Iterator[dict]:
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

        return self._db.tags.find(query, **params).sort(sort_data)

    def count(self, owner: str, only_unread: Optional[bool]=None, regexp: str='', sentiments: Optional[List[str]]=None, groups: Optional[List[str]]=None) -> int:
        query = {'owner': owner}
        if regexp:
            query['tag'] = {'$regex': regexp, '$options': 'i'}
        if only_unread:
            query['unread_count'] = {'$gt': 0}
        if sentiments:
            query['$and'] = [{'sentiment': {'$exists': True}}, {'sentiment': {'$all': sentiments}}]
        if groups:
            query['$and'] = [{'groups': {'$exists': True}}, {'groups': {'$all': groups}}]

        return self._db.tags.count(query)

    def change_unread(self, owner: str, tags: dict, readed: bool) -> bool:
        updates = []
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
            self._db.tags.bulk_write(updates, ordered=False)

        return True

    def get_city_tags(self, owner: str, only_unread: bool=None, projection: dict=None) -> Iterator[dict]:
        query = {
            'owner': owner,
            'city': {'$exists': True}
        }
        if only_unread:
            query['unread_count'] = {'$gt': 0}

        return self._db.tags.find(query, projection=projection)

    def get_country_tags(self, owner: str, only_unread: bool=None, projection: dict=None) -> Iterator[dict]:
        query = {
            'owner': owner,
            'country': {'$exists': True}
        }
        if only_unread:
            query['unread_count'] = {'$gt': 0}

        return self._db.tags.find(query, projection=projection)

    def add_sentiment(self, owner: str, tag: str, sentiment: List[str]) -> bool:
        self._db.tags.update({'owner': owner, 'tag': tag}, {'$set': {'sentiment': sentiment}})

        return True


    def get_sentiments(self, owner: str, only_unread: bool) -> tuple:
        query = {
            'owner': owner,
            'sentiment': {'$exists': True}
        }
        if only_unread:
            query['unread_count'] = {'$gt': 0}

        cur = self._db.tags.aggregate([
            {'$match': query},
            {'$group': {'_id': '$sentiment', 'counter': {'$sum': 1}}}
        ])
        sentiments = set()
        for sents in cur:
            for sent in sents['_id']:
                sentiments.add(sent)

        return tuple(sentiments)

    def get_by_sentiment(self, owner: str, sentiments: List[str], only_unread: Optional[bool] = None, hot_tags: bool = False,
                opts: Optional[dict]=None, projection: Optional[dict]=None) -> Iterator[dict]:
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

        return self._db.tags.find(query, **params).sort(sort_data)

    def get_by_group(self, owner: str, groups: List[str], only_unread: Optional[bool] = None, hot_tags: bool = False,
                opts: Optional[dict]=None, projection: Optional[dict]=None) -> Iterator[dict]:
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

        return self._db.tags.find(query, **params).sort(sort_data)

    def add_groups(self, owner: str, tags_groups: dict) -> bool:
        updates = []
        for tag, groups in tags_groups.items():
            updates.append(UpdateOne(
                {'owner': owner, 'tag': tag},
                {'$set': {'groups': list(groups)}}
            ))
        if updates:
            self._db.tags.bulk_write(updates)

        return True

    def get_groups(self, owner: str, only_unread: bool=False) -> dict:
        query = {
            'owner': owner,
            'groups': {'$exists': True}
        }
        if only_unread:
            query['unread_count'] = {'$gt': 0}

        aggr = self._db.tags.aggregate([
            {'$match': query},
            {'$group': {'_id': '$groups', 'counter': {'$sum': 1}}}
        ])
        groups = defaultdict(int)
        for agg in aggr:
            for group in agg['_id']:
                groups[group] += 1

        return groups

    def add_entities(self, owner: str, entities: dict, replace: bool=False) -> bool:
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
        if updates:
            self._db.tags.bulk_write(updates)

        return True

    def get_tags_sum(self, owner: str) -> int:
        cursor = self._db.tags.aggregate([
            {'$match': {'owner': owner}},
            {"$group": {"_id": "$owner", "counter": {"$sum": "$posts_count"}}}
        ])
        for dt in cursor:
            return dt["counter"]
