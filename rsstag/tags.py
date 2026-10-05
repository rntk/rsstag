import logging
from collections import defaultdict
from typing import Any, Optional, List, Iterator
from pymongo import MongoClient, UpdateOne

from rsstag.tag_rank import NOISE_FILTER, USER_RANKS, apply_derived, rank_snapshot_filter, sort_fields


class RssTagTags:
    indexes = [
        "owner",
        "tag",
        "unread_count",
        "posts_count",
        "processing",
        "topic_backed",
        "rank.score",
        "rank.hot",
        "rank.noise",
    ]

    def __init__(self, db: MongoClient) -> None:
        self._db = db
        self._log = logging.getLogger("tags")

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self._db.tags.create_index(index)
            except Exception as e:
                self._log.warning(
                    "Can`t create index %s. May be already exists. Info: %s", index, e
                )

    def get_by_tag(self, owner: str, tag: str) -> Optional[dict]:
        query = {"owner": owner, "tag": tag}

        return self._db.tags.find_one(query)

    def get_processing(self, owner: str) -> Iterator[dict]:
        query = {"owner": owner, "processing": {"$ne": 0, "$exists": True}}
        return self._db.tags.find(query, projection={"tag": True, "processing": True})

    def reset_processing(self, owner: str, tag: str) -> None:
        self._db.tags.update_one({"owner": owner, "tag": tag}, {"$set": {"processing": 0}})

    def get_by_tags(
        self,
        owner: str,
        tags: list,
        only_unread: Optional[bool] = None,
        projection: Optional[dict] = None,
    ) -> Iterator[dict]:
        query = {"owner": owner, "tag": {"$in": tags}}
        if only_unread:
            query["unread_count"] = {"$gt": 0}

        return self._db.tags.find(query, projection=projection)

    @staticmethod
    def _user_rank_update(derived: dict[str, Any], value: Optional[str]) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "rank.score": derived["score"],
            "rank.noise": derived["noise"],
        }
        if value is None:
            return {"$set": fields, "$unset": {"user_rank": ""}}
        fields["user_rank"] = value
        return {"$set": fields}

    def set_user_rank(self, owner: str, tag: str, value: Optional[str]) -> bool:
        """Hide / pin a tag (``None`` clears the override); True when a tag was updated.

        ``rank.score`` and ``rank.noise`` are re-derived so list queries keep
        using the plain ``rank.noise`` filter and ``rank.score`` sort.
        """
        if value is not None and value not in USER_RANKS:
            self._log.warning("Unknown user rank %r for tag %s", value, tag)
            return False
        query: dict[str, Any] = {"owner": owner, "tag": tag}
        try:
            for attempt in range(3):
                doc: Optional[dict] = self._db.tags.find_one(query)
                if not doc:
                    return False
                rank: Any = doc.get("rank")
                derived: dict[str, Any] = apply_derived(
                    rank if isinstance(rank, dict) else {},
                    int(doc.get("posts_count") or 0),
                    value,
                )
                update: dict[str, Any] = self._user_rank_update(derived, value)
                snapshot: dict[str, Any] = {**query, **rank_snapshot_filter(doc)}
                if self._db.tags.update_one(snapshot, update).matched_count > 0:
                    return True
            self._log.warning("Tag rank inputs kept changing for tag %s", tag)
            return False
        except Exception as exc:
            self._log.error("Can`t set user rank for tag %s. Info: %s", tag, exc)
            return False

    @staticmethod
    def _apply_list_filters(
        query: dict, only_unread: Optional[bool], hide_noise: bool
    ) -> dict:
        """Add the unread and generic-tag filters shared by list queries."""
        if only_unread:
            query["unread_count"] = {"$gt": 0}
        if hide_noise:
            query.update(NOISE_FILTER)
        return query

    @staticmethod
    def _find_params(opts: Optional[dict], projection: Optional[dict]) -> dict:
        params: dict[str, Any] = {}
        if opts and "offset" in opts:
            params["skip"] = opts["offset"]
        if opts and "limit" in opts:
            params["limit"] = opts["limit"]
        if projection:
            params["projection"] = projection
        return params

    def _find_sorted(
        self,
        query: dict,
        only_unread: Optional[bool],
        sort: str,
        hide_noise: bool,
        opts: Optional[dict],
        projection: Optional[dict],
    ) -> Iterator[dict]:
        if opts and "regexp" in opts:
            query["tag"] = {"$regex": opts["regexp"], "$options": "i"}
        self._apply_list_filters(query, only_unread, hide_noise)
        return (
            self._db.tags.find(query, **self._find_params(opts, projection))
            .allow_disk_use(True)
            .sort(sort_fields(sort, bool(only_unread)))
        )

    def get_all(
        self,
        owner: str,
        only_unread: Optional[bool] = None,
        sort: str = "count",
        opts: Optional[dict] = None,
        projection: Optional[dict] = None,
        hide_noise: bool = False,
    ) -> Iterator[dict]:
        query: dict[str, Any] = {"owner": owner}
        if opts and "topic_backed" in opts:
            query["topic_backed"] = bool(opts["topic_backed"])
        return self._find_sorted(query, only_unread, sort, hide_noise, opts, projection)

    def count(
        self,
        owner: str,
        only_unread: Optional[bool] = None,
        regexp: str = "",
        sentiments: Optional[List[str]] = None,
        groups: Optional[List[str]] = None,
        topic_backed: Optional[bool] = None,
        hide_noise: bool = False,
    ) -> int:
        query = {"owner": owner}
        if regexp:
            query["tag"] = {"$regex": regexp, "$options": "i"}
        self._apply_list_filters(query, only_unread, hide_noise)
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
        if topic_backed is not None:
            query["topic_backed"] = topic_backed

        return self._db.tags.count_documents(query)

    def get_topic_backed_names(
        self, owner: str, only_unread: Optional[bool] = None
    ) -> set[str]:
        """Return names of tags marked as occurring in post topics."""
        query = {"owner": owner, "topic_backed": True}
        if only_unread:
            query["unread_count"] = {"$gt": 0}
        return {
            str(tag_doc["tag"])
            for tag_doc in self._db.tags.find(query, projection={"tag": 1, "_id": 0})
            if tag_doc.get("tag")
        }

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
            self._db.tags.bulk_write(updates, ordered=False)

        return True

    def add_sentiment(self, owner: str, tag: str, sentiment: List[str]) -> bool:
        self._db.tags.update_one(
            {"owner": owner, "tag": tag}, {"$set": {"sentiment": sentiment}}
        )

        return True

    def get_sentiments(self, owner: str, only_unread: bool) -> tuple:
        query = {"owner": owner, "sentiment": {"$exists": True}}
        if only_unread:
            query["unread_count"] = {"$gt": 0}

        cur = self._db.tags.aggregate(
            [
                {"$match": query},
                {"$group": {"_id": "$sentiment", "counter": {"$sum": 1}}},
            ]
        )
        sentiments = set()
        for sents in cur:
            for sent in sents["_id"]:
                sentiments.add(sent)

        return tuple(sentiments)

    def get_by_sentiment(
        self,
        owner: str,
        sentiments: List[str],
        only_unread: Optional[bool] = None,
        sort: str = "count",
        opts: Optional[dict] = None,
        projection: Optional[dict] = None,
        hide_noise: bool = False,
    ) -> Iterator[dict]:
        query = {
            "owner": owner,
            "$and": [
                {"sentiment": {"$exists": True}},
                {"sentiment": {"$all": sentiments}},
            ],
        }
        return self._find_sorted(query, only_unread, sort, hide_noise, opts, projection)

    def get_by_group(
        self,
        owner: str,
        groups: List[str],
        only_unread: Optional[bool] = None,
        sort: str = "count",
        opts: Optional[dict] = None,
        projection: Optional[dict] = None,
        hide_noise: bool = False,
    ) -> Iterator[dict]:
        query = {
            "owner": owner,
            "$and": [{"groups": {"$exists": True}}, {"groups": {"$all": groups}}],
        }
        return self._find_sorted(query, only_unread, sort, hide_noise, opts, projection)

    def add_groups(self, owner: str, tags_groups: dict) -> bool:
        updates = []
        for tag, groups in tags_groups.items():
            updates.append(
                UpdateOne(
                    {"owner": owner, "tag": tag}, {"$set": {"groups": list(groups)}}
                )
            )
        if updates:
            self._db.tags.bulk_write(updates)

        return True

    def get_groups(self, owner: str, only_unread: bool = False) -> dict:
        query = {"owner": owner, "groups": {"$exists": True}}
        if only_unread:
            query["unread_count"] = {"$gt": 0}

        aggr = self._db.tags.aggregate(
            [{"$match": query}, {"$group": {"_id": "$groups", "counter": {"$sum": 1}}}]
        )
        groups = defaultdict(int)
        for agg in aggr:
            for group in agg["_id"]:
                groups[group] += 1

        return groups

    def mark_entities(self, owner: str, entities: dict[str, int]) -> bool:
        """Flag tags as named entities and count NER hits; never touches temperature."""
        updates = [
            UpdateOne(
                {"owner": owner, "tag": tag},
                {"$set": {"rank.is_entity": True, "rank_pending": True}, "$inc": {"ner": number}},
            )
            for tag, number in entities.items()
        ]
        if not updates:
            return True
        try:
            self._db.tags.bulk_write(updates, ordered=False)
        except Exception as e:
            self._log.error("Can`t mark entities for %s. Info: %s", owner, e)
            return False
        return True

    def add_classifications(self, owner: str, tag: str, classifications: list) -> bool:
        self._db.tags.update_one(
            {"owner": owner, "tag": tag}, {"$set": {"classifications": classifications}}
        )

        return True

    def get_categories(self, owner: str, only_unread: bool = False) -> dict:
        query = {"owner": owner, "classifications": {"$exists": True}}
        if only_unread:
            query["unread_count"] = {"$gt": 0}

        aggr = self._db.tags.aggregate(
            [
                {"$match": query},
                {"$unwind": "$classifications"},
                {
                    "$group": {
                        "_id": "$classifications.category",
                        "counter": {"$sum": 1},
                    }
                },
            ]
        )
        categories = defaultdict(int)
        for agg in aggr:
            categories[agg["_id"]] = agg["counter"]

        return categories

    def get_by_category(
        self,
        owner: str,
        category: str,
        only_unread: Optional[bool] = None,
        sort: str = "count",
        opts: Optional[dict] = None,
        projection: Optional[dict] = None,
        hide_noise: bool = False,
    ) -> Iterator[dict]:
        query = {"owner": owner, "classifications.category": category}
        return self._find_sorted(query, only_unread, sort, hide_noise, opts, projection)

    def count_by_category(
        self,
        owner: str,
        category: str,
        only_unread: bool = False,
        hide_noise: bool = False,
    ) -> int:
        query = {"owner": owner, "classifications.category": category}
        self._apply_list_filters(query, only_unread, hide_noise)
        return self._db.tags.count_documents(query)
