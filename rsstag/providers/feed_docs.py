"""Shared builder for ``feeds`` documents.

Every provider stores its sources in the same ``feeds`` collection, and the
same source must always produce the same ``feed_id`` no matter which code path
created it: a posts download, a raw-to-posts conversion, or a sources-list
refresh that fetches no posts at all. Building the document in one place is
what keeps those paths from inserting two documents for one source.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from rsstag.web.routes import RSSTagRoutes


def build_feed_doc(
    owner: str,
    feed_id: Any,
    title: str,
    provider: str,
    routes: RSSTagRoutes,
    category_id: str,
    category_title: Optional[str] = None,
    origin_feed_id: Optional[Any] = None,
    favicon: str = "",
) -> Dict[str, Any]:
    """Build one feed document with the canonical string ``feed_id``."""
    stream_id: str = str(feed_id)
    if category_title is None:
        category_title = category_id

    return {
        "createdAt": datetime.now(timezone.utc),
        "title": title or stream_id,
        "owner": owner,
        "category_id": category_id,
        "feed_id": stream_id,
        "origin_feed_id": feed_id if origin_feed_id is None else origin_feed_id,
        "category_title": category_title,
        "category_local_url": routes.get_url_by_endpoint(
            endpoint="on_category_get",
            params={"quoted_category": category_id},
        ),
        "local_url": routes.get_url_by_endpoint(
            endpoint="on_feed_get", params={"quoted_feed": stream_id}
        ),
        "favicon": favicon,
        "provider": provider,
    }


def dedup_feed_docs(feeds: list) -> list:
    """Drop repeated ``feed_id`` values inside one batch, keeping the first."""
    seen: set = set()
    unique_feeds: list = []
    for feed in feeds:
        feed_id: str = str(feed.get("feed_id", ""))
        if not feed_id:
            logging.warning("Skipping feed document without feed_id: %s", feed)
            continue
        if feed_id in seen:
            continue
        seen.add(feed_id)
        unique_feeds.append(feed)
    return unique_feeds
