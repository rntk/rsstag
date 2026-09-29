"""A stale ``in_queue.<provider>`` flag must not block downloads forever."""

import unittest
from typing import Any, Dict
from unittest.mock import MagicMock
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from rsstag.tasks import (
    RssTagTasks,
    TASK_DOWNLOAD,
    TASK_FEEDS_LIST,
    TASK_RAW_DOWNLOAD,
    TASK_RAW_TO_POSTS,
)
from rsstag.web.users import (
    is_provider_busy,
    _reset_provider_queue,
    on_provider_detail_post,
)
from rsstag.workers.provider_worker import ProviderWorker
from tests.db_utils import DBHelper


def _app(in_queue: Dict[str, bool], task_active: bool) -> MagicMock:
    app: MagicMock = MagicMock()
    app.users.get_in_queue.return_value = in_queue
    app.tasks.has_active_provider_task.return_value = task_active
    return app


class TestIsProviderBusy(unittest.TestCase):
    def setUp(self) -> None:
        self.user: Dict[str, Any] = {"sid": "alice"}

    def test_idle_when_flag_is_not_set(self) -> None:
        app: MagicMock = _app({}, task_active=False)
        self.assertFalse(is_provider_busy(app, self.user, "bazqux"))
        app.users.update_by_sid.assert_not_called()

    def test_busy_when_flag_is_backed_by_a_runnable_task(self) -> None:
        app: MagicMock = _app({"bazqux": True}, task_active=True)
        self.assertTrue(is_provider_busy(app, self.user, "bazqux"))
        app.users.update_by_sid.assert_not_called()

    def test_active_task_blocks_even_without_flag(self) -> None:
        app: MagicMock = _app({}, task_active=True)
        self.assertTrue(is_provider_busy(app, self.user, "bazqux"))
        app.users.update_by_sid.assert_not_called()

    def test_stale_flag_is_cleared_and_not_busy(self) -> None:
        app: MagicMock = _app({"bazqux": True}, task_active=False)
        self.assertFalse(is_provider_busy(app, self.user, "bazqux"))
        app.users.update_by_sid.assert_called_once_with(
            "alice", {"in_queue.bazqux": False}
        )


class TestResetProviderQueue(unittest.TestCase):
    def test_active_task_prevents_post_reset(self) -> None:
        app: MagicMock = _app({"bazqux": True}, task_active=True)
        app.routes.get_url_by_endpoint.return_value = "/provider/bazqux"
        request: Request = Request(
            EnvironBuilder(method="POST", data={"action": "reset_queue"}).get_environ()
        )
        response: Response = on_provider_detail_post(
            app, {"sid": "alice"}, "bazqux", request
        )
        self.assertEqual(response.status_code, 302)
        app.db.tasks.delete_many.assert_not_called()
        app.users.reset_in_queue_if_legacy.assert_not_called()
        update: Dict[str, Any] = app.users.update_by_sid.call_args[0][1]
        self.assertNotIn("in_queue.bazqux", update)
        self.assertIn("cannot be reset", update["message"])

    def test_drops_flag_and_dead_or_paused_tasks(self) -> None:
        app: MagicMock = _app({"bazqux": True}, task_active=False)
        _reset_provider_queue(app, {"sid": "alice"}, "bazqux")
        query: Dict[str, Any] = app.db.tasks.delete_many.call_args[0][0]
        self.assertEqual(query["user"], "alice")
        self.assertEqual(query["provider"], "bazqux")
        self.assertEqual(
            app.users.update_by_sid.call_args[0][1]["in_queue.bazqux"], False
        )


class TestProviderErrorReleasesFlag(unittest.TestCase):
    def test_failed_provider_run_clears_the_queue_flag(self) -> None:
        worker: ProviderWorker = ProviderWorker.__new__(ProviderWorker)
        worker._tasks = MagicMock()
        worker._tasks.has_active_provider_task.return_value = False
        worker._users = MagicMock()
        task: Dict[str, Any] = {
            "_id": 1,
            "type": TASK_DOWNLOAD,
            "user": {"sid": "alice"},
        }
        worker._handle_provider_error(task, "bazqux", KeyError("subscriptions"))
        update: Dict[str, Any] = worker._users.update_by_sid.call_args[0][1]
        self.assertEqual(update["in_queue.bazqux"], False)

    def test_raw_errors_preserve_the_queue_flag(self) -> None:
        for task_type in (TASK_RAW_DOWNLOAD, TASK_RAW_TO_POSTS):
            with self.subTest(task_type=task_type):
                worker: ProviderWorker = ProviderWorker.__new__(ProviderWorker)
                worker._tasks = MagicMock()
                worker._tasks.has_active_provider_task.return_value = False
                worker._users = MagicMock()
                task: Dict[str, Any] = {
                    "_id": 1,
                    "type": task_type,
                    "user": {"sid": "alice"},
                }
                worker._handle_provider_error(task, "bazqux", ValueError("failed"))
                update: Dict[str, Any] = worker._users.update_by_sid.call_args[0][1]
                self.assertNotIn("in_queue.bazqux", update)
                worker._tasks.has_active_provider_task.assert_not_called()

    def test_another_owning_task_preserves_the_queue_flag(self) -> None:
        for task_type in (TASK_DOWNLOAD, TASK_FEEDS_LIST):
            with self.subTest(task_type=task_type):
                worker: ProviderWorker = ProviderWorker.__new__(ProviderWorker)
                worker._tasks = MagicMock()
                worker._tasks.has_active_provider_task.return_value = True
                worker._users = MagicMock()
                task: Dict[str, Any] = {
                    "_id": 1,
                    "type": task_type,
                    "user": {"sid": "alice"},
                }
                worker._handle_provider_error(task, "bazqux", ValueError("failed"))
                update: Dict[str, Any] = worker._users.update_by_sid.call_args[0][1]
                self.assertNotIn("in_queue.bazqux", update)


