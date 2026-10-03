"""Cached LLM judge calls for the anthology pipeline."""

import hashlib
import logging
import time
from typing import Any, Dict, Optional

from pymongo.database import Database

JUDGMENTS_COLLECTION: str = "anthology_judgments"

_log: logging.Logger = logging.getLogger("anthology.judge")


class JudgeUnavailableError(RuntimeError):
    """Raised when every LLM call of a run failed."""


class Judge:
    """Send short judge prompts to the worker LLM, caching answers per owner."""

    def __init__(
        self,
        db: Database,
        llm_router: Any,
        owner: str,
        settings: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._db: Database = db
        self._llm: Any = llm_router
        self._owner: str = owner
        self._settings: Dict[str, Any] = settings or {}
        self.calls: int = 0
        self.cached: int = 0
        self.failures: int = 0

    def ask(self, prompt: str) -> str:
        """Return the (possibly cached) model answer; '' on failure."""
        prompt_hash: str = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        cached: Optional[str] = self._cached(prompt_hash)
        if cached is not None:
            self.cached += 1
            return cached
        self.calls += 1
        answer: str = self._call(prompt)
        if answer.strip():
            self._store(prompt_hash, answer)
        return answer

    def ensure_available(self) -> None:
        """Fail the run if the model never answered (avoid all-default results)."""
        if self.calls > 0 and self.failures >= self.calls and self.cached == 0:
            raise JudgeUnavailableError(f"LLM judge failed on all {self.calls} calls")

    def _call(self, prompt: str) -> str:
        try:
            raw: Any = self._llm.call(
                self._settings,
                [prompt],
                provider_key="worker_llm",
                default="llamacpp",
                temperature=0.1,
            )
        except Exception as exc:
            self.failures += 1
            _log.error("Anthology judge LLM call failed for %s: %s", self._owner, exc)
            return ""
        answer: str = str(raw or "")
        if not answer.strip():
            self.failures += 1
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

    def _store(self, prompt_hash: str, answer: str) -> None:
        try:
            self._db[JUDGMENTS_COLLECTION].update_one(
                {"owner": self._owner, "prompt_hash": prompt_hash},
                {"$set": {"response": answer, "created_at": time.time()}},
                upsert=True,
            )
        except Exception as exc:
            _log.warning("Can't store anthology judgment: %s", exc)


def prepare_judgments(db: Database) -> None:
    """Index the judgment cache."""
    try:
        db[JUDGMENTS_COLLECTION].create_index([("owner", 1), ("prompt_hash", 1)], unique=True)
    except Exception as exc:
        _log.warning("Can't create anthology judgment index: %s", exc)
