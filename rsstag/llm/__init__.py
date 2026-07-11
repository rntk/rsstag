import hashlib
import logging
import time
from typing import Any, Optional

from rsstag.llm.base import LLMResponse, ToolCall, ToolDefinition


class LLMCache:
    """Persistent, user-scoped cache for deterministic LLM results."""

    def __init__(self, db: Any) -> None:
        self._collection: Any = db.llm_cache
        self._log: logging.Logger = logging.getLogger(__name__)

    def prepare(self) -> None:
        try:
            self._collection.create_index([("owner", 1), ("key", 1)], unique=True)
        except Exception as exc:
            self._log.warning("Unable to create the LLM cache index: %s", exc)

    @staticmethod
    def make_key(namespace: str, value: str) -> str:
        payload: bytes = f"{namespace}\0{value}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def get(self, owner: str, key: str) -> Optional[str]:
        try:
            cached: Optional[dict[str, Any]] = self._collection.find_one(
                {"owner": owner, "key": key}, {"value": 1}
            )
        except Exception as exc:
            self._log.warning("Unable to read the LLM cache: %s", exc)
            return None

        value: Any = cached.get("value") if cached else None
        return value if isinstance(value, str) and value else None

    def set(self, owner: str, key: str, value: str) -> None:
        try:
            self._collection.update_one(
                {"owner": owner, "key": key},
                {
                    "$set": {"value": value, "updated_at": time.time()},
                    "$setOnInsert": {"owner": owner, "key": key},
                },
                upsert=True,
            )
        except Exception as exc:
            self._log.warning("Unable to write the LLM cache: %s", exc)

__all__ = ["LLMCache", "LLMResponse", "ToolCall", "ToolDefinition"]
