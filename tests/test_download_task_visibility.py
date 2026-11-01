"""Verify provider downloads appear throughout their normal queue lifecycle."""

import json
import unittest
from typing import Any
from unittest.mock import MagicMock

from jinja2 import Environment, PackageLoader
from pymongo.errors import PyMongoError
from werkzeug.wrappers import Request, Response

from rsstag.tasks import RssTagTasks, TASK_DOWNLOAD
from rsstag.users import RssTagUsers
from rsstag.web.routes import RSSTagRoutes
from rsstag.web.tasks import on_tasks_current_get, on_tasks_get
from rsstag.web.users import on_provider_detail_post
from tests.db_utils import DBHelper


class DownloadTaskVisibilityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.helper: DBHelper = DBHelper(port=8765)
        try:
            self.helper.client.admin.command("ping")
        except PyMongoError:
            self.helper.client.close()
            try:
                import mongomock
            except ImportError:
                self.skipTest("MongoDB on port 8765 or mongomock is required")
            self.helper.client = mongomock.MongoClient()
        self.db: Any = self.helper.create_test_db()
        self.helper.init_db_from_dict(
            self.db,
            {"users": [{"sid": "alice", "in_queue": {}, "providers": {}}]},
        )
        self.app: MagicMock = MagicMock()
        self.app.tasks = RssTagTasks(self.db)
        self.app.users = RssTagUsers(self.db)
        self.app.routes = RSSTagRoutes("localhost")
        self.app.config = {
            "settings": {"host_name": "localhost", "support": "", "version": "test"}
        }
        self.app.template_env = Environment(
            loader=PackageLoader("rsstag.web", "templates/default")
        )
        self.app.template_env.filters["json"] = json.dumps
        self.user: dict[str, Any] = {
            "sid": "alice", "in_queue": {}, "providers": {}, "settings": {}
        }

    def tearDown(self) -> None:
        self.helper.drop_test_db(self.db)
        self.helper.close()

    def _download(self, provider: str = "bazqux") -> Response:
        request: Request = Request.from_values(
            path=f"/provider/{provider}", method="POST", data={"action": "download"}
        )
        return on_provider_detail_post(self.app, self.user, provider, request)

    def _current(self) -> Response:
        return on_tasks_current_get(
            self.app, self.user, Request.from_values(path="/tasks/current")
        )

    def test_download_is_queued_claimed_and_removed_from_tasks(self) -> None:
        response: Response = self._download()
        self.assertEqual(response.headers["Location"], "/tasks")
        task: dict[str, Any] = self.db.tasks.find_one({"user": "alice"})
        self.assertEqual(task["type"], TASK_DOWNLOAD)
        self.assertEqual(task["status"], "pending")

        page: Response = on_tasks_get(
            self.app, self.user, Request.from_values(path="/tasks")
        )
        self.assertIn("Source: bazqux", page.get_data(as_text=True))
        self.assertIn(">Queued</span>", page.get_data(as_text=True))
        self.assertIn('data-refresh-url="/tasks/current"', page.get_data(as_text=True))

        claimed: dict[str, Any] = self.app.tasks.get_task(self.app.users)
        self.assertEqual(claimed["_id"], task["_id"])
        self.assertEqual(claimed["type"], TASK_DOWNLOAD)
        current: Response = self._current()
        self.assertIn(">In progress</span>", current.get_data(as_text=True))
        self.assertEqual(current.headers["Cache-Control"], "no-store")
        self.assertNotIn("<!DOCTYPE", current.get_data(as_text=True))

        # Repeat clicks must preserve the running job and its claim.
        self._download()
        self.assertEqual(self.db.tasks.count_documents({"user": "alice"}), 1)
        self.assertEqual(self.db.tasks.find_one({"_id": task["_id"]})["status"], "running")

        self.app.tasks.finish_task(claimed)
        self.assertIn("No active tasks.", self._current().get_data(as_text=True))

    def test_each_provider_is_identified_and_other_users_are_excluded(self) -> None:
        self._download("bazqux")
        self._download("telegram")
        self.helper.init_db_from_dict(
            self.db,
            {"tasks": [{"user": "bob", "type": TASK_DOWNLOAD, "provider": "gmail"}]},
        )
        body: str = self._current().get_data(as_text=True)
        self.assertIn("Source: bazqux", body)
        self.assertIn("Source: telegram", body)
        self.assertNotIn("Source: gmail", body)

    def test_provider_text_is_escaped_in_fragment(self) -> None:
        self.helper.init_db_from_dict(
            self.db,
            {"tasks": [{"user": "alice", "type": TASK_DOWNLOAD, "provider": "<script>"}]},
        )
        body: str = self._current().get_data(as_text=True)
        self.assertIn("Source: &lt;script&gt;", body)
        self.assertNotIn("Source: <script>", body)

    def test_current_tasks_route(self) -> None:
        endpoint: str
        values: dict[str, Any]
        endpoint, values = self.app.routes.get_werkzeug_routes().bind("localhost").match(
            "/tasks/current", method="GET"
        )
        self.assertEqual(endpoint, "on_tasks_current_get")
        self.assertEqual(values, {})
