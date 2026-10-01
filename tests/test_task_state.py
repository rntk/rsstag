"""Tests for rsstag.task_state.TaskStateMachine using isolated DBHelper stores."""

import time
import unittest
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import MagicMock, patch

from pymongo import MongoClient
from pymongo.database import Database

from rsstag.task_state import (
    LEGACY_PROCESSING_FROZEN,
    LEGACY_PROCESSING_IDLE,
    MAX_ERROR_LENGTH,
    TASK_STATUS_DEAD,
    TASK_STATUS_PAUSED,
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    TaskStateMachine,
)
from rsstag.workers.llm_worker import _PostGroupingWorker, _TagClassificationWorker
from rsstag.workers.outcome import RetryableFailure

_REAL_MONGO_PORT: int = 8765
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
        from tests.db_utils import DBHelper

        if _real_mongo_available():
            self._db_helper: Any = DBHelper(port=_REAL_MONGO_PORT)
        else:
            import mongomock

            with patch("tests.db_utils.MongoClient", mongomock.MongoClient):
                self._db_helper = DBHelper(port=_REAL_MONGO_PORT)
        self.db: Database = self._db_helper.create_test_db()
        self.sm: TaskStateMachine = TaskStateMachine(self.db)

    def tearDown(self) -> None:
        self._db_helper.drop_test_db(self.db)
        self._db_helper.close()

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

    def test_fail_uses_selected_poll_attempt_counter(self) -> None:
        tid: Any = self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_RUNNING,
            attempts=2,
            poll_attempts=0,
            lease_until=time.time() + 100,
        )

        self.assertTrue(
            self.sm.fail(self._get(tid), "poll error", attempt_field="poll_attempts")
        )

        doc: dict[str, Any] = self._get(tid)
        self.assertEqual(doc["status"], TASK_STATUS_PENDING)
        self.assertEqual(doc["attempts"], 2)
        self.assertEqual(doc["poll_attempts"], 1)

    def test_healthy_polls_reset_intermittent_poll_failures(self) -> None:
        tid: Any = self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_RUNNING,
            attempts=1,
            poll_attempts=2,
            lease_until=time.time() + 100,
        )

        self.assertTrue(
            self.sm.defer(self._get(tid), time.time() + 60, reset_poll_attempts=True)
        )
        healthy: dict[str, Any] = self._get(tid)
        self.assertEqual(healthy["poll_attempts"], 0)
        self.assertEqual(healthy["attempts"], 1)

        self.assertTrue(
            self.sm.fail(healthy, "temporary poll failure", attempt_field="poll_attempts")
        )
        self.assertEqual(self._get(tid)["poll_attempts"], 1)
        self.assertTrue(
            self.sm.defer(self._get(tid), time.time() + 60, reset_poll_attempts=True)
        )
        self.assertEqual(self._get(tid)["poll_attempts"], 0)

    def test_consecutive_poll_failures_dead_letter(self) -> None:
        tid: Any = self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_RUNNING,
            attempts=0,
            poll_attempts=0,
            lease_until=time.time() + 100,
        )

        doc: dict[str, Any] = {}
        expected_attempt: int
        for expected_attempt in (1, 2, 3):
            self.assertTrue(
                self.sm.fail(
                    self._get(tid), "poll unavailable", attempt_field="poll_attempts"
                )
            )
            doc = self._get(tid)
            self.assertEqual(doc["poll_attempts"], expected_attempt)

        self.assertEqual(doc["status"], TASK_STATUS_DEAD)
        self.assertEqual(doc["attempts"], 0)

    def test_repeated_remote_batch_failures_are_bounded_for_both_workers(self) -> None:
        provider: MagicMock = MagicMock()
        provider.name = "openai"
        provider.model = "test-model"
        provider.batch_endpoint = "/v1/chat/completions"
        provider.get_batch.return_value = SimpleNamespace(status="expired")
        llm: MagicMock = MagicMock()
        llm.get_batch_provider.return_value = provider
        storage: MagicMock = MagicMock()

        workers: list[tuple[Any, str, list[dict[str, Any]], dict[str, Any]]] = [
            (
                _PostGroupingWorker(MagicMock(), {}, llm, storage, MagicMock()),
                "make_post_grouping_batch",
                [{"_id": "post-1"}],
                {"pending_item_ids": ["post-1"]},
            ),
            (
                _TagClassificationWorker(MagicMock(), llm, storage, MagicMock()),
                "make_tags_classification_batch",
                [{"_id": "tag-1", "tag": "test"}],
                {"item_ids": ["tag-1"]},
            ),
        ]

        worker: Any
        handler_name: str
        data: list[dict[str, Any]]
        batch_extra: dict[str, Any]
        for worker, handler_name, data, batch_extra in workers:
            with self.subTest(handler=handler_name):
                tid: Any = self._insert(
                    user="u1",
                    type=1,
                    status=TASK_STATUS_RUNNING,
                    attempts=0,
                    lease_until=time.time() + 100,
                )
                attempt: int
                for attempt in range(1, 4):
                    task: dict[str, Any] = {
                        "_id": tid,
                        "type": 1,
                        "user": {"sid": "u1", "settings": {}},
                        "data": data,
                        "batch": {
                            "batch_id": f"batch-{attempt}",
                            "last_check": 0,
                            **batch_extra,
                        },
                    }
                    outcome: Any = getattr(worker, handler_name)(task)
                    self.assertIsInstance(outcome, RetryableFailure)
                    self.assertEqual(outcome.attempt_field, "attempts")
                    state_task: dict[str, Any] = self._get(tid)
                    state_task.update(task)
                    self.assertTrue(
                        self.sm.fail(
                            state_task,
                            outcome.error,
                            attempt_field=outcome.attempt_field,
                        )
                    )
                    stored: dict[str, Any] = self._get(tid)
                    self.assertEqual(stored["attempts"], attempt)

                    if attempt < 3:
                        # Model a healthy running poll before the failed batch
                        # is retried; this must preserve the regular retry budget.
                        self.assertTrue(
                            self.sm.defer(
                                stored,
                                time.time() + 60,
                                reset_poll_attempts=True,
                            )
                        )
                        self.assertEqual(self._get(tid)["attempts"], attempt)
                        self.db.tasks.update_one(
                            {"_id": tid}, {"$set": {"backoff_until": time.time() - 1}}
                        )
                        claimed: dict[str, Any] | None = self.sm.claim()
                        self.assertIsNotNone(claimed)
                        self.assertEqual(claimed["_id"], tid)
                    else:
                        self.assertEqual(stored["status"], TASK_STATUS_DEAD)

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
            poll_attempts=4,
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
        self.assertEqual(dead_doc["poll_attempts"], 0)
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


    # -- defer / dead_letter -----------------------------------------------

    def test_defer_requeues_without_consuming_attempt(self) -> None:
        tid = self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_RUNNING,
            attempts=1,
            poll_attempts=2,
            last_error="earlier",
            worker_id="w",
            lease_until=time.time() + 100,
        )
        next_run_at = time.time() + 600
        self.assertTrue(self.sm.defer(self._get(tid), next_run_at))
        doc = self._get(tid)
        self.assertEqual(doc["status"], TASK_STATUS_PENDING)
        self.assertEqual(doc["processing"], LEGACY_PROCESSING_IDLE)
        self.assertEqual(doc["attempts"], 1)
        self.assertEqual(doc["poll_attempts"], 2)
        self.assertEqual(doc["last_error"], "earlier")
        self.assertAlmostEqual(doc["backoff_until"], next_run_at)
        self.assertNotIn("worker_id", doc)
        self.assertNotIn("lease_until", doc)
        # Not claimable before next_run_at.
        self.assertIsNone(self.sm.claim())

    def test_defer_repeatedly_never_dead_letters(self) -> None:
        tid = self._insert(user="u1", type=1, status=TASK_STATUS_RUNNING, attempts=0)
        for _ in range(10):
            self.assertTrue(self.sm.defer(self._get(tid), time.time() - 1))
        doc = self._get(tid)
        self.assertEqual(doc["status"], TASK_STATUS_PENDING)
        self.assertEqual(doc["attempts"], 0)
        claimed = self.sm.claim()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["_id"], tid)

    def test_defer_does_not_resurrect_paused_or_dead(self) -> None:
        for status in (TASK_STATUS_PAUSED, TASK_STATUS_DEAD):
            tid = self._insert(
                user="u1",
                type=1,
                status=status,
                processing=LEGACY_PROCESSING_FROZEN,
                attempts=2,
            )
            self.assertFalse(self.sm.defer(self._get(tid), time.time() + 60))
            doc = self._get(tid)
            self.assertEqual(doc["status"], status)
            self.assertEqual(doc["processing"], LEGACY_PROCESSING_FROZEN)
            self.assertNotIn("backoff_until", doc)

    def test_defer_migrates_legacy_active_doc_but_not_legacy_frozen(self) -> None:
        active = self._insert(user="u1", type=1, processing=time.time())
        frozen = self._insert(user="u1", type=2, processing=LEGACY_PROCESSING_FROZEN)
        self.assertTrue(self.sm.defer(self._get(active), time.time() + 60))
        self.assertFalse(self.sm.defer(self._get(frozen), time.time() + 60))
        self.assertEqual(self._get(active)["status"], TASK_STATUS_PENDING)
        self.assertEqual(self._get(active)["processing"], LEGACY_PROCESSING_IDLE)
        self.assertNotIn("status", self._get(frozen))
        self.assertEqual(self._get(frozen)["processing"], LEGACY_PROCESSING_FROZEN)

    def test_defer_without_id_returns_false(self) -> None:
        self.assertFalse(self.sm.defer({}, time.time()))

    def test_dead_letter_marks_dead_immediately(self) -> None:
        tid = self._insert(
            user="u1",
            type=1,
            status=TASK_STATUS_RUNNING,
            attempts=0,
            lease_until=time.time() + 100,
        )
        self.assertTrue(self.sm.dead_letter(self._get(tid), "y" * (MAX_ERROR_LENGTH + 5)))
        doc = self._get(tid)
        self.assertEqual(doc["status"], TASK_STATUS_DEAD)
        self.assertEqual(doc["processing"], LEGACY_PROCESSING_FROZEN)
        self.assertTrue(doc["failed"])
        self.assertEqual(len(doc["error"]), MAX_ERROR_LENGTH)
        self.assertEqual(doc["attempts"], 0)
        self.assertNotIn("lease_until", doc)
        self.assertIsNone(self.sm.claim())

    def test_dead_letter_keeps_paused_task_paused(self) -> None:
        tid = self._insert(
            user="u1", type=1, status=TASK_STATUS_PAUSED, processing=LEGACY_PROCESSING_FROZEN
        )
        self.assertFalse(self.sm.dead_letter(self._get(tid), "nope"))
        doc = self._get(tid)
        self.assertEqual(doc["status"], TASK_STATUS_PAUSED)
        self.assertNotIn("failed", doc)

if __name__ == "__main__":
    unittest.main()
