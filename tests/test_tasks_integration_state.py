"""Integration tests wiring ``TaskStateMachine`` into ``RssTagTasks``.

Per /app/CLAUDE.md, DB tests use ``DBHelper`` from ``tests/db_utils.py``. This
sandbox has no Mongo server, so we probe a real server once (short
server-selection timeout) and fall back to ``mongomock`` when it is
unavailable, mirroring ``tests/test_task_state.py``.
"""

import sys
import time
import types
import unittest
from typing import Any, Optional

from pymongo import MongoClient
from pymongo.database import Database

# rsstag.tasks imports modules with runtime type issues in this environment;
# stub them before importing, mirroring tests/test_tasks.py.
sys.modules.setdefault(
    "rsstag.post_grouping", types.SimpleNamespace(RssTagPostGrouping=object)
)
sys.modules.setdefault("rsstag.tags", types.SimpleNamespace(RssTagTags=object))

from rsstag.tasks import (  # noqa: E402
    RssTagTasks,
    TASK_DOWNLOAD,
    TASK_LETTERS,
    TASK_NOOP,
    TASK_TAGS,
)
from rsstag.task_state import (  # noqa: E402
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_PAUSED,
    TASK_STATUS_DEAD,
    LEGACY_PROCESSING_IDLE,
    LEGACY_PROCESSING_FROZEN,
)
from rsstag.users import RssTagUsers  # noqa: E402

_REAL_MONGO_PORT = 8765
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


class TasksStateIntegrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._db_helper = None
        if _real_mongo_available():
            from tests.db_utils import DBHelper

            self._db_helper = DBHelper(port=_REAL_MONGO_PORT)
            self.db: Database = self._db_helper.create_test_db()
        else:
            import mongomock

            self._mongo_client = mongomock.MongoClient()
            self.db = self._mongo_client["rsstag_test"]
        self.tasks = RssTagTasks(self.db)
        self.users = RssTagUsers(self.db)

    def tearDown(self) -> None:
        if self._db_helper is not None:
            self._db_helper.drop_test_db(self.db)
            self._db_helper.close()
        else:
            self._mongo_client.close()

    # -- helpers -----------------------------------------------------------

    def _insert_user(self, sid: str) -> None:
        self.db.users.insert_one({"sid": sid})

    def _task_doc(self, **query: Any) -> Optional[dict]:
        return self.db.tasks.find_one(query)

    # -- tests -------------------------------------------------------------

    def test_add_task_inserts_pending_and_does_not_reset_running(self) -> None:
        self.assertTrue(
            self.tasks.add_task({"type": TASK_LETTERS, "user": "u1"}, manual=True)
        )
        doc = self._task_doc(user="u1", type=TASK_LETTERS)
        self.assertIsNotNone(doc)
        self.assertEqual(doc["status"], TASK_STATUS_PENDING)
        self.assertEqual(doc["attempts"], 0)
        self.assertEqual(doc["processing"], LEGACY_PROCESSING_IDLE)

        # Make it live-running; re-adding must not reset lease/status.
        lease = time.time() + 500
        self.db.tasks.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "status": TASK_STATUS_RUNNING,
                    "lease_until": lease,
                    "worker_id": "wLive",
                }
            },
        )
        self.assertTrue(
            self.tasks.add_task({"type": TASK_LETTERS, "user": "u1"}, manual=True)
        )
        doc = self._task_doc(user="u1", type=TASK_LETTERS)
        self.assertEqual(doc["status"], TASK_STATUS_RUNNING)
        self.assertEqual(doc["lease_until"], lease)
        self.assertEqual(doc["worker_id"], "wLive")

    def test_add_next_tasks_is_idempotent(self) -> None:
        self.assertTrue(self.tasks.add_next_tasks("u1", TASK_DOWNLOAD))
        self.assertTrue(self.tasks.add_next_tasks("u1", TASK_DOWNLOAD))
        self.assertEqual(
            self.db.tasks.count_documents({"user": "u1", "type": TASK_TAGS}), 1
        )

    def test_get_task_claims_simple_task(self) -> None:
        self._insert_user("u1")
        self.assertTrue(
            self.tasks.add_task({"type": TASK_LETTERS, "user": "u1"}, manual=True)
        )
        task = self.tasks.get_task(self.users)
        self.assertEqual(task["type"], TASK_LETTERS)
        doc = self._task_doc(user="u1", type=TASK_LETTERS)
        self.assertEqual(doc["status"], TASK_STATUS_RUNNING)
        self.assertGreater(doc["processing"], 0)
        self.assertIn("lease_until", doc)
        self.assertGreater(doc["lease_until"], time.time())

    def test_release_failed_task_retries_then_dead(self) -> None:
        self._insert_user("u1")
        self.assertTrue(
            self.tasks.add_task({"type": TASK_LETTERS, "user": "u1"}, manual=True)
        )
        task_id = self._task_doc(user="u1", type=TASK_LETTERS)["_id"]

        for expected_attempts in (1, 2):
            doc = self._task_doc(_id=task_id)
            self.assertTrue(self.tasks.release_failed_task(doc, "boom"))
            doc = self._task_doc(_id=task_id)
            self.assertEqual(doc["status"], TASK_STATUS_PENDING)
            self.assertEqual(doc["attempts"], expected_attempts)
            self.assertGreater(doc["backoff_until"], time.time())
            # Clear backoff so the next round is deterministic.
            self.db.tasks.update_one(
                {"_id": task_id}, {"$set": {"backoff_until": 0.0}}
            )

        # Third failure crosses the budget -> dead.
        doc = self._task_doc(_id=task_id)
        self.assertTrue(self.tasks.release_failed_task(doc, "final"))
        doc = self._task_doc(_id=task_id)
        self.assertEqual(doc["status"], TASK_STATUS_DEAD)
        self.assertEqual(doc["processing"], LEGACY_PROCESSING_FROZEN)

        # A dead task must never be handed out again.
        self.assertEqual(self.tasks.get_task(self.users)["type"], TASK_NOOP)

    def test_freeze_then_unfreeze_toggles_claimability(self) -> None:
        self._insert_user("u1")
        self.assertTrue(
            self.tasks.add_task({"type": TASK_LETTERS, "user": "u1"}, manual=True)
        )
        self.assertTrue(self.tasks.freeze_tasks({"sid": "u1"}, TASK_LETTERS))
        self.assertEqual(self.tasks.get_task(self.users)["type"], TASK_NOOP)

        self.assertTrue(self.tasks.unfreeze_tasks({"sid": "u1"}, TASK_LETTERS))
        self.assertEqual(self.tasks.get_task(self.users)["type"], TASK_LETTERS)

    def test_fail_on_frozen_task_stays_paused(self) -> None:
        self._insert_user("u1")
        self.assertTrue(
            self.tasks.add_task({"type": TASK_LETTERS, "user": "u1"}, manual=True)
        )
        # Claim it (running), then freeze mid-run.
        claimed = self.tasks.get_task(self.users)
        self.assertEqual(claimed["type"], TASK_LETTERS)
        self.assertTrue(self.tasks.freeze_tasks({"sid": "u1"}, TASK_LETTERS))
        doc = self._task_doc(user="u1", type=TASK_LETTERS)
        self.assertEqual(doc["status"], TASK_STATUS_PAUSED)

        # The dispatcher's uniform failure path must not flip it back to pending.
        self.tasks.release_failed_task(doc, "handler returned false")
        doc = self._task_doc(user="u1", type=TASK_LETTERS)
        self.assertEqual(doc["status"], TASK_STATUS_PAUSED)

    def test_finish_task_chains_successor_and_deletes(self) -> None:
        self._insert_user("u1")
        self.assertTrue(
            self.tasks.add_task(
                {"type": TASK_DOWNLOAD, "user": "u1", "host": "h", "provider": "p"},
                manual=False,
            )
        )
        original = self._task_doc(user="u1", type=TASK_DOWNLOAD)
        task = {
            "type": TASK_DOWNLOAD,
            "user": {"sid": "u1"},
            "_id": original["_id"],
            "manual": False,
            "data": original,
        }
        self.assertTrue(self.tasks.finish_task(task))
        # Successor enqueued, original gone.
        self.assertEqual(
            self.db.tasks.count_documents({"user": "u1", "type": TASK_TAGS}), 1
        )
        self.assertIsNone(self._task_doc(_id=original["_id"]))

    def test_stale_item_lock_self_heals(self) -> None:
        self._insert_user("u1")
        self.assertTrue(
            self.tasks.add_task({"type": TASK_TAGS, "user": "u1"}, manual=True)
        )
        stale_id = self.db.posts.insert_one(
            {"owner": "u1", "tags": [], "processing": time.time() - 7200}
        ).inserted_id
        self.db.posts.insert_one(
            {"owner": "u1", "tags": [], "processing": time.time()}
        )

        task = self.tasks.get_task(self.users)

        self.assertEqual(task["type"], TASK_TAGS)
        self.assertEqual(len(task["data"]), 1)
        self.assertEqual(task["data"][0]["_id"], stale_id)

    def test_mark_task_failed_sets_dead_and_unclaimable(self) -> None:
        self._insert_user("u1")
        self.assertTrue(
            self.tasks.add_task({"type": TASK_LETTERS, "user": "u1"}, manual=True)
        )
        task_id = self._task_doc(user="u1", type=TASK_LETTERS)["_id"]
        self.tasks.mark_task_failed(task_id, "scope invalid")
        doc = self._task_doc(_id=task_id)
        self.assertEqual(doc["status"], TASK_STATUS_DEAD)
        self.assertEqual(doc["processing"], LEGACY_PROCESSING_FROZEN)
        self.assertEqual(self.tasks.get_task(self.users)["type"], TASK_NOOP)


if __name__ == "__main__":
    unittest.main()
