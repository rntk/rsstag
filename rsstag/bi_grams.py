import logging
from typing import Optional, List, Iterator
from pymongo import MongoClient, DESCENDING, UpdateOne


class RssTagBiGrams:
    indexes = ["owner", "tag", "tags", "unread_count", "posts_count", "temperature"]

    def __init__(self, db: MongoClient) -> None:
        self.db = db
        self.log = logging.getLogger("bi_grams")

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self.db.bi_grams.create_index(index)
            except Exception as e:
                self.log.warning(
                    "Can`t create index %s. May be already exists. Info: %s", index, e
                )

    def get_by_bi_gram(self, owner: str, bi_gram: str) -> Optional[dict]:
        query = {"owner": owner, "tag": bi_gram}

        return self.db.bi_grams.find_one(query)

    def get_by_tags(
        self,
        owner: str,
        tags: List[str],
        only_unread: Optional[bool] = None,
        projection: Optional[dict] = None,
    ) -> Iterator[dict]:
        query = {"owner": owner, "tags": {"$all": tags}}
        sort_data = []
        if only_unread:
            query["unread_count"] = {"$gt": 0}
            sort_data.append(("unread_count", DESCENDING))
        else:
            sort_data.append(("posts_count", DESCENDING))

        return self.db.bi_grams.find(query, projection=projection).allow_disk_use(True).sort(sort_data)

    def change_unread(self, owner: str, tags: dict, readed: bool) -> bool:
        updates = []
        for tag in tags:
            updates.append(
                UpdateOne(
                    {"owner": owner, "tag": tag},
                    {"$inc": {"unread_count": -tags[tag] if readed else tags[tag]}},
                )
            )
        if updates:
            self.db.bi_grams.bulk_write(updates, ordered=False)

        return True

    def count(
        self,
        owner: str,
        only_unread: bool = False,
        regexp: str = "",
        sentiments: List[str] = None,
        groups: List[str] = None,
    ) -> int:
        query = {"owner": owner}
        if regexp:
            query["tag"] = {"$regex": regexp, "$options": "i"}
        if only_unread:
            query["unread_count"] = {"$gt": 0}
        if sentiments:
            query["$and"] = [
                {"sentiment": {"$exists": True}},
                {"sentiment": {"$all": sentiments}},
            ]
        if groups:
            query["$and"] = [
                {"groups": {"$exists": True}},
                {"groups": {"$all": groups}},
            ]

        return self.db.bi_grams.count_documents(query)

    def get_all(
        self,
        owner: str,
        only_unread: bool = False,
        hot_tags: bool = False,
        opts: dict = None,
        projection: dict = None,
    ) -> Iterator[dict]:
        query = {"owner": owner}
        if opts and "regexp" in opts:
            query["tag"] = {"$regex": opts["regexp"], "$options": "i"}
        sort_data = []
        if hot_tags:
            sort_data.append(("temperature", DESCENDING))
        if only_unread:
            sort_data.append(("unread_count", DESCENDING))
            query["unread_count"] = {"$gt": 0}
        else:
            sort_data.append(("posts_count", DESCENDING))
        params = {}
        if opts and "offset" in opts:
            params["skip"] = opts["offset"]
        if opts and "limit" in opts:
            params["limit"] = opts["limit"]
        if projection:
            params["projection"] = projection

        return self.db.bi_grams.find(query, **params).allow_disk_use(True).sort(sort_data)

    def set_temperature(self, owner: str, bi_gram: str, temperature: float) -> bool:
        self.db.bi_grams.update_one(
            {"owner": owner, "tag": bi_gram}, {"$set": {"temperature": temperature}}
        )

        return True

    def set_temperatures(self, owner: str, values: dict) -> bool:
        if not values:
            return True

        updates = []
        for bi_gram, temperature in values.items():
            updates.append(
                UpdateOne(
                    {"owner": owner, "tag": bi_gram},
                    {"$set": {"temperature": temperature}},
                )
            )

        self.db.bi_grams.bulk_write(updates, ordered=False)

        return True

    def remove_by_count(self, owner: str, n: int) -> bool:
        query = {"owner": owner, "posts_count": n}
        r = self.db.bi_grams.delete_many(query)
        self.log.info("Deleted bigrams: %d for %s", r.deleted_count, owner)

        return True
