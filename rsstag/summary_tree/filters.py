"""Document-set filters for summary trees.

A summary tree is built over a set of posts described by a plain ``filters``
dict. Every filter kind is registered in ``FILTERS`` with a normalizer and a
Mongo query builder; kinds that need post-level checks Mongo cannot express
(e.g. multi-word entity proximity) also register a predicate. Adding a new
filter (topics, dates, providers, ...) means adding one registry entry.
"""

import gzip
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

from pymongo.database import Database

_log: logging.Logger = logging.getLogger("summary_tree.filters")

DEFAULT_WINDOW: int = 10
DEFAULT_LIMIT: int = 50
MAX_LIMIT: int = 300

Normalizer = Callable[[Any], Any]
QueryBuilder = Callable[[Database, str, Any], Optional[Dict[str, Any]]]
Predicate = Callable[[Dict[str, Any], Any, Dict[str, Any]], bool]


@dataclass(frozen=True)
class FilterSpec:
    """One filter kind: how to normalize its value and turn it into a query."""

    normalize: Normalizer
    to_query: QueryBuilder
    predicate: Optional[Predicate] = None
    needs_lemmas: bool = False


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------


def _norm_text(value: Any) -> Optional[str]:
    text: str = " ".join(str(value or "").split()).strip()
    return text or None


def _norm_str_list(value: Any) -> Optional[List[str]]:
    raw: List[Any] = value if isinstance(value, list) else [value]
    items: List[str] = sorted({str(item).strip() for item in raw if str(item or "").strip()})
    return items or None


def _norm_flag(value: Any) -> Optional[bool]:
    if isinstance(value, str):
        value = value.strip().lower() in ("1", "true", "yes", "on")
    return True if value else None


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------


def entity_words(entity: str) -> List[str]:
    return [word for word in entity.split() if word]


def _entity_query(_db: Database, _owner: str, entity: str) -> Dict[str, Any]:
    return {"tags": {"$all": entity_words(entity)}}


def _tags_query(_db: Database, _owner: str, tags: List[str]) -> Dict[str, Any]:
    return {"tags": {"$all": tags}}


def _feeds_query(_db: Database, _owner: str, feed_ids: List[str]) -> Dict[str, Any]:
    return {"feed_id": {"$in": feed_ids}}


def _categories_query(db: Database, owner: str, category_ids: List[str]) -> Dict[str, Any]:
    feeds: Iterable[Dict[str, Any]] = db.feeds.find(
        {"owner": owner, "category_id": {"$in": category_ids}}, projection={"feed_id": True}
    )
    return {"feed_id": {"$in": [feed["feed_id"] for feed in feeds if feed.get("feed_id")]}}


def id_variants(values: Iterable[Any]) -> List[Any]:
    """Post ids are stored as str or int depending on the provider."""
    variants: List[Any] = []
    for value in values:
        variants.append(str(value))
        try:
            variants.append(int(value))
        except (TypeError, ValueError):
            pass
    return variants


def _posts_query(_db: Database, _owner: str, post_ids: List[str]) -> Dict[str, Any]:
    return {"pid": {"$in": id_variants(post_ids)}}


def _unread_query(_db: Database, _owner: str, _flag: bool) -> Dict[str, Any]:
    return {"read": False}


# ---------------------------------------------------------------------------
# Post-level predicates
# ---------------------------------------------------------------------------


def decode_lemmas(post: Dict[str, Any]) -> List[str]:
    payload: Any = post.get("lemmas")
    if not isinstance(payload, (bytes, bytearray)):
        return []
    try:
        return gzip.decompress(payload).decode("utf-8", "replace").split()
    except (EOFError, OSError) as exc:
        _log.warning("Can't decode lemmas for post %s: %s", post.get("pid"), exc)
        return []


def words_within_window(lemmas: List[str], words: List[str], window: int) -> bool:
    """True when every word occurs and some occurrence of each fits in ``window``."""
    wanted: set = set(words)
    if len(wanted) <= 1:
        return True
    last_seen: Dict[str, int] = {}
    for position, lemma in enumerate(lemmas):
        if lemma not in wanted:
            continue
        last_seen[lemma] = position
        if len(last_seen) == len(wanted) and position - min(last_seen.values()) <= window:
            return True
    return False


def _entity_predicate(post: Dict[str, Any], entity: str, options: Dict[str, Any]) -> bool:
    words: List[str] = entity_words(entity)
    if len(words) <= 1:
        return True
    return words_within_window(decode_lemmas(post), words, int(options["window"]))


FILTERS: Dict[str, FilterSpec] = {
    "entity": FilterSpec(_norm_text, _entity_query, _entity_predicate, needs_lemmas=True),
    "tags": FilterSpec(_norm_str_list, _tags_query),
    "feed_ids": FilterSpec(_norm_str_list, _feeds_query),
    "category_ids": FilterSpec(_norm_str_list, _categories_query),
    "post_ids": FilterSpec(_norm_str_list, _posts_query),
    "only_unread": FilterSpec(_norm_flag, _unread_query),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _bounded_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        number: int = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def normalize_filters(raw: Any) -> Dict[str, Any]:
    """Keep only known, non-empty filters in a canonical form."""
    source: Dict[str, Any] = raw if isinstance(raw, dict) else {}
    normalized: Dict[str, Any] = {}
    for name, spec in FILTERS.items():
        value: Any = spec.normalize(source.get(name))
        if value is not None:
            normalized[name] = value
    return normalized


def normalize_options(raw: Any) -> Dict[str, Any]:
    source: Dict[str, Any] = raw if isinstance(raw, dict) else {}
    return {
        "window": _bounded_int(source.get("window"), DEFAULT_WINDOW, 1, 100),
        "limit": _bounded_int(source.get("limit"), DEFAULT_LIMIT, 1, MAX_LIMIT),
    }


def filters_hash(filters: Dict[str, Any], options: Dict[str, Any]) -> str:
    payload: str = json.dumps({"f": filters, "o": options}, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def build_query(db: Database, owner: str, filters: Dict[str, Any]) -> Dict[str, Any]:
    """AND all active filter fragments into one posts query."""
    parts: List[Dict[str, Any]] = []
    for name, value in filters.items():
        spec: Optional[FilterSpec] = FILTERS.get(name)
        fragment: Optional[Dict[str, Any]] = spec.to_query(db, owner, value) if spec else None
        if fragment:
            parts.append(fragment)
    query: Dict[str, Any] = {"owner": owner}
    if parts:
        query["$and"] = parts
    return query


def needs_lemmas(filters: Dict[str, Any]) -> bool:
    return any(FILTERS[name].needs_lemmas for name in filters if name in FILTERS)


def matches_predicates(
    post: Dict[str, Any], filters: Dict[str, Any], options: Dict[str, Any]
) -> bool:
    for name, value in filters.items():
        spec: Optional[FilterSpec] = FILTERS.get(name)
        if spec and spec.predicate and not spec.predicate(post, value, options):
            return False
    return True


def describe(filters: Dict[str, Any]) -> str:
    """Short human label of a filter set."""
    parts: List[str] = []
    if filters.get("entity"):
        parts.append(str(filters["entity"]))
    for name in ("tags", "feed_ids", "category_ids", "post_ids"):
        if filters.get(name):
            parts.append(f"{name.replace('_ids', '')}: {', '.join(filters[name][:3])}")
    if filters.get("only_unread"):
        parts.append("unread")
    return " · ".join(parts) or "all posts"
