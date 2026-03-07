import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import requests

from rsstag.tasks import TASK_POST_GROUPING, TASK_TAG_CLASSIFICATION
from rsstag.workers.external_worker import (
    ExternalWorkerRunner,
    ExternalWorkerTokenAPI,
    PluginResult,
)


class TestExternalWorkerTokenAPI(unittest.TestCase):
    def test_claim_task_returns_task_payload(self) -> None:
        mock_session: MagicMock = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.json.return_value = {
            "success": True,
            "task": {"task_type": TASK_POST_GROUPING, "item": {"post_id": "1"}},
        }

        with patch("rsstag.workers.external_worker.requests.Session", return_value=mock_session):
            api = ExternalWorkerTokenAPI(
                base_url="http://worker.test",
                token="secret",
                timeout_seconds=5.0,
            )
            task = api.claim_task()

        self.assertEqual(task, {"task_type": TASK_POST_GROUPING, "item": {"post_id": "1"}})

    def test_claim_task_returns_none_for_empty_response(self) -> None:
        mock_session: MagicMock = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.json.return_value = {"success": True, "task": None}

        with patch("rsstag.workers.external_worker.requests.Session", return_value=mock_session):
            api = ExternalWorkerTokenAPI("http://worker.test", "secret", 5.0)

        self.assertIsNone(api.claim_task())

    def test_claim_task_handles_server_error(self) -> None:
        mock_session: MagicMock = MagicMock()
        mock_session.post.return_value.status_code = 500
        mock_session.post.return_value.text = "boom"

        with patch("rsstag.workers.external_worker.requests.Session", return_value=mock_session):
            api = ExternalWorkerTokenAPI("http://worker.test", "secret", 5.0)

        self.assertIsNone(api.claim_task())

    def test_claim_task_handles_network_error(self) -> None:
        mock_session: MagicMock = MagicMock()
        mock_session.post.side_effect = requests.ConnectionError("offline")

        with patch("rsstag.workers.external_worker.requests.Session", return_value=mock_session):
            api = ExternalWorkerTokenAPI("http://worker.test", "secret", 5.0)

        self.assertIsNone(api.claim_task())

    def test_submit_result_posts_success_payload(self) -> None:
        mock_session: MagicMock = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.content = b'{"success": true}'
        mock_session.post.return_value.json.return_value = {"success": True}

        with patch("rsstag.workers.external_worker.requests.Session", return_value=mock_session):
            api = ExternalWorkerTokenAPI("http://worker.test", "secret", 5.0)
            submitted = api.submit_result(
                task_type=TASK_POST_GROUPING,
                item_id="1",
                success=True,
                result={"groups": {}},
            )

        self.assertTrue(submitted)
        _, kwargs = mock_session.post.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(kwargs["json"]["task_type"], TASK_POST_GROUPING)
        self.assertEqual(kwargs["json"]["item_id"], "1")

    def test_submit_result_handles_failure_status(self) -> None:
        mock_session: MagicMock = MagicMock()
        mock_session.post.return_value.status_code = 500
        mock_session.post.return_value.content = b""
        mock_session.post.return_value.text = "bad submit"

        with patch("rsstag.workers.external_worker.requests.Session", return_value=mock_session):
            api = ExternalWorkerTokenAPI("http://worker.test", "secret", 5.0)

        self.assertFalse(
            api.submit_result(
                task_type=TASK_POST_GROUPING,
                item_id="1",
                success=False,
                error="boom",
            )
        )


class TestExternalWorkerRunner(unittest.TestCase):
    def setUp(self) -> None:
        self.config: Dict[str, Any] = {
            "llamacpp": {"host": "http://127.0.0.1:8080"},
            "openai": {"token": ""},
            "anthropic": {"token": ""},
            "groqcom": {"host": "https://api.groq.com", "token": ""},
            "cerebras": {"token": "", "model": "gpt-oss-120b"},
            "nebius": {"token": ""},
        }

    def _build_runner(self) -> ExternalWorkerRunner:
        with patch("rsstag.workers.external_worker.LLMRouter") as llm_router_cls:
            llm_router_cls.return_value = MagicMock()
            return ExternalWorkerRunner(
                config=self.config,
                api_base_url="http://worker.test",
                token="secret",
                poll_interval_seconds=0.1,
                request_timeout_seconds=5.0,
            )

    def test_start_once_exits_cleanly_when_no_task_is_available(self) -> None:
        runner: ExternalWorkerRunner = self._build_runner()
        runner._api = MagicMock()
        runner._api.claim_task.return_value = None

        runner.start(once=True)

        runner._api.claim_task.assert_called_once_with()

    def test_start_once_claims_dispatches_and_submits(self) -> None:
        runner: ExternalWorkerRunner = self._build_runner()
        runner._api = MagicMock()
        plugin: MagicMock = MagicMock()
        plugin.item_id_field = "post_id"
        plugin.process.return_value = PluginResult(success=True, result={"ok": True})
        runner._registry.get = MagicMock(return_value=plugin)
        runner._api.claim_task.return_value = {
            "task_type": TASK_POST_GROUPING,
            "item": {"post_id": "post-1"},
        }
        runner._api.submit_result.return_value = True

        runner.start(once=True)

        plugin.process.assert_called_once()
        runner._api.submit_result.assert_called_once_with(
            task_type=TASK_POST_GROUPING,
            item_id="post-1",
            success=True,
            result={"ok": True},
            error="",
        )

    def test_unknown_task_type_submits_error(self) -> None:
        runner: ExternalWorkerRunner = self._build_runner()
        runner._api = MagicMock()
        runner._registry.get = MagicMock(return_value=None)

        task: Dict[str, Any] = {"task_type": 999, "item": {"post_id": "post-1"}}
        runner._process_single_task(task)

        runner._api.submit_result.assert_called_once_with(
            task_type=999,
            item_id="post-1",
            success=False,
            result={},
            error="Unsupported task type: 999",
        )

    def test_plugin_result_is_submitted_for_tag_task(self) -> None:
        runner: ExternalWorkerRunner = self._build_runner()
        runner._api = MagicMock()
        plugin: MagicMock = MagicMock()
        plugin.item_id_field = "tag_id"
        plugin.process.return_value = PluginResult(
            success=True,
            result={"classifications": [{"category": "technology", "count": 1, "pids": []}]},
        )
        runner._registry.get = MagicMock(return_value=plugin)

        runner._process_single_task(
            {"task_type": TASK_TAG_CLASSIFICATION, "item": {"tag_id": "tag-1"}}
        )

        runner._api.submit_result.assert_called_once()

    def test_plugin_exception_is_caught_by_start_loop(self) -> None:
        runner: ExternalWorkerRunner = self._build_runner()
        runner._api = MagicMock()
        runner._api.claim_task.return_value = {
            "task_type": TASK_POST_GROUPING,
            "item": {"post_id": "post-1"},
        }
        with patch.object(runner, "_process_single_task", side_effect=RuntimeError("boom")):
            runner.start(once=True)

        runner._api.claim_task.assert_called_once_with()
