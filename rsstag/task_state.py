"""Explicit task state machine for the rsstag task queue.

This module introduces an explicit ``status`` state machine on top of the
existing ``tasks`` collection. It DUAL-WRITES the legacy numeric
``processing`` field so existing readers (see ``rsstag/tasks.py``) keep
working while callers migrate to the new API.

State diagram::

    pending --claim--> running --complete--> (deleted)
    running --fail(attempts < max)--> pending (with backoff)
    running --fail(attempts >= max)--> dead
    pending/dead <--pause / resume--> paused
    running --lease expires--> reclaimable by claim

Legacy ``processing`` mapping:
    - ``pending`` / ``running(released)`` -> ``LEGACY_PROCESSING_IDLE`` (0)
    - ``dead`` / ``paused``               -> ``LEGACY_PROCESSING_FROZEN`` (-1)
    - ``running``                         -> claim timestamp (positive)

Legacy docs (no ``status`` field) with ``processing == 0`` are treated as
claimable, giving an in-place migration path.
"""

import logging
import time
from typing import Any, Dict, Optional

from pymongo import ReturnDocument
from pymongo.database import Database

TASK_STATUS_PENDING = "pending"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_PAUSED = "paused"
TASK_STATUS_DEAD = "dead"

# Mirror TASK_NOT_IN_PROCESSING / TASK_FREEZED from rsstag/tasks.py. Defined
# locally to avoid a circular import; tasks.py will import from this module
# in a later phase.
LEGACY_PROCESSING_IDLE = 0
LEGACY_PROCESSING_FROZEN = -1

DEFAULT_LEASE_SECONDS = 3600.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_BASE_SECONDS = 30.0
MAX_BACKOFF_SECONDS = 3600.0
MAX_ERROR_LENGTH = 1000


