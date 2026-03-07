import socket
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from rsstag.tasks import (
    POST_NOT_IN_PROCESSING,
    TASK_DOWNLOAD,
    TASK_NOOP,
    TASK_POST_GROUPING,
    TASK_TAGS,
    TASK_W2V,
    RssTagTasks,
)
from rsstag.users import RssTagUsers
from rsstag.workers.registry import WorkerRegistry
from tests.db_utils import DBHelper


class MongoTaskDispatchTestCase(unittest.TestCase):
    db_helper: DBHelper

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        try:
            with socket.create_connection(("127.0.0.1", 8765), timeout=1):
                pass
        except OSError as exc:
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for worker task tests: {exc}"
            )

    def setUp(self) -> None:
        self.db_helper = DBHelper(port=8765)
        try:
            self.db_helper.client.admin.command("ping")
        except Exception as exc:
            self.db_helper.close()
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for worker task tests: {exc}"
            )

        self.db = self.db_helper.create_test_db()
        self.tasks = RssTagTasks(self.db)
        self.users = RssTagUsers(self.db)

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()

    def _create_user(self, username: str) -> Dict[str, Any]:
        sid: str | None = self.users.create_account(username, "password")
        self.assertIsNotNone(sid)
        user: Dict[str, Any] | None = self.users.get_by_sid(str(sid))
        self.assertIsNotNone(user)
        return dict(user)


class TestWorkerTaskDispatch(MongoTaskDispatchTestCase):
    def test_get_task_returns_seeded_tags_task_with_post_batch(self) -> None:
        user: Dict[str, Any] = self._create_user("alice")
        self.db.posts.insert_one(
            {
                "owner": user["sid"],
                "pid": "post-1",
                "tags": [],
                "processing": POST_NOT_IN_PROCESSING,
            }
        )
        inserted = self.db.tasks.insert_one(
            {
                "user": user["sid"],
                "type": TASK_TAGS,
                "processing": 0,
                "manual": True,
            }
        )

        task: Dict[str, Any] = self.tasks.get_task(self.users)

        self.assertEqual(task["type"], TASK_TAGS)
        self.assertEqual(task["_id"], inserted.inserted_id)
        self.assertEqual(task["user"]["sid"], user["sid"])
        self.assertEqual(len(task["data"]), 1)
        post: Dict[str, Any] | None = self.db.posts.find_one({"owner": user["sid"]})
        self.assertIsNotNone(post)
        self.assertNotEqual(post["processing"], POST_NOT_IN_PROCESSING)

    def test_finish_task_removes_download_and_chains_tags_task(self) -> None:
        user: Dict[str, Any] = self._create_user("bob")
        task_id = self.db.tasks.insert_one(
            {
                "user": user["sid"],
                "type": TASK_DOWNLOAD,
                "processing": 0,
                "manual": False,
                "host": "localhost",
                "provider": "textfile",
            }
        ).inserted_id

        finished: bool = self.tasks.finish_task(
            {
                "_id": task_id,
                "type": TASK_DOWNLOAD,
                "manual": False,
                "user": {"sid": user["sid"]},
                "data": {"provider": "textfile"},
            }
        )

        self.assertTrue(finished)
        self.assertIsNone(self.db.tasks.find_one({"_id": task_id}))
        next_task: Dict[str, Any] | None = self.db.tasks.find_one(
            {"user": user["sid"], "type": TASK_TAGS}
        )
        self.assertIsNotNone(next_task)
        self.assertFalse(bool(next_task["manual"]))

    def test_add_task_rejects_invalid_scope_for_global_only_task(self) -> None:
        created: bool | None = self.tasks.add_task(
            {
                "user": "scope-user",
                "type": TASK_W2V,
                "scope": {"mode": "posts", "post_ids": ["post-1"]},
            }
        )

        self.assertFalse(bool(created))
        self.assertEqual(self.db.tasks.count_documents({}), 0)

    def test_add_task_deduplicates_same_user_and_type(self) -> None:
        first: bool | None = self.tasks.add_task(
            {"user": "dedupe-user", "type": TASK_TAGS}
        )
        second: bool | None = self.tasks.add_task(
            {"user": "dedupe-user", "type": TASK_TAGS}
        )

        self.assertTrue(bool(first))
        self.assertTrue(bool(second))
        self.assertEqual(
            self.db.tasks.count_documents({"user": "dedupe-user", "type": TASK_TAGS}),
            1,
        )

    def test_get_task_invalid_scope_marks_task_failed_and_returns_noop(self) -> None:
        user: Dict[str, Any] = self._create_user("carol")
        task_id = self.db.tasks.insert_one(
            {
                "user": user["sid"],
                "type": TASK_W2V,
                "processing": 0,
                "manual": True,
                "scope": {"mode": "posts", "post_ids": ["post-1"]},
            }
        ).inserted_id

        task: Dict[str, Any] = self.tasks.get_task(self.users)

        self.assertEqual(task["type"], TASK_NOOP)
        failed_task: Dict[str, Any] | None = self.db.tasks.find_one({"_id": task_id})
        self.assertIsNotNone(failed_task)
        self.assertTrue(bool(failed_task["failed"]))
        self.assertEqual(failed_task["processing"], -1)
        self.assertIn("global-only", failed_task["error"])

    def test_registry_handle_calls_registered_handler(self) -> None:
        registry = WorkerRegistry()
        handler = MagicMock(return_value=True)
        task: Dict[str, Any] = {"type": TASK_POST_GROUPING, "data": []}
        registry.register(TASK_POST_GROUPING, handler)

        result = registry.handle(task)

        self.assertTrue(bool(result))
        handler.assert_called_once_with(task)

    def test_registry_handle_unknown_task_type_returns_none(self) -> None:
        registry = WorkerRegistry()

        result = registry.handle({"type": 999999})

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
