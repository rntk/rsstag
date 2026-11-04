"""Retry behaviour of the summary tree LLM wrapper."""

import unittest
from typing import Any, List
from unittest.mock import MagicMock, patch

from rsstag.summary_tree.llm import MAX_OUTAGE_ASKS, SummaryLLM, SummaryLLMUnavailableError


class Router:
    def __init__(self, answers: List[Any]) -> None:
        self.answers: List[Any] = answers
        self.temperatures: List[float] = []

    def call(self, _settings: Any, _prompts: List[str], **kwargs: Any) -> str:
        self.temperatures.append(kwargs["temperature"])
        answer: Any = self.answers.pop(0) if self.answers else ""
        if isinstance(answer, Exception):
            raise answer
        return answer


def _llm(router: Router) -> SummaryLLM:
    db: MagicMock = MagicMock()
    db.__getitem__.return_value.find_one.return_value = None
    return SummaryLLM(db, router, "owner", retry_delays=(1.0, 2.0))


class TestSummaryLLMRetry(unittest.TestCase):
    def test_timeout_backs_off_then_succeeds(self) -> None:
        llm: SummaryLLM = _llm(Router([TimeoutError("timed out"), "ok"]))
        with patch("rsstag.summary_tree.llm.time.sleep") as sleep:
            self.assertEqual(llm.ask("p", lambda _a: True), "ok")
        sleep.assert_called_once_with(1.0)

    def test_invalid_answer_retries_without_sleep_and_raises_temperature(self) -> None:
        router: Router = Router(["bad", "good"])
        llm: SummaryLLM = _llm(router)
        with patch("rsstag.summary_tree.llm.time.sleep") as sleep:
            self.assertEqual(llm.ask("p", lambda a: a == "good"), "good")
        sleep.assert_not_called()
        self.assertGreater(router.temperatures[1], router.temperatures[0])

    def test_persistent_outage_aborts_run(self) -> None:
        llm: SummaryLLM = _llm(Router([TimeoutError("timed out")] * 50))
        with patch("rsstag.summary_tree.llm.time.sleep"):
            for _ in range(MAX_OUTAGE_ASKS - 1):
                self.assertEqual(llm.ask("p", lambda _a: True), "")
            with self.assertRaises(SummaryLLMUnavailableError):
                llm.ask("p", lambda _a: True)


if __name__ == "__main__":
    unittest.main()
