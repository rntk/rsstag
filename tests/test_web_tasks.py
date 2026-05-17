import unittest
from unittest.mock import MagicMock, patch

from werkzeug.wrappers import Request

from rsstag.web.tasks import on_tasks_post, on_tasks_remove_post
from tests.web_test_utils import MongoWebTestCase


class TestWebTasksGet(MongoWebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.owner = "testuser"
        self.user_data, self.sid = self.seed_test_user(self.owner, "password")
        self.client = self.get_authenticated_client(self.sid)

    def test_returns_200(self) -> None:
        with patch.object(self.app.tasks, "get_current_tasks", return_value=[]) as mock_get:
            response = self.client.get("/tasks")
            self.assertEqual(response.status_code, 200)
            mock_get.assert_called_once_with(self.sid)

    def test_renders_current_tasks(self) -> None:
        fake_task = {"id": "task-1", "title": "Fake Task", "processing": 1}
        with patch.object(self.app.tasks, "get_current_tasks", return_value=[fake_task]):
            response = self.client.get("/tasks")
            body = response.get_data(as_text=True)
            self.assertIn("Fake Task", body)
            self.assertIn("task-1", body)

    def test_includes_scope_hints(self) -> None:
        with patch.object(self.app.tasks, "get_current_tasks", return_value=[]):
            response = self.client.get("/tasks")
            body = response.get_data(as_text=True)
            self.assertIn("(global only)", body)
            self.assertIn("(supports scoped reprocess)", body)


class TestWebTasksPost(MongoWebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.owner = "testuser"
        self.user_data, self.sid = self.seed_test_user(self.owner, "password")
        self.client = self.get_authenticated_client(self.sid)

    def test_valid_task_type_enqueues_with_exact_payload_and_redirects(self) -> None:
        with patch.object(self.app.tasks, "get_current_tasks", return_value=[]), patch.object(
            self.app.tasks, "add_task"
        ) as mock_add:
            response = self.client.post("/tasks", data={"task_type": "1"})
            self.assertIn(response.status_code, [301, 302, 307, 308])
            self.assertIn("/tasks", response.headers.get("Location", ""))

            mock_add.assert_called_once()
            payload = mock_add.call_args[0][0]
            self.assertEqual(payload["user"], self.sid)
            self.assertEqual(payload["type"], 1)
            self.assertEqual(payload["data"], [])
            self.assertEqual(payload["host"], "127.0.0.1:8885")
            self.assertEqual(payload["provider"], "")

    def test_invalid_task_type_redirects_without_enqueue(self) -> None:
        with patch.object(self.app.tasks, "get_current_tasks", return_value=[]), patch.object(
            self.app.tasks, "add_task"
        ) as mock_add:
            response = self.client.post("/tasks", data={"task_type": "not-an-int"})
            self.assertIn(response.status_code, [301, 302, 307, 308])
            self.assertIn("/tasks", response.headers.get("Location", ""))
            mock_add.assert_not_called()

    def test_missing_task_type_redirects_without_enqueue(self) -> None:
        with patch.object(self.app.tasks, "get_current_tasks", return_value=[]), patch.object(
            self.app.tasks, "add_task"
        ) as mock_add:
            response = self.client.post("/tasks", data={})
            self.assertIn(response.status_code, [301, 302, 307, 308])
            self.assertIn("/tasks", response.headers.get("Location", ""))
            mock_add.assert_not_called()


class TestWebTasksRemovePost(MongoWebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.owner = "testuser"
        self.user_data, self.sid = self.seed_test_user(self.owner, "password")
        self.client = self.get_authenticated_client(self.sid)

    def test_calls_remove_and_redirects(self) -> None:
        with patch.object(self.app.tasks, "remove_task") as mock_remove:
            response = self.client.post("/tasks/remove/task-123")
            self.assertIn(response.status_code, [301, 302, 307, 308])
            self.assertIn("/tasks", response.headers.get("Location", ""))
            mock_remove.assert_called_once_with("task-123")


class TestWebTasksUnit(unittest.TestCase):
    def test_on_tasks_post_invalid_task_type_logs_error(self) -> None:
        mock_app = MagicMock()
        mock_app.config = {"settings": {"host_name": "example.com"}}
        user = {"sid": "sid-123", "provider": "bazqux"}

        request = Request.from_values(path="/tasks", method="POST", data={"task_type": "invalid"})

        with self.assertLogs(level="ERROR") as cm:
            response = on_tasks_post(mock_app, user, request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/tasks")
        mock_app.tasks.add_task.assert_not_called()
        self.assertTrue(
            any("Invalid task type" in msg for msg in cm.output),
            f"Expected 'Invalid task type' in logs, got: {cm.output}",
        )

    def test_on_tasks_remove_post_empty_task_id_redirects_without_calling_remove(self) -> None:
        mock_app = MagicMock()
        user = {"sid": "sid-123"}

        request = Request.from_values(path="/tasks/remove/", method="POST")
        response = on_tasks_remove_post(mock_app, user, request, "")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/tasks")
        mock_app.tasks.remove_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()
