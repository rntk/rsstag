"""Cached, parallel decisions-API calls for summary trees.

Failures never become answers: a failed request yields ``None`` and switches the
judge off for the rest of the run, so callers fall back to the LLM-only path.
"""

import hashlib
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pymongo.database import Database

from rsstag.decisions.client import (
    DecisionsClient,
    DecisionsError,
    create_decisions_client,
)
from rsstag.decisions.models import Answer, DecisionResponse, Question

CACHE_COLLECTION: str = "summary_tree_decisions_cache"
RETRY_DELAY: float = 2.0
DEFAULT_WORKERS: int = 8

Request = Tuple[Dict[str, Any], Dict[str, Question]]
Answers = Dict[str, Answer]

_log: logging.Logger = logging.getLogger("summary_tree.judge")


class SummaryJudge:
    """Ask typed questions; answers are cached per owner by request hash."""

    def __init__(self, db: Database, client: DecisionsClient, owner: str,
                 workers: int = DEFAULT_WORKERS, retry_delay: float = RETRY_DELAY) -> None:
        self._db: Database = db
        self._client: DecisionsClient = client
        self._owner: str = owner
        self._workers: int = max(1, workers)
        self._retry_delay: float = retry_delay
        self._lock: threading.Lock = threading.Lock()
        self._disabled: bool = False
        self.calls: int = 0
        self.cached: int = 0
        self.failures: int = 0
        self.input_tokens: int = 0

    @property
    def active(self) -> bool:
        return not self._disabled

    def ask_many(self, requests: Sequence[Request]) -> List[Optional[Answers]]:
        """Answers in request order; ``None`` where a request failed."""
        if not requests or self._disabled:
            return [None] * len(requests)
        if len(requests) == 1:
            return [self.ask(*requests[0])]
        with ThreadPoolExecutor(max_workers=min(self._workers, len(requests))) as pool:
            return list(pool.map(lambda request: self.ask(*request), requests))

    def ask(self, state: Dict[str, Any], questions: Dict[str, Question]) -> Optional[Answers]:
        if self._disabled:
            return None
        key: str = self._key(state, questions)
        cached: Optional[Answers] = self._cached(key, questions)
        if cached is not None:
            with self._lock:
                self.cached += 1
            return cached
        response: Optional[DecisionResponse] = self._call(state, questions)
        if response is None:
            return None
        self._store(key, response)
        return dict(response.answers)

    def _call(self, state: Dict[str, Any], questions: Dict[str, Question]) -> Optional[DecisionResponse]:
        for attempt in range(2):
            if self._disabled:
                return None
            if attempt:
                time.sleep(self._retry_delay)
            with self._lock:
                self.calls += 1
            try:
                response: DecisionResponse = self._client.call(state, questions)
            except DecisionsError as exc:
                _log.warning("Summary tree decisions call failed for %s: %s", self._owner, exc)
                with self._lock:
                    self.failures += 1
                continue
            with self._lock:
                self.input_tokens += response.usage.input_tokens
            return response
        self._disable()
        return None

    def _disable(self) -> None:
        with self._lock:
            if not self._disabled:
                _log.warning("Decisions disabled for this summary tree run of %s; using LLM fallback",
                             self._owner)
            self._disabled = True

    def _key(self, state: Dict[str, Any], questions: Mapping[str, Question]) -> str:
        payload: Dict[str, Any] = {
            "model": self._client.model, "state": state,
            "questions": {name: q.model_dump(exclude_none=True) for name, q in questions.items()},
        }
        raw: str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _cached(self, key: str, questions: Mapping[str, Question]) -> Optional[Answers]:
        try:
            doc: Optional[Dict[str, Any]] = self._db[CACHE_COLLECTION].find_one(
                {"owner": self._owner, "request_hash": key}, projection={"response": True})
            if not doc or not isinstance(doc.get("response"), dict):
                return None
            response: DecisionResponse = DecisionResponse.model_validate(doc["response"])
        except Exception as exc:
            _log.warning("Can't read summary tree decisions cache: %s", exc)
            return None
        answers: Answers = dict(response.answers)
        return answers if answers.keys() == questions.keys() else None

    def _store(self, key: str, response: DecisionResponse) -> None:
        try:
            self._db[CACHE_COLLECTION].update_one(
                {"owner": self._owner, "request_hash": key},
                {"$set": {"response": response.model_dump(), "created_at": time.time()}},
                upsert=True,
            )
        except Exception as exc:
            _log.warning("Can't store summary tree decisions answer: %s", exc)


def noul(answers: Optional[Answers], name: str) -> Optional[float]:
    answer: Any = (answers or {}).get(name)
    return float(answer.noul) if answer is not None and answer.type == "noul" else None


def choice(answers: Optional[Answers], name: str) -> Optional[str]:
    answer: Any = (answers or {}).get(name)
    return str(answer.choice) if answer is not None and answer.type == "choice" else None


def _enabled(value: Any) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def prepare_judge_cache(db: Database) -> None:
    try:
        db[CACHE_COLLECTION].create_index([("owner", 1), ("request_hash", 1)], unique=True)
    except Exception as exc:
        _log.warning("Can't create summary tree decisions cache index: %s", exc)


def build_judge(db: Database, config: Mapping[str, Any], owner: str,
                user_settings: Optional[Mapping[str, Any]] = None) -> Optional[SummaryJudge]:
    """A judge when ``[decisions] summary_tree`` is on and a provider resolves; else None."""
    section: Mapping[str, Any] = config.get("decisions", {}) if config else {}
    if not _enabled(section.get("summary_tree")):
        return None
    try:
        client: DecisionsClient = create_decisions_client(
            config, user_settings=user_settings, provider_key="worker_decisions")
        workers: int = int(section.get("summary_tree_workers", DEFAULT_WORKERS))
    except (ValueError, TypeError) as exc:
        _log.warning("Summary tree decisions are misconfigured, using LLM only: %s", exc)
        return None
    prepare_judge_cache(db)
    return SummaryJudge(db, client, owner, workers)
