"""Snippet cluster persistence helpers."""

import logging
import time
from typing import Any, Dict, Iterator, List, Optional

from pymongo import MongoClient


class RssTagSnippetClusters:
    """Store persisted snippet cluster results per user."""

    def __init__(self, db: MongoClient) -> None:
        self._db: MongoClient = db
        self._log = logging.getLogger("snippet_clusters")

    def prepare(self) -> None:
        """Create indexes for snippet cluster lookup."""
        try:
            self._db.snippet_clusters.create_index("owner")
            self._db.snippet_clusters.create_index(
                [("owner", 1), ("cluster_id", 1)], unique=True
            )
        except Exception as exc:
            self._log.warning(
                "Can't create snippet cluster indexes. May already exist. Info: %s",
                exc,
            )

    def replace_clusters(self, owner: str, clusters: List[Dict[str, Any]]) -> bool:
        """Replace all snippet clusters for an owner."""
        try:
            payload: List[Dict[str, Any]] = []
            now_ts: float = time.time()
            for cluster in clusters:
                item: Dict[str, Any] = dict(cluster)
                item["owner"] = owner
                item["updated_at"] = now_ts
                payload.append(item)

            self._db.snippet_clusters.delete_many({"owner": owner})
            if payload:
                self._db.snippet_clusters.insert_many(payload)
            return True
        except Exception as exc:
            self._log.error("Can't replace snippet clusters for %s. Info: %s", owner, exc)
            return False

    def get_all_by_owner(
        self, owner: str, projection: Optional[Dict[str, int]] = None
    ) -> Iterator[Dict[str, Any]]:
        """Return all clusters for an owner."""
        return self._db.snippet_clusters.find(
            {"owner": owner},
            projection=projection,
        ).sort("cluster_id", 1)

    def get_by_cluster_id(
        self,
        owner: str,
        cluster_id: int,
        projection: Optional[Dict[str, int]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return a single cluster document by owner and cluster id."""
        return self._db.snippet_clusters.find_one(
            {"owner": owner, "cluster_id": cluster_id},
            projection=projection,
        )
