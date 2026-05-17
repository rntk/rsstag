"""Tests for PostGroupingPlugin, TagClassificationPlugin, and uncovered edge cases
in rsstag/workers/external_worker.py.

Existing test_worker_external_loop.py covers ExternalWorkerTokenAPI and
ExternalWorkerRunner at a high level with mocks. This file adds direct unit
tests for the plugin classes and fills in the uncovered branches.
"""

import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from rsstag.tasks import TASK_POST_GROUPING, TASK_TAG_CLASSIFICATION
from rsstag.workers.external_worker import (
    ExternalWorkerRegistry,
    ExternalWorkerTokenAPI,
    ExternalWorkerRunner,
    PluginResult,
    PostGroupingPlugin,
    TagClassificationPlugin,
)


class TestPostGroupingPlugin(unittest.TestCase):
    """Direct unit tests for PostGroupingPlugin.process()."""

    def test_task_type_and_item_id_field(self) -> None:
        """Plugin declares correct task_type and item_id_field."""
        self.assertEqual(PostGroupingPlugin.task_type, TASK_POST_GROUPING)
        self.assertEqual(PostGroupingPlugin.item_id_field, "post_id")

    @patch("rsstag.workers.external_worker.PostSplitter")
    def test_empty_content_returns_error(self, mock_splitter_cls: MagicMock) -> None:
        """Plugin returns error when content is empty."""
        mock_llm_router = MagicMock()
        plugin = PostGroupingPlugin(llm_router=mock_llm_router)
        task: Dict[str, Any] = {"item": {"title": "T", "content": ""}}

        result = plugin.process(task)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Empty content")

    @patch("rsstag.workers.external_worker.PostSplitter")
    def test_whitespace_only_content_returns_error(self, mock_splitter_cls: MagicMock) -> None:
        """Plugin returns error when content is whitespace only."""
        mock_llm_router = MagicMock()
        plugin = PostGroupingPlugin(llm_router=mock_llm_router)
        task: Dict[str, Any] = {"item": {"title": "T", "content": "   \n\t  "}}

        result = plugin.process(task)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Empty content")

    def test_no_llm_handler_returns_error(self) -> None:
        """Plugin returns error when LLM router has no handler."""
        mock_llm_router = MagicMock()
        mock_llm_router.get_handler.return_value = None
        plugin = PostGroupingPlugin(llm_router=mock_llm_router)
        task: Dict[str, Any] = {"item": {"title": "T", "content": "some content"}}

        result = plugin.process(task)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "No LLM handler")

    @patch("rsstag.workers.external_worker.PostSplitter")
    def test_successful_grouping(self, mock_splitter_cls: MagicMock) -> None:
        """Plugin returns success when grouping succeeds."""
        mock_llm_router = MagicMock()
        mock_handler = MagicMock()
        mock_llm_router.get_handler.return_value = mock_handler

        mock_splitter = MagicMock()
        mock_splitter_cls.return_value = mock_splitter
        mock_splitter.generate_grouped_data.return_value = {
            "sentences": [{"number": 1, "text": "s1"}],
            "groups": {"Main": [1]},
        }

        plugin = PostGroupingPlugin(llm_router=mock_llm_router)
        task: Dict[str, Any] = {"item": {"title": "Title", "content": "<p>Body</p>"}}

        result = plugin.process(task)

        self.assertTrue(result.success)
        self.assertEqual(result.error, "")
        self.assertEqual(result.result["groups"], {"Main": [1]})
        mock_splitter.generate_grouped_data.assert_called_once_with(
            content="<p>Body</p>", title="Title", is_html=True
        )

    @patch("rsstag.workers.external_worker.PostSplitter")
    def test_empty_grouping_result_returns_error(self, mock_splitter_cls: MagicMock) -> None:
        """Plugin returns error when grouping returns empty result."""
        mock_llm_router = MagicMock()
        mock_llm_router.get_handler.return_value = MagicMock()
        mock_splitter = MagicMock()
        mock_splitter_cls.return_value = mock_splitter
        mock_splitter.generate_grouped_data.return_value = None

        plugin = PostGroupingPlugin(llm_router=mock_llm_router)
        task: Dict[str, Any] = {"item": {"title": "T", "content": "content"}}

        result = plugin.process(task)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Post grouping returned empty result")

    @patch("rsstag.workers.external_worker.PostSplitter")
    def test_exception_during_grouping_returns_error(self, mock_splitter_cls: MagicMock) -> None:
        """Plugin catches exceptions and returns error."""
        mock_llm_router = MagicMock()
        mock_llm_router.get_handler.return_value = MagicMock()
        mock_splitter = MagicMock()
        mock_splitter_cls.return_value = mock_splitter
        mock_splitter.generate_grouped_data.side_effect = RuntimeError("splitter crash")

        plugin = PostGroupingPlugin(llm_router=mock_llm_router)
        task: Dict[str, Any] = {"item": {"title": "T", "content": "content"}}

        result = plugin.process(task)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "splitter crash")


