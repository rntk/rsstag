import json
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from rsstag.web.openai import on_openai_summary_post
from rsstag.web.routes import RSSTagRoutes


def _json_request(payload: Any) -> Request:
    builder: EnvironBuilder = EnvironBuilder(
        method="POST", json=payload, content_type="application/json"
    )
    return Request(builder.get_environ())


class TestOpenAISummary(unittest.TestCase):
    def setUp(self) -> None:
        self.llm: MagicMock = MagicMock()
        self.app: Any = SimpleNamespace(llm=self.llm)
        self.user: dict[str, Any] = {"settings": {"realtime_llm": "openai"}}

    def test_summary_route_is_registered(self) -> None:
        routes: RSSTagRoutes = RSSTagRoutes("localhost")
        endpoints: set[str] = {
            rule.endpoint for rule in routes.get_werkzeug_routes().iter_rules()
        }

        self.assertIn("on_openai_summary_post", endpoints)

    def test_generates_topic_summary(self) -> None:
        self.llm.call.return_value = "A concise summary.\n- One fact"

        response: Response = on_openai_summary_post(
            self.app,
            self.user,
            _json_request(
                {"topic": "Technology > AI", "sentences": ["First fact.", "Second fact."]}
            ),
        )
        payload: dict[str, Any] = json.loads(response.get_data(as_text=True))

        self.assertEqual(200, response.status_code)
        self.assertEqual("A concise summary.\n- One fact", payload["data"])
        prompt: str = self.llm.call.call_args.args[1][0]
        self.assertIn("<source>First fact. Second fact.</source>", prompt)
        self.assertEqual("realtime_llm", self.llm.call.call_args.kwargs["provider_key"])

    def test_rejects_empty_sentences(self) -> None:
        response: Response = on_openai_summary_post(
            self.app,
            self.user,
            _json_request({"topic": "Technology > AI", "sentences": []}),
        )

        self.assertEqual(400, response.status_code)
        self.llm.call.assert_not_called()

    def test_returns_cached_summary_without_calling_llm(self) -> None:
        cache: MagicMock = MagicMock()
        cache.make_key.return_value = "summary-key"
        cache.get.return_value = "A cached summary."
        self.app.llm_cache = cache
        self.user["sid"] = "owner-1"

        response: Response = on_openai_summary_post(
            self.app,
            self.user,
            _json_request({"topic": "Technology", "sentences": ["First fact."]}),
        )
        payload: dict[str, Any] = json.loads(response.get_data(as_text=True))

        self.assertEqual(200, response.status_code)
        self.assertEqual("A cached summary.", payload["data"])
        self.assertTrue(payload["cached"])
        cache.get.assert_called_once_with("owner-1", "summary-key")
        self.llm.call.assert_not_called()

    def test_caches_generated_summary(self) -> None:
        cache: MagicMock = MagicMock()
        cache.make_key.return_value = "summary-key"
        cache.get.return_value = None
        self.app.llm_cache = cache
        self.user["sid"] = "owner-1"
        self.llm.call.return_value = "A new summary."

        response: Response = on_openai_summary_post(
            self.app,
            self.user,
            _json_request({"topic": "Technology", "sentences": ["First fact."]}),
        )
        payload: dict[str, Any] = json.loads(response.get_data(as_text=True))

        self.assertEqual(200, response.status_code)
        self.assertFalse(payload["cached"])
        cache.set.assert_called_once_with("owner-1", "summary-key", "A new summary.")

    def test_returns_safe_error_when_llm_fails(self) -> None:
        self.llm.call.side_effect = RuntimeError("provider secret")

        response: Response = on_openai_summary_post(
            self.app,
            self.user,
            _json_request({"topic": "Technology > AI", "sentences": ["First fact."]}),
        )
        payload: dict[str, Any] = json.loads(response.get_data(as_text=True))

        self.assertEqual(502, response.status_code)
        self.assertNotIn("provider secret", payload["error"])


if __name__ == "__main__":
    unittest.main()
