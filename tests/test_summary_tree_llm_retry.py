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
    def test_cache_keys_are_separated_by_model(self) -> None:
        db: MagicMock = MagicMock()
        collection: MagicMock = db.__getitem__.return_value
        collection.find_one.return_value = None
        first: SummaryLLM = SummaryLLM(db, Router(["answer"]), "owner",
                                       {"worker_llm_model": "model-a"}, retry_delays=())
        second: SummaryLLM = SummaryLLM(db, Router(["answer"]), "owner",
                                        {"worker_llm_model": "model-b"}, retry_delays=())
        self.assertEqual(first.ask("same prompt", lambda _answer: True), "answer")
        self.assertEqual(second.ask("same prompt", lambda _answer: True), "answer")
        stored_hashes: List[str] = [call.args[0]["prompt_hash"]
                                    for call in collection.update_one.call_args_list]
        self.assertEqual(len(stored_hashes), 2)
        self.assertNotEqual(stored_hashes[0], stored_hashes[1])

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

    def test_persistent_invalid_response_uses_exact_retry_budget(self) -> None:
        router: Router = Router(["invalid"] * 5)
        db: MagicMock = MagicMock()
        db.__getitem__.return_value.find_one.return_value = None
        llm: SummaryLLM = SummaryLLM(db, router, "owner", retry_delays=(0.0, 0.0))
        with patch("rsstag.summary_tree.llm.time.sleep") as sleep:
            self.assertEqual(llm.ask("p", lambda _answer: False), "")
        self.assertEqual(len(router.temperatures), 3)
        self.assertEqual(llm.attempts, 3)
        self.assertEqual(llm.invalid_answers, 3)
        sleep.assert_not_called()

    def test_persistent_outage_aborts_run(self) -> None:
        llm: SummaryLLM = _llm(Router([TimeoutError("timed out")] * 50))
        with patch("rsstag.summary_tree.llm.time.sleep"):
            for _ in range(MAX_OUTAGE_ASKS - 1):
                self.assertEqual(llm.ask("p", lambda _a: True), "")
            with self.assertRaises(SummaryLLMUnavailableError):
                llm.ask("p", lambda _a: True)


if __name__ == "__main__":
    unittest.main()
