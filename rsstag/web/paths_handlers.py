"""Paths API and page handlers."""

import json
import logging
from typing import TYPE_CHECKING, Any, Optional

from werkzeug.exceptions import NotFound
from werkzeug.wrappers import Request, Response

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

from rsstag.web.posts import (
    _collect_topic_snippets,
    _load_posts_for_snippets,
    _normalize_topic_filter,
    _topic_filter_label,
    _topic_matches_requested,
)

log = logging.getLogger("paths_handlers")


def _json_response(data, status=200):
    return Response(json.dumps(data, default=str), mimetype="application/json", status=status)


def _normalize_filter_values(dim: str, values: list[Any]) -> list[Any]:
    """Normalize filter values before storing them in a path document."""
    normalized_values: list[Any] = []
    for value in values:
        if dim == "topics":
            normalized_topic_value: Optional[dict[str, Any]] = _normalize_topic_filter(value)
            if not normalized_topic_value:
                continue
            if normalized_topic_value["mode"] == "topic":
                normalized_values.append(normalized_topic_value["topic"])
            else:
                normalized_values.append(normalized_topic_value)
            continue

        normalized_value: str = str(value).strip()
        if normalized_value:
            normalized_values.append(normalized_value)
    return normalized_values


def _normalize_filterset(filterset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Normalize a path filterset into a consistent storage shape."""
    normalized_filterset: dict[str, dict[str, Any]] = {}
    for dim, spec in filterset.items():
        if not isinstance(spec, dict):
            continue
        values: list[Any] = spec.get("values", [])
        if not isinstance(values, list):
            continue
        normalized_values: list[Any] = _normalize_filter_values(dim, values)
        if not normalized_values:
            continue
        normalized_filterset[dim] = {
            "values": normalized_values,
            "logic": spec.get("logic", "and"),
        }
    return normalized_filterset


def _format_filter_value(dim: str, value: Any) -> str:
    """Render a filter value for titles and chips."""
    if dim == "topics":
        label: Optional[str] = _topic_filter_label(value)
        if label:
            return label
    return str(value)


def _build_filter_chips(filterset: dict[str, Any]) -> list[dict[str, Any]]:
    """Prepare filter chips for the path template."""
    chips: list[dict[str, Any]] = []
    for dim, spec in filterset.items():
        values: list[Any] = spec.get("values", []) if isinstance(spec, dict) else []
        labels: list[str] = [_format_filter_value(dim, value) for value in values if value]
        if not labels:
            continue
        chips.append({"dim": dim, "labels": labels})
    return chips


def _decorate_paths_for_display(paths: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach pre-rendered filter chips to path docs for list/detail templates."""
    decorated_paths: list[dict[str, Any]] = []
    for path in paths:
        filterset: dict[str, Any] = path.get("filterset", {})
        exclude: dict[str, Any] = path.get("exclude", {})
        decorated_path: dict[str, Any] = dict(path)
        decorated_path["filter_chips"] = _build_filter_chips(filterset)
        decorated_path["exclude_chips"] = _build_filter_chips(exclude)
        decorated_paths.append(decorated_path)
    return decorated_paths


def _auto_title(filterset: dict, exclude: Optional[dict]) -> str:
    """Generate a human-readable title from a filterset."""
    parts: list[str] = []
    for dim in ("tags", "topics", "feeds", "categories"):
        spec: Optional[dict[str, Any]] = filterset.get(dim)
        if spec and spec.get("values"):
            labels: list[str] = [_format_filter_value(dim, value) for value in spec["values"]]
            parts.append(" & ".join(labels))
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
    paths = _decorate_paths_for_display(app.paths.list_paths(user["sid"], limit=200, skip=0))
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
    filterset = _normalize_filterset(filterset)
    if not filterset:
        return _json_response({"error": "filterset is required"}, 400)

    raw_exclude: Any = data.get("exclude") or {}
    exclude: dict[str, dict[str, Any]] = (
        _normalize_filterset(raw_exclude) if isinstance(raw_exclude, dict) else {}
    )
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


def _get_matching_post_ids(
    app: "RSSTagApplication",
    owner: str,
    filterset: dict[str, Any],
    exclude: dict[str, Any],
) -> list[str]:
    filterset_no_topics = {key: value for key, value in filterset.items() if key != "topics"}
    query = filterset_to_mongo_query(owner, filterset_no_topics, exclude)
    post_ids: list[str] = []
    for post in app.db.posts.find(query, projection={"_id": 0, "pid": 1}):
        pid: str = str(post.get("pid") or "").strip()
        if pid:
            post_ids.append(pid)

    requested_topics: list[Any] = filterset.get("topics", {}).get("values", [])
    if not requested_topics or not post_ids:
        return post_ids

    matched_post_ids: list[str] = []
    for pid in post_ids:
        grouped = app.post_grouping.get_grouped_posts(owner, [pid])
        if not grouped or not grouped.get("groups"):
            continue
        for group_name in grouped["groups"]:
            if any(_topic_matches_requested(group_name, requested) for requested in requested_topics):
                matched_post_ids.append(pid)
                break

    return matched_post_ids


def _count_path_content(
    app: "RSSTagApplication",
    owner: str,
    filterset: dict[str, Any],
    exclude: dict[str, Any],
) -> dict[str, int]:
    post_ids: list[str] = _get_matching_post_ids(app, owner, filterset, exclude)
    requested_topics: list[Any] = filterset.get("topics", {}).get("values", [])
    sentences_count: int = 0

    for pid in post_ids:
        grouped = app.post_grouping.get_grouped_posts(owner, [pid])
        if not grouped or not grouped.get("groups"):
            continue

        matched_indices: set[int] = set()
        for topic_name, indices in grouped.get("groups", {}).items():
            if requested_topics and not any(
                _topic_matches_requested(topic_name, requested) for requested in requested_topics
            ):
                continue
            matched_indices.update(int(index) for index in indices)

        if not requested_topics and not matched_indices:
            continue
        sentences_count += len(matched_indices)

    return {
        "posts_count": len(post_ids),
        "sentences_count": sentences_count,
    }


def on_path_recommendations_get(
    app: "RSSTagApplication", user: dict, request: Request, path_id: str
) -> Response:
    doc = app.paths.get_by_path_id(user["sid"], path_id)
    if not doc:
        return _json_response({"error": "Path not found"}, 404)

    groups: list[dict[str, Any]] = app.paths.get_recommendations(user["sid"], doc)
    for group in groups:
        items: list[dict[str, Any]] = group.get("items", [])
        filtered_items: list[dict[str, Any]] = []
        for item in items:
            counts: dict[str, int] = _count_path_content(
                app,
                user["sid"],
                item.get("filterset", {}),
                item.get("exclude", {}),
            )
            item["posts_count"] = counts["posts_count"]
            item["sentences_count"] = counts["sentences_count"]

            content_type: str = str(item.get("content_type", "sentences")).strip()
            if content_type == "sentences" and item["sentences_count"] <= 0:
                continue
            if content_type == "posts" and item["posts_count"] <= 0:
                continue

            item["title"] = _auto_title(
                item.get("filterset", {}),
                item.get("exclude", {}),
            )
            filtered_items.append(item)
        group["items"] = filtered_items

    groups = [group for group in groups if group.get("items")]

    return _json_response({"data": {"path_id": path_id, "groups": groups}})


def on_path_cluster_recommendations_get(
    app: "RSSTagApplication", user: dict, request: Request, path_id: str
) -> Response:
    doc = app.paths.get_by_path_id(user["sid"], path_id)
    if not doc:
        return _json_response({"error": "Path not found"}, 404)

    path_post_ids: set[str] = set(
        _get_matching_post_ids(app, user["sid"], doc.get("filterset", {}), doc.get("exclude", {}))
    )

    projection: dict[str, int] = {
        "_id": 0,
        "cluster_id": 1,
        "title": 1,
        "post_ids": 1,
        "item_count": 1,
    }
    clusters_raw = app.snippet_clusters.get_all_by_owner(user["sid"], projection=projection)

    matches: list[dict[str, Any]] = []
    for cluster in clusters_raw:
        overlap: int = len(set(cluster.get("post_ids", [])) & path_post_ids)
        if overlap <= 0:
            continue
        matches.append(
            {
                "cluster_id": cluster["cluster_id"],
                "title": cluster.get("title", f"Cluster {cluster['cluster_id']}"),
                "item_count": cluster.get("item_count", 0),
                "overlap_count": overlap,
                "link": f"/sentence-clusters/{cluster['cluster_id']}",
            }
        )

    matches.sort(key=lambda c: c["overlap_count"], reverse=True)
    matches = matches[:10]

    return _json_response({"data": {"path_id": path_id, "clusters": matches}})


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
            filter_chips=_build_filter_chips(filterset),
            exclude_chips=_build_filter_chips(exclude),
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
            filter_chips=_build_filter_chips(filterset),
            exclude_chips=_build_filter_chips(exclude),
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )
