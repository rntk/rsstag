"""Load anthology units (snippets) from posts and their post_grouping docs."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from pymongo.database import Database

from rsstag.post_grouping import RssTagPostGrouping

MAX_SNIPPETS: int = 3000
PREVIEW_CHARS: int = 240
_GROUPING_BATCH: int = 500
_POST_PROJECTION: Dict[str, bool] = {
    "pid": True,
    "feed_id": True,
    "unix_date": True,
    "content.title": True,
}

_log: logging.Logger = logging.getLogger("anthology.units")


@dataclass
class Snippet:
    """One topic group of one post_grouping doc."""

    id: str
    post_id: str
    sentence_indices: List[int]
    topic_path: str
    title: str
    feed_id: str
    date: Optional[float]
    text: str

    @property
    def vector_text(self) -> str:
        return f"{self.topic_path.replace('>', ' ')} {self.text}"

    def preview(self, limit: int = PREVIEW_CHARS) -> str:
        text: str = " ".join(self.text.split())
        return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "post_id": self.post_id,
            "sentence_indices": list(self.sentence_indices),
            "topic_path": self.topic_path,
            "title": self.title,
            "feed_id": self.feed_id,
            "date": self.date,
            "preview": self.preview(),
        }


@dataclass
class UnitsResult:
    snippets: List[Snippet] = field(default_factory=list)
    posts_in_scope: int = 0
    ungrouped_posts: int = 0


def load_units(
    db: Database,
    owner: str,
    seed_value: str,
    scope: Optional[Dict[str, Any]],
    max_snippets: int = MAX_SNIPPETS,
) -> UnitsResult:
    """Select in-scope posts and cut their groupings into snippets."""
    posts_mode: bool = isinstance(scope, dict) and scope.get("mode") == "posts"
    posts: List[Dict[str, Any]] = _load_posts(db, owner, seed_value, scope, posts_mode)
    grouping: RssTagPostGrouping = RssTagPostGrouping(db)
    docs_by_post: Dict[str, List[Dict[str, Any]]] = _load_groupings(grouping, owner, posts)
    seed: Optional[str] = None if posts_mode else seed_value.strip().casefold() or None
    result: UnitsResult = UnitsResult(posts_in_scope=len(posts))
    seen_docs: Set[str] = set()
    for post in posts:
        pid: str = str(post.get("pid"))
        docs: List[Dict[str, Any]] = docs_by_post.get(pid, [])
        if not docs:
            result.ungrouped_posts += 1
            continue
        for doc in docs:
            if len(result.snippets) >= max_snippets:
                break
            doc_key: str = str(doc.get("_id"))
            if doc_key in seen_docs:
                continue
            seen_docs.add(doc_key)
            _append_snippets(result.snippets, doc, post, seed, max_snippets)
    _log.info(
        "Anthology units for %s: posts=%d snippets=%d ungrouped=%d",
        owner, len(posts), len(result.snippets), result.ungrouped_posts,
    )
    return result


def _load_posts(
    db: Database,
    owner: str,
    seed_value: str,
    scope: Optional[Dict[str, Any]],
    posts_mode: bool,
) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = RssTagPostGrouping(db)._build_scope_post_query(owner, scope)
    if posts_mode:
        query["pid"] = {"$in": _id_variants((scope or {}).get("post_ids") or [])}
    else:
        query["tags"] = seed_value
    cursor: Iterable[Dict[str, Any]] = db.posts.find(query, projection=_POST_PROJECTION).sort(
        [("unix_date", -1), ("pid", -1)]
    )
    return [post for post in cursor if post.get("pid") is not None]


def _id_variants(values: Iterable[Any]) -> List[Any]:
    variants: List[Any] = []
    for value in values:
        if value is None or value == "":
            continue
        variants.append(str(value))
        try:
            variants.append(int(value))
        except (TypeError, ValueError):
            pass
    return variants


def _load_groupings(
    grouping: RssTagPostGrouping, owner: str, posts: List[Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    wanted: Set[str] = {str(post.get("pid")) for post in posts}
    pids: List[Any] = [post.get("pid") for post in posts]
    docs_by_post: Dict[str, List[Dict[str, Any]]] = {}
    for start in range(0, len(pids), _GROUPING_BATCH):
        batch: List[Any] = pids[start : start + _GROUPING_BATCH]
        for doc in grouping.get_by_post_ids(owner, batch):
            for post_id in doc.get("post_ids") or []:
                key: str = str(post_id)
                if key in wanted:
                    bucket: List[Dict[str, Any]] = docs_by_post.setdefault(key, [])
                    if all(existing.get("_id") != doc.get("_id") for existing in bucket):
                        bucket.append(doc)
    return docs_by_post


def _append_snippets(
    snippets: List[Snippet],
    doc: Dict[str, Any],
    post: Dict[str, Any],
    seed: Optional[str],
    max_snippets: int,
) -> None:
    candidates: List[Tuple[str, List[int], str]] = _doc_groups(doc)
    if seed:
        matching = [c for c in candidates if seed in c[0].casefold() or seed in c[2].casefold()]
        candidates = matching or candidates
    for topic_path, indices, text in candidates:
        if len(snippets) >= max_snippets:
            return
        snippets.append(_make_snippet(len(snippets), post, topic_path, indices, text))


def _doc_groups(doc: Dict[str, Any]) -> List[Tuple[str, List[int], str]]:
    texts: Dict[int, str] = {}
    for sentence in doc.get("sentences") or []:
        if isinstance(sentence, dict) and isinstance(sentence.get("number"), int):
            texts[sentence["number"]] = str(sentence.get("text") or "")
    groups: Any = doc.get("groups") or {}
    if not isinstance(groups, dict):
        return []
    result: List[Tuple[str, List[int], str]] = []
    for topic_path, raw_indices in groups.items():
        indices: List[int] = sorted({i for i in raw_indices or [] if isinstance(i, int)})
        text: str = " ".join(texts.get(i, "") for i in indices).strip()
        if indices and text:
            result.append((str(topic_path), indices, text))
    return result


def _make_snippet(
    position: int,
    post: Dict[str, Any],
    topic_path: str,
    indices: List[int],
    text: str,
) -> Snippet:
    date: Any = post.get("unix_date")
    return Snippet(
        id=f"s{position}",
        post_id=str(post.get("pid")),
        sentence_indices=indices,
        topic_path=topic_path,
        title=str((post.get("content") or {}).get("title") or ""),
        feed_id=str(post.get("feed_id") or ""),
        date=float(date) if isinstance(date, (int, float)) else None,
        text=text,
    )
