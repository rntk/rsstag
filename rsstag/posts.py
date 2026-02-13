import logging
from typing import Optional, List, Iterator
import gzip

from pymongo import MongoClient, DESCENDING, ASCENDING, UpdateMany


class RssTagPosts:
    indexes = ["owner", "category_id", "feed_id", "read", "tags", "pid", "processing"]

    def __init__(self, db: MongoClient) -> None:
        self._db: MongoClient = db
        self._log = logging.getLogger("posts")

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self._db.posts.create_index(index)
            except Exception as e:
                self._log.warning(
                    "Can`t create index %s. May be already exists. Info: %s", index, e
                )

    def get_by_category(
        self,
        owner: str,
        only_unread: Optional[bool] = None,
        category: str = "",
        projection: Optional[dict] = None,
        context_tags: Optional[list] = None,
    ) -> Iterator[dict]:
        query = {"owner": owner}
        if category:
            query["category_id"] = category

        if only_unread is not None:
            query["read"] = not only_unread
        if context_tags:
            query["tags"] = {"$all": context_tags}
        if only_unread is not None:
            sort = [("feed_id", DESCENDING), ("unix_date", DESCENDING)]
        else:
            sort = [("unix_date", DESCENDING)]

        return (
            self._db.posts.find(query, projection=projection)
            .allow_disk_use(True)
            .sort(sort)
        )

    def get_all(
        self,
        owner: str,
        only_unread: Optional[bool] = None,
        projection: Optional[dict] = None,
    ) -> Iterator[dict]:
        query = {"owner": owner}
        if only_unread is not None:
            query["read"] = not only_unread

        return self._db.posts.find(query, projection=projection)

    def get_grouped_stat(
        self, owner: str, only_unread: Optional[bool] = None
    ) -> Iterator[dict]:
        query = {"owner": owner}
        if only_unread is not None:
            query["read"] = not only_unread

        return self._db.posts.aggregate(
            [
                {"$match": query},
                {
                    "$group": {
                        "_id": "$feed_id",
                        "category_id": {"$first": "$category_id"},
                        "count": {"$sum": 1},
                    }
                },
            ]
        )

    def get_by_tags(
        self,
        owner: str,
        tags: list,
        only_unread: Optional[bool] = None,
        projection: Optional[dict] = None,
        context_tags: Optional[list] = None,
    ) -> Iterator[dict]:
        """
        Get posts matching tags.

        Args:
            context_tags: Additional tags to require (from context filter).
                         These are merged with `tags` using AND logic.

        TODO: may be need change condition from 'tags': {'$all': tags} to 'tags': {'$elemMAtch': {'$in': tags}}
        """
        # Combine main tags with context tags
        all_tags = list(tags)
        if context_tags:
            for ct in context_tags:
                if ct not in all_tags:
                    all_tags.append(ct)

        query = {"owner": owner, "tags": {"$all": all_tags}}
        if only_unread is not None:
            query["read"] = not only_unread
        sort_data = [("feed_id", DESCENDING), ("unix_date", DESCENDING)]

        return (
            self._db.posts.find(query, projection=projection)
            .allow_disk_use(True)
            .sort(sort_data)
        )

    def get_by_bi_grams(
        self,
        owner: str,
        tags: list,
        only_unread: Optional[bool] = None,
        projection: Optional[dict] = None,
        context_tags: Optional[list] = None,
    ) -> Iterator[dict]:
        query = {"owner": owner, "bi_grams": {"$all": tags}}
        if only_unread is not None:
            query["read"] = not only_unread
        if context_tags:
            query["tags"] = {"$all": context_tags}
        sort_data = [("feed_id", DESCENDING), ("unix_date", DESCENDING)]

        return (
            self._db.posts.find(query, projection=projection)
            .allow_disk_use(True)
            .sort(sort_data)
        )

    def get_by_feed_id(
        self,
        owner: str,
        feed_id: str,
        only_unread: Optional[bool] = None,
        projection: Optional[dict] = None,
        context_tags: Optional[list] = None,
    ) -> Iterator[dict]:
        query = {"owner": owner, "feed_id": feed_id}
        if only_unread is not None:
            query["read"] = not only_unread
        if context_tags:
            query["tags"] = {"$all": context_tags}
        if only_unread is not None:
            sort = [("feed_id", DESCENDING), ("unix_date", DESCENDING)]
        else:
            sort = [("unix_date", DESCENDING)]

        return (
            self._db.posts.find(query, projection=projection)
            .allow_disk_use(True)
            .sort(sort)
        )

    def get_by_pid(
        self, owner: str, pid: str, projection: Optional[dict] = None
    ) -> Optional[dict]:
        query = {"owner": owner, "pid": pid}

        return self._db.posts.find_one(query, projection=projection)

    def get_by_id(
        self, owner: str, pid: str, projection: Optional[dict] = None
    ) -> Optional[dict]:
        query = {"owner": owner, "id": pid}

        return self._db.posts.find_one(query, projection=projection)

    def get_by_pids(
        self, owner: str, pids: List[str], projection: Optional[dict] = None
    ) -> Iterator[dict]:
        query = {"owner": owner, "pid": {"$in": pids}}

        return self._db.posts.find(query, projection=projection)

    def get_processing(self, owner: str) -> Iterator[dict]:
        query = {"owner": owner, "processing": {"$ne": 0, "$exists": True}}
        return self._db.posts.find(query, projection={"pid": True, "title": True, "processing": True})

    def reset_processing(self, owner: str, pid: str) -> None:
        self._db.posts.update_one({"owner": owner, "pid": pid}, {"$set": {"processing": 0}})

    def change_status(self, owner: str, pids: List[str], readed: bool) -> bool:
        query = {"owner": owner, "pid": {"$in": pids}}
        self._db.posts.update_many(query, {"$set": {"read": readed}})

        return True

    def get_stat(self, owner: str) -> dict:
        result = {"unread": 0, "read": 0, "tags": 0}
        cursor = self._db.posts.aggregate(
            [
                {"$match": {"owner": owner}},
                {"$group": {"_id": "$read", "counter": {"$sum": 1}}},
            ]
        )
        for dt in cursor:
            if dt["_id"]:
                result["read"] = dt["counter"]
            else:
                result["unread"] = dt["counter"]
        result["tags"] = self._db.tags.count_documents({"owner": owner})

        return result

    def set_clusters(self, owner: str, similars: dict) -> bool:
        updates = [
            UpdateMany(
                {"owner": owner, "pid": {"$in": list(ids)}},
                {"$addToSet": {"clusters": cluster}},
            )
            for cluster, ids in similars.items()
        ]

        if updates:
            self._db.posts.bulk_write(updates)

        return True

    def get_neighbors_by_unix_date(
        self,
        owner: str,
        unix_date: float,
        count: int,
        projection: Optional[dict] = None,
    ) -> List[dict]:
        before = list(
            self._db.posts.find(
                {"owner": owner, "unix_date": {"$lt": unix_date}},
                projection=projection,
            )
            .sort("unix_date", DESCENDING)
            .limit(count)
        )
        after = list(
            self._db.posts.find(
                {"owner": owner, "unix_date": {"$gt": unix_date}},
                projection=projection,
            )
            .sort("unix_date", ASCENDING)
            .limit(count)
        )
        return before + after

    def get_by_clusters(
        self,
        owner: str,
        clusters: list,
        only_unread: Optional[bool] = None,
        projection: Optional[dict] = None,
        context_tags: Optional[list] = None,
    ) -> Iterator[dict]:
        query = {
            "owner": owner,
            "clusters": {"$exists": True, "$elemMatch": {"$in": clusters}},
        }
        if only_unread is not None:
            query["read"] = not only_unread
        if context_tags:
            query["tags"] = {"$all": context_tags}
        sort_data = [("feed_id", DESCENDING), ("unix_date", DESCENDING)]

        return (
            self._db.posts.find(query, projection=projection)
            .allow_disk_use(True)
            .sort(sort_data)
        )

    def get_clusters(self, posts: List[dict]) -> set:
        result = set()
        field = "clusters"
        for post in posts:
            if (field in post) and post[field]:
                result.update(post[field])

        return result

    def count(self, owner: str) -> int:
        return self._db.posts.count_documents({"owner": owner})


class PostLemmaSentence:
    def __init__(self, db: MongoClient, owner: str, split: bool = False):
        self.__db = db
        self.__owner = owner
        self.__split = split

    def __iter__(self):
        cursor = self.__db.posts.find(
            {"owner": self.__owner}, projection={"lemmas": True}
        )
        if self.__split:
            for p in cursor:
                yield gzip.decompress(p["lemmas"]).decode("utf-8", "replace").split()
        else:
            for p in cursor:
                yield gzip.decompress(p["lemmas"]).decode("utf-8", "replace")

    def count(self) -> int:
        return self.__db.posts.count_documents({"owner": self.__owner})
