import gzip
import unittest
from typing import Any

from pymongo.database import Database

from rsstag_lite.repository import Repository
from rsstag_lite.tasks import TASK_POST_GROUPING, TASK_RUNNING, TaskQueue
from tests.db_utils import DBHelper


class TestLiteRepository(unittest.TestCase):
    def setUp(self) -> None:
        self.db_helper: DBHelper = DBHelper(port=8765)
        self.database: Database[Any] = self.db_helper.create_test_db()
        self.repository: Repository = Repository(self.database)
        self.repository.prepare()

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.database)
        self.db_helper.close()

    def test_grouping_and_read_state_round_trip(self) -> None:
        self.database.posts.insert_one(
            {
                "owner": "owner",
                "provider": "telegram",
                "pid": "post-1",
                "id": 1,
                "feed_id": "10",
                "unix_date": 1,
                "read": False,
                "processing": 1,
                "grouping_claim": "claim-1",
                "content": {"title": "", "content": gzip.compress(b"One. Two.")},
            }
        )

        self.repository.save_grouping(
            "owner",
            "post-1",
            [
                {"number": 1, "text": "One.", "read": False},
                {"number": 2, "text": "Two.", "read": False},
            ],
            {"Topic": [1, 2]},
            "claim-1",
        )
        self.repository.set_sentences_read("owner", "post-1", [1], True)

        grouping: dict[str, Any] | None = self.repository.get_grouping("owner", "post-1")
        self.assertIsNotNone(grouping)
        assert grouping is not None
        self.assertTrue(grouping["sentences"][0]["read"])
        self.assertFalse(grouping["sentences"][1]["read"])
        self.assertFalse(self.database.posts.find_one({"pid": "post-1"})["read"])

    def test_task_queue_claim_and_finish(self) -> None:
        queue: TaskQueue = TaskQueue(self.database, lease_seconds=60, max_attempts=3)
        queue.prepare()
        task_id: Any = queue.enqueue(TASK_POST_GROUPING, "owner", {"post_ids": ["p1"]})

        task = queue.claim()

        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task.id, task_id)
        self.assertEqual(self.database.tasks.find_one({"_id": task_id})["status"], TASK_RUNNING)
        queue.finish(task)
        self.assertIsNone(queue.claim())


if __name__ == "__main__":
    unittest.main()
