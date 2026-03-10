"""Paths API and page handlers."""

import json
import logging
from typing import TYPE_CHECKING, Optional

from werkzeug.exceptions import NotFound
from werkzeug.wrappers import Request, Response

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

from rsstag.web.posts import (
    _collect_topic_snippets,
    _load_posts_for_snippets,
    _topic_matches_requested,
)

log = logging.getLogger("paths_handlers")


def _json_response(data, status=200):
    return Response(json.dumps(data, default=str), mimetype="application/json", status=status)


def _auto_title(filterset: dict, exclude: Optional[dict]) -> str:
    """Generate a human-readable title from a filterset."""
    parts = []
    for dim in ("tags", "topics", "feeds", "categories"):
        spec = filterset.get(dim)
        if spec and spec.get("values"):
            parts.append(" & ".join(spec["values"]))
    title = " + ".join(parts) if parts else "Path"
    if len(title) > 120:
        title = title[:117] + "..."
    return title


def filterset_to_mongo_query(owner: str, filterset: dict, exclude: Optional[dict]) -> dict:
    """Build a MongoDB query from a filterset + exclude spec."""
    clauses = [{"owner": owner}]
    for dim, spec in (filterset or {}).items():
        values = spec.get("values", [])
        if not values:
            continue
        logic = spec.get("logic", "and")
        if dim == "tags":
            clauses.append(
                {"tags": {"$all": values}} if logic == "and" else {"tags": {"$in": values}}
            )
        elif dim == "feeds":
            clauses.append({"feed_id": {"$in": values}})
        elif dim == "categories":
            clauses.append({"category_id": {"$in": values}})
        # topics are handled separately via post_grouping

    for dim, spec in (exclude or {}).items():
        values = spec.get("values", [])
        if not values:
            continue
        if dim == "tags":
            clauses.append({"tags": {"$nin": values}})
        elif dim == "feeds":
            clauses.append({"feed_id": {"$nin": values}})

    return {"$and": clauses} if len(clauses) > 1 else clauses[0]


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


