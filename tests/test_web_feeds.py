import json
import unittest
from unittest.mock import MagicMock

from rsstag.tasks import TASK_DELETE_FEEDS
from rsstag.web.feeds import on_delete_feeds_categories_post
from tests.web_test_utils import MongoWebTestCase


class TestWebFeedsDelete(MongoWebTestCase):
    """Integration tests for the /delete-feeds-categories endpoint."""

    def setUp(self) -> None:
        super().setUp()
        self.owner = "testuser"
        user_data, self.sid = self.seed_test_user(self.owner, "password")
        self.minimal_data = self.seed_minimal_data(self.sid)
        self.client = self.get_authenticated_client(self.sid)

    def test_delete_feeds_categories_post_with_feed_ids_enqueues_task(self) -> None:
        """POST with feed_ids creates a TASK_DELETE_FEEDS task with correct payload."""
        feed_id = self.minimal_data["feed_id"]
        resp = self.client.post(
            "/delete-feeds-categories",
            data=json.dumps({"feed_ids": [feed_id], "category_ids": []}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data)
        self.assertEqual(body["status"], "success")

        task = self.test_db.tasks.find_one({"user": self.sid, "type": TASK_DELETE_FEEDS})
        self.assertIsNotNone(task)
        self.assertEqual(task["feed_ids"], [feed_id])
        self.assertTrue(task["manual"])
        self.assertEqual(task["host"], self.app.config["settings"]["host_name"])

    def test_delete_feeds_categories_post_expands_categories_to_feeds(self) -> None:
        """POST with category_ids expands them to feed_ids via DB lookup."""
        category = self.minimal_data["category"]
        feed_id = self.minimal_data["feed_id"]
        resp = self.client.post(
            "/delete-feeds-categories",
            data=json.dumps({"feed_ids": [], "category_ids": [category]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data)
        self.assertEqual(body["status"], "success")

        task = self.test_db.tasks.find_one({"user": self.sid, "type": TASK_DELETE_FEEDS})
        self.assertIsNotNone(task)
        self.assertEqual(task["feed_ids"], [feed_id])

    def test_delete_feeds_categories_post_empty_input_returns_400(self) -> None:
        """POST with empty feed_ids and category_ids returns 400."""
        resp = self.client.post(
            "/delete-feeds-categories",
            data=json.dumps({"feed_ids": [], "category_ids": []}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.data)
        self.assertEqual(body["status"], "error")

    def test_delete_feeds_categories_post_no_feeds_resolved_returns_404(self) -> None:
        """POST with category_ids that resolve to no feeds returns 404."""
        resp = self.client.post(
            "/delete-feeds-categories",
            data=json.dumps({"feed_ids": [], "category_ids": ["nonexistent-category"]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        body = json.loads(resp.data)
        self.assertEqual(body["status"], "error")


class TestWebFeedsDeleteUnit(unittest.TestCase):
    """Pure unit tests for rsstag/web/feeds.py with mocked dependencies."""

    def test_exception_in_add_task_returns_500(self) -> None:
        """If app.tasks.add_task raises, the handler returns 500."""
        mock_app = MagicMock()
        mock_app.config = {"settings": {"host_name": "test-host"}}
        mock_app.tasks.add_task.side_effect = Exception("DB error")

        user = {"sid": "user-123"}
        request = MagicMock()
        request.data = json.dumps({"feed_ids": ["feed-1"], "category_ids": []}).encode("utf-8")

        response = on_delete_feeds_categories_post(mock_app, user, request)
        self.assertEqual(response.status_code, 500)
        body = json.loads(response.data)
        self.assertEqual(body["status"], "error")


if __name__ == "__main__":
    unittest.main()
