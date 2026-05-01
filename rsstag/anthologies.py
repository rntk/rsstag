"""Anthology persistence helpers."""

import hashlib
import json
import logging
import time
from typing import Any, Dict, Iterator, Optional

from bson import ObjectId
from pymongo import DESCENDING, MongoClient, ReturnDocument


class RssTagAnthologies:
    """Persist anthology metadata and results."""

    def __init__(self, db: MongoClient) -> None:
        self._db: MongoClient = db
        self._log = logging.getLogger("anthologies")

    def prepare(self) -> None:
        """Create indexes for anthology lookups."""
        try:
            self._db.anthologies.create_index("owner")
            self._db.anthologies.create_index("status")
            self._db.anthologies.create_index("stale")
            self._db.anthologies.create_index([("owner", 1), ("updated_at", DESCENDING)])
            self._db.anthologies.create_index(
                [
                    ("owner", 1),
                    ("seed_type", 1),
                    ("seed_value", 1),
                    ("scope_hash", 1),
                ],
                unique=True,
            )
        except Exception as exc:
            self._log.warning(
                "Can't create anthology indexes. May already exist. Info: %s",
                exc,
            )

    def create(
        self,
        owner: str,
        seed_type: str,
        seed_value: str,
        scope: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Create or reuse an anthology root document."""
        try:
            normalized_scope: Dict[str, Any] = self._normalize_scope(scope)
            scope_hash: str = self._scope_hash(normalized_scope)
            now_ts: float = time.time()
            doc = self._db.anthologies.find_one_and_update(
                {
                    "owner": owner,
                    "seed_type": seed_type,
                    "seed_value": seed_value,
                    "scope_hash": scope_hash,
                },
                {
                    "$setOnInsert": {
                        "owner": owner,
                        "seed_type": seed_type,
                        "seed_value": seed_value,
                        "scope": normalized_scope,
                        "scope_hash": scope_hash,
                        "status": "pending",
                        "stale": False,
                        "source_snapshot": {
                            "post_grouping_updated_at": None,
                            "post_grouping_doc_ids": [],
                        },
                        "current_run_id": None,
                        "result": None,
                        "created_at": now_ts,
                        "updated_at": now_ts,
                    }
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            if not doc:
                return None
            return str(doc["_id"])
        except Exception as exc:
            self._log.error("Can't create anthology for %s. Info: %s", owner, exc)
            return None

    def get_by_id(self, owner: str, anthology_id: Any) -> Optional[Dict[str, Any]]:
        """Fetch anthology by id for an owner."""
        try:
            object_id: ObjectId = self._to_object_id(anthology_id)
            doc = self._db.anthologies.find_one({"_id": object_id, "owner": owner})
            return self._serialize_doc(doc)
        except Exception as exc:
            self._log.error("Can't get anthology %s. Info: %s", anthology_id, exc)
            return None

    def list_by_owner(
        self,
        owner: str,
        status: Optional[str] = None,
        include_stale: Optional[bool] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Iterate anthologies for an owner."""
        query: Dict[str, Any] = {"owner": owner}
        if status:
            query["status"] = status
        if include_stale is not None:
            query["stale"] = include_stale

        cursor = self._db.anthologies.find(query).sort("updated_at", DESCENDING)
        for doc in cursor:
            serialized = self._serialize_doc(doc)
            if serialized:
                yield serialized

    def update_status(self, anthology_id: Any, status: str) -> bool:
        """Update anthology status."""
        try:
            result = self._db.anthologies.update_one(
                {"_id": self._to_object_id(anthology_id)},
                {"$set": {"status": status, "updated_at": time.time()}},
            )
            return result.matched_count > 0
        except Exception as exc:
            self._log.error("Can't update anthology status %s. Info: %s", anthology_id, exc)
            return False

    def update_result(
        self,
        anthology_id: Any,
        result: Dict[str, Any],
        run_id: Optional[Any],
        source_snapshot: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store anthology result and mark it completed."""
        try:
            update_data: Dict[str, Any] = {
                "result": result,
                "status": "done",
                "updated_at": time.time(),
                "stale": False,
                "source_snapshot": source_snapshot
                or {"post_grouping_updated_at": None, "post_grouping_doc_ids": []},
            }
            if run_id is not None:
                update_data["current_run_id"] = self._to_object_id(run_id)
            result_doc = self._db.anthologies.update_one(
                {"_id": self._to_object_id(anthology_id)},
                {"$set": update_data},
            )
            return result_doc.matched_count > 0
        except Exception as exc:
            self._log.error("Can't update anthology result %s. Info: %s", anthology_id, exc)
            return False

    def mark_stale_for_source_change(self, owner: str, changed_post_ids: list[str]) -> int:
        """Mark anthologies stale when source post ids change."""
        if not changed_post_ids:
            return 0
        try:
            result = self._db.anthologies.update_many(
                {
                    "owner": owner,
                    "result.source_refs.post_id": {"$in": [str(post_id) for post_id in changed_post_ids]},
                },
                {"$set": {"stale": True, "updated_at": time.time()}},
            )
            return int(result.modified_count)
        except Exception as exc:
            self._log.error("Can't mark anthologies stale for %s. Info: %s", owner, exc)
            return 0

    def get_pending(self, owner: str) -> Optional[Dict[str, Any]]:
        """Return the next pending anthology for an owner."""
        doc = self._db.anthologies.find_one(
            {"owner": owner, "status": "pending"},
            sort=[("created_at", 1)],
        )
        return self._serialize_doc(doc)

    def delete(self, owner: str, anthology_id: Any) -> bool:
        """Delete anthology for an owner."""
        try:
            result = self._db.anthologies.delete_one(
                {"_id": self._to_object_id(anthology_id), "owner": owner}
            )
            return result.deleted_count > 0
        except Exception as exc:
            self._log.error("Can't delete anthology %s. Info: %s", anthology_id, exc)
            return False

    @staticmethod
    def _normalize_scope(scope: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(scope, dict):
            return {"mode": "all"}
        mode = str(scope.get("mode", "all")).strip() or "all"
        normalized: Dict[str, Any] = {"mode": mode}
        for key in ("post_ids", "feed_ids", "category_ids"):
            values = scope.get(key)
            if isinstance(values, list) and values:
                normalized[key] = [str(value) for value in values if value]
        provider = str(scope.get("provider", "")).strip()
        if provider:
            normalized["provider"] = provider
        return normalized

    @staticmethod
    def _scope_hash(scope: Dict[str, Any]) -> str:
        payload: str = json.dumps(scope, sort_keys=True, separators=(",", ":"))
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _to_object_id(value: Any) -> ObjectId:
        if isinstance(value, ObjectId):
            return value
        return ObjectId(str(value))

    def _serialize_doc(self, doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not doc:
            return None
        result: Dict[str, Any] = dict(doc)
        result["_id"] = str(result["_id"])
        if result.get("current_run_id") is not None:
            result["current_run_id"] = str(result["current_run_id"])
        return result


class RssTagAnthologyRuns:
    """Persist anthology execution runs."""

    def __init__(self, db: MongoClient) -> None:
        self._db: MongoClient = db
        self._log = logging.getLogger("anthology_runs")

    def prepare(self) -> None:
        """Create indexes for run lookup."""
        try:
            self._db.anthology_runs.create_index("owner")
            self._db.anthology_runs.create_index(
                [("anthology_id", 1), ("started_at", DESCENDING)]
            )
        except Exception as exc:
            self._log.warning(
                "Can't create anthology run indexes. May already exist. Info: %s",
                exc,
            )

    def create(self, anthology_id: Any, owner: str) -> Optional[str]:
        """Create a run record."""
        try:
            now_ts: float = time.time()
            doc: Dict[str, Any] = {
                "anthology_id": self._to_object_id(anthology_id),
                "owner": owner,
                "status": "processing",
                "started_at": now_ts,
                "finished_at": None,
                "error": None,
                "turns": [],
            }
            result = self._db.anthology_runs.insert_one(doc)
            return str(result.inserted_id)
        except Exception as exc:
            self._log.error("Can't create anthology run for %s. Info: %s", owner, exc)
            return None

    def append_turn(self, run_id: Any, turn_data: Dict[str, Any]) -> bool:
        """Append a turn to a run."""
        try:
            result = self._db.anthology_runs.update_one(
                {"_id": self._to_object_id(run_id)},
                {"$push": {"turns": turn_data}},
            )
            return result.matched_count > 0
        except Exception as exc:
            self._log.error("Can't append anthology run turn %s. Info: %s", run_id, exc)
            return False

    def finish(self, run_id: Any, status: str, error: Optional[str] = None) -> bool:
        """Mark a run finished."""
        try:
            result = self._db.anthology_runs.update_one(
                {"_id": self._to_object_id(run_id)},
                {
                    "$set": {
                        "status": status,
                        "error": error,
                        "finished_at": time.time(),
                    }
                },
            )
            return result.matched_count > 0
        except Exception as exc:
            self._log.error("Can't finish anthology run %s. Info: %s", run_id, exc)
            return False

    def get_latest_for_anthology(self, owner: str, anthology_id: Any) -> Optional[Dict[str, Any]]:
        """Return the latest run for an anthology."""
        try:
            doc = self._db.anthology_runs.find_one(
                {"owner": owner, "anthology_id": self._to_object_id(anthology_id)},
                sort=[("started_at", DESCENDING)],
            )
            if not doc:
                return None
            doc["_id"] = str(doc["_id"])
            doc["anthology_id"] = str(doc["anthology_id"])
            return doc
        except Exception as exc:
            self._log.error("Can't get anthology run for %s. Info: %s", anthology_id, exc)
            return None

    def delete_for_anthology(self, owner: str, anthology_id: Any) -> bool:
        """Delete all runs for an anthology."""
        try:
            self._db.anthology_runs.delete_many(
                {"owner": owner, "anthology_id": self._to_object_id(anthology_id)}
            )
            return True
        except Exception as exc:
            self._log.error("Can't delete anthology runs for %s. Info: %s", anthology_id, exc)
            return False

    @staticmethod
    def _to_object_id(value: Any) -> ObjectId:
        if isinstance(value, ObjectId):
            return value
        return ObjectId(str(value))
