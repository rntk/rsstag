"""Cached LLM judge calls for the anthology pipeline."""

import hashlib
import logging
import time
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from pymongo.database import Database

JUDGMENTS_COLLECTION: str = "anthology_judgments"
RETRY_DELAYS: Tuple[float, ...] = (2.0, 8.0)  # backoff before each extra attempt
MAX_MISSING_RATIO: float = 0.2  # above this share of unanswered items the run fails

_log: logging.Logger = logging.getLogger("anthology.judge")


class JudgeUnavailableError(RuntimeError):
    """Raised when the LLM failed every call or left too many items unjudged."""


class Judge:
    """Send short judge prompts to the worker LLM, caching answers per owner."""

    def __init__(
        self,
        db: Database,
        llm_router: Any,
        owner: str,
        settings: Optional[Dict[str, Any]] = None,
        retry_delays: Optional[Sequence[float]] = None,
    ) -> None:
        self._db: Database = db
        self._llm: Any = llm_router
        self._owner: str = owner
        self._settings: Dict[str, Any] = settings or {}
        self.calls: int = 0
        self.cached: int = 0
        self.failures: int = 0
        self.retries: int = 0
        self.expected: int = 0
        self.missing: int = 0
        self._retry_delays: Tuple[float, ...] = tuple(
            RETRY_DELAYS if retry_delays is None else retry_delays
        )
        self.on_progress: Optional[Callable[[], None]] = None

    def ask(self, prompt: str) -> str:
        """Return the (possibly cached) model answer; '' on failure."""
        if self.on_progress is not None:
            self.on_progress()
        try:
            return self._answer(prompt)
        finally:
            if self.on_progress is not None:
                self.on_progress()

    def _answer(self, prompt: str) -> str:
        """Resolve the answer while keeping progress callbacks outside LLM errors."""
        prompt_hash: str = _hash(prompt)
        cached: Optional[str] = self._cached(prompt_hash)
        if cached is not None:
            self.cached += 1
            return cached
        self.calls += 1
        answer: str = self._call(prompt)
        if answer.strip():
            self._store(prompt_hash, answer)
        return answer

    def record(self, prompt: str, expected: int, answered: int) -> None:
        """Count parsed judgments; incomplete answers leave the cache so a rebuild re-asks."""
        self.expected += expected
        self.missing += max(0, expected - answered)
        if answered < expected:
            self._forget(_hash(prompt))

    def ensure_available(self) -> None:
        """Fail the run if the model never answered or left too many items unjudged."""
        if self.calls > 0 and self.failures >= self.calls and self.cached == 0:
            raise JudgeUnavailableError(f"LLM judge failed on all {self.calls} calls")
        if self.expected and self.missing / self.expected > MAX_MISSING_RATIO:
            raise JudgeUnavailableError(
                f"LLM judge left {self.missing} of {self.expected} judgments unanswered; "
                "retry the anthology build"
            )

    def _call(self, prompt: str) -> str:
        """Call the model, retrying errors and empty answers with backoff."""
        answer: str = ""
        for attempt, delay in enumerate((0.0,) + self._retry_delays):
            if attempt:
                self.retries += 1
                _log.info("Retrying anthology judge call for %s in %.1fs", self._owner, delay)
                time.sleep(delay)
            answer = self._attempt(prompt)
            if answer.strip():
                return answer
        self.failures += 1
        return answer

    def _attempt(self, prompt: str) -> str:
        try:
            raw: Any = self._llm.call(
                self._settings,
                [prompt],
                provider_key="worker_llm",
                default="llamacpp",
                temperature=0.1,
            )
        except Exception as exc:
            _log.error("Anthology judge LLM call failed for %s: %s", self._owner, exc)
            return ""
        answer: str = str(raw or "")
        if not answer.strip():
            _log.warning("Anthology judge got an empty answer for %s", self._owner)
        return answer

    def _cached(self, prompt_hash: str) -> Optional[str]:
        try:
            doc = self._db[JUDGMENTS_COLLECTION].find_one(
                {"owner": self._owner, "prompt_hash": prompt_hash}, projection={"response": True}
            )
        except Exception as exc:
            _log.warning("Can't read anthology judgment cache: %s", exc)
            return None
        return str(doc["response"]) if doc and doc.get("response") is not None else None

    def _forget(self, prompt_hash: str) -> None:
        try:
            self._db[JUDGMENTS_COLLECTION].delete_one(
                {"owner": self._owner, "prompt_hash": prompt_hash}
            )
        except Exception as exc:
            _log.warning("Can't drop unusable anthology judgment: %s", exc)

    def _store(self, prompt_hash: str, answer: str) -> None:
        try:
            self._db[JUDGMENTS_COLLECTION].update_one(
                {"owner": self._owner, "prompt_hash": prompt_hash},
                {"$set": {"response": answer, "created_at": time.time()}},
                upsert=True,
            )
        except Exception as exc:
            _log.warning("Can't store anthology judgment: %s", exc)


def _hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def prepare_judgments(db: Database) -> None:
    """Index the judgment cache."""
    try:
        db[JUDGMENTS_COLLECTION].create_index([("owner", 1), ("prompt_hash", 1)], unique=True)
    except Exception as exc:
        _log.warning("Can't create anthology judgment index: %s", exc)
