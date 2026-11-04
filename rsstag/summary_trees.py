"""Summary tree persistence (``summary_trees`` collection).

A summary tree is a focus (entity) plus a document-set ``filters`` dict and
``options``. The worker pipeline in ``rsstag.summary_tree`` fills ``result``;
this module owns the collection, claiming and progress updates.
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING, ReturnDocument
from pymongo.database import Database

from rsstag.summary_tree.filters import filters_hash, normalize_filters, normalize_options

STATUS_PENDING: str = "pending"
STATUS_PROCESSING: str = "processing"
STATUS_DONE: str = "done"
STATUS_FAILED: str = "failed"
PROCESSING_TIMEOUT_SECONDS: float = 3600.0
STAGES: tuple = ("sources", "posts", "topics", "summaries", "done")

COLLECTION: str = "summary_trees"
_LIST_PROJECTION: Dict[str, int] = {"result": 0}


def is_stuck(doc: Dict[str, Any]) -> bool:
    return (
        doc.get("status") == STATUS_PROCESSING
        and float(doc.get("updated_at") or 0) <= time.time() - PROCESSING_TIMEOUT_SECONDS
    )


def _claim_fields(run_id: str) -> Dict[str, Any]:
    return {
        "status": STATUS_PROCESSING, "run_id": run_id, "stage": None,
        "progress": {"done": 0, "total": 0}, "error": None, "updated_at": time.time(),
    }


class RssTagSummaryTrees:
    """CRUD, claiming and progress for summary trees."""

    def __init__(self, db: Database) -> None:
        self._db: Database = db
        self._log: logging.Logger = logging.getLogger("summary_trees")

    @property
    def _coll(self) -> Any:
        return self._db[COLLECTION]

    def prepare(self) -> None:
        try:
            self._coll.create_index([("owner", 1), ("status", 1)])
            self._coll.create_index([("owner", 1), ("filters_hash", 1)], unique=True)
        except Exception as exc:
            self._log.warning("Can't create summary tree indexes: %s", exc)

    def create(self, owner: str, filters: Any, options: Any = None) -> Optional[str]:
        """Create or reuse the tree for (owner, filters, options)."""
        norm_filters: Dict[str, Any] = normalize_filters(filters)
        norm_options: Dict[str, Any] = normalize_options(options)
        key: str = filters_hash(norm_filters, norm_options)
        now: float = time.time()
        try:
            doc: Optional[Dict[str, Any]] = self._coll.find_one_and_update(
                {"owner": owner, "filters_hash": key},
                {"$setOnInsert": self._new_doc(owner, norm_filters, norm_options, key, now)},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            return str(doc["_id"]) if doc else None
        except Exception as exc:
            self._log.error("Can't create summary tree for %s: %s", owner, exc)
            return None

    def find(self, owner: str, filters: Any, options: Any = None) -> Optional[Dict[str, Any]]:
        key: str = filters_hash(normalize_filters(filters), normalize_options(options))
        try:
            return self._serialize(
                self._coll.find_one({"owner": owner, "filters_hash": key}, projection=_LIST_PROJECTION)
            )
        except Exception as exc:
            self._log.error("Can't find summary tree for %s: %s", owner, exc)
            return None

    def get_by_id(self, owner: str, tree_id: Any) -> Optional[Dict[str, Any]]:
        object_id: Optional[ObjectId] = _to_object_id(tree_id)
        if object_id is None:
            return None
        try:
            return self._serialize(self._coll.find_one({"_id": object_id, "owner": owner}))
        except Exception as exc:
            self._log.error("Can't get summary tree %s: %s", tree_id, exc)
            return None

    def list_by_owner(self, owner: str) -> List[Dict[str, Any]]:
        try:
            cursor = self._coll.find({"owner": owner}, projection=_LIST_PROJECTION).sort(
                "updated_at", DESCENDING
            )
            return [doc for doc in (self._serialize(raw) for raw in cursor) if doc]
        except Exception as exc:
            self._log.error("Can't list summary trees for %s: %s", owner, exc)
            return []

    def count_pending(self, owner: str) -> int:
        return self._coll.count_documents({"owner": owner, "status": STATUS_PENDING})

    def claim_next(self, owner: str) -> Optional[Dict[str, Any]]:
        """Atomically claim the oldest pending tree of an owner."""
        return self._coll.find_one_and_update(
            {"owner": owner, "status": STATUS_PENDING},
            {"$set": _claim_fields(uuid.uuid4().hex)},
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )

    def set_stage(self, tree_id: Any, owner: str, run_id: str, stage: str, total: int = 0) -> bool:
        return self._update(tree_id, owner, run_id, {"stage": stage, "progress": {"done": 0, "total": total}})

    def set_progress(self, tree_id: Any, owner: str, run_id: str, done: int) -> bool:
        """Also acts as the run heartbeat."""
        return self._update(tree_id, owner, run_id, {"progress.done": done})

    def save_partial(self, tree_id: Any, owner: str, run_id: str, result: Dict[str, Any]) -> bool:
        """Save successful nodes immediately, fenced by the active run."""
        return self._update(tree_id, owner, run_id, {"result": result})

    def save_result(self, tree_id: Any, owner: str, run_id: str, result: Dict[str, Any]) -> bool:
        return self._update(
            tree_id, owner, run_id,
            {"result": result, "post_ids": sorted(str(post.get("pid")) for post in result.get("posts") or []),
             "status": STATUS_DONE, "stage": "done", "error": None},
        )

    def fail(self, tree_id: Any, owner: str, run_id: Optional[str], message: str) -> bool:
        fields: Dict[str, Any] = {"status": STATUS_FAILED, "error": message[:500]}
        if run_id is None:
            return self._update_any(tree_id, owner, fields)
        return self._update(tree_id, owner, run_id, fields)

    def reset_for_retry(self, owner: str, tree_id: Any) -> bool:
        object_id: Optional[ObjectId] = _to_object_id(tree_id)
        if object_id is None:
            return False
        now: float = time.time()
        query: Dict[str, Any] = {
            "_id": object_id, "owner": owner,
            "$or": [
                {"status": {"$ne": STATUS_PROCESSING}},
                {"updated_at": {"$not": {"$gt": now - PROCESSING_TIMEOUT_SECONDS}}},
            ],
        }
        try:
            result: Any = self._coll.update_one(
                query,
                {"$set": {"status": STATUS_PENDING, "stage": None, "error": None, "updated_at": now},
                 "$unset": {"run_id": ""}},
            )
            return result.matched_count > 0
        except Exception as exc:
            self._log.exception("Can't reset summary tree %s: %s", tree_id, exc)
            return False

    def delete(self, owner: str, tree_id: Any) -> bool:
        object_id: Optional[ObjectId] = _to_object_id(tree_id)
        if object_id is None:
            return False
        try:
            return self._coll.delete_one({"_id": object_id, "owner": owner}).deleted_count > 0
        except Exception as exc:
            self._log.error("Can't delete summary tree %s: %s", tree_id, exc)
            return False

    def _update(self, tree_id: Any, owner: str, run_id: str, fields: Dict[str, Any]) -> bool:
        object_id: Optional[ObjectId] = _to_object_id(tree_id)
        if object_id is None:
            return False
        query: Dict[str, Any] = {
            "_id": object_id, "owner": owner, "status": STATUS_PROCESSING, "run_id": run_id,
        }
        try:
            result: Any = self._coll.update_one(query, {"$set": {**fields, "updated_at": time.time()}})
            return result.matched_count > 0
        except Exception as exc:
            self._log.error("Can't update summary tree %s: %s", tree_id, exc)
            return False

    def _update_any(self, tree_id: Any, owner: str, fields: Dict[str, Any]) -> bool:
        object_id: Optional[ObjectId] = _to_object_id(tree_id)
        if object_id is None:
            return False
        try:
            result: Any = self._coll.update_one(
                {"_id": object_id, "owner": owner}, {"$set": {**fields, "updated_at": time.time()}}
            )
            return result.matched_count > 0
        except Exception as exc:
            self._log.error("Can't update summary tree %s: %s", tree_id, exc)
            return False

    @staticmethod
    def _new_doc(
        owner: str, filters: Dict[str, Any], options: Dict[str, Any], key: str, now: float
    ) -> Dict[str, Any]:
        return {
            "owner": owner,
            "focus": str(filters.get("entity") or ""),
            "filters": filters,
            "options": options,
            "filters_hash": key,
            "status": STATUS_PENDING,
            "stage": None,
            "progress": {"done": 0, "total": 0},
            "error": None,
            "result": None,
            "post_ids": [],
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def _serialize(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not doc:
            return None
        result: Dict[str, Any] = dict(doc)
        result["_id"] = str(result["_id"])
        return result


def _to_object_id(value: Any) -> Optional[ObjectId]:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        return None
