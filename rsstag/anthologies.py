"""Anthology persistence helpers.

An anthology is a seed (tag or topic label) plus a scope. The worker pipeline
in ``rsstag.anthology`` fills ``result`` with clusters/themes; this module only
owns the ``anthologies`` collection.
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING, ReturnDocument
from pymongo.database import Database

STATUS_PENDING: str = "pending"
STATUS_PROCESSING: str = "processing"
STATUS_DONE: str = "done"
STATUS_FAILED: str = "failed"

PROCESSING_TIMEOUT_SECONDS: float = 3600.0


def is_stuck(doc: Dict[str, Any]) -> bool:
    """A processing run without progress for an hour can be retried."""
    return (
        doc.get("status") == STATUS_PROCESSING
        and float(doc.get("updated_at") or 0) <= time.time() - PROCESSING_TIMEOUT_SECONDS
    )


STAGES: tuple = ("units", "candidates", "merge", "label", "intruder", "themes", "done")

_LIST_PROJECTION: Dict[str, int] = {"result.snippets": 0, "result.clusters": 0}


class RssTagAnthologies:
    """Persist anthology metadata, progress and results."""

    def __init__(self, db: Database) -> None:
        self._db: Database = db
        self._log: logging.Logger = logging.getLogger("anthologies")

    def prepare(self) -> None:
        """Create indexes for anthology lookups."""
        try:
            self._db.anthologies.create_index("owner")
            self._db.anthologies.create_index([("owner", 1), ("status", 1)])
            self._db.anthologies.create_index([("owner", 1), ("post_ids", 1)])
            self._db.anthologies.create_index(
                [("owner", 1), ("seed_type", 1), ("seed_value", 1), ("scope_hash", 1)],
                unique=True,
            )
        except Exception as exc:
            self._log.warning("Can't create anthology indexes. May already exist. Info: %s", exc)

    def create(
        self,
        owner: str,
        seed_type: str,
        seed_value: str,
        scope: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Create or reuse the anthology for (owner, seed, scope)."""
        try:
            normalized_scope: Dict[str, Any] = self._normalize_scope(scope)
            scope_hash: str = self._scope_hash(normalized_scope)
            now_ts: float = time.time()
            doc: Optional[Dict[str, Any]] = self._db.anthologies.find_one_and_update(
                {
                    "owner": owner,
                    "seed_type": seed_type,
                    "seed_value": seed_value,
                    "scope_hash": scope_hash,
                },
                {"$setOnInsert": self._new_doc(owner, seed_type, seed_value, normalized_scope, scope_hash, now_ts)},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            return str(doc["_id"]) if doc else None
        except Exception as exc:
            self._log.error("Can't create anthology for %s. Info: %s", owner, exc)
            return None

    def get_by_id(self, owner: str, anthology_id: Any) -> Optional[Dict[str, Any]]:
        """Fetch an anthology of an owner; invalid ids yield None."""
        object_id: Optional[ObjectId] = self._to_object_id(anthology_id)
        if object_id is None:
            return None
        try:
            doc = self._db.anthologies.find_one({"_id": object_id, "owner": owner})
            return self._serialize_doc(doc)
        except Exception as exc:
            self._log.error("Can't get anthology %s. Info: %s", anthology_id, exc)
            return None

    def list_by_owner(self, owner: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List anthologies (without heavy result parts), newest first."""
        query: Dict[str, Any] = {"owner": owner}
        if status:
            query["status"] = status
        try:
            cursor = self._db.anthologies.find(query, projection=_LIST_PROJECTION).sort(
                "updated_at", DESCENDING
            )
            return [doc for doc in (self._serialize_doc(raw) for raw in cursor) if doc]
        except Exception as exc:
            self._log.error("Can't list anthologies for %s. Info: %s", owner, exc)
            return []

    def update_status(self, anthology_id: Any, status: str, error: Optional[str] = None) -> bool:
        """Set status (and error message) of an anthology."""
        return self._update(anthology_id, {"status": status, "error": error})

    def set_stage(self, anthology_id: Any, stage: str) -> bool:
        """Record the pipeline stage currently running."""
        return self._update(anthology_id, {"stage": stage})

    def save_result(self, anthology_id: Any, result: Dict[str, Any]) -> bool:
        """Store a finished result and mark the anthology done."""
        return self._update(
            anthology_id,
            {
                "result": result,
                "post_ids": self._result_post_ids(result),
                "status": STATUS_DONE,
                "stage": "done",
                "stale": False,
                "error": None,
            },
        )

    def mark_stale_for_source_change(self, owner: str, changed_post_ids: List[str]) -> int:
        """Mark done anthologies built from any of the changed posts stale."""
        if not changed_post_ids:
            return 0
        try:
            result = self._db.anthologies.update_many(
                {
                    "owner": owner,
                    "status": STATUS_DONE,
                    "post_ids": {"$in": [str(post_id) for post_id in changed_post_ids]},
                },
                {"$set": {"stale": True, "updated_at": time.time()}},
            )
            return int(result.modified_count)
        except Exception as exc:
            self._log.error("Can't mark anthologies stale for %s. Info: %s", owner, exc)
            return 0

    def get_pending(self, owner: str) -> Optional[Dict[str, Any]]:
        """Return the oldest pending anthology for an owner."""
        try:
            doc = self._db.anthologies.find_one(
                {"owner": owner, "status": STATUS_PENDING}, sort=[("created_at", 1)]
            )
            return self._serialize_doc(doc)
        except Exception as exc:
            self._log.error("Can't get pending anthology for %s. Info: %s", owner, exc)
            return None

    def reset_for_retry(self, owner: str, anthology_id: Any) -> bool:
        """Put an anthology back to pending; the old result stays until replaced."""
        object_id: Optional[ObjectId] = self._to_object_id(anthology_id)
        if object_id is None:
            return False
        now: float = time.time()
        query: Dict[str, Any] = {
            "_id": object_id,
            "owner": owner,
            "$or": [
                {"status": {"$ne": STATUS_PROCESSING}},
                {
                    "status": STATUS_PROCESSING,
                    "updated_at": {"$not": {"$gt": now - PROCESSING_TIMEOUT_SECONDS}},
                },
            ],
        }
        try:
            result: Any = self._db.anthologies.update_one(
                query,
                {"$set": {"status": STATUS_PENDING, "stage": None, "error": None, "updated_at": now}},
            )
            return result.matched_count > 0
        except Exception as exc:
            self._log.exception("Can't reset anthology %s: %s", anthology_id, exc)
            return False

    def delete(self, owner: str, anthology_id: Any) -> bool:
        """Delete an anthology of an owner."""
        object_id: Optional[ObjectId] = self._to_object_id(anthology_id)
        if object_id is None:
            return False
        try:
            result = self._db.anthologies.delete_one({"_id": object_id, "owner": owner})
            return result.deleted_count > 0
        except Exception as exc:
            self._log.error("Can't delete anthology %s. Info: %s", anthology_id, exc)
            return False

    def _update(self, anthology_id: Any, fields: Dict[str, Any], owner: Optional[str] = None) -> bool:
        object_id: Optional[ObjectId] = self._to_object_id(anthology_id)
        if object_id is None:
            return False
        query: Dict[str, Any] = {"_id": object_id}
        if owner is not None:
            query["owner"] = owner
        try:
            result = self._db.anthologies.update_one(
                query, {"$set": {**fields, "updated_at": time.time()}}
            )
            return result.matched_count > 0
        except Exception as exc:
            self._log.error("Can't update anthology %s. Info: %s", anthology_id, exc)
            return False

    @staticmethod
    def _new_doc(
        owner: str,
        seed_type: str,
        seed_value: str,
        scope: Dict[str, Any],
        scope_hash: str,
        now_ts: float,
    ) -> Dict[str, Any]:
        return {
            "owner": owner,
            "seed_type": seed_type,
            "seed_value": seed_value,
            "scope": scope,
            "scope_hash": scope_hash,
            "status": STATUS_PENDING,
            "stage": None,
            "error": None,
            "stale": False,
            "result": None,
            "post_ids": [],
            "created_at": now_ts,
            "updated_at": now_ts,
        }

    @staticmethod
    def _result_post_ids(result: Dict[str, Any]) -> List[str]:
        snippets: Any = (result or {}).get("snippets") or {}
        if not isinstance(snippets, dict):
            return []
        post_ids = {str(s.get("post_id")) for s in snippets.values() if isinstance(s, dict) and s.get("post_id") is not None}
        return sorted(post_ids)

    @staticmethod
    def _normalize_scope(scope: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(scope, dict):
            return {"mode": "all"}
        mode: str = str(scope.get("mode", "all")).strip() or "all"
        normalized: Dict[str, Any] = {"mode": mode}
        for key in ("post_ids", "feed_ids", "category_ids"):
            values: Any = scope.get(key)
            if isinstance(values, list) and values:
                normalized[key] = [str(value) for value in values if value]
        provider: str = str(scope.get("provider", "")).strip()
        if provider:
            normalized["provider"] = provider
        return normalized

    @staticmethod
    def _scope_hash(scope: Dict[str, Any]) -> str:
        payload: str = json.dumps(scope, sort_keys=True, separators=(",", ":"))
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _to_object_id(value: Any) -> Optional[ObjectId]:
        if isinstance(value, ObjectId):
            return value
        try:
            return ObjectId(str(value))
        except (InvalidId, TypeError):
            return None

    @staticmethod
    def _serialize_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not doc:
            return None
        result: Dict[str, Any] = dict(doc)
        result["_id"] = str(result["_id"])
        return result
