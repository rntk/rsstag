import gzip
import unittest
from typing import Any, Dict

from rsstag.tasks import (
    POST_NOT_IN_PROCESSING,
    TAG_NOT_IN_PROCESSING,
    TASK_DOWNLOAD,
    TASK_POST_GROUPING,
    TASK_TAG_CLASSIFICATION,
    RssTagTasks,
)
from tests.db_utils import DBHelper


class TestExternalWorkerTasks(unittest.TestCase):
    def setUp(self) -> None:
        self.db_helper: DBHelper = DBHelper(port=8765)
        self.db = self.db_helper.create_test_db()
        self.tasks: RssTagTasks = RssTagTasks(self.db)
        self.owner: str = "owner-1"

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()

    @staticmethod
    def _compress_text(text: str) -> bytes:
        return gzip.compress(text.encode("utf-8"))

    def test_claim_external_task_only_whitelisted_types(self) -> None:
        self.db.tasks.insert_many(
            [
                {
                    "user": self.owner,
                    "type": TASK_DOWNLOAD,
                    "processing": 0,
                    "manual": True,
                },
                {
                    "user": self.owner,
                    "type": TASK_POST_GROUPING,
                    "processing": 0,
                    "manual": True,
                },
            ]
        )
        self.db.posts.insert_one(
            {
                "owner": self.owner,
                "pid": 1001,
                "processing": POST_NOT_IN_PROCESSING,
                "content": {
                    "title": "Title",
                    "content": self._compress_text("Body text"),
                },
            }
        )

        task: Dict[str, Any] = self.tasks.claim_external_task(self.owner) or {}

        self.assertEqual(task.get("task_type"), TASK_POST_GROUPING)
        self.assertIn("item", task)
        self.assertIn("post_id", task["item"])

    def test_claim_post_grouping_returns_single_locked_post(self) -> None:
        self.db.tasks.insert_one(
            {
                "user": self.owner,
                "type": TASK_POST_GROUPING,
                "processing": 0,
                "manual": True,
            }
        )
        first_id = self.db.posts.insert_one(
            {
                "owner": self.owner,
                "pid": 1,
                "processing": POST_NOT_IN_PROCESSING,
                "content": {
                    "title": "A",
                    "content": self._compress_text("First post"),
                },
            }
        ).inserted_id
        second_id = self.db.posts.insert_one(
            {
                "owner": self.owner,
                "pid": 2,
                "processing": POST_NOT_IN_PROCESSING,
                "content": {
                    "title": "B",
                    "content": self._compress_text("Second post"),
                },
            }
        ).inserted_id

        task = self.tasks.claim_external_task(self.owner)
        self.assertIsNotNone(task)
        claimed_id = task["item"]["post_id"]
        self.assertIn(claimed_id, {str(first_id), str(second_id)})

        locked_count = self.db.posts.count_documents(
            {"owner": self.owner, "processing": {"$ne": POST_NOT_IN_PROCESSING}}
        )
        self.assertEqual(locked_count, 1)

    def test_submit_post_grouping_success_updates_and_completes_task(self) -> None:
        self.db.tasks.insert_one(
            {
                "user": self.owner,
                "type": TASK_POST_GROUPING,
                "processing": 0,
                "manual": True,
            }
        )
        post_id = self.db.posts.insert_one(
            {
                "owner": self.owner,
                "pid": 777,
                "processing": POST_NOT_IN_PROCESSING,
                "content": {
                    "title": "X",
                    "content": self._compress_text("Some content"),
                },
            }
        ).inserted_id

        claim = self.tasks.claim_external_task(self.owner)
        self.assertEqual(claim["item"]["post_id"], str(post_id))

        result = self.tasks.submit_external_task_result(
            owner=self.owner,
            task_type=TASK_POST_GROUPING,
            item_id=str(post_id),
            success=True,
            result={
                "sentences": [{"number": 1, "text": "s1"}],
                "groups": {"Main": [1]},
            },
        )
        self.assertTrue(result)

        post = self.db.posts.find_one({"_id": post_id})
        self.assertEqual(post.get("processing"), POST_NOT_IN_PROCESSING)
        self.assertEqual(post.get("grouping"), 1)
        grouped = self.db.post_grouping.find_one({"owner": self.owner})
        self.assertIsNotNone(grouped)
        self.assertEqual(grouped.get("post_ids"), ["777"])
        self.assertIsNone(
            self.db.tasks.find_one({"user": self.owner, "type": TASK_POST_GROUPING})
        )

    def test_submit_tag_classification_failure_unlocks_item(self) -> None:
        self.db.tasks.insert_one(
            {
                "user": self.owner,
                "type": TASK_TAG_CLASSIFICATION,
                "processing": 0,
                "manual": True,
            }
        )
        tag_id = self.db.tags.insert_one(
            {
                "owner": self.owner,
                "tag": "python",
                "words": ["python"],
                "processing": TAG_NOT_IN_PROCESSING,
            }
        ).inserted_id

        claim = self.tasks.claim_external_task(self.owner)
        self.assertEqual(claim["item"]["tag_id"], str(tag_id))

        submitted = self.tasks.submit_external_task_result(
            owner=self.owner,
            task_type=TASK_TAG_CLASSIFICATION,
            item_id=str(tag_id),
            success=False,
            error="transient worker error",
        )
        self.assertTrue(submitted)

        tag = self.db.tags.find_one({"_id": tag_id})
        self.assertEqual(tag.get("processing"), TAG_NOT_IN_PROCESSING)
        self.assertFalse("classifications" in tag)
        self.assertIsNotNone(
            self.db.tasks.find_one({"user": self.owner, "type": TASK_TAG_CLASSIFICATION})
        )

    def test_submit_tag_classification_success_sets_categories_and_removes_task(self) -> None:
        self.db.tasks.insert_one(
            {
                "user": self.owner,
                "type": TASK_TAG_CLASSIFICATION,
                "processing": 0,
                "manual": True,
            }
        )
        tag_id = self.db.tags.insert_one(
            {
                "owner": self.owner,
                "tag": "python",
                "words": ["python"],
                "processing": TAG_NOT_IN_PROCESSING,
            }
        ).inserted_id

        claim = self.tasks.claim_external_task(self.owner)
        self.assertEqual(claim["item"]["tag_id"], str(tag_id))

        submitted = self.tasks.submit_external_task_result(
            owner=self.owner,
            task_type=TASK_TAG_CLASSIFICATION,
            item_id=str(tag_id),
            success=True,
            result={
                "classifications": [
                    {"category": "technology", "count": 3, "pids": [1, 2, 3]}
                ]
            },
        )
        self.assertTrue(submitted)

        tag = self.db.tags.find_one({"_id": tag_id})
        self.assertEqual(tag.get("processing"), TAG_NOT_IN_PROCESSING)
        self.assertEqual(
            tag.get("classifications"),
            [{"category": "technology", "count": 3, "pids": [1, 2, 3]}],
        )
        self.assertIsNone(
            self.db.tasks.find_one({"user": self.owner, "type": TASK_TAG_CLASSIFICATION})
        )

    def test_submit_rejects_unclaimed_item(self) -> None:
        self.db.tasks.insert_one(
            {
                "user": self.owner,
                "type": TASK_POST_GROUPING,
                "processing": 0,
                "manual": True,
            }
        )
        post_id = self.db.posts.insert_one(
            {
                "owner": self.owner,
                "pid": 123,
                "processing": POST_NOT_IN_PROCESSING,
                "content": {
                    "title": "T",
                    "content": self._compress_text("Body"),
                },
            }
        ).inserted_id

        submitted = self.tasks.submit_external_task_result(
            owner=self.owner,
            task_type=TASK_POST_GROUPING,
            item_id=str(post_id),
            success=True,
            result={
                "sentences": [{"number": 1, "text": "x"}],
                "groups": {"Main": [1]},
            },
        )
        self.assertFalse(submitted)

        post = self.db.posts.find_one({"_id": post_id})
        self.assertEqual(post.get("processing"), POST_NOT_IN_PROCESSING)
        self.assertFalse("grouping" in post)

    def test_submit_tracks_worker_token_id_and_rejects_other_worker(self) -> None:
        self.db.tasks.insert_one(
            {
                "user": self.owner,
                "type": TASK_POST_GROUPING,
                "processing": 0,
                "manual": True,
            }
        )
        post_id = self.db.posts.insert_one(
            {
                "owner": self.owner,
                "pid": "feed-42",
                "processing": POST_NOT_IN_PROCESSING,
                "content": {
                    "title": "Tracked",
                    "content": self._compress_text("Body"),
                },
            }
        ).inserted_id

        worker_a = "token-a"
        worker_b = "token-b"
        claim = self.tasks.claim_external_task(self.owner, worker_token_id=worker_a)
        self.assertEqual(claim["item"]["post_id"], str(post_id))

        claimed_post = self.db.posts.find_one({"_id": post_id})
        self.assertEqual(claimed_post.get("external_claim_worker_token_id"), worker_a)
        self.assertIsNotNone(claimed_post.get("external_claimed_at"))

        wrong_submit = self.tasks.submit_external_task_result(
            owner=self.owner,
            task_type=TASK_POST_GROUPING,
            item_id=str(post_id),
            success=True,
            result={
                "sentences": [{"number": 1, "text": "x"}],
                "groups": {"Main": [1]},
            },
            worker_token_id=worker_b,
        )
        self.assertFalse(wrong_submit)

        correct_submit = self.tasks.submit_external_task_result(
            owner=self.owner,
            task_type=TASK_POST_GROUPING,
            item_id=str(post_id),
            success=True,
            result={
                "sentences": [{"number": 1, "text": "x"}],
                "groups": {"Main": [1]},
            },
            worker_token_id=worker_a,
        )
        self.assertTrue(correct_submit)

        post = self.db.posts.find_one({"_id": post_id})
        self.assertEqual(post.get("external_result_worker_token_id"), worker_a)
        self.assertIsNotNone(post.get("external_submitted_at"))
        self.assertNotIn("external_claim_worker_token_id", post)
        self.assertNotIn("external_claimed_at", post)


if __name__ == "__main__":
    unittest.main()