class TestActiveProviderTasks(unittest.TestCase):
    def setUp(self) -> None:
        import mongomock

        self.helper: DBHelper = DBHelper()
        self.helper.client.close()
        self.helper.client = mongomock.MongoClient()
        self.db: Any = self.helper.create_test_db()
        self.tasks: RssTagTasks = RssTagTasks(self.db)

    def tearDown(self) -> None:
        self.helper.drop_test_db(self.db)
        self.helper.close()

    def test_active_and_inactive_lifecycle_states(self) -> None:
        states: list[tuple[Dict[str, Any], bool]] = [
            ({"processing": 0}, True),
            ({"processing": 123456}, True),
            ({"processing": -1}, False),
            ({"status": "pending", "processing": 0}, True),
            ({"status": "running", "processing": 123456}, True),
            ({"status": "paused", "processing": 0}, False),
            ({"status": "dead", "processing": 0}, False),
        ]
        for task_type in (TASK_DOWNLOAD, TASK_FEEDS_LIST):
            for fields, expected in states:
                with self.subTest(task_type=task_type, fields=fields):
                    self.db.tasks.delete_many({})
                    self.helper.init_db_from_dict(
                        self.db,
                        {
                            "tasks": [
                                {
                                    "user": "alice",
                                    "provider": "bazqux",
                                    "type": task_type,
                                    **fields,
                                }
                            ]
                        },
                    )
                    self.assertEqual(
                        self.tasks.has_active_provider_task("alice", "bazqux"), expected
                    )

    def test_activity_is_scoped_to_user_provider_and_owning_type(self) -> None:
        self.helper.init_db_from_dict(
            self.db,
            {
                "tasks": [
                    {
                        "user": "bob",
                        "provider": "bazqux",
                        "type": TASK_DOWNLOAD,
                        "processing": 0,
                    },
                    {
                        "user": "alice",
                        "provider": "telegram",
                        "type": TASK_FEEDS_LIST,
                        "processing": 0,
                    },
                    {
                        "user": "alice",
                        "provider": "bazqux",
                        "type": TASK_RAW_DOWNLOAD,
                        "processing": 0,
                    },
                ]
            },
        )
        self.assertFalse(self.tasks.has_active_provider_task("alice", "bazqux"))

    def test_error_releases_only_after_last_owning_task_stops(self) -> None:
        self.helper.init_db_from_dict(
            self.db,
            {
                "tasks": [
                    {
                        "_id": 1,
                        "user": "alice",
                        "provider": "bazqux",
                        "type": TASK_DOWNLOAD,
                        "status": "running",
                    },
                    {
                        "_id": 2,
                        "user": "alice",
                        "provider": "bazqux",
                        "type": TASK_FEEDS_LIST,
                        "processing": 0,
                    },
                ]
            },
        )
        worker: ProviderWorker = ProviderWorker.__new__(ProviderWorker)
        worker._tasks = self.tasks
        worker._users = MagicMock()
        for task_id, task_type in ((1, TASK_DOWNLOAD), (2, TASK_FEEDS_LIST)):
            task: Dict[str, Any] = {
                "_id": task_id,
                "type": task_type,
                "user": {"sid": "alice"},
            }
            worker._handle_provider_error(task, "bazqux", ValueError("failed"))
            update: Dict[str, Any] = worker._users.update_by_sid.call_args[0][1]
            self.assertEqual("in_queue.bazqux" in update, task_id == 2)
            self.assertEqual(self.db.tasks.find_one({"_id": task_id})["status"], "dead")


class TestRetokenFreezeScope(unittest.TestCase):
    def _worker(self) -> ProviderWorker:
        worker: ProviderWorker = ProviderWorker.__new__(ProviderWorker)
        worker._tasks = MagicMock()
        worker._tasks.has_active_provider_task.return_value = True
        worker._users = MagicMock()
        return worker

    def test_retoken_freeze_is_scoped_to_the_failing_provider(self) -> None:
        for task_type in (TASK_DOWNLOAD, TASK_FEEDS_LIST):
            with self.subTest(task_type=task_type):
                worker: ProviderWorker = self._worker()
                task: Dict[str, Any] = {
                    "_id": 1,
                    "type": task_type,
                    "user": {"sid": "alice"},
                }
                error: Exception = ValueError("expired")
                setattr(error, "retoken", True)
                worker._handle_provider_error(task, "bazqux", error)
                worker._tasks.freeze_tasks.assert_called_once_with(
                    task["user"], task_type, "bazqux"
                )
