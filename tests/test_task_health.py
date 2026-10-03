"""Tests for the user-facing task health summary shown on /tasks."""

import time
import unittest
from typing import Any, Dict

from rsstag.task_state import (
    TASK_STATUS_DEAD,
    TASK_STATUS_PAUSED,
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
)
from rsstag.tasks import TASK_FREEZED, describe_task_health


class DescribeTaskHealthTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.now: float = time.time()

    def test_dead_task_is_failed_with_error_and_retry(self) -> None:
        task: Dict[str, Any] = {
            "status": TASK_STATUS_DEAD,
            "failed": True,
            "failed_at": self.now,
            "attempts": 3,
            "error": "Handler returned false for type 19",
            "last_error": "older error",
        }

        health: Dict[str, Any] = describe_task_health(task, self.now)

        self.assertEqual(health["state"], "failed")
        self.assertEqual(health["error"], "Handler returned false for type 19")
        self.assertEqual(health["attempts"], 3)
        self.assertTrue(health["error_at"])
        self.assertTrue(health["can_retry"])

    def test_legacy_frozen_task_is_paused(self) -> None:
        for task in ({"status": TASK_STATUS_PAUSED}, {"processing": TASK_FREEZED}):
            health: Dict[str, Any] = describe_task_health(task, self.now)
            self.assertEqual(health["state"], "paused")
            self.assertTrue(health["can_retry"])

    def test_backoff_after_failure_is_retrying(self) -> None:
        task: Dict[str, Any] = {
            "status": TASK_STATUS_PENDING,
            "attempts": 1,
            "backoff_until": self.now + 30,
            "last_error": "boom",
        }

        health: Dict[str, Any] = describe_task_health(task, self.now)

        self.assertEqual(health["state"], "retrying")
        self.assertEqual(health["error"], "boom")
        self.assertTrue(health["retry_at"])
        self.assertFalse(health["can_retry"])

    def test_deferred_without_attempts_is_waiting(self) -> None:
        task: Dict[str, Any] = {
            "status": TASK_STATUS_PENDING,
            "backoff_until": self.now + 60,
            "last_error": "LLM provider failed, retrying shortly: timed out",
            "last_error_at": self.now,
        }

        health: Dict[str, Any] = describe_task_health(task, self.now)

        self.assertEqual(health["state"], "waiting")
        self.assertIn("timed out", health["error"])
        self.assertTrue(health["error_at"])

    def test_healthy_tasks(self) -> None:
        running: Dict[str, Any] = {"status": TASK_STATUS_RUNNING, "processing": self.now}
        queued: Dict[str, Any] = {"status": TASK_STATUS_PENDING, "backoff_until": 0.0}

        self.assertEqual(describe_task_health(running, self.now)["state"], "processing")
        queued_health: Dict[str, Any] = describe_task_health(queued, self.now)
        self.assertEqual(queued_health["state"], "queued")
        self.assertEqual(queued_health["error"], "")
        self.assertEqual(queued_health["retry_at"], "")


if __name__ == "__main__":
    unittest.main()
