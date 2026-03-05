import logging
from typing import Optional, Iterator
from pymongo import MongoClient


class RssTagFeeds:
    indexes = ["owner", "feed_id"]
    all_feeds = "All"

    def __init__(self, db: MongoClient) -> None:
        self.db = db
        self.log = logging.getLogger("feeds")

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self.db.feeds.create_index(index)
            except Exception as e:
                self.log.warning(
                    "Can`t create index %s. May be already exists. Info: %s", index, e
                )

    def get_by_category(
        self, owner: str, category: str, projection: Optional[dict] = None
    ) -> Iterator[dict]:
        query = {"owner": owner}
        if category != self.all_feeds:
            query["category_id"] = category

        return self.db.feeds.find(query, projection=projection)

    def get_all(self, owner: str, projection: Optional[dict] = None) -> Iterator[dict]:
        query = {"owner": owner}

        return self.db.feeds.find(query, projection=projection)

    def get_all_with_category(self, owner: str) -> Iterator[dict]:
        projection = {"feed_id": True, "title": True, "category_id": True}
        return self.get_all(owner, projection=projection)

    def get_by_feed_id(self, owner: str, feed_id: str) -> Optional[dict]:
        query = {"owner": owner, "feed_id": feed_id}

        return self.db.feeds.find_one(query)

    def get_by_categories(
        self, owner: str, categories: list, projection: Optional[dict] = None
    ) -> Iterator[dict]:
        query = {"owner": owner, "category_id": {"$in": categories}}
        return self.db.feeds.find(query, projection=projection)

    def get_ids_by_categories(self, owner: str, categories: list) -> Iterator[dict]:
        projection = {"feed_id": True}
        return self.get_by_categories(owner, categories, projection=projection)

    def get_by_feed_ids(
        self, owner: str, feed_ids: list, projection: Optional[dict] = None
    ) -> Iterator[dict]:
        query = {"owner": owner, "feed_id": {"$in": feed_ids}}
        return self.db.feeds.find(query, projection=projection)

    def get_titles_by_ids(self, owner: str, feed_ids: list) -> Iterator[dict]:
        projection = {"_id": 0, "feed_id": 1, "title": 1}
        return self.get_by_feed_ids(owner, feed_ids, projection=projection)

    def find(self, owner: str, query: Optional[dict] = None, projection: Optional[dict] = None):
        full_query = {"owner": owner}
        if query:
            full_query.update(query)
        return self.db.feeds.find(full_query, projection=projection)
