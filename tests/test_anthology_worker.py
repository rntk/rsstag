"""Anthology startup failures must leave a visible, retryable status."""

import builtins
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from rsstag.workers.llm_worker import _AnthologyWorker


class TestAnthologyWorker(unittest.TestCase):
    def setUp(self) -> None:
        self.worker: _AnthologyWorker = _AnthologyWorker(MagicMock(), MagicMock())
        self.task: Dict[str, Any] = {"data": {"_id": "anthology-id"}, "user": {"sid": "owner"}}

    def test_import_failure_marks_anthology_failed(self) -> None:
        original_import: Any = builtins.__import__

        def failing_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "rsstag.anthology.pipeline":
                raise ModuleNotFoundError("No module named 'rsstag.anthology_agent'")
            return original_import(name, *args, **kwargs)

        with patch("rsstag.anthologies.RssTagAnthologies") as store, patch(
            "builtins.__import__", side_effect=failing_import
        ):
            self.assertFalse(self.worker.handle_anthology(self.task))
            store.return_value.update_status.assert_called_once_with(
                "anthology-id", "failed",
                error="Anthology worker error: No module named 'rsstag.anthology_agent'",
            )

    def test_constructor_failure_marks_anthology_failed(self) -> None:
        with patch("rsstag.anthologies.RssTagAnthologies") as store, patch(
            "rsstag.anthology.pipeline.AnthologyPipeline", side_effect=RuntimeError("startup failed")
        ):
            self.assertFalse(self.worker.handle_anthology(self.task))
            store.return_value.update_status.assert_called_once_with(
                "anthology-id", "failed", error="Anthology worker error: startup failed"
            )
