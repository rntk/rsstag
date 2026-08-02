"""Deduplication cache for the post grouping task.

Post grouping is the most expensive LLM task in rsstag: every post (and every
chunk of a post) is sent to an LLM to get topic ranges back. Feeds repeat
themselves a lot -- the same article is republished by several sources, posts
are re-downloaded, and long posts share boilerplate chunks. This module stores
LLM work keyed by a hash of the exact text that was sent, so repeats cost
nothing.

Two kinds of entries live in the same collection:

* ``document`` -- the finished grouping result (sentences + groups) for a whole
  document. A hit skips the whole pipeline for a post.
* ``chunk`` -- a single LLM response for one prompt. A hit skips one request.

Keys are hashes of the *exact* text handed to the LLM, without normalization:
sentence offsets stored by :mod:`rsstag.post_grouping` are byte offsets into
that text, so a "close enough" match would corrupt sentence boundaries. The
model identity is part of the key as well, so switching providers does not
replay answers from the old model forever.
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

KIND_DOCUMENT = "document"
KIND_CHUNK = "chunk"

NAMESPACE_DOCUMENT = "post_grouping:document"
NAMESPACE_CHUNK_SYNC = "post_grouping:chunk:sync"
NAMESPACE_CHUNK_BATCH = "post_grouping:chunk:batch"

_NAMESPACE_KINDS: Dict[str, str] = {
    NAMESPACE_DOCUMENT: KIND_DOCUMENT,
    NAMESPACE_CHUNK_SYNC: KIND_CHUNK,
    NAMESPACE_CHUNK_BATCH: KIND_CHUNK,
}

SORTABLE_FIELDS: List[str] = [
    "hits",
    "created_at",
    "last_hit_at",
    "value_size",
    "hits_per_day",
]


def text_hash(text: str) -> str:
    """Hash of a document text, used to invalidate everything it produced."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _handler_model(handler: Any) -> str:
    """Read the configured model of a handler.

    Batch providers and the OpenAI handler expose ``model`` publicly, while the
    anthropic/groqcom/cerebras/llamacpp handlers keep it in a private
    ``__model`` attribute; without the mangled lookup every one of them would
    share a single cache identity and answers from the previously configured
    model would be replayed after a model switch.
    """
    model: Any = getattr(handler, "model", "")
    if model:
        return str(model)
    for klass in type(handler).__mro__:
        # Python strips leading underscores of the class name when mangling.
        mangled: Any = getattr(handler, f"_{klass.__name__.lstrip('_')}__model", "")
        if mangled:
            return str(mangled)
    return ""


def model_identity(handler: Any) -> str:
    """Build a stable identity string for an LLM handler or batch provider."""
    if handler is None:
        return "unknown"
    name: str = str(getattr(handler, "name", "") or type(handler).__name__)
    return f"{name}:{_handler_model(handler)}"


class ChunkCacheView:
    """Owner/model bound view used by :class:`rsstag.post_splitter.PostSplitter`."""

    def __init__(
        self,
        cache: "PostGroupingCache",
        owner: str,
        model: str,
        namespace: str = NAMESPACE_CHUNK_SYNC,
    ) -> None:
        self._cache: "PostGroupingCache" = cache
        self._owner: str = owner
        self._model: str = model
        self._namespace: str = namespace
        self._document_hash: str = ""

    def bind_document(self, text: str) -> None:
        """Tag the entries written next with the document they came from.

        A grouping cleanup asks for a reprocess of some posts; without this tag
        their chunk answers would be replayed and the reprocess would return the
        very same grouping.
        """
        self._document_hash = text_hash(text)

    @staticmethod
    def _payload(prompt: str, temperature: float) -> str:
        return f"{temperature!r}\0{prompt}"

    def get(self, prompt: str, temperature: float) -> Optional[str]:
        return self._cache.get(
            self._owner, self._namespace, self._model, self._payload(prompt, temperature)
        )

    def set(self, prompt: str, temperature: float, value: str) -> bool:
        return self._cache.set(
            self._owner,
            self._namespace,
            self._model,
            self._payload(prompt, temperature),
            value,
            document_hash=self._document_hash,
        )