class TestTagClassificationPlugin(unittest.TestCase):
    """Direct unit tests for TagClassificationPlugin."""

    def test_task_type_and_item_id_field(self) -> None:
        """Plugin declares correct task_type and item_id_field."""
        self.assertEqual(TagClassificationPlugin.task_type, TASK_TAG_CLASSIFICATION)
        self.assertEqual(TagClassificationPlugin.item_id_field, "tag_id")

    def test_build_prompt(self) -> None:
        """_build_prompt produces correctly formatted prompt."""
        prompt = TagClassificationPlugin._build_prompt("python", "snippet text")
        self.assertIn('"python"', prompt)
        self.assertIn("snippet text", prompt)
        self.assertIn("<snippet>", prompt)
        self.assertIn("</snippet>", prompt)

    def test_normalize_category(self) -> None:
        """_normalize_category strips whitespace and punctuation, lowers case."""
        self.assertEqual(TagClassificationPlugin._normalize_category("  Technology  "), "technology")
        self.assertEqual(TagClassificationPlugin._normalize_category("Sport!"), "sport")
        self.assertEqual(TagClassificationPlugin._normalize_category("  POLITICS. "), "politics")
        self.assertEqual(TagClassificationPlugin._normalize_category(" Medicine "), "medicine")
        self.assertEqual(TagClassificationPlugin._normalize_category("Tech, "), "tech")

    def test_process_missing_tag_returns_error(self) -> None:
        """process() returns error when tag is missing or empty."""
        mock_llm_router = MagicMock()
        plugin = TagClassificationPlugin(llm_router=mock_llm_router)

        for task_data in [
            {"item": {}},
            {"item": {"tag": ""}},
            {"item": {"tag": "   "}},
        ]:
            result = plugin.process(task_data)
            self.assertFalse(result.success)
            self.assertEqual(result.error, "Missing tag")

    def test_process_no_llm_handler_returns_error(self) -> None:
        """process() returns error when LLM router has no handler."""
        mock_llm_router = MagicMock()
        mock_llm_router.get_handler.return_value = None
        plugin = TagClassificationPlugin(llm_router=mock_llm_router)
        task: Dict[str, Any] = {"item": {"tag": "python", "snippets": []}}

        result = plugin.process(task)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "No LLM handler")

    @patch.object(TagClassificationPlugin, "_classify")
    def test_process_success(self, mock_classify: MagicMock) -> None:
        """process() returns success when classification succeeds."""
        mock_llm_router = MagicMock()
        mock_llm_router.get_handler.return_value = MagicMock()
        mock_classify.return_value = {
            "classifications": [
                {"category": "technology", "count": 3, "pids": [1, 2, 3]}
            ]
        }

        plugin = TagClassificationPlugin(llm_router=mock_llm_router)
        task: Dict[str, Any] = {
            "item": {
                "tag": "python",
                "snippets": [{"snippet": "some context", "pid": 1}],
            }
        }

        result = plugin.process(task)

        self.assertTrue(result.success)
        self.assertEqual(result.error, "")
        self.assertEqual(len(result.result["classifications"]), 1)

    @patch.object(TagClassificationPlugin, "_classify")
    def test_process_exception_returns_error(self, mock_classify: MagicMock) -> None:
        """process() catches exceptions from _classify."""
        mock_llm_router = MagicMock()
        mock_llm_router.get_handler.return_value = MagicMock()
        mock_classify.side_effect = ValueError("classification failed")

        plugin = TagClassificationPlugin(llm_router=mock_llm_router)
        task: Dict[str, Any] = {"item": {"tag": "python", "snippets": []}}

        result = plugin.process(task)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "classification failed")

    def test_classify_empty_snippets_returns_empty(self) -> None:
        """_classify with no snippets returns empty classifications."""
        mock_llm_router = MagicMock()
        plugin = TagClassificationPlugin(llm_router=mock_llm_router)
        result = plugin._classify(tag="python", snippets=[])
        self.assertEqual(result, {"classifications": []})

    def test_classify_skips_empty_snippets(self) -> None:
        """_classify skips snippets with empty/None text.

        Note: whitespace-only strings are truthy after str() conversion,
        so "  " snippets pass through to the LLM call. Only "" and None
        are filtered out by `if not snippet_text`.
        """
        mock_llm_router = MagicMock()
        plugin = TagClassificationPlugin(llm_router=mock_llm_router)
        snippets = [
            {"snippet": "", "pid": 1},
            {"snippet": None, "pid": 2},
        ]
        result = plugin._classify(tag="python", snippets=snippets)
        self.assertEqual(result, {"classifications": []})

    def test_classify_aggregates_by_category(self) -> None:
        """_classify aggregates counts and pids per category."""
        mock_llm_router = MagicMock()
        # Two calls return the same category
        mock_llm_router.call.side_effect = ["technology", "technology"]

        plugin = TagClassificationPlugin(llm_router=mock_llm_router)
        snippets = [
            {"snippet": "Python is a programming language", "pid": 10},
            {"snippet": "Python 3.12 release notes", "pid": 20},
        ]

        result = plugin._classify(tag="python", snippets=snippets)

        self.assertEqual(len(result["classifications"]), 1)
        cat = result["classifications"][0]
        self.assertEqual(cat["category"], "technology")
        self.assertEqual(cat["count"], 2)
        self.assertEqual(set(cat["pids"]), {10, 20})

    def test_classify_aggregates_without_pids(self) -> None:
        """_classify aggregates counts when snippets have no pid field."""
        mock_llm_router = MagicMock()
        mock_llm_router.call.side_effect = ["technology", "technology"]

        plugin = TagClassificationPlugin(llm_router=mock_llm_router)
        snippets = [
            {"snippet": "Python is a programming language"},
            {"snippet": "Python 3.12 release notes"},
        ]

        result = plugin._classify(tag="python", snippets=snippets)

        self.assertEqual(len(result["classifications"]), 1)
        cat = result["classifications"][0]
        self.assertEqual(cat["category"], "technology")
        self.assertEqual(cat["count"], 2)
        self.assertEqual(cat["pids"], [])

    def test_classify_sorts_by_count_descending(self) -> None:
        """_classify sorts classifications by count descending, then category."""
        mock_llm_router = MagicMock()
        mock_llm_router.call.side_effect = ["sport", "technology", "sport"]

        plugin = TagClassificationPlugin(llm_router=mock_llm_router)
        snippets = [
            {"snippet": "football game", "pid": 1},
            {"snippet": "AI news", "pid": 2},
            {"snippet": "basketball scores", "pid": 3},
        ]

        result = plugin._classify(tag="tag", snippets=snippets)

        cats = result["classifications"]
        self.assertEqual(cats[0]["category"], "sport")
        self.assertEqual(cats[0]["count"], 2)
        self.assertEqual(cats[1]["category"], "technology")
        self.assertEqual(cats[1]["count"], 1)

    def test_classify_sorts_ties_by_category_name(self) -> None:
        """_classify breaks ties by sorting category name alphabetically."""
        mock_llm_router = MagicMock()
        mock_llm_router.call.side_effect = ["zebra", "apple", "banana"]

        plugin = TagClassificationPlugin(llm_router=mock_llm_router)
        snippets = [
            {"snippet": "z text", "pid": 1},
            {"snippet": "a text", "pid": 2},
            {"snippet": "b text", "pid": 3},
        ]

        result = plugin._classify(tag="tag", snippets=snippets)

        cats = result["classifications"]
        # All have count=1, so sorted alphabetically by category name
        self.assertEqual(cats[0]["category"], "apple")
        self.assertEqual(cats[1]["category"], "banana")
        self.assertEqual(cats[2]["category"], "zebra")

    def test_classify_skips_empty_category(self) -> None:
        """_classify skips categories that normalize to empty string."""
        mock_llm_router = MagicMock()
        mock_llm_router.call.return_value = "   "  # normalizes to empty

        plugin = TagClassificationPlugin(llm_router=mock_llm_router)
        snippets = [{"snippet": "text", "pid": 1}]

        result = plugin._classify(tag="tag", snippets=snippets)

        self.assertEqual(result, {"classifications": []})

    def test_classify_skips_long_category(self) -> None:
        """_classify skips categories >= 100 chars."""
        mock_llm_router = MagicMock()
        mock_llm_router.call.return_value = "a" * 100

        plugin = TagClassificationPlugin(llm_router=mock_llm_router)
        snippets = [{"snippet": "text", "pid": 1}]

        result = plugin._classify(tag="tag", snippets=snippets)

        self.assertEqual(result, {"classifications": []})

    def test_classify_handles_llm_exception_gracefully(self) -> None:
        """_classify continues when individual LLM calls fail."""
        mock_llm_router = MagicMock()
        # First call fails, second succeeds
        mock_llm_router.call.side_effect = [RuntimeError("timeout"), "technology"]

        plugin = TagClassificationPlugin(llm_router=mock_llm_router)
        snippets = [
            {"snippet": "failed text", "pid": 1},
            {"snippet": "AI news", "pid": 2},
        ]

        result = plugin._classify(tag="tag", snippets=snippets)

        self.assertEqual(len(result["classifications"]), 1)
        self.assertEqual(result["classifications"][0]["count"], 1)


