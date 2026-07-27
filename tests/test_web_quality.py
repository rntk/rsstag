import json
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from rsstag.tasks import (
    SCOPE_MODE_CATEGORIES,
    SCOPE_MODE_FEEDS,
    TASK_POST_QUALITY,
)
from rsstag.web.quality import on_quality_scan_post


def _request(payload: Any) -> Request:
    body = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
    builder = EnvironBuilder(
        method="POST", data=body, content_type="application/json"
    )
    return Request(builder.get_environ())


class TestQualityScanEndpoint(unittest.TestCase):
    def setUp(self):
        self.app = MagicMock()
        self.app.config = {"settings": {"host_name": "localhost"}}
        self.app.tasks.add_task.return_value = True
        self.user = {"sid": "alice", "provider": "telegram"}

    def _post(self, payload: Any) -> Dict[str, Any]:
        response = on_quality_scan_post(self.app, self.user, _request(payload))
        return {
            "status_code": response.status_code,
            "body": json.loads(response.get_data(as_text=True)),
        }

    def _queued_task(self) -> Dict[str, Any]:
        return self.app.tasks.add_task.call_args[0][0]

    def test_queues_a_scoped_scan_for_a_category(self):
        result = self._post({"category_ids": ["tech"]})

        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["body"]["status"], "success")
        task = self._queued_task()
        self.assertEqual(task["type"], TASK_POST_QUALITY)
        self.assertEqual(task["user"], "alice")
        self.assertEqual(
            task["scope"], {"mode": SCOPE_MODE_CATEGORIES, "category_ids": ["tech"]}
        )

    def test_queues_a_scoped_scan_for_a_feed(self):
        self._post({"feed_ids": ["f1"]})

        self.assertEqual(
            self._queued_task()["scope"],
            {"mode": SCOPE_MODE_FEEDS, "feed_ids": ["f1"]},
        )

    def test_feed_selection_wins_over_category_selection(self):
        self._post({"feed_ids": ["f1"], "category_ids": ["tech"]})

        self.assertEqual(self._queued_task()["scope"]["mode"], SCOPE_MODE_FEEDS)

    def test_empty_selection_is_rejected_without_queueing(self):
        result = self._post({})

        self.assertEqual(result["status_code"], 400)
        self.app.tasks.add_task.assert_not_called()

    def test_blank_ids_are_dropped(self):
        result = self._post({"feed_ids": ["", None]})

        self.assertEqual(result["status_code"], 400)
        self.app.tasks.add_task.assert_not_called()

    def test_malformed_body_is_rejected(self):
        result = self._post("not json at all")

        self.assertEqual(result["status_code"], 400)
        self.app.tasks.add_task.assert_not_called()

    def test_queue_failure_is_reported_as_an_error(self):
        self.app.tasks.add_task.return_value = False

        result = self._post({"category_ids": ["tech"]})

        self.assertEqual(result["status_code"], 500)
        self.assertEqual(result["body"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
