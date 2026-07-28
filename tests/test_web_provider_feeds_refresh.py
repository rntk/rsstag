"""Tests for the "refresh sources list" web endpoint and its routing.

Mirrors tests/test_web_provider_feed_download.py: a fully mocked
RSSTagApplication so the endpoint's validation/queueing logic can be
exercised without a database.
"""

import json
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from rsstag.providers import providers as data_providers
from rsstag.tasks import TASK_FEEDS_LIST
from rsstag.web.providers import (
    feeds_list_capable_providers,
    on_provider_feeds_get_post,
    on_provider_feeds_refresh_post,
)
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


class TestProviderFeedsRefreshEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.app: MagicMock = MagicMock()
        self.app.config = {"settings": {"host_name": "configured.test"}}
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
        response: Response = on_provider_feeds_refresh_post(
            self.app, self.user, _request(payload)
        )
        return {
            "status_code": response.status_code,
            "body": json.loads(response.get_data(as_text=True)),
        }

    def _queued_task(self) -> Dict[str, Any]:
        return self.app.tasks.add_task.call_args[0][0]

    def test_happy_path_queues_task_and_flags_in_queue(self) -> None:
        result: Dict[str, Any] = self._post({"provider": "telegram"})

        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["body"]["status"], "success")

        task: Dict[str, Any] = self._queued_task()
        self.assertEqual(task["type"], TASK_FEEDS_LIST)
        self.assertEqual(task["user"], "alice")
        self.assertEqual(task["provider"], "telegram")
        self.assertEqual(task["host"], "rsstag.test")
        self.assertIs(self.app.tasks.add_task.call_args.kwargs["manual"], False)

        self.app.users.update_by_sid.assert_called_once_with(
            "alice",
            {
                "in_queue.telegram": True,
                "message": "Refreshing the telegram sources list",
            },
        )

    def test_rejects_malformed_json(self) -> None:
        result: Dict[str, Any] = self._post("not json")

        self.assertEqual(result["status_code"], 400)
        self.app.tasks.add_task.assert_not_called()

    def test_rejects_missing_provider(self) -> None:
        result: Dict[str, Any] = self._post({})

        self.assertEqual(result["status_code"], 400)
        self.app.tasks.add_task.assert_not_called()

    def test_rejects_unknown_provider(self) -> None:
        result: Dict[str, Any] = self._post({"provider": "not_a_real_provider"})

        self.assertEqual(result["status_code"], 400)
        self.app.tasks.add_task.assert_not_called()

    def test_rejects_provider_that_cannot_list_feeds(self) -> None:
        # X is a known provider class but does not implement list_feeds.
        result: Dict[str, Any] = self._post({"provider": "x"})

        self.assertEqual(result["status_code"], 400)
        self.assertIn("can`t refresh", result["body"]["message"])
        self.app.tasks.add_task.assert_not_called()

    def test_rejects_when_provider_not_connected(self) -> None:
        self.app.users.is_provider_connected.return_value = False

        result: Dict[str, Any] = self._post({"provider": "telegram"})

        self.assertEqual(result["status_code"], 400)
        self.assertIn("not connected", result["body"]["message"])
        self.app.tasks.add_task.assert_not_called()

    def test_rejects_when_a_refresh_is_already_in_queue(self) -> None:
        self.app.users.get_in_queue.return_value = {"telegram": True}

        result: Dict[str, Any] = self._post({"provider": "telegram"})

        self.assertEqual(result["status_code"], 409)
        self.app.tasks.add_task.assert_not_called()

    def test_reports_task_queue_failure_as_500(self) -> None:
        self.app.tasks.add_task.return_value = False

        result: Dict[str, Any] = self._post({"provider": "telegram"})

        self.assertEqual(result["status_code"], 500)
        self.assertEqual(result["body"]["status"], "error")

    def test_reports_unexpected_exception_as_500(self) -> None:
        self.app.tasks.add_task.side_effect = Exception("db down")

        result: Dict[str, Any] = self._post({"provider": "telegram"})

        self.assertEqual(result["status_code"], 500)
        self.assertEqual(result["body"]["status"], "error")

    def test_route_is_registered_as_post_only(self) -> None:
        routes: list[Any] = [
            rule
            for rule in RSSTagRoutes("rsstag.test").get_werkzeug_routes().iter_rules()
            if rule.endpoint == "on_provider_feeds_refresh_post"
        ]

        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].rule, "/api/provider/feeds/refresh")
        self.assertEqual(routes[0].methods, {"POST"})


class TestFeedsListGetRedirectsTelegram(unittest.TestCase):
    """GET /provider/telegram/feeds now redirects to the categories page."""

    def setUp(self) -> None:
        self.app: MagicMock = MagicMock()
        self.app.routes = RSSTagRoutes("rsstag.test")
        self.request: MagicMock = MagicMock()
        self.request.method = "GET"
        self.user: Dict[str, Any] = {"sid": "alice", "providers": {}}

    def test_telegram_redirects_to_group_by_category(self) -> None:
        response: Response = on_provider_feeds_get_post(
            self.app, self.user, self.request, provider=data_providers.TELEGRAM
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/group/category"))


class TestFeedsListCapableProviders(unittest.TestCase):
    def test_lists_only_connected_and_capable_providers(self) -> None:
        user: Dict[str, Any] = {
            "sid": "alice",
            "providers": {
                "telegram": {"phone": "+1"},
                "bazqux": {"login": "a"},
                "x": {"token": "t"},
            },
        }

        result = feeds_list_capable_providers(user)

        self.assertEqual(result, ["bazqux", "telegram"])

    def test_returns_empty_list_when_nothing_connected(self) -> None:
        user: Dict[str, Any] = {"sid": "alice", "providers": {}}

        self.assertEqual(feeds_list_capable_providers(user), [])

    def test_ignores_connected_provider_without_providers_key(self) -> None:
        user: Dict[str, Any] = {"sid": "alice"}

        self.assertEqual(feeds_list_capable_providers(user), [])


if __name__ == "__main__":
    unittest.main()