def on_paths_list_get(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    try:
        limit = int(request.args.get("limit", 50))
        skip = int(request.args.get("skip", 0))
    except (ValueError, TypeError):
        limit, skip = 50, 0
    paths = app.paths.list_paths(user["sid"], limit=limit, skip=skip)
    return _json_response({"data": paths})


def on_paths_page_get(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    paths = app.paths.list_paths(user["sid"], limit=200, skip=0)
    page = app.template_env.get_template("paths-list.html")
    return Response(
        page.render(
            paths=paths,
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )


def on_paths_create_post(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _json_response({"error": "JSON body required"}, 400)

    content_type = str(data.get("content_type", "sentences")).strip()
    if content_type not in ("sentences", "posts"):
        return _json_response({"error": "content_type must be 'sentences' or 'posts'"}, 400)

    filterset = data.get("filterset")
    if not isinstance(filterset, dict) or not filterset:
        return _json_response({"error": "filterset is required"}, 400)

    exclude = data.get("exclude") or {}
    title = str(data.get("title", "")).strip() or _auto_title(filterset, exclude)

    doc = app.paths.create_or_get(user["sid"], content_type, filterset, exclude, title)
    if not doc:
        return _json_response({"error": "Failed to create path"}, 500)
    return _json_response({"data": doc})


def on_paths_detail_get(
    app: "RSSTagApplication", user: dict, request: Request, path_id: str
) -> Response:
    doc = app.paths.get_by_path_id(user["sid"], path_id)
    if not doc:
        return _json_response({"error": "Path not found"}, 404)
    return _json_response({"data": doc})


def on_paths_delete(
    app: "RSSTagApplication", user: dict, request: Request, path_id: str
) -> Response:
    ok = app.paths.delete(user["sid"], path_id)
    if not ok:
        return _json_response({"error": "Path not found"}, 404)
    return _json_response({"data": "ok"})


# ---------------------------------------------------------------------------
# Page endpoints
# ---------------------------------------------------------------------------


def _get_path_or_404(app: "RSSTagApplication", user: dict, request: Request, path_id: str):
    doc = app.paths.get_by_path_id(user["sid"], path_id)
    if not doc:
        return None, app.on_error(user, request, NotFound())
    return doc, None


def on_path_sentences_get(
    app: "RSSTagApplication", user: dict, request: Request, path_id: str
) -> Response:
    doc, err = _get_path_or_404(app, user, request, path_id)
    if err:
        return err

    filterset = doc.get("filterset", {})
    exclude = doc.get("exclude", {})

    # Build mongo query (excluding topics — handled via post_grouping)
    filterset_no_topics = {k: v for k, v in filterset.items() if k != "topics"}
    query = filterset_to_mongo_query(user["sid"], filterset_no_topics, exclude)

    projection = {"pid": True, "content": True, "feed_id": True, "url": True, "tags": True}
    posts_cursor = app.db.posts.find(query, projection=projection).limit(500)

    post_ids = []
    for p in posts_cursor:
        post_ids.append(str(p.get("pid") or ""))
    post_ids = [pid for pid in post_ids if pid]

    # If topics filter specified, narrow by post_grouping
    requested_topics = filterset.get("topics", {}).get("values", [])
    if requested_topics and post_ids:
        matched_post_ids = []
        for pid in post_ids:
            grouped = app.post_grouping.get_grouped_posts(user["sid"], [pid])
            if not grouped or not grouped.get("groups"):
                continue
            for group_name in grouped["groups"]:
                if any(_topic_matches_requested(group_name, t) for t in requested_topics):
                    matched_post_ids.append(pid)
                    break
        post_ids = matched_post_ids

    all_posts, combined_feed_title = _load_posts_for_snippets(app, user, post_ids)

    # Collect snippets for each requested topic (or all topics if none specified)
    requested_topic = requested_topics[0] if requested_topics else None
    topics_data = _collect_topic_snippets(app, user, post_ids, all_posts, requested_topic, None)
    sorted_topics = sorted(topics_data.items(), key=lambda x: x[0])

    page = app.template_env.get_template("path-view.html")
    return Response(
        page.render(
            path=doc,
            content_type="sentences",
            topics=sorted_topics,
            feed_title=combined_feed_title,
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )


def on_path_posts_get(
    app: "RSSTagApplication", user: dict, request: Request, path_id: str
) -> Response:
    doc, err = _get_path_or_404(app, user, request, path_id)
    if err:
        return err

    filterset = doc.get("filterset", {})
    exclude = doc.get("exclude", {})

    filterset_no_topics = {k: v for k, v in filterset.items() if k != "topics"}
    query = filterset_to_mongo_query(user["sid"], filterset_no_topics, exclude)

    projection = {"content.content": False}
    posts_cursor = list(app.db.posts.find(query, projection=projection).limit(500))

    # If topics filter, restrict to posts that have matching groups
    requested_topics = filterset.get("topics", {}).get("values", [])
    if requested_topics:
        filtered_posts = []
        for p in posts_cursor:
            pid = str(p.get("pid") or "")
            if not pid:
                continue
            grouped = app.post_grouping.get_grouped_posts(user["sid"], [pid])
            if not grouped or not grouped.get("groups"):
                continue
            for group_name in grouped["groups"]:
                if any(_topic_matches_requested(group_name, t) for t in requested_topics):
                    filtered_posts.append(p)
                    break
        posts_cursor = filtered_posts

    # Enrich with feed info
    feed_ids = list({str(p.get("feed_id", "")) for p in posts_cursor if p.get("feed_id")})
    feeds = {}
    for feed in app.feeds.get_by_feed_ids(user["sid"], feed_ids):
        feeds[feed["feed_id"]] = feed

    posts_list = []
    for p in posts_cursor:
        feed = feeds.get(p.get("feed_id"), {})
        posts_list.append({
            "pid": str(p.get("pid") or ""),
            "url": p.get("url", ""),
            "content": p.get("content", {}),
            "feed_title": feed.get("title", ""),
            "category_title": feed.get("category_title", ""),
            "date": p.get("date", ""),
            "read": p.get("read", False),
            "feed_id": str(p.get("feed_id", "")),
        })

    page = app.template_env.get_template("path-view.html")
    return Response(
        page.render(
            path=doc,
            content_type="posts",
            posts=posts_list,
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )
