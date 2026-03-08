"""Module 5: External worker HTTP API tests (claim/submit endpoints)."""
import gzip
import json
import unittest
from typing import Any, Dict, Optional

from werkzeug.test import Client
from werkzeug.wrappers import Response

from rsstag.tasks import TASK_POST_GROUPING
from tests.web_test_utils import MongoWebTestCase


class TestExternalWorkerAPI(MongoWebTestCase):
    """Tests for /api/external-workers/claim and /api/external-workers/submit."""

    CLAIM_URL = "/api/external-workers/claim"
    SUBMIT_URL = "/api/external-workers/submit"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user_doc, cls.user_sid = cls.seed_test_user("extworker", "extpass")
        cls.token: str = cls.app.tokens.create(cls.user_sid)

    def setUp(self) -> None:
        """Each test gets a clean tasks/posts slate (drop and reseed)."""
        self.test_db.tasks.drop()
        self.test_db.posts.drop()

    def _auth_headers(self, token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _seed_claimable_task(self) -> None:
        """Insert a TASK_POST_GROUPING task and a matching post."""
        compressed = gzip.compress("Body text for grouping.".encode("utf-8"))
        self.test_db.tasks.insert_one({
            "user": self.user_sid,
            "type": TASK_POST_GROUPING,
            "processing": 0,
            "manual": True,
        })
        self.test_db.posts.insert_one({
            "owner": self.user_sid,
            "pid": "ext-post-1",
            "processing": 0,
            "content": {"title": "Ext Post", "content": compressed},
        })

    # ------------------------------------------------------------------
    # Auth enforcement
    # ------------------------------------------------------------------

    def test_claim_without_token_returns_401(self) -> None:
        resp = self.client.post(self.CLAIM_URL)
        self.assertEqual(resp.status_code, 401)

    def test_claim_with_invalid_token_returns_401(self) -> None:
        resp = self.client.post(
            self.CLAIM_URL,
            headers=self._auth_headers("invalid-token-xyz"),
        )
        self.assertEqual(resp.status_code, 401)

    def test_submit_without_token_returns_401(self) -> None:
        resp = self.client.post(
            self.SUBMIT_URL,
            data=json.dumps({"task_type": TASK_POST_GROUPING, "item_id": "abc",
                             "success": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    # ------------------------------------------------------------------
    # Claim behaviour
    # ------------------------------------------------------------------

    def test_claim_with_no_tasks_returns_null_task(self) -> None:
        resp = self.client.post(self.CLAIM_URL, headers=self._auth_headers(self.token))
        self.assertEqual(resp.status_code, 200)
        body: Dict[str, Any] = json.loads(resp.data)
        self.assertTrue(body.get("success"))
        self.assertIsNone(body.get("task"))

    def test_claim_with_available_task_returns_task_payload(self) -> None:
        self._seed_claimable_task()
        resp = self.client.post(self.CLAIM_URL, headers=self._auth_headers(self.token))
        self.assertEqual(resp.status_code, 200)
        body: Dict[str, Any] = json.loads(resp.data)
        self.assertTrue(body.get("success"))
        task = body.get("task")
        self.assertIsNotNone(task)
        self.assertEqual(task["task_type"], TASK_POST_GROUPING)
        self.assertIn("item", task)

    def test_double_claim_returns_null_on_second_call(self) -> None:
        """After all items are claimed the second call returns null."""
        self._seed_claimable_task()
        # First claim takes the single post
        self.client.post(self.CLAIM_URL, headers=self._auth_headers(self.token))
        # Second claim: no unclaimed posts remain
        resp = self.client.post(self.CLAIM_URL, headers=self._auth_headers(self.token))
        body: Dict[str, Any] = json.loads(resp.data)
        self.assertIsNone(body.get("task"))

    # ------------------------------------------------------------------
    # Submit behaviour
    # ------------------------------------------------------------------

    def test_submit_success_result_returns_200(self) -> None:
        self._seed_claimable_task()
        claim_resp = self.client.post(self.CLAIM_URL, headers=self._auth_headers(self.token))
        task_payload: Dict[str, Any] = json.loads(claim_resp.data)["task"]
        item_id: str = task_payload["item"]["post_id"]

        submit_resp = self.client.post(
            self.SUBMIT_URL,
            headers=self._auth_headers(self.token),
            data=json.dumps({
                "task_type": TASK_POST_GROUPING,
                "item_id": item_id,
                "success": True,
                "result": {"grouping": 1},
                "error": "",
            }),
            content_type="application/json",
        )
        self.assertEqual(submit_resp.status_code, 200)
        body: Dict[str, Any] = json.loads(submit_resp.data)
        self.assertTrue(body.get("success"))

    def test_submit_missing_fields_returns_400(self) -> None:
        resp = self.client.post(
            self.SUBMIT_URL,
            headers=self._auth_headers(self.token),
            data=json.dumps({"task_type": TASK_POST_GROUPING}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_wrong_token_cannot_submit_another_users_claimed_task(self) -> None:
        """A token that does not own the claimed post cannot successfully submit."""
        self._seed_claimable_task()
        claim_resp = self.client.post(self.CLAIM_URL, headers=self._auth_headers(self.token))
        task_payload: Dict[str, Any] = json.loads(claim_resp.data)["task"]
        item_id: str = task_payload["item"]["post_id"]

        # Create a second user and token
        _, other_sid = self.seed_test_user("extother", "otherpass")
        other_token: str = self.app.tokens.create(other_sid)

        submit_resp = self.client.post(
            self.SUBMIT_URL,
            headers=self._auth_headers(other_token),
            data=json.dumps({
                "task_type": TASK_POST_GROUPING,
                "item_id": item_id,
                "success": True,
                "result": {},
                "error": "",
            }),
            content_type="application/json",
        )
        # Submit must be rejected (wrong owner or wrong token_id)
        body: Dict[str, Any] = json.loads(submit_resp.data)
        self.assertFalse(body.get("success"))


if __name__ == "__main__":
    unittest.main()
