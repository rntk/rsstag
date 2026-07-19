"""Tests for rsstag.task_state.TaskStateMachine.

Per /app/CLAUDE.md, DB tests use ``DBHelper`` from ``tests/db_utils.py``.
This sandbox has no Mongo server, so ``_get_db()`` probes a real server once
(with a short server-selection timeout) and falls back to ``mongomock`` when
it is unavailable. Each test gets a fresh, isolated store.
"""

import time
import unittest
from typing import Any, Optional

from pymongo import MongoClient
from pymongo.database import Database

from rsstag.task_state import (
    TaskStateMachine,
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_PAUSED,
    TASK_STATUS_DEAD,
    LEGACY_PROCESSING_IDLE,
    LEGACY_PROCESSING_FROZEN,
    MAX_ERROR_LENGTH,
)

_REAL_MONGO_PORT = 8765
# Cache the availability decision at module load so the connection timeout is
# paid at most once for the whole suite instead of once per test.
_USE_REAL_MONGO: Optional[bool] = None


def _real_mongo_available() -> bool:
    global _USE_REAL_MONGO
    if _USE_REAL_MONGO is None:
        client: Optional[MongoClient] = None
        try:
            client = MongoClient(port=_REAL_MONGO_PORT, serverSelectionTimeoutMS=500)
            client.admin.command("ping")
            _USE_REAL_MONGO = True
        except Exception:
            _USE_REAL_MONGO = False
        finally:
            if client is not None:
                client.close()
    return _USE_REAL_MONGO


class TaskStateMachineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._db_helper = None
        if _real_mongo_available():
            from tests.db_utils import DBHelper

            self._db_helper = DBHelper(port=_REAL_MONGO_PORT)
            self.db: Database = self._db_helper.create_test_db()
        else:
            import mongomock

            # A fresh client gives a per-test isolated store.
            self._mongo_client = mongomock.MongoClient()
            self.db = self._mongo_client["rsstag_test"]
        self.sm = TaskStateMachine(self.db)

    def tearDown(self) -> None:
        if self._db_helper is not None:
            self._db_helper.drop_test_db(self.db)
            self._db_helper.close()
        else:
            self._mongo_client.close()

    # -- helpers -----------------------------------------------------------

    def _insert(self, **fields: Any) -> Any:
        result = self.db.tasks.insert_one(fields)
        return result.inserted_id

    def _get(self, task_id: Any) -> dict:
        return self.db.tasks.find_one({"_id": task_id})

    # -- tests -------------------------------------------------------------

    def test_claim_returns_pending_and_marks_running(self) -> None:
        tid = self._insert(user="u1", type=1, status=TASK_STATUS_PENDING)
        before = time.time()
        claimed = self.sm.claim(worker_id="w1")
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["_id"], tid)
        self.assertEqual(claimed["status"], TASK_STATUS_RUNNING)
        self.assertGreater(claimed["processing"], 0)
        self.assertGreaterEqual(claimed["lease_until"], before)
        self.assertGreater(claimed["lease_until"], time.time() - 1)
        self.assertEqual(claimed["worker_id"], "w1")

    def test_claim_skips_future_backoff(self) -> None:
        self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_PENDING,
            backoff_until=time.time() + 500,
        )
        self.assertIsNone(self.sm.claim())

    def test_claim_pending_without_backoff(self) -> None:
        tid = self._insert(user="u1", type=1, status=TASK_STATUS_PENDING)
        claimed = self.sm.claim()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["_id"], tid)

    def test_claim_skips_running_with_valid_lease(self) -> None:
        self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_RUNNING,
            lease_until=time.time() + 500,
        )
        self.assertIsNone(self.sm.claim())

    def test_claim_reclaims_running_with_stale_lease(self) -> None:
        tid = self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_RUNNING,
            lease_until=time.time() - 10,
        )
        claimed = self.sm.claim(worker_id="w2")
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["_id"], tid)
        self.assertEqual(claimed["worker_id"], "w2")

    def test_claim_legacy_idle_doc(self) -> None:
        tid = self._insert(user="u1", type=1, processing=LEGACY_PROCESSING_IDLE)
        claimed = self.sm.claim()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["_id"], tid)
        self.assertEqual(claimed["status"], TASK_STATUS_RUNNING)

    def test_claim_ignores_legacy_frozen_or_active(self) -> None:
        self._insert(user="u1", type=1, processing=LEGACY_PROCESSING_FROZEN)
        self._insert(user="u1", type=2, processing=time.time())
        self.assertIsNone(self.sm.claim())

    def test_enqueue_insert_liverunning_and_dead_reset(self) -> None:
        key = {"user": "u1", "type": 1}
        # Insert into empty collection.
        self.assertTrue(self.sm.enqueue(key, {"host": "h"}))
        doc = self.db.tasks.find_one(key)
        self.assertIsNotNone(doc)
        self.assertEqual(doc["status"], TASK_STATUS_PENDING)
        self.assertEqual(doc["processing"], LEGACY_PROCESSING_IDLE)

        # Make it live-running; enqueue must not touch it.
        lease = time.time() + 500
        self.db.tasks.update_one(
            key,
            {
                "$set": {
                    "status": TASK_STATUS_RUNNING,
                    "lease_until": lease,
                    "worker_id": "wLive",
                }
            },
        )
        self.assertTrue(self.sm.enqueue(key, {"host": "h2"}))
        doc = self.db.tasks.find_one(key)
        self.assertEqual(doc["status"], TASK_STATUS_RUNNING)
        self.assertEqual(doc["lease_until"], lease)
        self.assertEqual(doc["worker_id"], "wLive")
        self.assertNotEqual(doc.get("host"), "h2")

        # Make it dead; enqueue must reset it and clear failure fields.
        self.db.tasks.update_one(
            key,
            {
                "$set": {
                    "status": TASK_STATUS_DEAD,
                    "failed": True,
                    "failed_at": time.time(),
                    "error": "boom",
                },
                "$unset": {"lease_until": "", "worker_id": ""},
            },
        )
        self.assertTrue(self.sm.enqueue(key, {"host": "h3"}))
        doc = self.db.tasks.find_one(key)
        self.assertEqual(doc["status"], TASK_STATUS_PENDING)
        self.assertEqual(doc["attempts"], 0)
        self.assertNotIn("failed", doc)
        self.assertNotIn("error", doc)
        self.assertEqual(doc.get("host"), "h3")

    def test_fail_below_max_retries_with_backoff(self) -> None:
        tid = self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_RUNNING,
            attempts=0,
            lease_until=time.time() + 100,
        )
        task = self._get(tid)
        now = time.time()
        self.assertTrue(self.sm.fail(task, "some error"))
        doc = self._get(tid)
        self.assertEqual(doc["status"], TASK_STATUS_PENDING)
        self.assertEqual(doc["attempts"], 1)
        self.assertGreater(doc["backoff_until"], now)
        self.assertEqual(doc["processing"], LEGACY_PROCESSING_IDLE)
        self.assertEqual(doc["last_error"], "some error")

    def test_fail_at_max_marks_dead(self) -> None:
        tid = self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_RUNNING,
            attempts=2,
            lease_until=time.time() + 100,
        )
        task = self._get(tid)
        self.assertTrue(self.sm.fail(task, "fatal"))
        doc = self._get(tid)
        self.assertEqual(doc["status"], TASK_STATUS_DEAD)
        self.assertEqual(doc["processing"], LEGACY_PROCESSING_FROZEN)
        self.assertTrue(doc["failed"])
        self.assertEqual(doc["error"], "fatal")
        # Subsequent claim must not return it.
        self.assertIsNone(self.sm.claim())

    def test_fail_per_task_max_attempts_override(self) -> None:
        tid = self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_RUNNING,
            attempts=0,
            max_attempts=1,
            lease_until=time.time() + 100,
        )
        task = self._get(tid)
        self.assertTrue(self.sm.fail(task, "one strike"))
        doc = self._get(tid)
        self.assertEqual(doc["status"], TASK_STATUS_DEAD)

    def test_release_returns_to_pending(self) -> None:
        tid = self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_RUNNING,
            worker_id="w",
            lease_until=time.time() + 100,
        )
        self.assertTrue(self.sm.release(tid))
        doc = self._get(tid)
        self.assertEqual(doc["status"], TASK_STATUS_PENDING)
        self.assertEqual(doc["processing"], LEGACY_PROCESSING_IDLE)
        self.assertNotIn("worker_id", doc)
        self.assertNotIn("lease_until", doc)
        claimed = self.sm.claim()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["_id"], tid)

    def test_renew_running_true_pending_false(self) -> None:
        tid = self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_RUNNING,
            lease_until=time.time() + 10,
        )
        old_lease = self._get(tid)["lease_until"]
        self.assertTrue(self.sm.renew(tid, lease_seconds=1000))
        self.assertGreater(self._get(tid)["lease_until"], old_lease)

        pid = self._insert(user="u1", type=2, status=TASK_STATUS_PENDING)
        self.assertFalse(self.sm.renew(pid))

    def test_complete_deletes_doc(self) -> None:
        tid = self._insert(user="u1", type=1, status=TASK_STATUS_RUNNING)
        self.assertTrue(self.sm.complete(tid))
        self.assertIsNone(self._get(tid))
        self.assertFalse(self.sm.complete(tid))

    def test_pause_and_resume(self) -> None:
        pending = self._insert(user="u1", type=1, status=TASK_STATUS_PENDING)
        # Pause makes it unclaimable.
        self.assertEqual(self.sm.pause("u1"), 1)
        self.assertEqual(self._get(pending)["status"], TASK_STATUS_PAUSED)
        self.assertIsNone(self.sm.claim())

        # A dead task with failure fields.
        dead = self._insert(
            user="u1",
            type=2,
            status=TASK_STATUS_DEAD,
            attempts=5,
            error="dead err",
            failed=True,
        )
        # A running task must be untouched by resume.
        running = self._insert(
            user="u1",
            type=3,
            status=TASK_STATUS_RUNNING,
            lease_until=time.time() + 500,
        )

        modified = self.sm.resume("u1")
        # paused + dead reset, running left alone.
        self.assertEqual(modified, 2)
        self.assertEqual(self._get(pending)["status"], TASK_STATUS_PENDING)
        dead_doc = self._get(dead)
        self.assertEqual(dead_doc["status"], TASK_STATUS_PENDING)
        self.assertEqual(dead_doc["attempts"], 0)
        self.assertNotIn("error", dead_doc)
        self.assertNotIn("failed", dead_doc)
        self.assertEqual(self._get(running)["status"], TASK_STATUS_RUNNING)

    def test_fail_truncates_long_error(self) -> None:
        tid = self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_RUNNING,
            attempts=0,
            lease_until=time.time() + 100,
        )
        task = self._get(tid)
        long_error = "x" * (MAX_ERROR_LENGTH + 500)
        self.assertTrue(self.sm.fail(task, long_error))
        doc = self._get(tid)
        self.assertEqual(len(doc["last_error"]), MAX_ERROR_LENGTH)


if __name__ == "__main__":
    unittest.main()
