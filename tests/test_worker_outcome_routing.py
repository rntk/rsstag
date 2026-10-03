"""Dispatcher routing of handler outcomes (no DB: queue facade is mocked)."""

import time
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from rsstag.tasks import TASK_CLUSTERING, TASK_DOWNLOAD, TASK_LETTERS
from rsstag.workers.dispatcher import _apply_outcome, _run_handler
from rsstag.workers.outcome import (
    CONTINUE_DELAY_SECONDS,
    Completed,
    Continue,
    Deferred,
    PermanentFailure,
    RetryableFailure,
    is_failure,
    normalize_outcome,
)
from rsstag.workers.registry import WorkerRegistry


def _task(task_type: int = TASK_LETTERS, **extra: Any) -> Dict[str, Any]:
    return {"_id": "task-1", "type": task_type, "user": {"sid": "sid-1"}, **extra}


class NormalizeOutcomeTestCase(unittest.TestCase):
    def test_true_is_completed(self) -> None:
        self.assertEqual(normalize_outcome(True), Completed())

    def test_false_and_none_are_retryable(self) -> None:
        self.assertIsInstance(normalize_outcome(False), RetryableFailure)
        self.assertIsInstance(normalize_outcome(None), RetryableFailure)
        self.assertEqual(normalize_outcome(False, "boom"), RetryableFailure("boom"))

    def test_outcomes_pass_through(self) -> None:
        for outcome in (
            Completed(),
            Continue(),
            Deferred(5.0),
            RetryableFailure("x"),
            PermanentFailure("y"),
        ):
            self.assertIs(normalize_outcome(outcome), outcome)

    def test_is_failure(self) -> None:
        self.assertTrue(is_failure(False))
        self.assertTrue(is_failure(RetryableFailure("x")))
        self.assertTrue(is_failure(PermanentFailure("x")))
        self.assertFalse(is_failure(True))
        self.assertFalse(is_failure(Deferred(1.0)))
        self.assertFalse(is_failure(Continue()))


class RunHandlerTestCase(unittest.TestCase):
    def test_unknown_task_type_is_retryable_failure(self) -> None:
        outcome = _run_handler(WorkerRegistry(), _task(999999))

        self.assertIsInstance(outcome, RetryableFailure)
        self.assertIn("999999", outcome.error)

    def test_legacy_bool_handlers_are_normalized(self) -> None:
        registry: WorkerRegistry = WorkerRegistry()
        registry.register(TASK_LETTERS, lambda task: True)
        registry.register(TASK_DOWNLOAD, lambda task: False)

        self.assertEqual(_run_handler(registry, _task()), Completed())
        self.assertIsInstance(
            _run_handler(registry, _task(TASK_DOWNLOAD)), RetryableFailure
        )

    def test_outcome_handlers_pass_through(self) -> None:
        registry: WorkerRegistry = WorkerRegistry()
        registry.register(TASK_LETTERS, lambda task: Deferred(42.0))

        self.assertEqual(_run_handler(registry, _task()), Deferred(42.0))


class ApplyOutcomeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tasks: MagicMock = MagicMock()
        self.tasks.finish_task.return_value = True
        self.tasks.defer_task.return_value = True
        self.users: MagicMock = MagicMock()

    def test_completed_runs_finish_path(self) -> None:
        backoff: bool = _apply_outcome(self.tasks, self.users, _task(), Completed())

        self.assertFalse(backoff)
        self.tasks.finish_task.assert_called_once()
        self.tasks.release_failed_task.assert_not_called()
        self.tasks.defer_task.assert_not_called()

    def test_completed_clears_provider_queue_flag(self) -> None:
        task: Dict[str, Any] = _task(TASK_DOWNLOAD, provider="bazqux")

        _apply_outcome(self.tasks, self.users, task, Completed())

        self.users.update_by_sid.assert_called_once_with(
            "sid-1", {"in_queue.bazqux": False}
        )

    def test_completed_clears_clustering_queue_flag(self) -> None:
        _apply_outcome(self.tasks, self.users, _task(TASK_CLUSTERING), Completed())

        self.users.update_by_sid.assert_called_once_with("sid-1", {"in_queue": {}})

    def test_completed_with_failed_finish_releases_as_failure(self) -> None:
        self.tasks.finish_task.return_value = False

        _apply_outcome(self.tasks, self.users, _task(), Completed())

        self.tasks.release_failed_task.assert_called_once()

    def test_continue_defers_shortly_without_failure(self) -> None:
        before: float = time.time()

        backoff: bool = _apply_outcome(self.tasks, self.users, _task(), Continue())

        self.assertFalse(backoff)
        next_run_at: float = self.tasks.defer_task.call_args[0][1]
        self.assertGreaterEqual(next_run_at, before + CONTINUE_DELAY_SECONDS)
        self.assertLess(next_run_at, time.time() + CONTINUE_DELAY_SECONDS + 1)
        self.tasks.defer_task.assert_called_once_with(
            _task(), next_run_at, reset_poll_attempts=False, reason=""
        )
        self.tasks.release_failed_task.assert_not_called()
        self.tasks.finish_task.assert_not_called()

    def test_deferred_defers_to_requested_time(self) -> None:
        task: Dict[str, Any] = _task()

        backoff: bool = _apply_outcome(self.tasks, self.users, task, Deferred(1234.5))

        self.assertFalse(backoff)
        self.tasks.defer_task.assert_called_once_with(
            task, 1234.5, reset_poll_attempts=False, reason=""
        )
        self.tasks.release_failed_task.assert_not_called()
        self.tasks.finish_task.assert_not_called()

    def test_retryable_failure_releases_with_error(self) -> None:
        task: Dict[str, Any] = _task()

        backoff: bool = _apply_outcome(
            self.tasks, self.users, task, RetryableFailure("transient")
        )

        self.assertTrue(backoff)
        self.tasks.release_failed_task.assert_called_once_with(
            task, "transient", attempt_field="attempts"
        )
        self.tasks.dead_letter_task.assert_not_called()

    def test_permanent_failure_dead_letters(self) -> None:
        task: Dict[str, Any] = _task()

        backoff: bool = _apply_outcome(
            self.tasks, self.users, task, PermanentFailure("no provider")
        )

        self.assertTrue(backoff)
        self.tasks.dead_letter_task.assert_called_once_with(task, "no provider")
        self.tasks.release_failed_task.assert_not_called()

    def test_retryable_failure_uses_selected_attempt_counter(self) -> None:
        task: Dict[str, Any] = _task()

        _apply_outcome(
            self.tasks,
            self.users,
            task,
            RetryableFailure("poll failed", attempt_field="poll_attempts"),
        )

        self.tasks.release_failed_task.assert_called_once_with(
            task, "poll failed", attempt_field="poll_attempts"
        )

    def test_healthy_defer_forwards_poll_attempt_reset(self) -> None:
        task: Dict[str, Any] = _task()

        _apply_outcome(
            self.tasks, self.users, task, Deferred(1234.5, reset_poll_attempts=True)
        )

        self.tasks.defer_task.assert_called_once_with(
            task, 1234.5, reset_poll_attempts=True, reason=""
        )

    def test_deferred_forwards_reason(self) -> None:
        task: Dict[str, Any] = _task()

        _apply_outcome(
            self.tasks, self.users, task, Deferred(1234.5, reason="LLM timed out")
        )

        self.tasks.defer_task.assert_called_once_with(
            task, 1234.5, reset_poll_attempts=False, reason="LLM timed out"
        )


if __name__ == "__main__":
    unittest.main()
