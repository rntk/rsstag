import unittest
from configparser import ConfigParser
from typing import Any
from unittest.mock import MagicMock, patch

import requests

from rsstag.decisions import (
    DecisionsClient,
    DecisionsError,
    Jev,
    LLamaCPPDecisions,
    create_decisions_client,
)


class TestDecisionsClient(unittest.TestCase):
    def response(self, payload: object, status_code: int = 200) -> MagicMock:
        response: MagicMock = MagicMock()
        response.status_code = status_code
        response.json.return_value = payload
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        return response

    def test_request_route_auth_timeout_and_mixed_answers(self) -> None:
        payload: dict[str, object] = {
            "model": "m1",
            "answers": {
                "is": {"type": "noul", "noul": 0.8},
                "kind": {
                    "type": "choice",
                    "choice": "a",
                    "confidence": 0.9,
                    "probabilities": {"a": 0.9, "b": 0.1},
                },
                "rating": {
                    "type": "score",
                    "score": 1,
                    "confidence": 0.7,
                    "legend": {"0": "low", "1": "high"},
                    "probabilities": {"0": 0.2, "1": 0.8},
                },
                "region": {
                    "type": "box",
                    "box": {"top": 0.1, "bottom": 0.8, "left": 0.2, "right": 0.9},
                    "confidence": None,
                },
            },
            "usage": {"input_tokens": 12, "output_tokens": 4},
        }
        client: DecisionsClient = DecisionsClient(
            "https://example.test/v1/", "m1", "secret", timeout=12.5
        )
        questions: dict[str, dict[str, object]] = {
            "is": {"type": "noul"},
            "kind": {"type": "choice", "criteria": {"a": "A", "b": "B"}},
            "rating": {"type": "score", "criteria": ["low", "high"]},
            "region": {"type": "box"},
        }
        with patch("rsstag.decisions.client.requests.post") as post:
            post.return_value = self.response(payload)
            result = client.call({"text": "hello"}, questions, long_context=True)

        self.assertEqual(set(result.answers), set(questions))
        self.assertEqual(result.answers["kind"].type, "choice")
        post.assert_called_once()
        args: tuple[object, ...] = post.call_args.args
        kwargs: dict[str, object] = post.call_args.kwargs
        self.assertEqual(args[0], "https://example.test/v1/systemone")
        self.assertEqual(kwargs["timeout"], 12.5)
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(kwargs["headers"]["TypeSafe-Danger-Zone-Images"], "true")
        self.assertEqual(kwargs["headers"]["TypeSafe-Danger-Zone-Long-Context"], "true")

    def test_local_endpoint_omits_authentication(self) -> None:
        client: LLamaCPPDecisions = LLamaCPPDecisions(
            "http://localhost:8080", "local", max_context_tokens=1
        )
        payload: dict[str, object] = {
            "model": "local",
            "answers": {"yes": {"type": "noul", "noul": 1}},
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
        with patch("rsstag.decisions.client.requests.post") as post:
            post.return_value = self.response(payload)
            client.call("state", {"yes": {"type": "noul"}})
        self.assertEqual(post.call_args.args[0], "http://localhost:8080/v1/systemone")
        self.assertNotIn("Authorization", post.call_args.kwargs["headers"])
        self.assertEqual(post.call_args.kwargs["json"]["state"], "state")
        self.assertNotIn("max_context_tokens", post.call_args.kwargs["json"])

    def test_malformed_json_and_invalid_schema_raise_decisions_error(self) -> None:
        client: DecisionsClient = DecisionsClient("https://example.test", "m")
        question: dict[str, dict[str, object]] = {"yes": {"type": "noul"}}
        for payload in (
            ValueError("bad json"),
            {"model": "m", "answers": {}, "usage": {}},
        ):
            with self.subTest(payload=payload):
                response: MagicMock = self.response({})
                if isinstance(payload, Exception):
                    response.json.side_effect = payload
                else:
                    response.json.return_value = payload
                with (
                    patch(
                        "rsstag.decisions.client.requests.post", return_value=response
                    ),
                    self.assertRaises(DecisionsError),
                ):
                    client.call("state", question)

    def test_http_status_and_transport_failures_raise_decisions_error(self) -> None:
        client: DecisionsClient = DecisionsClient("https://example.test", "m")
        question: dict[str, dict[str, object]] = {"yes": {"type": "noul"}}
        with (
            patch(
                "rsstag.decisions.client.requests.post",
                return_value=self.response({}, 503),
            ),
            self.assertRaisesRegex(DecisionsError, "HTTP 503"),
        ):
            client.call("state", question)
        with (
            patch(
                "rsstag.decisions.client.requests.post", side_effect=requests.Timeout()
            ),
            self.assertRaisesRegex(DecisionsError, "Could not reach"),
        ):
            client.call("state", question)

    def test_mismatched_answer_names_and_types_raise(self) -> None:
        client: DecisionsClient = DecisionsClient("https://example.test", "m")
        question: dict[str, dict[str, object]] = {"yes": {"type": "noul"}}
        templates: list[dict[str, object]] = [
            {"no": {"type": "noul", "noul": 1}},
            {
                "yes": {
                    "type": "choice",
                    "choice": "a",
                    "confidence": 1,
                    "probabilities": {"a": 1},
                }
            },
        ]
        for answers in templates:
            payload: dict[str, object] = {
                "model": "m",
                "answers": answers,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
            with (
                self.subTest(answers=answers),
                patch(
                    "rsstag.decisions.client.requests.post",
                    return_value=self.response(payload),
                ),
                self.assertRaises(DecisionsError),
            ):
                client.call("state", question)

    def test_invalid_probability_and_explicit_assets_header(self) -> None:
        client: DecisionsClient = DecisionsClient("https://example.test", "m")
        payload: dict[str, object] = {
            "model": "m",
            "answers": {"yes": {"type": "noul", "noul": 1.1}},
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
        with patch("rsstag.decisions.client.requests.post") as post:
            post.return_value = self.response(payload)
            with self.assertRaises(DecisionsError):
                client.call(
                    "state", {"yes": {"type": "noul"}}, assets={"img": {"url": "x"}}
                )
        self.assertEqual(
            post.call_args.kwargs["headers"]["TypeSafe-Danger-Zone-Images"], "true"
        )


class TestDecisionsClientFactory(unittest.TestCase):
    def test_context_budget_defaults_and_provider_override(self) -> None:
        config: dict[str, Any] = {
            "decisions": {"provider": "llamacpp", "max_context_tokens": "8192"},
            "jev": {"token": "token", "max_context_tokens": "32768"},
            "llamacpp_decisions": {"host": "http://localhost:8080"},
        }
        self.assertEqual(create_decisions_client(config).max_context_tokens, 8192)
        self.assertEqual(create_decisions_client(config, "jev").max_context_tokens, 32768)
        config["jev"]["max_context_tokens"] = "0"
        self.assertEqual(create_decisions_client(config, "jev").max_context_tokens, 0)
        self.assertEqual(
            create_decisions_client({"jev": {"token": "token"}}, "jev").max_context_tokens,
            0,
        )

    def test_context_budget_from_config_parser(self) -> None:
        config: ConfigParser = ConfigParser()
        config.read_string(
            "[decisions]\nprovider=llamacpp\nmax_context_tokens=8192\n"
            "[llamacpp_decisions]\nhost=http://localhost:8080\n"
            "[jev]\ntoken=token\nmax_context_tokens=16384\n"
        )
        settings: dict[str, dict[str, str]] = {
            section: dict(config[section]) for section in config.sections()
        }
        self.assertEqual(create_decisions_client(settings).max_context_tokens, 8192)
        self.assertEqual(create_decisions_client(settings, "jev").max_context_tokens, 16384)

    def test_invalid_context_budgets_raise(self) -> None:
        invalid: object
        for invalid in (-1, "-1", "invalid", "1.5", 1.5, True, None):
            with self.subTest(limit=invalid):
                with self.assertRaisesRegex(ValueError, "max_context_tokens"):
                    create_decisions_client(
                        {
                            "decisions": {"provider": "jev", "max_context_tokens": invalid},
                            "jev": {"token": "token"},
                        }
                    )

    def test_user_preference_and_provider_precedence(self) -> None:
        config: dict[str, object] = {
            "decisions": {"provider": "jev"},
            "jev": {"token": "token"},
            "llamacpp_decisions": {"host": "http://localhost:8080"},
        }
        self.assertIsInstance(
            create_decisions_client(
                config, user_settings={"realtime_decisions": "llamacpp"}
            ),
            LLamaCPPDecisions,
        )
        self.assertIsInstance(
            create_decisions_client(
                config, "jev", user_settings={"realtime_decisions": "llamacpp"}
            ),
            Jev,
        )
        preferences: dict[str, str]
        for preferences in ({}, {"realtime_decisions": ""}):
            with self.subTest(preferences=preferences):
                self.assertIsInstance(
                    create_decisions_client(config, user_settings=preferences), Jev
                )
        with self.assertRaisesRegex(ValueError, "Unknown decisions provider"):
            create_decisions_client(
                config, user_settings={"realtime_decisions": "openai"}
            )

    def test_worker_and_realtime_choices_are_independent(self) -> None:
        config: dict[str, object] = {
            "decisions": {"provider": "llamacpp"},
            "jev": {"token": "token"},
            "llamacpp_decisions": {"host": "http://localhost:8080"},
        }
        preferences: dict[str, str] = {
            "worker_decisions": "jev",
            "realtime_decisions": "llamacpp",
        }
        self.assertIsInstance(
            create_decisions_client(config, user_settings=preferences), LLamaCPPDecisions
        )
        self.assertIsInstance(
            create_decisions_client(
                config, user_settings=preferences, provider_key="worker_decisions"
            ),
            Jev,
        )
        self.assertIsInstance(
            create_decisions_client(
                config,
                "llamacpp",
                user_settings=preferences,
                provider_key="worker_decisions",
            ),
            LLamaCPPDecisions,
        )
        preferences["worker_decisions"] = ""
        self.assertIsInstance(
            create_decisions_client(
                config, user_settings=preferences, provider_key="worker_decisions"
            ),
            LLamaCPPDecisions,
        )
        with self.assertRaisesRegex(ValueError, "Unknown decisions provider setting"):
            create_decisions_client(config, provider_key="worker_llm")

    def test_selects_jev_and_local_clients(self) -> None:
        jev: object = create_decisions_client(
            {
                "decisions": {"provider": "jev", "timeout": 9},
                "jev": {"token": "token", "host": "https://jev.test", "model": "j"},
            }
        )
        local: object = create_decisions_client(
            {
                "decisions": {"provider": "llamacpp", "timeout": 3},
                "llamacpp_decisions": {
                    "host": "http://localhost:8080",
                    "model": "local",
                },
            }
        )
        self.assertIsInstance(jev, Jev)
        self.assertIsInstance(local, LLamaCPPDecisions)
        self.assertEqual(jev._timeout, 9)
        self.assertEqual(local._timeout, 3)

    def test_invalid_provider_and_invalid_provider_config_raise(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown decisions provider"):
            create_decisions_client({"decisions": {"provider": "unknown"}})
        with self.assertRaisesRegex(ValueError, "API token"):
            create_decisions_client(
                {"decisions": {"provider": "jev"}, "jev": {"token": " "}}
            )
        with self.assertRaisesRegex(ValueError, "HTTP or HTTPS URL"):
            create_decisions_client(
                {
                    "decisions": {"provider": "llamacpp"},
                    "llamacpp_decisions": {"host": "nope"},
                }
            )


if __name__ == "__main__":
    unittest.main()
