import inspect
import logging
import unittest
from unittest.mock import MagicMock, patch

from rsstag.llm.base import LLMResponse, ToolDefinition
from rsstag.llm.router import LLMRouter


class TestLLMRouter(unittest.TestCase):
    def _make_router(self, config: dict) -> LLMRouter:
        """Create an LLMRouter with batch providers mocked out."""
        with patch("rsstag.llm.router.OpenAIBatchProvider"), patch(
            "rsstag.llm.router.NebiusBatchProvider"
        ):
            return LLMRouter(config)

    # --- __init__ / _init_handlers / _init_batch_providers ---

    @patch("rsstag.llm.router.OpenAIBatchProvider")
    @patch("rsstag.llm.router.NebiusBatchProvider")
    @patch("rsstag.llm.cerebras.RCerebras")
    @patch("rsstag.llm.groqcom.GroqCom")
    @patch("rsstag.llm.anthropic.Anthropic")
    @patch("rsstag.llm.openai.ROpenAI")
    @patch("rsstag.llm.llamacpp.LLamaCPP")
    def test_init_initializes_handlers_and_batch_providers(
        self,
        mock_llama,
        mock_openai,
        mock_anthropic,
        mock_groq,
        mock_cerebras,
        mock_nebius,
        mock_openai_batch,
    ):
        config = {
            "openai": {"token": "tok", "model": "gpt-4"},
            "anthropic": {"token": "tok"},
        }
        router = LLMRouter(config)
        # present config sections -> handlers built
        self.assertIsNotNone(router._handlers["openai"])
        self.assertIsNotNone(router._handlers["anthropic"])
        # missing config sections -> None
        self.assertIsNone(router._handlers["llamacpp"])
        self.assertIsNone(router._handlers["groqcom"])
        self.assertIsNone(router._handlers["cerebras"])
        # batch provider initialized for openai because token present
        mock_openai_batch.assert_called_once()
        mock_nebius.assert_not_called()

    @patch("rsstag.llm.router.OpenAIBatchProvider")
    @patch("rsstag.llm.router.NebiusBatchProvider")
    @patch("rsstag.llm.cerebras.RCerebras")
    @patch("rsstag.llm.groqcom.GroqCom")
    @patch("rsstag.llm.anthropic.Anthropic")
    @patch("rsstag.llm.openai.ROpenAI")
    @patch("rsstag.llm.llamacpp.LLamaCPP")
    def test_init_batch_providers_nebius(
        self,
        mock_llama,
        mock_openai,
        mock_anthropic,
        mock_groq,
        mock_cerebras,
        mock_nebius,
        mock_openai_batch,
    ):
        config = {"nebius": {"token": "tok", "model": "m"}}
        router = LLMRouter(config)
        mock_nebius.assert_called_once_with(
            "tok",
            "m",
            batch_host=None,
            timeout=300.0,
            max_retries=0,
        )
        mock_openai_batch.assert_not_called()

    @patch("rsstag.llm.router.logging.warning")
    @patch("rsstag.llm.router.OpenAIBatchProvider", side_effect=Exception("boom"))
    @patch("rsstag.llm.router.NebiusBatchProvider")
    @patch("rsstag.llm.cerebras.RCerebras")
    @patch("rsstag.llm.groqcom.GroqCom")
    @patch("rsstag.llm.anthropic.Anthropic")
    @patch("rsstag.llm.openai.ROpenAI")
    @patch("rsstag.llm.llamacpp.LLamaCPP")
    def test_init_batch_providers_logs_warning_on_failure(
        self,
        mock_llama,
        mock_openai,
        mock_anthropic,
        mock_groq,
        mock_cerebras,
        mock_nebius,
        mock_openai_batch,
        mock_warn,
    ):
        config = {
            "llamacpp": {"host": "h"},
            "openai": {"token": "tok"},
            "anthropic": {"token": "t"},
            "groqcom": {"host": "h", "token": "t"},
            "cerebras": {"token": "t"},
        }
        router = LLMRouter(config)
        mock_warn.assert_called_once()
        self.assertIn("OpenAI batch provider", mock_warn.call_args[0][0])

    # --- _safe_build ---

    def test_safe_build_returns_handler_on_success(self):
        router = self._make_router({})
        expected = MagicMock()
        with patch.object(router, "_build_handler", return_value=expected):
            result = router._safe_build("openai", None)
        self.assertIs(result, expected)

    @patch("rsstag.llm.router.logging.warning")
    def test_safe_build_returns_none_and_logs_warning_on_failure(self, mock_warn):
        router = self._make_router({})
        before = mock_warn.call_count
        with patch.object(router, "_build_handler", side_effect=RuntimeError("fail")):
            result = router._safe_build("openai", None)
        self.assertIsNone(result)
        self.assertEqual(mock_warn.call_count, before + 1)

    # --- _build_handler ---

    @patch("rsstag.llm.cerebras.RCerebras")
    @patch("rsstag.llm.groqcom.GroqCom")
    @patch("rsstag.llm.anthropic.Anthropic")
    @patch("rsstag.llm.openai.ROpenAI")
    @patch("rsstag.llm.llamacpp.LLamaCPP")
    @patch("rsstag.llm.router.NebiusBatchProvider")
    @patch("rsstag.llm.router.OpenAIBatchProvider")
    def test_build_handler_returns_correct_class_for_each_name(
        self,
        mock_openai_batch,
        mock_nebius,
        mock_llama,
        mock_openai,
        mock_anthropic,
        mock_groq,
        mock_cerebras,
    ):
        config = {
            "llamacpp": {"host": "http://localhost:8080"},
            "openai": {"token": "tok", "model": "gpt-4"},
            "anthropic": {"token": "tok"},
            "groqcom": {"host": "https://api.groq.com", "token": "tok"},
            "cerebras": {"token": "tok", "model": "llama3.1-8b"},
        }
        router = LLMRouter(config)
        # reset mocks because __init__ already built handlers
        mock_llama.reset_mock()
        mock_openai.reset_mock()
        mock_anthropic.reset_mock()
        mock_groq.reset_mock()
        mock_cerebras.reset_mock()

        router._build_handler("llamacpp", None)
        mock_llama.assert_called_once_with(
            "http://localhost:8080",
            timeout=300.0,
        )

        router._build_handler("openai", None)
        mock_openai.assert_called_once_with(
            "tok",
            model="gpt-4",
            timeout=300.0,
            max_retries=0,
        )

        router._build_handler("anthropic", None)
        mock_anthropic.assert_called_once_with(
            "tok",
            timeout=300.0,
            max_retries=0,
        )

        router._build_handler("groqcom", None)
        mock_groq.assert_called_once_with(
            host="https://api.groq.com",
            token="tok",
            timeout=300.0,
        )

        router._build_handler("cerebras", None)
        mock_cerebras.assert_called_once_with(
            token="tok",
            model="llama3.1-8b",
            timeout=300.0,
            max_retries=0,
        )

    @patch("rsstag.llm.cerebras.RCerebras")
    @patch("rsstag.llm.groqcom.GroqCom")
    @patch("rsstag.llm.anthropic.Anthropic")
    @patch("rsstag.llm.openai.ROpenAI")
    @patch("rsstag.llm.llamacpp.LLamaCPP")
    @patch("rsstag.llm.router.NebiusBatchProvider")
    @patch("rsstag.llm.router.OpenAIBatchProvider")
    def test_build_handler_model_override(
        self,
        mock_openai_batch,
        mock_nebius,
        mock_llama,
        mock_openai,
        mock_anthropic,
        mock_groq,
        mock_cerebras,
    ):
        config = {
            "llamacpp": {"host": "h"},
            "openai": {"token": "t", "model": "cfg-model"},
            "anthropic": {"token": "t"},
            "groqcom": {"host": "h", "token": "t"},
            "cerebras": {"token": "t", "model": "cfg-model"},
        }
        router = LLMRouter(config)
        mock_llama.reset_mock()
        mock_openai.reset_mock()
        mock_anthropic.reset_mock()
        mock_groq.reset_mock()
        mock_cerebras.reset_mock()

        router._build_handler("llamacpp", "m")
        mock_llama.assert_called_once_with("h", model="m", timeout=300.0)

        router._build_handler("openai", "m")
        mock_openai.assert_called_once_with(
            "t",
            model="m",
            timeout=300.0,
            max_retries=0,
        )

        router._build_handler("anthropic", "m")
        mock_anthropic.assert_called_once_with(
            "t",
            model="m",
            timeout=300.0,
            max_retries=0,
        )

        router._build_handler("groqcom", "m")
        mock_groq.assert_called_once_with(
            host="h",
            token="t",
            model="m",
            timeout=300.0,
        )

        router._build_handler("cerebras", "m")
        mock_cerebras.assert_called_once_with(
            token="t",
            model="m",
            timeout=300.0,
            max_retries=0,
        )

    @patch("rsstag.llm.openai.ROpenAI")
    @patch("rsstag.llm.router.NebiusBatchProvider")
    @patch("rsstag.llm.router.OpenAIBatchProvider")
    def test_build_handler_uses_configured_request_limits(
        self,
        mock_openai_batch: MagicMock,
        mock_nebius: MagicMock,
        mock_openai: MagicMock,
    ) -> None:
        config: dict = {
            "settings": {
                "llm_request_timeout_seconds": "45.5",
                "llm_request_max_retries": "1",
            },
            "openai": {"token": "tok", "model": "gpt-5-mini"},
        }
        router: LLMRouter = LLMRouter(config)

        mock_openai.assert_called_once_with(
            "tok",
            model="gpt-5-mini",
            timeout=45.5,
            max_retries=1,
        )
        mock_openai_batch.assert_called_once_with(
            "tok",
            "gpt-5-mini",
            batch_host=None,
            timeout=45.5,
            max_retries=1,
        )

    def test_invalid_request_limits_fall_back_to_safe_defaults(self) -> None:
        router: LLMRouter = self._make_router(
            {
                "settings": {
                    "llm_request_timeout_seconds": "invalid",
                    "llm_request_max_retries": "invalid",
                }
            }
        )

        self.assertEqual(router._get_request_timeout_seconds(), 300.0)
        self.assertEqual(router._get_request_max_retries(), 0)

    def test_request_retry_limit_is_capped_at_one(self) -> None:
        router: LLMRouter = self._make_router(
            {"settings": {"llm_request_max_retries": "5"}}
        )

        self.assertEqual(router._get_request_max_retries(), 1)

    def test_non_finite_request_timeout_uses_safe_default(self) -> None:
        for raw_timeout in ("nan", "inf", "-inf"):
            with self.subTest(raw_timeout=raw_timeout):
                router: LLMRouter = self._make_router(
                    {"settings": {"llm_request_timeout_seconds": raw_timeout}}
                )

                self.assertEqual(router._get_request_timeout_seconds(), 300.0)

    def test_build_handler_raises_for_unknown_name(self):
        router = self._make_router({})
        with self.assertRaises(ValueError) as ctx:
            router._build_handler("unknown", None)
        self.assertIn("Unknown LLM handler", str(ctx.exception))

    @patch("rsstag.llm.router.logging.warning")
    def test_safe_build_returns_none_for_unknown_name(self, mock_warn):
        router = self._make_router({})
        before = mock_warn.call_count
        result = router._safe_build("unknown", None)
        self.assertIsNone(result)
        self.assertEqual(mock_warn.call_count, before + 1)

    # --- _select_provider / _select_model ---

    def test_select_provider(self):
        router = self._make_router({})
        self.assertEqual(
            router._select_provider(
                {"realtime_llm": "openai"}, "realtime_llm", "llamacpp"
            ),
            "openai",
        )
        self.assertEqual(
            router._select_provider({}, "realtime_llm", "llamacpp"),
            "llamacpp",
        )
        self.assertEqual(
            router._select_provider({"realtime_llm": ""}, "realtime_llm", "llamacpp"),
            "llamacpp",
        )

    def test_select_model(self):
        router = self._make_router({})
        # provider_key_model takes precedence
        self.assertEqual(
            router._select_model(
                {"realtime_llm_model": "gpt-5"}, "realtime_llm", "openai"
            ),
            "gpt-5",
        )
        # falls back to provider_model
        self.assertEqual(
            router._select_model(
                {"openai_model": "gpt-4"}, "realtime_llm", "openai"
            ),
            "gpt-4",
        )
        self.assertIsNone(router._select_model({}, "realtime_llm", "openai"))

    # --- _get_handler / get_handler ---

    def test_get_handler_exact_match_by_model(self):
        router = self._make_router({})
        mock_handler = MagicMock()
        with patch.object(router, "_safe_build", return_value=mock_handler) as mock_safe:
            handler = router._get_handler("openai", "gpt-4")
            self.assertIs(handler, mock_handler)
            mock_safe.assert_called_once_with("openai", "gpt-4")
            # cached on second call
            handler2 = router._get_handler("openai", "gpt-4")
            self.assertIs(handler2, mock_handler)
            self.assertEqual(mock_safe.call_count, 1)

    def test_get_handler_without_model_uses_handlers_cache(self):
        router = self._make_router({})
        mock_handler = MagicMock()
        router._handlers["openai"] = mock_handler
        handler = router._get_handler("openai", None)
        self.assertIs(handler, mock_handler)

    def test_get_handler_unknown_provider_builds_and_caches(self):
        router = self._make_router({})
        mock_handler = MagicMock()
        with patch.object(router, "_safe_build", return_value=mock_handler) as mock_safe:
            handler = router._get_handler("unknown", None)
            self.assertIs(handler, mock_handler)
            mock_safe.assert_called_once_with("unknown", None)
            self.assertIn("unknown", router._handlers)

    def test_get_handler_exact_match_by_model_via_settings(self):
        router = self._make_router({})
        specific = MagicMock()
        with patch.object(router, "_safe_build", return_value=specific) as mock_safe:
            result = router.get_handler(
                {"realtime_llm": "openai", "realtime_llm_model": "gpt-4"},
                provider_key="realtime_llm",
                default="llamacpp",
            )
            self.assertIs(result, specific)
            mock_safe.assert_called_once_with("openai", "gpt-4")

    def test_get_handler_fallback_chain(self):
        router = self._make_router({})
        router._handlers["llamacpp"] = None
        router._handlers["openai"] = None
        fallback = MagicMock()
        router._handlers["anthropic"] = fallback
        result = router.get_handler(
            {"realtime_llm": "openai"},
            provider_key="realtime_llm",
            default="llamacpp",
        )
        self.assertIs(result, fallback)

    def test_get_handler_returns_none_when_nothing_available(self):
        router = self._make_router({})
        for name in list(router._handlers.keys()):
            router._handlers[name] = None
        result = router.get_handler(None)
        self.assertIsNone(result)

    # --- call ---

    def test_call_gets_handler_filters_kwargs_and_invokes_call(self):
        router = self._make_router({})
        handler = MagicMock()
        handler.call.return_value = "result"
        with patch.object(router, "get_handler", return_value=handler):
            with patch.object(
                router, "_filter_call_kwargs", return_value={"temperature": 0.5}
            ) as mock_filter:
                result = router.call(
                    {"realtime_llm": "openai"},
                    ["hello"],
                    temperature=0.5,
                    extra=1,
                )
        self.assertEqual(result, "result")
        mock_filter.assert_called_once_with(
            handler, {"temperature": 0.5, "extra": 1}
        )
        handler.call.assert_called_once_with(["hello"], temperature=0.5)

    @patch("rsstag.llm.router.logging.error")
    def test_call_returns_empty_string_when_no_handler(self, mock_log_error):
        router = self._make_router({})
        for name in list(router._handlers.keys()):
            router._handlers[name] = None
        result = router.call(None, ["hello"])
        self.assertEqual(result, "")
        mock_log_error.assert_called_once()

    # --- call_citation ---

    def test_call_citation_uses_native_call_citation(self):
        router = self._make_router({})
        handler = MagicMock()
        handler.call_citation.return_value = "cited"
        with patch.object(router, "get_handler", return_value=handler):
            result = router.call_citation(None, "prompt", ["doc1", "doc2"])
        self.assertEqual(result, "cited")
        handler.call_citation.assert_called_once_with("prompt", ["doc1", "doc2"])

    def test_call_citation_falls_back_to_concatenating_docs(self):
        router = self._make_router({})
        handler = MagicMock(spec=["call"])
        with patch.object(router, "get_handler", return_value=handler):
            with patch.object(router, "call", return_value="fallback") as mock_call:
                result = router.call_citation(None, "prompt", ["doc1", "doc2"])
        self.assertEqual(result, "fallback")
        expected_prompt = "prompt\n\ndoc1\n\ndoc2"
        mock_call.assert_called_once_with(
            None,
            [expected_prompt],
            provider_key="realtime_llm",
            default="llamacpp",
        )

    def test_call_citation_fallback_without_docs(self):
        router = self._make_router({})
        handler = MagicMock(spec=["call"])
        with patch.object(router, "get_handler", return_value=handler):
            with patch.object(router, "call", return_value="fallback") as mock_call:
                result = router.call_citation(None, "prompt", [])
        self.assertEqual(result, "fallback")
        mock_call.assert_called_once_with(
            None,
            ["prompt"],
            provider_key="realtime_llm",
            default="llamacpp",
        )

    # --- call_with_tools ---

    def test_call_with_tools_returns_llmresponse(self):
        router = self._make_router({})
        expected = LLMResponse(content="tools")
        handler = MagicMock()
        handler.call_with_tools.return_value = expected
        with patch.object(router, "get_handler", return_value=handler):
            with patch.object(
                router, "_filter_call_kwargs", return_value={"top_p": 0.9}
            ) as mock_filter:
                tools = [MagicMock(spec=ToolDefinition)]
                result = router.call_with_tools(
                    None, ["hello"], tools, top_p=0.9, bad=1
                )
        self.assertIs(result, expected)
        mock_filter.assert_called_once_with(
            handler.call_with_tools, {"top_p": 0.9, "bad": 1}
        )
        handler.call_with_tools.assert_called_once_with(
            ["hello"], tools, top_p=0.9
        )

    def test_call_with_tools_falls_back_to_plain_call(self):
        router = self._make_router({})
        handler = MagicMock(spec=["call"])
        with patch.object(router, "get_handler", return_value=handler):
            with patch.object(router, "call", return_value="plain") as mock_call:
                tools = [MagicMock(spec=ToolDefinition)]
                result = router.call_with_tools(None, ["hello"], tools)
        self.assertEqual(result, LLMResponse(content="plain"))
        mock_call.assert_called_once_with(
            None,
            ["hello"],
            provider_key="realtime_llm",
            default="llamacpp",
        )

    @patch("rsstag.llm.router.logging.warning")
    def test_call_with_tools_fallback_logs_warning(self, mock_warn):
        router = self._make_router({})
        before = mock_warn.call_count
        handler = MagicMock(spec=["call"])
        with patch.object(router, "get_handler", return_value=handler):
            with patch.object(router, "call", return_value="plain"):
                router.call_with_tools(None, ["hello"], [])
        self.assertEqual(mock_warn.call_count, before + 1)

    @patch("rsstag.llm.router.logging.error")
    def test_call_with_tools_returns_empty_response_when_no_handler(
        self, mock_log_error
    ):
        router = self._make_router({})
        for name in list(router._handlers.keys()):
            router._handlers[name] = None
        result = router.call_with_tools(None, ["hello"], [])
        self.assertEqual(result, LLMResponse())
        mock_log_error.assert_called_once()

    # --- _filter_call_kwargs ---

    def test_filter_call_kwargs_strips_unsupported_kwargs(self):
        def dummy(a, b):
            pass

        router = self._make_router({})
        result = router._filter_call_kwargs(dummy, {"a": 1, "b": 2, "c": 3})
        self.assertEqual(result, {"a": 1, "b": 2})

    def test_filter_call_kwargs_respects_var_kwargs(self):
        def dummy(a, **kwargs):
            pass

        router = self._make_router({})
        result = router._filter_call_kwargs(dummy, {"a": 1, "b": 2})
        self.assertEqual(result, {"a": 1, "b": 2})

    def test_filter_call_kwargs_for_object_with_call(self):
        class Handler:
            def call(self, x, y):
                pass

        router = self._make_router({})
        result = router._filter_call_kwargs(
            Handler(), {"x": 1, "y": 2, "z": 3}
        )
        self.assertEqual(result, {"x": 1, "y": 2})

    def test_filter_call_kwargs_returns_empty_for_empty_kwargs(self):
        router = self._make_router({})
        self.assertEqual(router._filter_call_kwargs(lambda a: None, {}), {})

    def test_filter_call_kwargs_fallback_on_signature_error(self):
        router = self._make_router({})
        handler = MagicMock()
        with patch.object(inspect, "signature", side_effect=TypeError):
            result = router._filter_call_kwargs(handler, {"a": 1})
        self.assertEqual(result, {"a": 1})

    # --- get_batch_provider ---

    def test_get_batch_provider_exact_match(self):
        router = self._make_router({})
        provider = MagicMock()
        router._batch_providers = {"openai": provider}
        self.assertIs(router.get_batch_provider("openai"), provider)

    def test_get_batch_provider_fallback_chain_openai_then_nebius(self):
        router = self._make_router({})
        nebius = MagicMock()
        router._batch_providers = {"nebius": nebius}
        self.assertIs(router.get_batch_provider(), nebius)
        self.assertIs(router.get_batch_provider("unknown"), nebius)

    def test_get_batch_provider_prefers_openai_over_nebius(self):
        router = self._make_router({})
        openai = MagicMock()
        nebius = MagicMock()
        router._batch_providers = {"openai": openai, "nebius": nebius}
        self.assertIs(router.get_batch_provider(), openai)
        self.assertIs(router.get_batch_provider("openai"), openai)
        self.assertIs(router.get_batch_provider("nebius"), nebius)

    @patch("rsstag.llm.router.logging.error")
    def test_get_batch_provider_returns_none_when_none_available(
        self, mock_log_error
    ):
        router = self._make_router({})
        router._batch_providers = {}
        self.assertIsNone(router.get_batch_provider())
        mock_log_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
