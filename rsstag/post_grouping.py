"""Post grouping data management and DB dispatching"""

import logging
from typing import Optional, List, Dict, Any
from pymongo import MongoClient
import hashlib


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

    def get_grouped_posts(self, owner: str, post_ids: List[int]) -> Optional[dict]:
        """Get grouped posts data by owner and post IDs"""
        post_ids_hash = self._generate_post_ids_hash(post_ids)
        return self._db.post_grouping.find_one(
            {"owner": owner, "post_ids_hash": post_ids_hash}
        )

    def save_grouped_posts(
        self,
        owner: str,
        post_ids: List[int],
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

    def mark_sequences_read(self, owner: str, post_id: int, read_status: bool) -> bool:
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

    def _generate_post_ids_hash(self, post_ids: List[int]) -> str:
        """Generate a hash from post IDs for unique identification"""
        post_ids_sorted = sorted(post_ids)
        post_ids_str = ",".join(str(pid) for pid in post_ids_sorted)
        return hashlib.md5(post_ids_str.encode("utf-8")).hexdigest()
