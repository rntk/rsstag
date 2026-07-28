"""Post grouping data management and DB dispatching"""

import logging
import time
from typing import Optional, List, Dict, Any, Union, Iterator, Set
from pymongo import MongoClient
import hashlib

from rsstag.anthologies import RssTagAnthologies

PostId = Union[int, str]


class RssTagPostGrouping:
    """Post grouping dispatcher handling DB operations"""

    def __init__(self, db: MongoClient) -> None:
        self._db: MongoClient = db
        self._log = logging.getLogger("post_grouping")
        self._anthologies = RssTagAnthologies(db)

    def prepare(self) -> None:
        """Create indexes for post_grouping collection"""
        try:
            self._db.post_grouping.create_index("owner")
            self._db.post_grouping.create_index("post_ids_hash")
            self._db.post_grouping.create_index(
                [("owner", 1), ("post_ids_hash", 1)], unique=True
            )
            # Lookups by a single post id (post links block) match on membership,
            # not on the exact id list the hash identifies.
            self._db.post_grouping.create_index([("owner", 1), ("post_ids", 1)])
        except Exception as e:
            self._log.warning(
                "Can't create post_grouping indexes. May already exist. Info: %s", e
            )

    def get_grouped_posts(self, owner: str, post_ids: List[PostId]) -> Optional[dict]:
        """Get grouped posts data by owner and post IDs"""
        post_ids_hash = self._generate_post_ids_hash(post_ids)
        return self._db.post_grouping.find_one(
            {"owner": owner, "post_ids_hash": post_ids_hash}
        )

    def get_all_by_owner(self, owner: str, projection: Optional[dict] = None) -> Iterator[dict]:
        """Get all grouped posts data by owner"""
        return self._db.post_grouping.find({"owner": owner}, projection=projection)

    def get_by_post_id(
        self, owner: str, post_id: PostId, projection: Optional[dict] = None
    ) -> List[dict]:
        """Get every grouping doc of an owner that contains the given post id.

        Unlike `get_grouped_posts` this matches multi post groupings too: the
        hash identifies an exact post id list, while a post may be grouped
        together with others. Post ids are stored both as int and as str
        depending on the writer, so both variants are queried.
        """
        if post_id is None:
            return []

        query_values: List[PostId] = [post_id]
        for value in (str(post_id), self._as_int(post_id)):
            if value is not None and value not in query_values:
                query_values.append(value)

        try:
            return list(
                self._db.post_grouping.find(
                    {"owner": owner, "post_ids": {"$in": query_values}},
                    projection=projection,
                )
            )
        except Exception as e:
            self._log.error(
                "Can't get grouped posts for post %s. Info: %s", post_id, e
            )
            return []

    @staticmethod
    def _as_int(post_id: PostId) -> Optional[int]:
        try:
            return int(post_id)
        except (ValueError, TypeError):
            return None

    def get_existing_post_ids(
        self, owner: str, post_ids: List[PostId]
    ) -> Set[str]:
        """Return requested post ids that already have persisted grouping data."""
        normalized_post_ids: Set[str] = {
            str(post_id) for post_id in post_ids if post_id is not None
        }
        if not normalized_post_ids:
            return set()

        query_values: List[PostId] = []
        for post_id in post_ids:
            if post_id is None:
                continue
            for value in (post_id, str(post_id)):
                if value not in query_values:
                    query_values.append(value)

        post_ids_hashes: List[str] = [
            self._generate_post_ids_hash([post_id])
            for post_id in normalized_post_ids
        ]
        cursor: Iterator[dict] = self._db.post_grouping.find(
            {
                "owner": owner,
                "$or": [
                    {"post_ids_hash": {"$in": post_ids_hashes}},
                    {"post_ids": {"$in": query_values}},
                ],
            },
            projection={"post_ids": True, "_id": False},
        )

        existing_post_ids: Set[str] = set()
        for document in cursor:
            grouped_post_ids: Any = document.get("post_ids", [])
            if not isinstance(grouped_post_ids, list):
                continue
            existing_post_ids.update(
                str(post_id)
                for post_id in grouped_post_ids
                if post_id is not None and str(post_id) in normalized_post_ids
            )
        return existing_post_ids

    def save_grouped_posts(
        self,
        owner: str,
        post_ids: List[PostId],
        sentences: List[Dict[str, Any]],
        groups: Dict[str, List[int]],
    ) -> bool:
        """Save grouped posts data"""
        post_ids_hash = self._generate_post_ids_hash(post_ids)

        data = {
            "owner": owner,
            "post_ids": post_ids,
            "post_ids_hash": post_ids_hash,
            "sentences": sentences,
            "groups": groups,
            # Stamp every rewrite so the topic-merge agent can tell whether a
            # doc it collected was re-grouped mid-run (and must not be marked
            # merged with now-stale labels). See TopicMergeAgent._mark_docs_merged.
            "updated_at": time.time(),
        }

        try:
            self._db.post_grouping.update_one(
                {"owner": owner, "post_ids_hash": post_ids_hash},
                {"$set": data, "$unset": {"topic_merged": ""}},
                upsert=True,
            )
            self._anthologies.mark_stale_for_source_change(owner, [str(pid) for pid in post_ids])
            return True
        except Exception as e:
            self._log.error("Can't save grouped posts data. Info: %s", e)
            return False

    def delete_grouped_posts_by_post_ids(
        self, owner: str, post_ids: List[PostId], batch_size: int = 500
    ) -> int:
        """Delete post_grouping docs for owner where any `post_ids` value matches."""
        if not post_ids:
            return 0

        deleted_total = 0
        unique_post_ids = [pid for pid in set(str(post_id) for post_id in post_ids) if pid]
        for start in range(0, len(unique_post_ids), batch_size):
            batch = unique_post_ids[start : start + batch_size]
            result = self._db.post_grouping.delete_many(
                {"owner": owner, "post_ids": {"$in": batch}}
            )
            deleted_total += int(result.deleted_count)
            self._anthologies.mark_stale_for_source_change(owner, batch)

        return deleted_total

    def delete_grouped_posts_by_scope(self, owner: str, scope: Optional[dict]) -> int:
        """Delete post_grouping docs by owner and expanded scope."""
        post_ids = self._get_scope_post_ids(owner, scope)
        return self.delete_grouped_posts_by_post_ids(owner, post_ids)

    def get_scope_post_ids(self, owner: str, scope: Optional[dict]) -> List[PostId]:
        """Public: expand a task scope into the matching post ids."""
        return self._get_scope_post_ids(owner, scope)

    def update_snippets_read_status(
        self, owner: str, post_id: Any, sentence_indices: List[int], read_status: bool
    ) -> Optional[bool]:
        """Update read status for multiple sentences in a post's grouping

        Returns True if ALL sentences in the post are now read, False otherwise.
        Returns None when nothing was updated: the grouping doc is missing, or
        none of `sentence_indices` matched a sentence of this post. Callers use
        None to skip the post entirely instead of rolling its read state up.
        """
        post_ids = [post_id]
        post_ids_hash = self._generate_post_ids_hash(post_ids)

        doc = self.get_grouped_posts(owner, post_ids)
        if not doc:
            return None

        sentences = doc.get("sentences", [])
        indices_set = set(sentence_indices)
        all_read = True
        found_any = False
        for s in sentences:
            if s.get("number") in indices_set:
                s["read"] = read_status
                found_any = True
            if not s.get("read", False):
                all_read = False

        if not found_any:
            return None

        self._db.post_grouping.update_one(
            {"owner": owner, "post_ids_hash": post_ids_hash},
            {"$set": {"sentences": sentences}},
        )
        return all_read

    def mark_sequences_read(self, owner: str, post_id: PostId, read_status: bool) -> bool:
        """Mark ALL sentences in a post's grouping as read/unread"""
        post_ids = [post_id]
        post_ids_hash = self._generate_post_ids_hash(post_ids)

        doc = self.get_grouped_posts(owner, post_ids)
        if not doc:
            return False

        sentences = doc.get("sentences", [])
        for s in sentences:
            s["read"] = read_status

        self._db.post_grouping.update_one(
            {"owner": owner, "post_ids_hash": post_ids_hash},
            {"$set": {"sentences": sentences}},
        )
        return True

    def _generate_post_ids_hash(self, post_ids: List[PostId]) -> str:
        """Generate a hash from post IDs for unique identification"""
        # Convert to int where possible for numeric sorting, keep strings otherwise
        def to_sortable(pid: PostId) -> Union[int, str]:
            try:
                return int(pid)
            except (ValueError, TypeError):
                return str(pid)
        
        post_ids_sorted = sorted(to_sortable(pid) for pid in post_ids)
        post_ids_str = ",".join(str(pid) for pid in post_ids_sorted)
        return hashlib.md5(post_ids_str.encode("utf-8")).hexdigest()

    def _get_scope_post_ids(self, owner: str, scope: Optional[dict]) -> List[PostId]:
        query = self._build_scope_post_query(owner, scope)
        cursor = self._db.posts.find(query, projection={"pid": True})
        return [post.get("pid") for post in cursor if post.get("pid")]

    def _build_scope_post_query(self, owner: str, scope: Optional[dict]) -> Dict[str, Any]:
        query: Dict[str, Any] = {"owner": owner}
        if not isinstance(scope, dict):
            return query

        mode = scope.get("mode", "all")
        if mode == "posts":
            query["pid"] = {"$in": [str(value) for value in scope.get("post_ids", []) if value]}
        elif mode == "feeds":
            query["feed_id"] = {
                "$in": [str(value) for value in scope.get("feed_ids", []) if value]
            }
        elif mode == "categories":
            category_ids = [str(value) for value in scope.get("category_ids", []) if value]
            if category_ids:
                feeds = self._db.feeds.find(
                    {"owner": owner, "category_id": {"$in": category_ids}},
                    projection={"feed_id": True},
                )
                feed_ids = [feed.get("feed_id") for feed in feeds if feed.get("feed_id")]
                query["feed_id"] = {"$in": feed_ids}
            else:
                query["feed_id"] = {"$in": []}
        elif mode == "provider":
            provider = str(scope.get("provider", "")).strip()
            if provider:
                query["provider"] = provider

        return query