class TestExternalWorkerTokenAPIEdgeCases(unittest.TestCase):
    """Edge cases in ExternalWorkerTokenAPI not covered by existing tests."""

    def test_submit_result_with_empty_response_body(self) -> None:
        """submit_result returns False when response is 200 with empty body.

        With an empty body, `body` stays `{}`, so `body.get("success")` is
        falsy and the submission is treated as rejected.
        """
        mock_session: MagicMock = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.content = b""

        with patch("rsstag.workers.external_worker.requests.Session", return_value=mock_session):
            api = ExternalWorkerTokenAPI("http://worker.test", "secret", 5.0)
            submitted = api.submit_result(
                task_type=TASK_POST_GROUPING,
                item_id="1",
                success=True,
                result={"ok": True},
            )

        self.assertFalse(submitted)

    def test_submit_result_rejected_with_200_status(self) -> None:
        """submit_result returns False when server returns 200 with success=false."""
        mock_session: MagicMock = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.content = b'{"success": false}'
        mock_session.post.return_value.json.return_value = {"success": False}

        with patch("rsstag.workers.external_worker.requests.Session", return_value=mock_session):
            api = ExternalWorkerTokenAPI("http://worker.test", "secret", 5.0)
            submitted = api.submit_result(
                task_type=TASK_POST_GROUPING,
                item_id="1",
                success=True,
            )

        self.assertFalse(submitted)

    def test_submit_result_network_error(self) -> None:
        """submit_result returns False on network exception."""
        mock_session: MagicMock = MagicMock()
        mock_session.post.side_effect = ConnectionError("timeout")

        with patch("rsstag.workers.external_worker.requests.Session", return_value=mock_session):
            api = ExternalWorkerTokenAPI("http://worker.test", "secret", 5.0)
            submitted = api.submit_result(
                task_type=TASK_POST_GROUPING,
                item_id="1",
                success=True,
            )

        self.assertFalse(submitted)

    def test_claim_task_rejected_with_success_false(self) -> None:
        """claim_task returns None when server returns success=false."""
        mock_session: MagicMock = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.json.return_value = {"success": False, "error": "rate limited"}

        with patch("rsstag.workers.external_worker.requests.Session", return_value=mock_session):
            api = ExternalWorkerTokenAPI("http://worker.test", "secret", 5.0)
            task = api.claim_task()

        self.assertIsNone(task)

    def test_claim_task_with_non_dict_task(self) -> None:
        """claim_task returns None when task is not a dict."""
        mock_session: MagicMock = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.json.return_value = {
            "success": True,
            "task": "not-a-dict",
        }

        with patch("rsstag.workers.external_worker.requests.Session", return_value=mock_session):
            api = ExternalWorkerTokenAPI("http://worker.test", "secret", 5.0)
            task = api.claim_task()

        self.assertIsNone(task)


class TestExternalWorkerRunnerEdgeCases(unittest.TestCase):
    """Edge cases in ExternalWorkerRunner not covered by existing tests."""

    def _build_runner(self) -> ExternalWorkerRunner:
        config: Dict[str, Any] = {
            "llamacpp": {"host": "http://127.0.0.1:8080"},
            "openai": {"token": ""},
            "anthropic": {"token": ""},
            "groqcom": {"host": "https://api.groq.com", "token": ""},
            "cerebras": {"token": "", "model": "gpt-oss-120b"},
            "nebius": {"token": ""},
        }
        with patch("rsstag.workers.external_worker.LLMRouter") as llm_router_cls:
            llm_router_cls.return_value = MagicMock()
            return ExternalWorkerRunner(
                config=config,
                api_base_url="http://worker.test",
                token="secret",
                poll_interval_seconds=0.1,
                request_timeout_seconds=5.0,
            )

    def test_process_single_task_missing_item_id(self) -> None:
        """_process_single_task returns early when item_id is empty."""
        runner = self._build_runner()
        runner._api = MagicMock()
        plugin: MagicMock = MagicMock()
        plugin.item_id_field = "post_id"
        runner._registry.get = MagicMock(return_value=plugin)

        task: Dict[str, Any] = {"task_type": 1, "item": {}}
        runner._process_single_task(task)

        runner._api.submit_result.assert_not_called()

    def test_process_single_task_unsupported_type_no_item_id(self) -> None:
        """_process_single_task skips submit when unsupported task has no item_id."""
        runner = self._build_runner()
        runner._api = MagicMock()
        runner._registry.get = MagicMock(return_value=None)

        task: Dict[str, Any] = {"task_type": 999, "item": {}}
        runner._process_single_task(task)

        runner._api.submit_result.assert_not_called()

    def test_process_single_task_submits_failure(self) -> None:
        """_process_single_task submits failure when plugin returns error."""
        runner = self._build_runner()
        runner._api = MagicMock()
        plugin: MagicMock = MagicMock()
        plugin.item_id_field = "post_id"
        plugin.process.return_value = PluginResult(
            success=False, result={}, error="plugin error"
        )
        runner._registry.get = MagicMock(return_value=plugin)
        runner._api.submit_result.return_value = True

        task: Dict[str, Any] = {
            "task_type": TASK_POST_GROUPING,
            "item": {"post_id": "post-42"},
        }
        runner._process_single_task(task)

        runner._api.submit_result.assert_called_once_with(
            task_type=TASK_POST_GROUPING,
            item_id="post-42",
            success=False,
            result={},
            error="plugin error",
        )

    def test_process_single_task_logs_when_submit_fails(self) -> None:
        """_process_single_task logs warning when submit_result fails."""
        runner = self._build_runner()
        runner._api = MagicMock()
        plugin: MagicMock = MagicMock()
        plugin.item_id_field = "post_id"
        plugin.process.return_value = PluginResult(success=True, result={"ok": True})
        runner._registry.get = MagicMock(return_value=plugin)
        runner._api.submit_result.return_value = False

        task: Dict[str, Any] = {
            "task_type": TASK_POST_GROUPING,
            "item": {"post_id": "post-42"},
        }
        runner._process_single_task(task)

        runner._api.submit_result.assert_called_once()

    def test_registry_register_and_get(self) -> None:
        """ExternalWorkerRegistry stores and retrieves plugins."""
        registry = ExternalWorkerRegistry()
        plugin: MagicMock = MagicMock()
        plugin.task_type = 42

        registry.register(plugin)
        self.assertEqual(registry.get(42), plugin)
        self.assertIsNone(registry.get(99))

    def test_registry_plugins_property(self) -> None:
        """ExternalWorkerRegistry.plugins returns all registered plugins."""
        registry = ExternalWorkerRegistry()
        p1: MagicMock = MagicMock()
        p1.task_type = 1
        p2: MagicMock = MagicMock()
        p2.task_type = 2
        registry.register(p1)
        registry.register(p2)
        self.assertEqual(len(registry.plugins), 2)
        self.assertIn(1, registry.plugins)
        self.assertIn(2, registry.plugins)

    def test_runner_registers_default_plugins(self) -> None:
        """ExternalWorkerRunner registers PostGroupingPlugin and TagClassificationPlugin."""
        runner = self._build_runner()
        self.assertIsNotNone(runner._registry.get(TASK_POST_GROUPING))
        self.assertIsNotNone(runner._registry.get(TASK_TAG_CLASSIFICATION))

    def test_runner_poll_interval_minimum(self) -> None:
        """ExternalWorkerRunner enforces minimum poll interval of 0.1s."""
        config: Dict[str, Any] = {
            "llamacpp": {"host": "http://127.0.0.1:8080"},
            "openai": {"token": ""},
            "anthropic": {"token": ""},
            "groqcom": {"host": "https://api.groq.com", "token": ""},
            "cerebras": {"token": "", "model": "gpt-oss-120b"},
            "nebius": {"token": ""},
        }
        with patch("rsstag.workers.external_worker.LLMRouter") as llm_router_cls:
            llm_router_cls.return_value = MagicMock()
            runner = ExternalWorkerRunner(
                config=config,
                api_base_url="http://worker.test",
                token="secret",
                poll_interval_seconds=0.0,  # below minimum
            )
        self.assertGreaterEqual(runner._poll_interval_seconds, 0.1)

    def test_runner_trims_base_url(self) -> None:
        """ExternalWorkerRunner trims trailing slash from API base URL."""
        runner = self._build_runner()
        self.assertTrue(runner._api._base_url.endswith("/") is False)

    def test_start_polling_loop_sleeps_and_continues(self) -> None:
        """start(once=False) sleeps when no task is available, exits after processing."""
        runner = self._build_runner()
        runner._api = MagicMock()
        plugin: MagicMock = MagicMock()
        plugin.item_id_field = "post_id"
        plugin.process.return_value = PluginResult(success=True, result={"ok": True})
        runner._registry.get = MagicMock(return_value=plugin)
        runner._api.submit_result.return_value = True

        sleep_count = [0]

        def sleep_side_effect(seconds):
            sleep_count[0] += 1
            if sleep_count[0] >= 2:
                raise SystemExit("stop loop")

        def claim_side_effect():
            # First: no task, second: task, third: no task (triggers sleep #2)
            claim_side_effect.calls += 1
            if claim_side_effect.calls == 2:
                return {"task_type": TASK_POST_GROUPING, "item": {"post_id": "1"}}
            return None
        claim_side_effect.calls = 0

        runner._api.claim_task.side_effect = claim_side_effect

        with patch("rsstag.workers.external_worker.time.sleep", side_effect=sleep_side_effect):
            with self.assertRaises(SystemExit):
                runner.start(once=False)

        self.assertEqual(sleep_count[0], 2)
        self.assertGreaterEqual(claim_side_effect.calls, 3)
        runner._api.submit_result.assert_called_once()

    def test_plugin_result_dataclass(self) -> None:
        """PluginResult dataclass has expected fields."""
        result = PluginResult(success=True, result={"data": 1})
        self.assertTrue(result.success)
        self.assertEqual(result.result, {"data": 1})
        self.assertEqual(result.error, "")

        result_with_error = PluginResult(success=False, result={}, error="boom")
        self.assertFalse(result_with_error.success)
        self.assertEqual(result_with_error.error, "boom")


if __name__ == "__main__":
    unittest.main()