class TaskStateMachine:
    """State machine operating on ``db.tasks`` with legacy dual-writes."""

    def __init__(self, db: Database) -> None:
        self._db: Database = db
        self._log: logging.Logger = logging.getLogger("task_state")

    def ensure_indexes(self) -> None:
        """Create indexes used by claim/enqueue queries."""
        indexes = [
            "status",
            [("status", 1), ("lease_until", 1)],
            [("user", 1), ("type", 1)],
        ]
        for index in indexes:
            try:
                self._db.tasks.create_index(index)
            except Exception as e:
                self._log.warning(
                    "Can`t create index %s. May be already exists. Info: %s", index, e
                )

    @staticmethod
    def claimable_filter(now: float) -> Dict[str, Any]:
        """Return the filter matching claimable task docs.

        Branch 1 (pending, backoff elapsed) uses ``{"$not": {"$gt": now}}``
        instead of a nested ``$or`` so the expression stays a single flat
        predicate. ``$not``+``$gt`` also matches a missing ``backoff_until``
        field, which is what we want. Verified to behave identically on real
        Mongo and mongomock.
        """
        return {
            "$or": [
                {
                    "status": TASK_STATUS_PENDING,
                    "backoff_until": {"$not": {"$gt": now}},
                },
                {
                    "status": TASK_STATUS_RUNNING,
                    "lease_until": {"$lt": now},
                },
                {
                    "status": {"$exists": False},
                    "processing": LEGACY_PROCESSING_IDLE,
                },
            ]
        }

    def claim(
        self,
        worker_id: str = "",
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
        extra_filter: Optional[Dict[str, Any]] = None,
        sample_size: int = 5,
    ) -> Optional[dict]:
        """Atomically claim one claimable task, returning the running doc."""
        try:
            now = time.time()
            base_filter = self.claimable_filter(now)
            match_filter: Dict[str, Any] = (
                {"$and": [base_filter, extra_filter]} if extra_filter else base_filter
            )

            candidates = self._sample_candidates(match_filter, sample_size)
            if not candidates:
                return None

            for candidate in candidates:
                claimed = self._db.tasks.find_one_and_update(
                    {"_id": candidate["_id"], **self.claimable_filter(now)},
                    {
                        "$set": {
                            "status": TASK_STATUS_RUNNING,
                            "lease_until": now + lease_seconds,
                            "worker_id": worker_id,
                            "started_at": now,
                            "updated_at": now,
                            "processing": now,
                        }
                    },
                    return_document=ReturnDocument.AFTER,
                )
                if claimed:
                    return claimed
            return None
        except Exception as e:
            self._log.error("Can`t claim task. Info: %s", e)
            return None

    def _sample_candidates(self, match_filter: Dict[str, Any], sample_size: int) -> list:
        """Sample up to ``sample_size`` candidates, tolerant of backends."""
        try:
            pipeline = [
                {"$match": match_filter},
                {"$sample": {"size": sample_size}},
            ]
            return list(self._db.tasks.aggregate(pipeline))
        except Exception as e:
            self._log.warning(
                "Aggregate $sample failed, falling back to find(). Info: %s", e
            )
            return list(self._db.tasks.find(match_filter).limit(sample_size))

    def renew(
        self, task_id: Any, lease_seconds: float = DEFAULT_LEASE_SECONDS
    ) -> bool:
        """Extend the lease of a still-running task."""
        try:
            now = time.time()
            result = self._db.tasks.update_one(
                {"_id": task_id, "status": TASK_STATUS_RUNNING},
                {"$set": {"lease_until": now + lease_seconds, "updated_at": now}},
            )
            return result.matched_count > 0
        except Exception as e:
            self._log.error("Can`t renew task %s. Info: %s", task_id, e)
            return False

    def release(self, task_id: Any) -> bool:
        """Return a running task to pending (used when a batch task yields)."""
        try:
            now = time.time()
            result = self._db.tasks.update_one(
                {"_id": task_id, "status": TASK_STATUS_RUNNING},
                {
                    "$set": {
                        "status": TASK_STATUS_PENDING,
                        "processing": LEGACY_PROCESSING_IDLE,
                        "updated_at": now,
                    },
                    "$unset": {"worker_id": "", "lease_until": ""},
                },
            )
            return result.matched_count > 0
        except Exception as e:
            self._log.error("Can`t release task %s. Info: %s", task_id, e)
            return False

    def complete(self, task_id: Any) -> bool:
        """Delete a completed task doc (completion-as-deletion for UI compat)."""
        try:
            result = self._db.tasks.delete_one({"_id": task_id})
            return result.deleted_count > 0
        except Exception as e:
            self._log.error("Can`t complete task %s. Info: %s", task_id, e)
            return False

    def fail(
        self,
        task: dict,
        error: str,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
    ) -> bool:
        """Record a failure, retrying with backoff until attempts hit max.

        The update is guarded on ``_id`` plus ``status`` not in
        ``{paused, dead}`` so it still works if the lease expired mid-run, but
        never resurrects a task a caller already paused (via ``freeze_tasks``)
        or that already reached the dead-letter state. The ``$nin`` predicate
        also matches legacy docs with no ``status`` field, keeping them covered.
        """
        task_id: Any = task.get("_id")
        if not task_id:
            self._log.error("Can`t fail task without _id: %s", task)
            return False

        try:
            now = time.time()
            attempts = int(task.get("attempts", 0)) + 1
            limit = int(task.get("max_attempts", max_attempts))
            message = error[:MAX_ERROR_LENGTH]

            if attempts >= limit:
                update: Dict[str, Any] = {
                    "$set": {
                        "status": TASK_STATUS_DEAD,
                        "processing": LEGACY_PROCESSING_FROZEN,
                        "failed": True,
                        "failed_at": now,
                        "error": message,
                        "attempts": attempts,
                        "updated_at": now,
                    }
                }
            else:
                backoff = min(
                    backoff_base_seconds * (2 ** (attempts - 1)), MAX_BACKOFF_SECONDS
                )
                update = {
                    "$set": {
                        "status": TASK_STATUS_PENDING,
                        "processing": LEGACY_PROCESSING_IDLE,
                        "attempts": attempts,
                        "last_error": message,
                        "backoff_until": now + backoff,
                        "updated_at": now,
                    },
                    "$unset": {"worker_id": "", "lease_until": ""},
                }

            self._db.tasks.update_one(
                {
                    "_id": task_id,
                    "status": {"$nin": [TASK_STATUS_PAUSED, TASK_STATUS_DEAD]},
                },
                update,
            )
            return True
        except Exception as e:
            self._log.error("Can`t fail task %s. Info: %s", task_id, e)
            return False

    def enqueue(self, key: Dict[str, Any], fields: Dict[str, Any]) -> bool:
        """Idempotently enqueue a task identified by ``key``.

        ``key`` is the identity filter (e.g. ``{"user": u, "type": t}``). A
        live running task (running with a future lease) is left untouched so
        re-adding never resurrects a claimed task. Otherwise the doc is reset
        to pending.

        There is a small find-then-update race: two concurrent enqueues can
        both observe "no live task" and both write, so duplicate work is
        possible. Corruption is not, because actual claims are per-doc CAS.
        """
        try:
            now = time.time()
            existing = self._db.tasks.find_one(key)
            if (
                existing
                and existing.get("status") == TASK_STATUS_RUNNING
                and float(existing.get("lease_until", 0)) > now
            ):
                return True

            self._db.tasks.update_one(
                key,
                {
                    "$set": {
                        **key,
                        **fields,
                        "status": TASK_STATUS_PENDING,
                        "processing": LEGACY_PROCESSING_IDLE,
                        "attempts": 0,
                        "backoff_until": 0.0,
                        "updated_at": now,
                    },
                    "$unset": {
                        "worker_id": "",
                        "lease_until": "",
                        "failed": "",
                        "failed_at": "",
                        "error": "",
                        "last_error": "",
                    },
                },
                upsert=True,
            )
            return True
        except Exception as e:
            self._log.error("Can`t enqueue task %s. Info: %s", key, e)
            return False

    def pause(self, user: str, task_type: Optional[int] = None) -> int:
        """Pause matching non-dead tasks. Returns modified count."""
        try:
            now = time.time()
            query: Dict[str, Any] = {"user": user, "status": {"$ne": TASK_STATUS_DEAD}}
            if task_type is not None:
                query["type"] = task_type
            result = self._db.tasks.update_many(
                query,
                {
                    "$set": {
                        "status": TASK_STATUS_PAUSED,
                        "processing": LEGACY_PROCESSING_FROZEN,
                        "updated_at": now,
                    }
                },
            )
            return int(result.modified_count)
        except Exception as e:
            self._log.error("Can`t pause tasks for user %s. Info: %s", user, e)
            return 0

    def resume(self, user: str, task_type: Optional[int] = None) -> int:
        """Resume paused/dead tasks back to pending. Returns modified count.

        Running tasks are deliberately untouched to prevent double-runs;
        expired leases self-heal via ``claim``.
        """
        try:
            now = time.time()
            query: Dict[str, Any] = {
                "user": user,
                "status": {"$in": [TASK_STATUS_PAUSED, TASK_STATUS_DEAD]},
            }
            if task_type is not None:
                query["type"] = task_type
            result = self._db.tasks.update_many(
                query,
                {
                    "$set": {
                        "status": TASK_STATUS_PENDING,
                        "processing": LEGACY_PROCESSING_IDLE,
                        "attempts": 0,
                        "backoff_until": 0.0,
                        "updated_at": now,
                    },
                    "$unset": {
                        "failed": "",
                        "failed_at": "",
                        "error": "",
                        "last_error": "",
                        "worker_id": "",
                        "lease_until": "",
                    },
                },
            )
            return int(result.modified_count)
        except Exception as e:
            self._log.error("Can`t resume tasks for user %s. Info: %s", user, e)
            return 0
