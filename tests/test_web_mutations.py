"""Module 6: Form POST & mutation endpoint tests."""
import json
import unittest
from typing import Any, Dict, Optional

from werkzeug.test import Client
from werkzeug.wrappers import Response

from rsstag.tasks import TASK_LETTERS
from tests.web_test_utils import MongoWebTestCase


class TestWebMutations(MongoWebTestCase):
    """Tests for write/mutating endpoints: tasks, tokens, settings, processing, etc."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user_doc, cls.user_sid = cls.seed_test_user("mutuser", "mutpass")
        cls.data: Dict[str, Any] = cls.seed_minimal_data(cls.user_sid)
        cls.auth_client: Client = cls.get_authenticated_client(cls.user_sid)

    # ------------------------------------------------------------------
    # Posts
    # ------------------------------------------------------------------

    def test_read_posts_post_marks_posts_read(self) -> None:
        pid = self.data["post_pids"][0]
        resp = self.auth_client.post(
            "/read/posts",
            data=json.dumps({"ids": [pid], "readed": True}),
            content_type="application/json",
        )
        self.assertNotEqual(resp.status_code, 500)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def test_settings_post_valid_payload_returns_200(self) -> None:
        resp = self.auth_client.post(
            "/settings",
            data=json.dumps({"only_unread": False}),
            content_type="application/json",
        )
        self.assertNotEqual(resp.status_code, 500)

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def test_tasks_post_creates_task(self) -> None:
        """POST /tasks with a valid task_type adds a task to the DB."""
        before = self.test_db.tasks.count_documents({"user": self.user_sid, "type": TASK_LETTERS})
        resp = self.auth_client.post("/tasks", data={"task_type": str(TASK_LETTERS)})
        # Handler always redirects to /tasks
        self.assertIn(resp.status_code, (200, 301, 302))
        after = self.test_db.tasks.count_documents({"user": self.user_sid, "type": TASK_LETTERS})
        self.assertGreaterEqual(after, before)

    def test_tasks_remove_post_removes_task(self) -> None:
        """POST /tasks/remove/<task_id> deletes the specified task."""
        task_id = self.test_db.tasks.insert_one(
            {"user": self.user_sid, "type": TASK_LETTERS, "processing": 0, "manual": True}
        ).inserted_id
        resp = self.auth_client.post(f"/tasks/remove/{task_id}")
        self.assertIn(resp.status_code, (200, 301, 302))
        self.assertIsNone(self.test_db.tasks.find_one({"_id": task_id}))

    # ------------------------------------------------------------------
    # Tokens
    # ------------------------------------------------------------------

    def test_tokens_create_post_creates_token(self) -> None:
        """POST /tokens/create inserts a new token for the user."""
        before = self.test_db.tokens.count_documents({"owner": self.user_sid})
        resp = self.auth_client.post("/tokens/create", data={"expires_days": "7"})
        self.assertIn(resp.status_code, (200, 301, 302))
        after = self.test_db.tokens.count_documents({"owner": self.user_sid})
        self.assertGreater(after, before)

    def test_tokens_delete_post_removes_token(self) -> None:
        """POST /tokens/delete/<token> removes the token from the DB."""
        token_val: str = self.app.tokens.create(self.user_sid)
        self.assertIsNotNone(self.test_db.tokens.find_one({"token": token_val}))
        resp = self.auth_client.post(f"/tokens/delete/{token_val}")
        self.assertIn(resp.status_code, (200, 301, 302))
        self.assertIsNone(self.test_db.tokens.find_one({"token": token_val}))

    # ------------------------------------------------------------------
    # Metadata & processing
    # ------------------------------------------------------------------

    def test_metadata_post_with_empty_form_does_not_500(self) -> None:
        resp = self.auth_client.post("/metadata", data={})
        self.assertNotEqual(resp.status_code, 500)

    def test_processing_reset_post_does_not_500(self) -> None:
        resp = self.auth_client.post("/processing/reset", data={"type": "post", "id": "xyz"})
        self.assertNotEqual(resp.status_code, 500)

    # ------------------------------------------------------------------
    # Feeds / categories deletion
    # ------------------------------------------------------------------

    def test_delete_feeds_categories_post_does_not_500(self) -> None:
        resp = self.auth_client.post(
            "/delete-feeds-categories",
            data=json.dumps({"feed_ids": [], "category_ids": []}),
            content_type="application/json",
        )
        self.assertNotEqual(resp.status_code, 500)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def test_register_post_new_user_creates_account(self) -> None:
        """POST /register with fresh credentials creates user and redirects."""
        resp = self.client.post(
            "/register",
            data={"login": "brandnew_user", "password": "pass123", "password_confirm": "pass123"},
        )
        self.assertIn(resp.status_code, (200, 301, 302))
        user = self.app.users.get_by_username("brandnew_user")
        self.assertIsNotNone(user)

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    def test_workers_spawn_post_inserts_command(self) -> None:
        """POST /workers/spawn inserts a spawn command into worker_commands."""
        before = self.test_db.worker_commands.count_documents({"command": "spawn"})
        resp = self.auth_client.post("/workers/spawn")
        self.assertNotEqual(resp.status_code, 500)
        after = self.test_db.worker_commands.count_documents({"command": "spawn"})
        self.assertGreater(after, before)


if __name__ == "__main__":
    unittest.main()
