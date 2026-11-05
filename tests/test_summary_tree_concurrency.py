"""Concurrency safeguards: outage counting, cancellation, judge cap, save flushing."""

import threading
import time
import unittest
from typing import Any, List
from unittest.mock import MagicMock, patch

from rsstag.decisions.models import DecisionResponse
from rsstag.summary_tree import questions as q
from rsstag.summary_tree.judge import SummaryJudge
from rsstag.summary_tree.llm import (MAX_OUTAGE_ASKS, SummaryLLM, SummaryLLMCancelledError,
                                     SummaryLLMUnavailableError)
from rsstag.summary_tree.pipeline import SummaryTreePipeline
from rsstag.summary_tree.pool import worker_pool


def _db() -> MagicMock:
    db: MagicMock = MagicMock()
    db.__getitem__.return_value.find_one.return_value = None
    return db


class LockstepRouter:
    """Every call fails, and callers wait for each other so their asks overlap."""

    def __init__(self, parties: int) -> None:
        self._barrier: threading.Barrier = threading.Barrier(parties, timeout=5)
        self.calls: int = 0

    def call(self, _settings: Any, _prompts: List[str], **_kwargs: Any) -> str:
        self.calls += 1
        self._barrier.wait()
        raise TimeoutError("timed out")


class TestOutageCounting(unittest.TestCase):
    def test_overlapping_failures_count_as_one_outage(self) -> None:
        workers: int = MAX_OUTAGE_ASKS + 1
        llm: SummaryLLM = SummaryLLM(_db(), LockstepRouter(workers), "owner",
                                     {"summary_tree_workers": workers}, retry_delays=(0.0, 0.0))
        errors: List[BaseException] = []

        def ask() -> None:
            try:
                llm.ask("p", lambda _a: True)
            except BaseException as exc:  # recorded for the assertion below
                errors.append(exc)

        with patch("rsstag.summary_tree.llm.time.sleep"):
            threads: List[threading.Thread] = [threading.Thread(target=ask) for _ in range(workers)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
        self.assertEqual(errors, [])
        self.assertEqual(llm.failures, workers)

    def test_sequential_outages_still_abort(self) -> None:
        llm: SummaryLLM = SummaryLLM(_db(), LockstepRouter(1), "owner", retry_delays=())
        for _ in range(MAX_OUTAGE_ASKS - 1):
            self.assertEqual(llm.ask("p", lambda _a: True), "")
        with self.assertRaises(SummaryLLMUnavailableError):
            llm.ask("p", lambda _a: True)


class TestCancellation(unittest.TestCase):
    def test_cancelled_llm_makes_no_calls(self) -> None:
        router: LockstepRouter = LockstepRouter(1)
        llm: SummaryLLM = SummaryLLM(_db(), router, "owner", retry_delays=())
        llm.cancel()
        with self.assertRaises(SummaryLLMCancelledError):
            llm.ask("p", lambda _a: True)
        self.assertEqual(router.calls, 0)

    def test_failing_coordinator_does_not_wait_for_running_work(self) -> None:
        llm: MagicMock = MagicMock()
        release: threading.Event = threading.Event()
        started: float = time.monotonic()
        with self.assertRaises(ValueError):
            with worker_pool(2, llm) as pool:
                pool.submit(release.wait, 5)
                raise ValueError("coordinator failed")
        self.assertLess(time.monotonic() - started, 2.0)
        llm.cancel.assert_called_once()
        release.set()

    def test_successful_pool_joins_workers(self) -> None:
        llm: MagicMock = MagicMock()
        results: List[int] = []
        with worker_pool(2, llm) as pool:
            pool.submit(lambda: (time.sleep(0.05), results.append(1)))
        self.assertEqual(results, [1])
        llm.cancel.assert_not_called()


class CountingClient:
    model: str = "fake-model"

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._active: int = 0
        self.peak: int = 0

    def call(self, _state: Any, _questions: Any, **_kwargs: Any) -> DecisionResponse:
        with self._lock:
            self._active += 1
            self.peak = max(self.peak, self._active)
        time.sleep(0.02)
        with self._lock:
            self._active -= 1
        return DecisionResponse.model_validate(
            {"model": self.model, "answers": {"s0": {"type": "noul", "noul": 0.9}},
             "usage": {"input_tokens": 1, "output_tokens": 1}})


class TestJudgeCap(unittest.TestCase):
    def test_nested_ask_many_respects_worker_limit(self) -> None:
        client: CountingClient = CountingClient()
        judge: SummaryJudge = SummaryJudge(_db(), client, "u", workers=2, retry_delay=0)
        requests: List[Any] = [({"n": index}, {"s0": q.claim_supported("s0")}) for index in range(6)]
        threads: List[threading.Thread] = [
            threading.Thread(target=judge.ask_many, args=(requests,)) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(client.peak, 2)
        self.assertEqual(judge.failures, 0)


class TestSaveFlush(unittest.TestCase):
    def _pipeline(self) -> SummaryTreePipeline:
        pipeline: SummaryTreePipeline = SummaryTreePipeline(_db(), MagicMock(spec=["call"]), "u")
        pipeline._store = MagicMock()
        return pipeline

    def test_throttled_save_is_flushed_on_stage_change(self) -> None:
        pipeline: SummaryTreePipeline = self._pipeline()
        pipeline._save()
        pipeline._save()
        self.assertEqual(pipeline._store.save_partial.call_count, 1)
        pipeline._stage("summaries")
        self.assertEqual(pipeline._store.save_partial.call_count, 2)

    def test_throttled_save_is_flushed_before_failure(self) -> None:
        pipeline: SummaryTreePipeline = self._pipeline()
        pipeline._save()
        pipeline._save()
        pipeline._fail("boom")
        self.assertEqual(pipeline._store.save_partial.call_count, 2)
        pipeline._store.fail.assert_called_once()

    def test_nothing_to_flush_saves_nothing(self) -> None:
        pipeline: SummaryTreePipeline = self._pipeline()
        pipeline._fail("boom")
        pipeline._store.save_partial.assert_not_called()


if __name__ == "__main__":
    unittest.main()
