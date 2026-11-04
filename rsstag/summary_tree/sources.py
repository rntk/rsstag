"""Load complete cleaned post text for numbered summary evidence."""

import gzip
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from pymongo.database import Database

from rsstag.html_cleaner import HTMLCleaner
from rsstag.summary_tree import filters as doc_filters

_POST_PROJECTION: Dict[str, bool] = {
    "_id": False,
    "pid": True,
    "feed_id": True,
    "unix_date": True,
    "url": True,
    "content.title": True,
    "content.content": True,
}

_log: logging.Logger = logging.getLogger("summary_tree.sources")


@dataclass
class SourcePost:
    pid: str
    title: str
    text: str
    feed_id: str
    url: str
    date: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "title": self.title,
            "feed_id": self.feed_id,
            "url": self.url,
            "date": self.date,
        }


def load_posts(
    db: Database, owner: str, filters: Dict[str, Any], options: Dict[str, Any]
) -> List[SourcePost]:
    """Newest matching posts, at most ``options['limit']`` of them."""
    projection: Dict[str, bool] = dict(_POST_PROJECTION)
    if doc_filters.needs_lemmas(filters):
        projection["lemmas"] = True
    query: Dict[str, Any] = doc_filters.build_query(db, owner, filters)
    cursor: Iterable[Dict[str, Any]] = db.posts.find(query, projection=projection).sort(
        [("unix_date", -1), ("pid", -1)]
    )
    posts: List[SourcePost] = []
    seen: set = set()
    for post in cursor:
        pid: str = str(post.get("pid", ""))
        if not pid or pid in seen or not doc_filters.matches_predicates(post, filters, options):
            continue
        seen.add(pid)
        posts.append(_to_source(post))
        if len(posts) >= options["limit"]:
            break
    _log.info("Summary tree sources for %s: %d posts", owner, len(posts))
    return posts


def _to_source(post: Dict[str, Any]) -> SourcePost:
    content: Dict[str, Any] = post.get("content") or {}
    return SourcePost(
        pid=str(post["pid"]),
        title=str(content.get("title") or "").strip(),
        text=html_to_text(_decode_content(post)),
        feed_id=str(post.get("feed_id") or ""),
        url=str(post.get("url") or ""),
        date=post.get("unix_date"),
    )


def _decode_content(post: Dict[str, Any]) -> str:
    payload: Any = (post.get("content") or {}).get("content")
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, (bytes, bytearray)):
        return ""
    try:
        return gzip.decompress(payload).decode("utf-8", "replace")
    except (EOFError, OSError) as exc:
        _log.warning("Can't decode content of post %s: %s", post.get("pid"), exc)
        return ""


def html_to_text(html: str) -> str:
    cleaner: HTMLCleaner = HTMLCleaner()
    try:
        cleaner.feed(html)
        cleaner.close()
    except Exception as exc:
        _log.warning("Can't clean post html: %s", exc)
        return " ".join(html.split())
    return " ".join(" ".join(cleaner.get_content()).split())

