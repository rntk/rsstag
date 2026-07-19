import gzip
import unittest
from typing import Any

from pymongo.database import Database
from werkzeug.test import Client
from werkzeug.wrappers import Response

from rsstag_lite.app import Application
from rsstag_lite.config import Settings
from tests.db_utils import DBHelper


def _settings() -> Settings:
    return Settings(
        mongo_url="mongodb://127.0.0.1:8765",
        mongo_database="unused",
        owner="owner",
        host="127.0.0.1",
        port=8886,
        log_level="INFO",
        telegram_api_id=0,
        telegram_api_hash="",
        telegram_phone="",
        telegram_database_key="",
        telegram_database_path="./tlg-lite",
        telegram_tdjson_path="",
        telegram_channels=("all",),
        telegram_limit=100,
        telegram_ready_delay=0,
        llm_base_url="http://localhost/v1",
        llm_api_key="",
        llm_model="test",
        llm_timeout=1,
        worker_poll_interval=1,
        task_lease_seconds=60,
        task_max_attempts=3,
    )


class TestLiteWeb(unittest.TestCase):
    def setUp(self) -> None:
        self.db_helper: DBHelper = DBHelper(port=8765)
        self.database: Database[Any] = self.db_helper.create_test_db()
        self.application: Application = Application(_settings(), self.database)
        self.client: Client = Client(self.application, Response)
        self.database.feeds.insert_one(
            {"owner": "owner", "provider": "telegram", "feed_id": "10", "title": "Feed"}
        )
        self.database.posts.insert_one(
            {
                "owner": "owner",
                "provider": "telegram",
                "pid": "post-1",
                "id": 1,
                "feed_id": "10",
                "unix_date": 1,
                "read": False,
                "tags": ["telegram"],
                "grouping_claim": "claim-1",
                "url": "https://example.test/post",
                "content": {"title": "A post", "content": gzip.compress(b"One.")},
            }
        )
        self.application.repository.save_grouping(
            "owner",
            "post-1",
            [{"number": 1, "text": "One.", "read": False}],
            {"News > Telegram": [1]},
            "claim-1",
        )

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.database)
        self.db_helper.close()

    def test_canvas_and_hierarchy_render_grouping(self) -> None:
        canvas: Response = self.client.get("/canvas?feed=10")
        hierarchy: Response = self.client.get("/hierarchy?feed=10")

        self.assertEqual(canvas.status_code, 200)
        self.assertIn(b"A post", canvas.data)
        self.assertIn(b"News \\u003e Telegram", canvas.data)
        self.assertEqual(hierarchy.status_code, 200)
        self.assertIn(b"News \\u003e Telegram", hierarchy.data)

    def test_unknown_feed_is_not_found(self) -> None:
        response: Response = self.client.get("/canvas?feed=missing")
        self.assertEqual(response.status_code, 404)

    def test_read_api_updates_post_and_queues_telegram_mark(self) -> None:
        response: Response = self.client.post(
            "/api/posts/read",
            data='{"ids":["post-1"],"read":true}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.database.posts.find_one({"pid": "post-1"})["read"])
        self.assertEqual(self.database.tasks.count_documents({"type": 17}), 1)


if __name__ == "__main__":
    unittest.main()
