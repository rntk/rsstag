"""Cached, retried LLM calls for summary trees."""

import hashlib
import logging
import json
import threading
import time
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from pymongo.database import Database

CACHE_COLLECTION: str = "summary_tree_llm_cache"
RETRY_DELAYS: Tuple[float, ...] = (2.0, 8.0)
MAX_OUTAGE_ASKS: int = 3  # consecutive asks ending without any answer before giving up
RETRY_TEMPERATURE_STEP: float = 0.2

_log: logging.Logger = logging.getLogger("summary_tree.llm")


class SummaryLLMUnavailableError(RuntimeError):
    """The model failed every call of a run."""


class SummaryLLMCancelledError(RuntimeError):
    """The run was aborted; in-flight workers stop before their next attempt."""


class SummaryLLM:
    """Ask the worker LLM; answers are cached per owner by prompt hash."""

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
        self._retry_delays: Tuple[float, ...] = tuple(
            RETRY_DELAYS if retry_delays is None else retry_delays
        )
        self._lock: threading.Lock = threading.Lock()
        self._slots: threading.Semaphore = threading.Semaphore(self.workers)
        handler: Any = (llm_router.get_handler(self._settings, "worker_llm", "llamacpp")
                        if hasattr(llm_router, "get_handler") else None)
        self._identity: str = json.dumps({
            "version": 2, "provider": self._settings.get("worker_llm", "llamacpp"),
            "handler": type(handler).__name__,
            "model": str(getattr(handler, "model", self._settings.get("worker_llm_model", ""))),
        }, sort_keys=True, default=str)
        self.attempts: int = 0
        self.request_seconds: float = 0.0
        self.invalid_answers: int = 0
        self.calls: int = 0
        self.cached: int = 0
        self.failures: int = 0
        self._outage_asks: int = 0
        self._last_outage_at: float = float("-inf")
        self._cancelled: threading.Event = threading.Event()

    @property
    def workers(self) -> int:
        """Bound API concurrency; local inference defaults to one slot."""
        default: int = 1 if self._settings.get("worker_llm", "llamacpp") == "llamacpp" else 4
        try:
            return max(1, min(32, int(self._settings.get("summary_tree_workers", default))))
        except (ValueError, TypeError):
            return default

    def cancel(self) -> None:
        """Abort the run: pending and in-flight asks raise before their next attempt."""
        self._cancelled.set()

    def _check_runnable(self) -> None:
        if self._cancelled.is_set():
            raise SummaryLLMCancelledError("Summary tree run aborted")
        with self._lock:
            if self._outage_asks >= MAX_OUTAGE_ASKS:
                raise SummaryLLMUnavailableError("LLM unavailable; retry later")

    def ask(self, prompt: str, accept: Callable[[str], bool]) -> str:
        """Answer accepted by ``accept`` (cached or fresh); '' when none was produced."""
        if self._cancelled.is_set():
            raise SummaryLLMCancelledError("Summary tree run aborted")
        asked_at: float = time.monotonic()
        prompt_hash: str = _hash(self._identity + prompt)
        cached: Optional[str] = self._cached(prompt_hash)
        if cached is not None and accept(cached):
            with self._lock:
                self.cached += 1
            return cached
        with self._lock:
            self.calls += 1
        answered: bool = False
        for attempt, delay in enumerate((0.0,) + self._retry_delays):
            if attempt and not answered:
                time.sleep(delay)  # back off only when the model gave nothing (timeout, error)
            self._check_runnable()
            with self._slots:
                started: float = time.monotonic()
                answer: str = self._attempt(prompt, attempt)
                with self._lock:
                    self.attempts += 1
                    self.request_seconds += time.monotonic() - started
            answered = bool(answer.strip())
            if answered and accept(answer):
                self._store(prompt_hash, answer)
                with self._lock:
                    self._outage_asks = 0
                return answer
            if answered:
                with self._lock:
                    self.invalid_answers += 1
        with self._lock:
            self.failures += 1
        self._note_outage(answered, asked_at)
        return ""

    def _note_outage(self, answered: bool, asked_at: float) -> None:
        """Stop early when the model keeps returning nothing.

        Concurrent asks that overlap an already counted outage count once, so the
        threshold means consecutive outages over time, not parallel casualties.
        """
        with self._lock:
            if answered:
                self._outage_asks = 0
            elif asked_at >= self._last_outage_at:
                self._outage_asks += 1
                self._last_outage_at = time.monotonic()
            outages: int = self._outage_asks
        if outages >= MAX_OUTAGE_ASKS:
            _log.error("Summary tree LLM unavailable for %s after %d outages", self._owner, outages)
            raise SummaryLLMUnavailableError(
                f"LLM returned no answer for {outages} requests in a row; retry later"
            )

    def ensure_available(self) -> None:
        if self.calls > 0 and self.failures >= self.calls and self.cached == 0:
            raise SummaryLLMUnavailableError(f"LLM failed on all {self.calls} calls")

    def _attempt(self, prompt: str, attempt: int = 0) -> str:
        try:
            raw: Any = self._llm.call(
                self._settings,
                [prompt],
                provider_key="worker_llm",
                default="llamacpp",
                temperature=min(0.7, 0.1 + RETRY_TEMPERATURE_STEP * attempt),
            )
        except Exception as exc:
            _log.error("Summary tree LLM call failed for %s: %s", self._owner, exc)
            return ""
        return str(raw or "")

    def _cached(self, prompt_hash: str) -> Optional[str]:
        try:
            doc = self._db[CACHE_COLLECTION].find_one(
                {"owner": self._owner, "prompt_hash": prompt_hash}, projection={"response": True}
            )
        except Exception as exc:
            _log.warning("Can't read summary tree LLM cache: %s", exc)
            return None
        return str(doc["response"]) if doc and doc.get("response") is not None else None

    def _store(self, prompt_hash: str, answer: str) -> None:
        try:
            self._db[CACHE_COLLECTION].update_one(
                {"owner": self._owner, "prompt_hash": prompt_hash},
                {"$set": {"response": answer, "created_at": time.time()}},
                upsert=True,
            )
        except Exception as exc:
            _log.warning("Can't store summary tree LLM answer: %s", exc)


def _hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def prepare_cache(db: Database) -> None:
    try:
        db[CACHE_COLLECTION].create_index([("owner", 1), ("prompt_hash", 1)], unique=True)
    except Exception as exc:
        _log.warning("Can't create summary tree LLM cache index: %s", exc)