class PostGroupingCache:
    """Mongo backed cache with per-entry hit statistics."""

    # Mongo documents are capped at 16MB; stay well below with the metadata.
    MAX_VALUE_BYTES: int = 8 * 1024 * 1024

    def __init__(self, db: Any, enabled: bool = True) -> None:
        self._db: Any = db
        self._collection: Any = db.post_grouping_cache
        self._enabled: bool = enabled
        self._log: logging.Logger = logging.getLogger(__name__)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def prepare(self) -> None:
        try:
            self._collection.create_index([("owner", 1), ("key", 1)], unique=True)
            self._collection.create_index([("owner", 1), ("kind", 1), ("hits", 1)])
            self._collection.create_index([("owner", 1), ("created_at", 1)])
            self._collection.create_index([("owner", 1), ("document_hashes", 1)])
        except Exception as exc:
            self._log.warning("Unable to create post grouping cache indexes: %s", exc)

    @staticmethod
    def make_key(namespace: str, model: str, value: str) -> str:
        payload: bytes = f"{namespace}\0{model}\0{value}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    # -- raw entries ----------------------------------------------------

    def get(
        self, owner: str, namespace: str, model: str, value: str
    ) -> Optional[str]:
        """Read an entry and count the hit atomically."""
        if not self._enabled or not owner:
            return None

        key: str = self.make_key(namespace, model, value)
        try:
            cached: Optional[Dict[str, Any]] = self._collection.find_one_and_update(
                {"owner": owner, "key": key},
                {"$inc": {"hits": 1}, "$set": {"last_hit_at": time.time()}},
                projection={"value": 1},
            )
        except Exception as exc:
            self._log.warning("Unable to read the post grouping cache: %s", exc)
            return None

        if not cached:
            return None
        stored: Any = cached.get("value")
        return stored if isinstance(stored, str) and stored else None

    def set(
        self,
        owner: str,
        namespace: str,
        model: str,
        value: str,
        result: str,
        document_hash: str = "",
    ) -> bool:
        """Store an entry. Returns False when the write was skipped."""
        if not self._enabled or not owner or not result:
            return False

        size: int = len(result.encode("utf-8"))
        if size > self.MAX_VALUE_BYTES:
            self._log.info(
                "Skip caching post grouping result of %d bytes (owner %s, %s)",
                size,
                owner,
                namespace,
            )
            return False

        key: str = self.make_key(namespace, model, value)
        now: float = time.time()
        update: Dict[str, Any] = {
            "$set": {
                "value": result,
                "value_size": size,
                "updated_at": now,
            },
            "$setOnInsert": {
                "owner": owner,
                "key": key,
                "namespace": namespace,
                "kind": _NAMESPACE_KINDS.get(namespace, KIND_CHUNK),
                "model": model,
                "created_at": now,
                "last_hit_at": None,
                "hits": 0,
            },
        }
        if document_hash:
            # A chunk can come from several documents; remember all of them so a
            # cleanup of any one of them invalidates the shared answer.
            update["$addToSet"] = {"document_hashes": document_hash}
        else:
            update["$setOnInsert"]["document_hashes"] = []
        try:
            self._collection.update_one({"owner": owner, "key": key}, update, upsert=True)
        except Exception as exc:
            self._log.warning("Unable to write the post grouping cache: %s", exc)
            return False
        return True

    # -- document entries -----------------------------------------------

    def get_document(self, owner: str, model: str, text: str) -> Optional[Dict[str, Any]]:
        """Return a cached grouping result for the exact pipeline input text."""
        raw: Optional[str] = self.get(owner, NAMESPACE_DOCUMENT, model, text)
        if not raw:
            return None
        try:
            result: Any = json.loads(raw)
        except (ValueError, TypeError) as exc:
            self._log.warning("Broken post grouping cache entry for %s: %s", owner, exc)
            return None
        if not isinstance(result, dict) or "sentences" not in result:
            return None
        return result

    def set_document(
        self, owner: str, model: str, text: str, result: Dict[str, Any]
    ) -> bool:
        if not result or not result.get("sentences"):
            return False
        try:
            payload: str = json.dumps(
                {"sentences": result["sentences"], "groups": result.get("groups", {})}
            )
        except (TypeError, ValueError) as exc:
            self._log.warning("Can`t serialize grouping result for cache: %s", exc)
            return False
        return self.set(
            owner,
            NAMESPACE_DOCUMENT,
            model,
            text,
            payload,
            document_hash=text_hash(text),
        )

    def invalidate_documents(self, owner: str, texts: List[str]) -> int:
        """Drop every entry produced by the given document texts."""
        hashes: List[str] = [text_hash(text) for text in texts if text]
        if not hashes:
            return 0
        try:
            result: Any = self._collection.delete_many(
                {"owner": owner, "document_hashes": {"$in": hashes}}
            )
        except Exception as exc:
            self._log.error("Unable to invalidate post grouping cache: %s", exc)
            return 0
        return int(result.deleted_count)

    def chunk_cache(
        self, owner: str, model: str, namespace: str = NAMESPACE_CHUNK_SYNC
    ) -> Optional[ChunkCacheView]:
        if not self._enabled or not owner:
            return None
        return ChunkCacheView(self, owner, model, namespace)

    # -- management ------------------------------------------------------

    def summary(self, owner: str) -> Dict[str, Any]:
        """Aggregate counters for the management page."""
        summary: Dict[str, Any] = {
            "entries": 0,
            "hits": 0,
            "size": 0,
            "document_entries": 0,
            "document_hits": 0,
            "chunk_entries": 0,
            "chunk_hits": 0,
            "unused_entries": 0,
        }
        pipeline: List[Dict[str, Any]] = [
            {"$match": {"owner": owner}},
            {
                "$group": {
                    "_id": "$kind",
                    "entries": {"$sum": 1},
                    "hits": {"$sum": {"$ifNull": ["$hits", 0]}},
                    "size": {"$sum": {"$ifNull": ["$value_size", 0]}},
                    "unused": {
                        "$sum": {
                            "$cond": [{"$gt": [{"$ifNull": ["$hits", 0]}, 0]}, 0, 1]
                        }
                    },
                }
            },
        ]
        try:
            rows: List[Dict[str, Any]] = list(self._collection.aggregate(pipeline))
        except Exception as exc:
            self._log.warning("Unable to aggregate post grouping cache: %s", exc)
            return summary

        for row in rows:
            kind: str = str(row.get("_id") or KIND_CHUNK)
            summary["entries"] += int(row.get("entries", 0))
            summary["hits"] += int(row.get("hits", 0))
            summary["size"] += int(row.get("size", 0))
            summary["unused_entries"] += int(row.get("unused", 0))
            if kind == KIND_DOCUMENT:
                summary["document_entries"] = int(row.get("entries", 0))
                summary["document_hits"] = int(row.get("hits", 0))
            else:
                summary["chunk_entries"] += int(row.get("entries", 0))
                summary["chunk_hits"] += int(row.get("hits", 0))
        return summary

    def count_entries(self, owner: str, kind: str = "") -> int:
        query: Dict[str, Any] = {"owner": owner}
        if kind:
            query["kind"] = kind
        try:
            return int(self._collection.count_documents(query))
        except Exception as exc:
            self._log.warning("Unable to count post grouping cache: %s", exc)
            return 0

    def find_entries(
        self,
        owner: str,
        kind: str = "",
        sort_by: str = "hits",
        descending: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List entries enriched with age and hit rate for the management page."""
        query: Dict[str, Any] = {"owner": owner}
        if kind:
            query["kind"] = kind
        if sort_by not in SORTABLE_FIELDS:
            sort_by = "hits"

        now: float = time.time()
        # Age and hit rate are computed by the server so that sorting and paging
        # agree with each other.
        pipeline: List[Dict[str, Any]] = [
            {"$match": query},
            {
                "$addFields": {
                    "age_days": {
                        "$max": [
                            0,
                            {
                                "$divide": [
                                    {"$subtract": [now, {"$ifNull": ["$created_at", now]}]},
                                    86400,
                                ]
                            },
                        ]
                    }
                }
            },
            {
                "$addFields": {
                    "hits_per_day": {
                        "$divide": [
                            {"$ifNull": ["$hits", 0]},
                            {"$max": [1, "$age_days"]},
                        ]
                    }
                }
            },
            {"$sort": {sort_by: -1 if descending else 1, "key": 1}},
            {"$skip": max(0, skip)},
            {"$limit": max(1, limit)},
            {"$project": {"value": 0}},
        ]
        try:
            entries: List[Dict[str, Any]] = list(self._collection.aggregate(pipeline))
        except Exception as exc:
            self._log.warning("Unable to list post grouping cache: %s", exc)
            return []

        for entry in entries:
            entry["key"] = str(entry.get("key", ""))
            entry["hits"] = int(entry.get("hits", 0))
            entry["age_days"] = round(float(entry.get("age_days", 0.0)), 3)
            entry["hits_per_day"] = round(float(entry.get("hits_per_day", 0.0)), 3)
        return entries

    def delete_keys(self, owner: str, keys: List[str]) -> int:
        clean_keys: List[str] = [str(key) for key in keys if key]
        if not clean_keys:
            return 0
        try:
            result: Any = self._collection.delete_many(
                {"owner": owner, "key": {"$in": clean_keys}}
            )
        except Exception as exc:
            self._log.error("Unable to delete post grouping cache entries: %s", exc)
            return 0
        return int(result.deleted_count)

    def purge(
        self,
        owner: str,
        max_hits: int = 0,
        older_than_days: float = 0.0,
        kind: str = "",
    ) -> int:
        """Drop low value entries: at most ``max_hits`` hits and old enough."""
        query: Dict[str, Any] = {
            "owner": owner,
            "hits": {"$lte": max(0, int(max_hits))},
        }
        if kind:
            query["kind"] = kind
        if older_than_days > 0:
            query["created_at"] = {"$lte": time.time() - older_than_days * 86400.0}
        try:
            result: Any = self._collection.delete_many(query)
        except Exception as exc:
            self._log.error("Unable to purge post grouping cache: %s", exc)
            return 0
        deleted: int = int(result.deleted_count)
        logging.info(
            "Purged %d post grouping cache entries for %s (max_hits=%s, older_than_days=%s)",
            deleted,
            owner,
            max_hits,
            older_than_days,
        )
        return deleted

    def clear(self, owner: str, kind: str = "") -> int:
        query: Dict[str, Any] = {"owner": owner}
        if kind:
            query["kind"] = kind
        try:
            result: Any = self._collection.delete_many(query)
        except Exception as exc:
            self._log.error("Unable to clear post grouping cache: %s", exc)
            return 0
        return int(result.deleted_count)
