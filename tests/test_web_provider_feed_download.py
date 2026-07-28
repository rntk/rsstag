import json
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from rsstag.tasks import TASK_DOWNLOAD
from rsstag.web.providers import on_provider_feed_download_post
from rsstag.web.routes import RSSTagRoutes


def _request(payload: Any) -> Request:
    body: Any = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
    builder: EnvironBuilder = EnvironBuilder(
        method="POST",
        data=body,
        content_type="application/json",
        headers={"Host": "rsstag.test"},
    )
    return Request(builder.get_environ())


class TestProviderFeedDownloadEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.app: MagicMock = MagicMock()
        self.app.config = {"settings": {"host_name": "configured.test"}}
        self.app.feeds.get_by_feed_id.return_value = {
            "feed_id": "-100123",
            "provider": "telegram",
            "title": "Test channel",
        }
        self.app.users.is_provider_connected.return_value = True
        self.app.users.get_in_queue.return_value = {}
        self.app.users.update_by_sid.return_value = True
        self.app.tasks.add_task.return_value = True
        self.user: Dict[str, Any] = {
            "sid": "alice",
            "providers": {"telegram": {"phone": "+10000000000"}},
            "in_queue": {},
        }

    def _post(self, payload: Any) -> Dict[str, Any]:
        response: Response = on_provider_feed_download_post(
            self.app, self.user, _request(payload)
        )
        return {
            "status_code": response.status_code,
            "body": json.loads(response.get_data(as_text=True)),
        }

    def _queued_task(self) -> Dict[str, Any]:
        return self.app.tasks.add_task.call_args[0][0]

    def test_queues_bounded_download_for_one_telegram_feed(self) -> None:
        result: Dict[str, Any] = self._post(
            {"feed_id": "-100123", "posts_count": 250}
        )

        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["body"]["status"], "success")
        task: Dict[str, Any] = self._queued_task()
        self.assertEqual(task["type"], TASK_DOWNLOAD)
        self.assertEqual(task["user"], "alice")
        self.assertEqual(task["provider"], "telegram")
        self.assertEqual(task["host"], "rsstag.test")
        self.assertEqual(
            task["selection"],
            {
                "channels": ["-100123"],
                "feeds": [],
                "categories": [],
                "telegram_load_mode": "limit",
                "telegram_load_limit": 250,
                "telegram_limit": 250,
            },
        )
        self.assertIs(
            self.app.tasks.add_task.call_args.kwargs["manual"],
            False,
        )
        self.app.users.update_by_sid.assert_called_once_with(
            "alice",
            {
                "in_queue.telegram": True,
                "message": "Refreshing Test channel",
            },
        )

    def test_rejects_feed_not_owned_by_user(self) -> None:
        self.app.feeds.get_by_feed_id.return_value = None

        result: Dict[str, Any] = self._post(
            {"feed_id": "-100999", "posts_count": 100}
        )

        self.assertEqual(result["status_code"], 404)
        self.app.tasks.add_task.assert_not_called()

    def test_rejects_non_telegram_feed(self) -> None:
        self.app.feeds.get_by_feed_id.return_value["provider"] = "bazqux"

        result: Dict[str, Any] = self._post(
            {"feed_id": "-100123", "posts_count": 100}
        )

        self.assertEqual(result["status_code"], 400)
        self.assertIn("only for Telegram", result["body"]["message"])
        self.app.tasks.add_task.assert_not_called()

    def test_rejects_when_telegram_is_not_connected(self) -> None:
        self.app.users.is_provider_connected.return_value = False

        result: Dict[str, Any] = self._post(
            {"feed_id": "-100123", "posts_count": 100}
        )

        self.assertEqual(result["status_code"], 400)
        self.app.tasks.add_task.assert_not_called()

    def test_rejects_invalid_post_counts(self) -> None:
        invalid_values: list[Any] = [None, True, 0, -1, 10001, 1.5, "many"]

        for invalid_value in invalid_values:
            with self.subTest(posts_count=invalid_value):
                self.app.tasks.add_task.reset_mock()
                result: Dict[str, Any] = self._post(
                    {"feed_id": "-100123", "posts_count": invalid_value}
                )
                self.assertEqual(result["status_code"], 400)
                self.app.tasks.add_task.assert_not_called()

    def test_rejects_malformed_json(self) -> None:
        result: Dict[str, Any] = self._post("not json")

        self.assertEqual(result["status_code"], 400)
        self.app.tasks.add_task.assert_not_called()

    def test_rejects_refresh_while_telegram_download_is_running(self) -> None:
        self.app.users.get_in_queue.return_value = {"telegram": True}

        result: Dict[str, Any] = self._post(
            {"feed_id": "-100123", "posts_count": 100}
        )

        self.assertEqual(result["status_code"], 409)
        self.app.tasks.add_task.assert_not_called()

    def test_reports_task_queue_failure(self) -> None:
        self.app.tasks.add_task.return_value = False

        result: Dict[str, Any] = self._post(
            {"feed_id": "-100123", "posts_count": 100}
        )

        self.assertEqual(result["status_code"], 500)
        self.assertEqual(result["body"]["status"], "error")

    def test_route_is_registered_as_post_only(self) -> None:
        routes: list[Any] = [
            rule
            for rule in RSSTagRoutes("rsstag.test").get_werkzeug_routes().iter_rules()
            if rule.endpoint == "on_provider_feed_download_post"
        ]

        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].rule, "/api/provider/feed/download")
        self.assertEqual(routes[0].methods, {"POST"})


if __name__ == "__main__":
    unittest.main()
