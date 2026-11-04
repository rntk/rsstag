"""Summary tree web handlers: list/form page, tree canvas page and JSON API."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from urllib.parse import quote

from werkzeug.utils import redirect
from werkzeug.wrappers import Request, Response

from rsstag.summary_tree.filters import describe, normalize_filters, normalize_options
from rsstag.summary_trees import STAGES, STATUS_PENDING, STATUS_PROCESSING, is_stuck
from rsstag.tasks import TASK_SUMMARY_TREE

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

log: logging.Logger = logging.getLogger("web.summary_tree")


# ---------------------------------------------------------------------------
# Parsing / serialization
# ---------------------------------------------------------------------------


def _split_csv(value: str) -> List[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def filters_from_args(rqst: Request, user: dict) -> Dict[str, Any]:
    """Query-string filters (``?tag=x&tags=a,b&feed=..&category=..&unread=1``)."""
    args = rqst.args
    unread: Optional[str] = args.get("unread")
    return {
        "entity": args.get("tag") or args.get("entity") or "",
        "tags": _split_csv(args.get("tags", "")),
        "feed_ids": args.getlist("feed"),
        "category_ids": args.getlist("category"),
        "post_ids": _split_csv(args.get("posts", "")),
        "only_unread": bool(user["settings"].get("only_unread")) if unread is None else unread,
    }


def options_from_args(rqst: Request) -> Dict[str, Any]:
    return {"window": rqst.args.get("window"), "limit": rqst.args.get("limit")}


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def serialize_summary(doc: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = _as_dict(doc.get("result"))
    filters: Dict[str, Any] = _as_dict(doc.get("filters"))
    return {
        "id": str(doc.get("_id", "")),
        "focus": doc.get("focus", ""),
        "filters": filters,
        "filters_label": describe(filters),
        "options": _as_dict(doc.get("options")),
        "status": doc.get("status", STATUS_PENDING),
        "stage": doc.get("stage"),
        "stages": list(STAGES),
        "progress": _as_dict(doc.get("progress")),
        "stuck": is_stuck(doc),
        "error": doc.get("error"),
        "created_at": doc.get("created_at", 0),
        "updated_at": doc.get("updated_at", 0),
        "metrics": _as_dict(result.get("metrics")),
    }


def _feed_titles(app: "RSSTagApplication", owner: str, feed_ids: List[str]) -> Dict[str, str]:
    titles: Dict[str, str] = {}
    if not feed_ids:
        return titles
    try:
        for feed in app.feeds.get_by_feed_ids(owner, feed_ids):
            titles[str(feed.get("feed_id"))] = str(feed.get("title") or "")
    except Exception as exc:
        log.warning("Can't load feed titles for %s: %s", owner, exc)
    return titles


def _result_payload(app: "RSSTagApplication", owner: str, result: Dict[str, Any]) -> Dict[str, Any]:
    posts: List[Dict[str, Any]] = [p for p in result.get("posts") or [] if isinstance(p, dict)]
    titles: Dict[str, str] = _feed_titles(app, owner, sorted({str(p.get("feed_id")) for p in posts}))
    by_pid: Dict[str, Dict[str, Any]] = {}
    for post in posts:
        pid: str = str(post.get("pid"))
        by_pid[pid] = {**post, "feed_title": titles.get(str(post.get("feed_id")), "")}
    return {
        "schema_version": result.get("schema_version", 1),
        "root_id": result.get("root_id"),
        "converged": bool(result.get("converged")),
        "nodes": _as_dict(result.get("nodes")),
        "posts": by_pid,
        "skipped": result.get("skipped") or [],
    }


def detail_payload(app: "RSSTagApplication", owner: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = serialize_summary(doc)
    result: Dict[str, Any] = _as_dict(doc.get("result"))
    payload["result"] = _result_payload(app, owner, result) if result else None
    return payload


def _script_json(value: Any) -> str:
    """JSON safe to embed in a <script> block."""
    text: str = json.dumps(value, default=str)
    for char, escaped in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"), ("'", "\\u0027")):
        text = text.replace(char, escaped)
    return text


def _page_context(app: "RSSTagApplication", user: dict) -> Dict[str, Any]:
    return {
        "user_settings": user["settings"],
        "provider": user.get("provider", ""),
        "support": app.config["settings"]["support"],
        "version": app.config["settings"]["version"],
    }


def _enqueue(app: "RSSTagApplication", owner: str) -> bool:
    try:
        return bool(app.tasks.add_task({"user": owner, "type": TASK_SUMMARY_TREE}))
    except Exception as exc:
        log.exception("Can't enqueue summary tree task for %s: %s", owner, exc)
        return False


def _not_found(app: "RSSTagApplication") -> Response:
    return app._json_response({"error": "Summary tree not found"}, 404)


def _detail_url(tree_id: str) -> str:
    return f"/summary-tree/{quote(tree_id)}"


def _render(app: "RSSTagApplication", user: dict, **context: Any) -> Response:
    page = app.template_env.get_template("summary-tree.html")
    return Response(page.render(**context, **_page_context(app, user)), mimetype="text/html")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def on_summary_tree_get(app: "RSSTagApplication", user: dict, rqst: Request) -> Response:
    """List + build form; an existing tree for the query's filters opens directly."""
    filters: Dict[str, Any] = normalize_filters(filters_from_args(rqst, user))
    options: Dict[str, Any] = normalize_options(options_from_args(rqst))
    if filters.get("entity"):
        existing: Optional[Dict[str, Any]] = app.summary_trees.find(user["sid"], filters, options)
        if existing:
            return redirect(_detail_url(existing["_id"]))
    trees: List[Dict[str, Any]] = [
        serialize_summary(doc) for doc in app.summary_trees.list_by_owner(user["sid"])
    ]
    page_data: Dict[str, Any] = {"mode": "list", "trees": trees, "draft": {"filters": filters, "options": options}}
    return _render(app, user, page_title="Summary trees", page_json=_script_json(page_data))


