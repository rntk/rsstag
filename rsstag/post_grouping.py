"""Post grouping data management and DB dispatching"""

import logging
from typing import Optional, List, Dict, Any, Union
from pymongo import MongoClient
import hashlib

PostId = Union[int, str]


class RssTagPostGrouping:
    """Post grouping dispatcher handling DB operations"""

    def __init__(self, db: MongoClient) -> None:
        self._db: MongoClient = db
        self._log = logging.getLogger("post_grouping")

    def prepare(self) -> None:
        """Create indexes for post_grouping collection"""
        try:
            self._db.post_grouping.create_index("owner")
            self._db.post_grouping.create_index("post_ids_hash")
            self._db.post_grouping.create_index(
                [("owner", 1), ("post_ids_hash", 1)], unique=True
            )
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

    def get_all(self, owner: str, projection: Optional[dict] = None):
        """Get all grouped posts for an owner"""
        return self._db.post_grouping.find({"owner": owner}, projection=projection)

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
        }

        try:
            self._db.post_grouping.update_one(
                {"owner": owner, "post_ids_hash": post_ids_hash},
                {"$set": data},
                upsert=True,
            )
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

        return deleted_total

    def delete_grouped_posts_by_scope(self, owner: str, scope: Optional[dict]) -> int:
        """Delete post_grouping docs by owner and expanded scope."""
        post_ids = self._get_scope_post_ids(owner, scope)
        return self.delete_grouped_posts_by_post_ids(owner, post_ids)

    def update_snippets_read_status(
        self, owner: str, post_id: Any, sentence_indices: List[int], read_status: bool
    ) -> Optional[bool]:
        """Update read status for multiple sentences in a post's grouping

        Returns True if ALL sentences in the post are now read, False otherwise.
        Returns None if post grouping not found.
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

        if found_any:
            self._db.post_grouping.update_one(
                {"owner": owner, "post_ids_hash": post_ids_hash},
                {"$set": {"sentences": sentences}},
            )
            return all_read
        return False

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

    def delete_by_post_ids(self, owner: str, pids: List[PostId]) -> None:
        """Delete groupings that contain any of the specified post IDs"""
        self._db.post_grouping.delete_many(
            {"owner": owner, "post_ids": {"$in": pids}}
        )

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
