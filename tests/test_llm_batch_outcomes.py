"""Outcome contract of the LLM batch handlers.

The handlers talk to the DB only through ``_LLMBatchStorage`` and a few
helpers, which are mocked here, so no Mongo server is needed.
"""

import time
import unittest
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from rsstag.llm.batch import BatchTaskStatus
from rsstag.workers.llm_worker import (
    BATCH_POLL_INTERVAL_SECONDS,
    _LLMBatchStorage,
    _PostGroupingWorker,
    _TagClassificationWorker,
)
from rsstag.workers.outcome import (
    Completed,
    Continue,
    Deferred,
    PermanentFailure,
    RetryableFailure,
)


def _provider(status: str = "in_progress") -> MagicMock:
    provider: MagicMock = MagicMock()
    provider.name = "openai"
    provider.model = "gpt-test"
    provider.batch_endpoint = "/v1/chat/completions"
    provider.get_batch.return_value = SimpleNamespace(
        status=status, output_file_id="out-1", error_file_id="err-1"
    )
    provider.get_file_content.return_value = ""
    provider.create_batch.return_value = {
        "batch": SimpleNamespace(id="batch-new"),
        "input_file_id": "in-1",
    }
    return provider


def _task(batch: Dict[str, Any], data: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    return {
        "_id": "task-1",
        "type": 0,
        "user": {"sid": "owner", "settings": {}},
        "data": data if data is not None else [],
        "batch": batch,
    }


def _last_persisted(storage: MagicMock) -> Dict[str, Any]:
    return storage.update_task_batch_state.call_args[0][1]


class BatchStorageTestCase(unittest.TestCase):
    def test_update_task_batch_state_does_not_mutate_argument(self) -> None:
        db: MagicMock = MagicMock()
        storage: _LLMBatchStorage = _LLMBatchStorage(db)
        state: Dict[str, Any] = {"status": "submitted"}

        storage.update_task_batch_state("task-1", state)

        self.assertEqual(state, {"status": "submitted"})
        persisted: Dict[str, Any] = db.tasks.update_one.call_args[0][1]["$set"]["batch"]
        self.assertEqual(persisted["status"], "submitted")
        self.assertIn("updated_at", persisted)


class PostGroupingBatchOutcomeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.storage: MagicMock = MagicMock()
        self.llm: MagicMock = MagicMock()
        self.provider: MagicMock = _provider()
        self.llm.get_batch_provider.return_value = self.provider
        self.worker: _PostGroupingWorker = _PostGroupingWorker(
            MagicMock(), {}, self.llm, self.storage, MagicMock()
        )

    def test_missing_provider_is_permanent_failure(self) -> None:
        self.llm.get_batch_provider.return_value = None

        outcome = self.worker.make_post_grouping_batch(_task({}))

        self.assertIsInstance(outcome, PermanentFailure)

    def test_throttled_poll_defers_to_next_poll_without_calling_provider(self) -> None:
        last_check: float = time.time() - 10
        task: Dict[str, Any] = _task({"batch_id": "b-1", "last_check": last_check})

        outcome = self.worker.make_post_grouping_batch(task)

        self.assertEqual(outcome, Deferred(last_check + BATCH_POLL_INTERVAL_SECONDS))
        self.assertFalse(outcome.reset_poll_attempts)
        self.provider.get_batch.assert_not_called()

    def test_running_batch_is_deferred_and_task_batch_not_mutated(self) -> None:
        task: Dict[str, Any] = _task({"batch_id": "b-1", "last_check": 0})
        before: float = time.time()

        outcome = self.worker.make_post_grouping_batch(task)

        self.assertIsInstance(outcome, Deferred)
        self.assertTrue(outcome.reset_poll_attempts)
        self.assertGreaterEqual(outcome.next_run_at, before + BATCH_POLL_INTERVAL_SECONDS)
        self.assertEqual(task["batch"], {"batch_id": "b-1", "last_check": 0})
        self.assertGreaterEqual(_last_persisted(self.storage)["last_check"], before)

    def test_completed_remote_batch_continues_to_raw_processing(self) -> None:
        self.provider.get_batch.return_value.status = "completed"
        self.storage.store_batch_raw_results.return_value = "raw-1"
        task: Dict[str, Any] = _task({"batch_id": "b-1", "last_check": 0})

        outcome = self.worker.make_post_grouping_batch(task)

        self.assertIsInstance(outcome, Continue)
        self.assertTrue(outcome.reset_poll_attempts)
        persisted: Dict[str, Any] = _last_persisted(self.storage)
        self.assertEqual(persisted["status"], BatchTaskStatus.RAW_PENDING.value)
        self.assertEqual(persisted["raw_result_id"], "raw-1")

    def test_failed_remote_batch_with_pending_items_is_retryable(self) -> None:
        self.provider.get_batch.return_value.status = "expired"
        task: Dict[str, Any] = _task(
            {"batch_id": "b-1", "last_check": 0, "pending_item_ids": ["p-2"]}
        )

        outcome = self.worker.make_post_grouping_batch(task)

        self.assertIsInstance(outcome, RetryableFailure)
        self.assertEqual(outcome.attempt_field, "attempts")
        self.assertEqual(_last_persisted(self.storage)["item_ids"], ["p-2"])

    def test_failed_remote_batch_without_pending_items_completes(self) -> None:
        self.provider.get_batch.return_value.status = "failed"
        task: Dict[str, Any] = _task({"batch_id": "b-1", "last_check": 0})

        outcome = self.worker.make_post_grouping_batch(task)

        self.assertIsInstance(outcome, Completed)
        self.assertEqual(
            _last_persisted(self.storage)["status"], BatchTaskStatus.FAILED.value
        )

    def test_provider_exception_is_retryable(self) -> None:
        self.provider.get_batch.side_effect = RuntimeError("api down")
        task: Dict[str, Any] = _task({"batch_id": "b-1", "last_check": 0})

        outcome = self.worker.make_post_grouping_batch(task)

        self.assertIsInstance(outcome, RetryableFailure)
        self.assertEqual(outcome.attempt_field, "poll_attempts")
        self.assertIn("api down", outcome.error)

    def test_submit_defers_until_first_poll(self) -> None:
        posts: List[Dict[str, Any]] = [{"_id": "p-1"}]
        task: Dict[str, Any] = _task({}, data=posts)
        before: float = time.time()
        with patch.object(
            self.worker, "_exclude_posts_with_existing_groupings", side_effect=lambda o, p: p
        ), patch.object(
            self.worker, "_save_cached_documents", side_effect=lambda o, p, m, g: p
        ), patch.object(
            self.worker,
            "_build_post_grouping_batch_subset",
            return_value=([{"custom_id": "c"}], ["p-1"], [], [], []),
        ), patch("rsstag.post_splitter.PostSplitter"), patch(
            "rsstag.post_grouping.RssTagPostGrouping"
        ):
            outcome = self.worker.make_post_grouping_batch(task)

        self.assertIsInstance(outcome, Deferred)
        self.assertFalse(outcome.reset_poll_attempts)
        self.assertGreaterEqual(outcome.next_run_at, before + BATCH_POLL_INTERVAL_SECONDS)
        persisted: Dict[str, Any] = _last_persisted(self.storage)
        self.assertEqual(persisted["status"], BatchTaskStatus.SUBMITTED.value)
        self.assertEqual(persisted["batch_id"], "batch-new")
        self.assertEqual(task["batch"], {})

    def test_missing_raw_results_is_permanent_failure(self) -> None:
        self.storage.load_batch_raw_results.return_value = None
        task: Dict[str, Any] = _task({"raw_result_id": "raw-1", "raw_processed": False})

        outcome = self.worker.make_post_grouping_batch(task)

        self.assertIsInstance(outcome, PermanentFailure)

    def test_raw_processing_with_pending_items_continues(self) -> None:
        self.storage.load_batch_raw_results.return_value = {
            "_id": "raw-1",
            "output": "",
            "error": "",
        }
        task: Dict[str, Any] = _task(
            {
                "raw_result_id": "raw-1",
                "raw_processed": False,
                "pending_item_ids": ["p-9"],
            }
        )
        with patch("rsstag.post_splitter.PostSplitter"), patch(
            "rsstag.post_grouping.RssTagPostGrouping"
        ):
            outcome = self.worker.make_post_grouping_batch(task)

        self.assertIsInstance(outcome, Continue)
        persisted: Dict[str, Any] = _last_persisted(self.storage)
        self.assertEqual(persisted["status"], BatchTaskStatus.NEW.value)
        self.assertEqual(persisted["item_ids"], ["p-9"])

    def test_raw_processing_done_completes_and_persists_done(self) -> None:
        self.storage.load_batch_raw_results.return_value = {
            "_id": "raw-1",
            "output": "",
            "error": "",
        }
        task: Dict[str, Any] = _task({"raw_result_id": "raw-1", "raw_processed": False})
        with patch("rsstag.post_splitter.PostSplitter"), patch(
            "rsstag.post_grouping.RssTagPostGrouping"
        ):
            outcome = self.worker.make_post_grouping_batch(task)

        self.assertIsInstance(outcome, Completed)
        self.assertEqual(
            _last_persisted(self.storage)["status"], BatchTaskStatus.COMPLETED.value
        )
        # The claimed task's in-memory checkpoint is left untouched.
        self.assertEqual(task["batch"]["raw_result_id"], "raw-1")


class TagClassificationBatchOutcomeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.storage: MagicMock = MagicMock()
        self.llm: MagicMock = MagicMock()
        self.provider: MagicMock = _provider()
        self.llm.get_batch_provider.return_value = self.provider
        self.worker: _TagClassificationWorker = _TagClassificationWorker(
            MagicMock(), self.llm, self.storage, MagicMock()
        )

    def test_missing_provider_is_permanent_failure(self) -> None:
        self.llm.get_batch_provider.return_value = None

        outcome = self.worker.make_tags_classification_batch(_task({}))

        self.assertIsInstance(outcome, PermanentFailure)

    def test_throttled_poll_defers(self) -> None:
        last_check: float = time.time() - 5
        task: Dict[str, Any] = _task({"batch_id": "b-1", "last_check": last_check})

        outcome: Any = self.worker.make_tags_classification_batch(task)

        self.assertEqual(outcome, Deferred(last_check + BATCH_POLL_INTERVAL_SECONDS))
        self.assertFalse(outcome.reset_poll_attempts)
        self.provider.get_batch.assert_not_called()

    def test_running_batch_is_deferred(self) -> None:
        task: Dict[str, Any] = _task({"batch_id": "b-1", "last_check": 0})

        outcome = self.worker.make_tags_classification_batch(task)

        self.assertIsInstance(outcome, Deferred)
        self.assertTrue(outcome.reset_poll_attempts)
        self.assertEqual(task["batch"], {"batch_id": "b-1", "last_check": 0})

    def test_provider_exception_uses_poll_attempt_counter(self) -> None:
        self.provider.get_batch.side_effect = RuntimeError("api down")
        task: Dict[str, Any] = _task({"batch_id": "b-1", "last_check": 0})

        outcome: Any = self.worker.make_tags_classification_batch(task)

        self.assertIsInstance(outcome, RetryableFailure)
        self.assertEqual(outcome.attempt_field, "poll_attempts")

    def test_completed_remote_batch_continues(self) -> None:
        self.provider.get_batch.return_value.status = "completed"
        self.storage.store_batch_raw_results.return_value = "raw-1"
        task: Dict[str, Any] = _task({"batch_id": "b-1", "last_check": 0})

        outcome = self.worker.make_tags_classification_batch(task)

        self.assertIsInstance(outcome, Continue)
        self.assertTrue(outcome.reset_poll_attempts)
        self.assertEqual(
            _last_persisted(self.storage)["status"], BatchTaskStatus.RAW_PENDING.value
        )

    def test_failed_remote_batch_is_retryable_and_clears_batch_id(self) -> None:
        self.provider.get_batch.return_value.status = "cancelled"
        task: Dict[str, Any] = _task(
            {"batch_id": "b-1", "last_check": 0, "item_ids": ["t-1"]}
        )

        outcome = self.worker.make_tags_classification_batch(task)

        self.assertIsInstance(outcome, RetryableFailure)
        self.assertEqual(outcome.attempt_field, "attempts")
        persisted: Dict[str, Any] = _last_persisted(self.storage)
        self.assertIsNone(persisted["batch_id"])
        self.assertEqual(persisted["item_ids"], ["t-1"])
        self.assertEqual(persisted["status"], BatchTaskStatus.FAILED.value)

    def test_submit_defers_until_first_poll(self) -> None:
        task: Dict[str, Any] = _task({}, data=[{"_id": "t-1", "tag": "x"}])
        with patch.object(
            self.worker,
            "_build_tag_classification_prompts",
            return_value=[{"pid": "p-1", "prompt": "classify"}],
        ):
            outcome = self.worker.make_tags_classification_batch(task)

        self.assertIsInstance(outcome, Deferred)
        self.assertFalse(outcome.reset_poll_attempts)
        persisted: Dict[str, Any] = _last_persisted(self.storage)
        self.assertEqual(persisted["status"], BatchTaskStatus.SUBMITTED.value)
        self.assertEqual(persisted["item_ids"], ["t-1"])

    def test_no_tags_completes(self) -> None:
        outcome = self.worker.make_tags_classification_batch(_task({}))

        self.assertIsInstance(outcome, Completed)

    def test_raw_processing_done_completes(self) -> None:
        self.storage.load_batch_raw_results.return_value = {
            "_id": "raw-1",
            "output": "",
            "error": "",
        }
        task: Dict[str, Any] = _task(
            {"raw_result_id": "raw-1", "raw_processed": False},
            data=[{"_id": "t-1", "tag": "x"}],
        )
        with patch("rsstag.workers.llm_worker.RssTagTags"):
            outcome = self.worker.make_tags_classification_batch(task)

        self.assertIsInstance(outcome, Completed)
        self.assertEqual(
            _last_persisted(self.storage)["status"], BatchTaskStatus.COMPLETED.value
        )

    def test_missing_raw_results_is_permanent_failure(self) -> None:
        self.storage.load_batch_raw_results.return_value = None
        task: Dict[str, Any] = _task({"raw_result_id": "raw-1", "raw_processed": False})

        outcome = self.worker.make_tags_classification_batch(task)

        self.assertIsInstance(outcome, PermanentFailure)


if __name__ == "__main__":
    unittest.main()