def on_summary_tree_detail_get(
    app: "RSSTagApplication", user: dict, rqst: Request, tree_id: str
) -> Response:
    doc: Optional[Dict[str, Any]] = app.summary_trees.get_by_id(user["sid"], tree_id)
    if not doc:
        return Response("Summary tree not found", status=404)
    page_data: Dict[str, Any] = {"mode": "detail", "tree": detail_payload(app, user["sid"], doc)}
    return _render(app, user, page_title=doc.get("focus") or "Summary tree", page_json=_script_json(page_data))


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def on_summary_trees_api_list_get(app: "RSSTagApplication", user: dict, rqst: Request) -> Response:
    trees: List[Dict[str, Any]] = [
        serialize_summary(doc) for doc in app.summary_trees.list_by_owner(user["sid"])
    ]
    return app._json_response({"data": trees})


def on_summary_trees_api_create_post(app: "RSSTagApplication", user: dict, rqst: Request) -> Response:
    payload: Dict[str, Any] = _as_dict(rqst.get_json(silent=True))
    filters: Dict[str, Any] = normalize_filters(payload.get("filters"))
    if not filters.get("entity"):
        return app._json_response({"error": "filters.entity is required"}, 400)
    tree_id: Optional[str] = app.summary_trees.create(user["sid"], filters, payload.get("options"))
    doc: Optional[Dict[str, Any]] = app.summary_trees.get_by_id(user["sid"], tree_id) if tree_id else None
    if not doc:
        log.error("Summary tree creation failed for %s", user["sid"])
        return app._json_response({"error": "Failed to create summary tree"}, 500)
    if doc.get("status") == STATUS_PENDING and not _enqueue(app, user["sid"]):
        return app._json_response({"error": "Failed to queue summary tree. Please retry."}, 500)
    return app._json_response(
        {"data": {"tree_id": doc["_id"], "url": _detail_url(doc["_id"]), "tree": serialize_summary(doc)}}
    )


def on_summary_trees_api_detail_get(
    app: "RSSTagApplication", user: dict, rqst: Request, tree_id: str
) -> Response:
    doc: Optional[Dict[str, Any]] = app.summary_trees.get_by_id(user["sid"], tree_id)
    if not doc:
        return _not_found(app)
    return app._json_response({"data": detail_payload(app, user["sid"], doc)})


def on_summary_trees_api_retry_post(
    app: "RSSTagApplication", user: dict, rqst: Request, tree_id: str
) -> Response:
    doc: Optional[Dict[str, Any]] = app.summary_trees.get_by_id(user["sid"], tree_id)
    if not doc:
        return _not_found(app)
    if doc.get("status") == STATUS_PROCESSING and not is_stuck(doc):
        return app._json_response({"error": "Summary tree is already processing"}, 400)
    if not app.summary_trees.reset_for_retry(user["sid"], tree_id):
        return app._json_response({"error": "Failed to reset summary tree"}, 500)
    if not _enqueue(app, user["sid"]):
        return app._json_response({"error": "Failed to queue summary tree. Please retry."}, 500)
    fresh: Optional[Dict[str, Any]] = app.summary_trees.get_by_id(user["sid"], tree_id)
    return app._json_response({"data": detail_payload(app, user["sid"], fresh or doc)})


def on_summary_trees_api_delete(
    app: "RSSTagApplication", user: dict, rqst: Request, tree_id: str
) -> Response:
    if not app.summary_trees.delete(user["sid"], tree_id):
        return _not_found(app)
    return app._json_response({"data": "ok"})
