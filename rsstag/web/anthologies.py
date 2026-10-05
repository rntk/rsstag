"""Anthology web handlers.

An anthology groups sentence-range snippets of posts into clusters, and
clusters into themes. These handlers expose the stored result to the
explorer UI and enrich it with sentence-level read state that lives in the
``post_grouping`` collection.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Set, Tuple

from werkzeug.wrappers import Request, Response

from rsstag.anthologies import is_stuck
from rsstag.read_state import ReadStateService
from rsstag.tasks import TASK_ANTHOLOGY

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

log: logging.Logger = logging.getLogger("web.anthologies")

UNSORTED_ID: str = "unsorted"
READ_TARGET_KINDS: Tuple[str, ...] = ("theme", "cluster", "snippet", UNSORTED_ID)

SentenceMap = Dict[str, Dict[int, Dict[str, Any]]]
SentenceKey = Tuple[str, int]


# ---------------------------------------------------------------------------
# Payload parsing and serialization
# ---------------------------------------------------------------------------


def _scope_from_form(rqst: Request) -> Dict[str, Any]:
    feed_id: str = str(rqst.form.get("feed_id", "")).strip()
    if feed_id:
        return {"mode": "feeds", "feed_ids": [feed_id]}
    return {"mode": "all"}


def _parse_create_payload(rqst: Request) -> Dict[str, Any]:
    payload: Any = rqst.get_json(silent=True)
    if isinstance(payload, dict) and payload:
        return payload
    return {
        "seed_type": rqst.form.get("seed_type", "tag"),
        "seed_value": rqst.form.get("seed_value", ""),
        "scope": _scope_from_form(rqst),
    }


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _serialize_summary(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Light-weight anthology view for the list page."""
    result: Dict[str, Any] = _as_dict(doc.get("result"))
    return {
        "id": str(doc.get("_id", "")),
        "seed_type": doc.get("seed_type", ""),
        "seed_value": doc.get("seed_value", ""),
        "scope": doc.get("scope") or {"mode": "all"},
        "status": doc.get("status", "pending"),
        "stage": doc.get("stage"),
        "stuck": is_stuck(doc),
        "error": doc.get("error"),
        "stale": bool(doc.get("stale", False)),
        "created_at": doc.get("created_at", 0),
        "updated_at": doc.get("updated_at", 0),
        "themes_count": len(_as_list(result.get("themes"))),
        "metrics": _as_dict(result.get("metrics")),
        "has_result": bool(result),
    }


# ---------------------------------------------------------------------------
# Sentence / read-state lookups
# ---------------------------------------------------------------------------


def _snippet_post_ids(snippets: Iterable[Dict[str, Any]]) -> List[str]:
    post_ids: Set[str] = {str(s.get("post_id", "")).strip() for s in snippets}
    post_ids.discard("")
    return sorted(post_ids)


def _sentence_index(grouping: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    return {
        int(sentence["number"]): sentence
        for sentence in _as_list(grouping.get("sentences"))
        if isinstance(sentence, dict) and isinstance(sentence.get("number"), int)
    }


def _load_sentence_maps(
    app: "RSSTagApplication", owner: str, post_ids: List[str]
) -> SentenceMap:
    """Fetch post_grouping sentences for all posts with a single query."""
    if not post_ids:
        return {}
    wanted: Set[str] = set(post_ids)
    maps: SentenceMap = {}
    try:
        cursor = app.db.post_grouping.find(
            {"owner": owner, "post_ids": {"$in": post_ids}},
            projection={"_id": False, "post_ids": True, "sentences": True},
        )
        for grouping in cursor:
            index: Dict[int, Dict[str, Any]] = _sentence_index(grouping)
            for post_id in _as_list(grouping.get("post_ids")):
                if post_id in wanted and post_id not in maps:
                    maps[post_id] = index
    except Exception as exc:
        log.error("Can't load post grouping sentences for %s: %s", owner, exc)
    return maps


def _snippet_indices(snippet: Dict[str, Any]) -> List[int]:
    return [i for i in _as_list(snippet.get("sentence_indices")) if isinstance(i, int)]


def _sentence_keys(snippet_ids: Iterable[str], snippets: Dict[str, Any]) -> Set[SentenceKey]:
    keys: Set[SentenceKey] = set()
    for snippet_id in snippet_ids:
        snippet: Dict[str, Any] = _as_dict(snippets.get(snippet_id))
        post_id: str = str(snippet.get("post_id", "")).strip()
        if post_id:
            keys.update((post_id, index) for index in _snippet_indices(snippet))
    return keys


def _count_read(keys: Iterable[SentenceKey], sentence_maps: SentenceMap) -> Dict[str, int]:
    total: int = 0
    unread: int = 0
    for post_id, index in keys:
        sentence: Optional[Dict[str, Any]] = sentence_maps.get(post_id, {}).get(index)
        if sentence is None:
            continue
        total += 1
        if not sentence.get("read", False):
            unread += 1
    return {"unread": unread, "total": total}


# ---------------------------------------------------------------------------
# Result traversal
# ---------------------------------------------------------------------------


def _cluster_snippet_ids(result: Dict[str, Any], cluster_id: str) -> List[str]:
    cluster: Dict[str, Any] = _as_dict(_as_dict(result.get("clusters")).get(cluster_id))
    return [str(s) for s in _as_list(cluster.get("snippet_ids"))]


def _theme_snippet_ids(result: Dict[str, Any], theme: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for cluster_id in _as_list(theme.get("cluster_ids")):
        ids.extend(_cluster_snippet_ids(result, str(cluster_id)))
    return ids


def _find_theme(result: Dict[str, Any], theme_id: str) -> Optional[Dict[str, Any]]:
    for theme in _as_list(result.get("themes")):
        if isinstance(theme, dict) and str(theme.get("id", "")) == theme_id:
            return theme
    return None


def _unsorted_ids(result: Dict[str, Any]) -> List[str]:
    return [str(s) for s in _as_list(result.get("unsorted"))]


def _resolve_target_snippet_ids(result: Dict[str, Any], target: Dict[str, Any]) -> List[str]:
    kind: str = str(target.get("kind", "")).strip()
    target_id: str = str(target.get("id", "")).strip()
    if kind == UNSORTED_ID:
        return _unsorted_ids(result)
    if kind == "cluster":
        return _cluster_snippet_ids(result, target_id)
    if kind == "theme":
        theme: Optional[Dict[str, Any]] = _find_theme(result, target_id)
        return _theme_snippet_ids(result, theme) if theme else []
    if kind == "snippet" and target_id in _as_dict(result.get("snippets")):
        return [target_id]
    return []


def _source_refs(snippet_ids: Iterable[str], snippets: Dict[str, Any]) -> List[Dict[str, Any]]:
    by_post: Dict[str, Set[int]] = defaultdict(set)
    for post_id, index in _sentence_keys(snippet_ids, snippets):
        by_post[post_id].add(index)
    return [
        {"post_id": post_id, "sentence_indices": sorted(indices)}
        for post_id, indices in sorted(by_post.items())
    ]


# ---------------------------------------------------------------------------
# Detail payload
# ---------------------------------------------------------------------------


def _annotate_read_counts(result: Dict[str, Any], sentence_maps: SentenceMap) -> Dict[str, Any]:
    """Return a copy of result without snippets, enriched with read counts."""
    snippets: Dict[str, Any] = _as_dict(result.get("snippets"))
    clusters: Dict[str, Any] = {}
    for cluster_id, cluster in _as_dict(result.get("clusters")).items():
        keys = _sentence_keys(_cluster_snippet_ids(result, cluster_id), snippets)
        clusters[cluster_id] = {**_as_dict(cluster), "read": _count_read(keys, sentence_maps)}
    themes: List[Dict[str, Any]] = []
    for theme in _as_list(result.get("themes")):
        if isinstance(theme, dict):
            keys = _sentence_keys(_theme_snippet_ids(result, theme), snippets)
            themes.append({**theme, "read": _count_read(keys, sentence_maps)})
    unsorted_keys = _sentence_keys(_unsorted_ids(result), snippets)
    annotated: Dict[str, Any] = {k: v for k, v in result.items() if k != "snippets"}
    annotated.update(
        {
            "themes": themes,
            "clusters": clusters,
            "unsorted": _unsorted_ids(result),
            "unsorted_read": _count_read(unsorted_keys, sentence_maps),
            "total_read": _count_read(_sentence_keys(snippets.keys(), snippets), sentence_maps),
        }
    )
    return annotated


def _feed_titles_for_ids(
    app: "RSSTagApplication", owner: str, feed_ids: Iterable[str]
) -> Dict[str, str]:
    """Resolve feed ids to display titles with a single query."""
    wanted: Set[str] = {str(f).strip() for f in feed_ids if str(f).strip()}
    if not wanted:
        return {}
    try:
        feeds = app.feeds.get_all(owner, projection={"_id": False, "feed_id": True, "title": True})
        return {
            str(f.get("feed_id")): str(f.get("title") or f.get("feed_id"))
            for f in feeds
            if str(f.get("feed_id", "")) in wanted
        }
    except Exception as exc:
        log.warning("Can't load feed titles for %s: %s", owner, exc)
        return {}


def _feed_titles(app: "RSSTagApplication", owner: str, result: Dict[str, Any]) -> Dict[str, str]:
    wanted: Set[str] = set()
    for cluster in _as_dict(result.get("clusters")).values():
        wanted.update(str(f) for f in _as_list(_as_dict(cluster).get("feed_ids")))
    return _feed_titles_for_ids(app, owner, wanted)


def _snippet_feed_ids(snippets: Iterable[Dict[str, Any]]) -> List[str]:
    feed_ids: Set[str] = {str(s.get("feed_id", "")).strip() for s in snippets}
    feed_ids.discard("")
    return sorted(feed_ids)


def _post_urls(
    app: "RSSTagApplication", owner: str, post_ids: List[str]
) -> Dict[str, str]:
    """Map post ids to their source urls with a single query."""
    if not post_ids:
        return {}
    variants: List[Any] = []
    for post_id in set(post_ids):
        variants.append(post_id)
        try:
            variants.append(int(post_id))
        except (TypeError, ValueError):
            pass
    try:
        cursor = app.db.posts.find(
            {"owner": owner, "pid": {"$in": variants}},
            projection={"_id": False, "pid": True, "url": True},
        )
        return {
            str(post["pid"]): str(post.get("url") or "")
            for post in cursor
            if post.get("pid") is not None and post.get("url")
        }
    except Exception as exc:
        log.warning("Can't load post urls for %s: %s", owner, exc)
        return {}


def _build_detail_payload(
    app: "RSSTagApplication", owner: str, doc: Dict[str, Any]
) -> Dict[str, Any]:
    payload: Dict[str, Any] = _serialize_summary(doc)
    result: Dict[str, Any] = _as_dict(doc.get("result"))
    payload["result"] = None
    payload["feed_titles"] = {}
    if result:
        snippets: Dict[str, Any] = _as_dict(result.get("snippets"))
        post_ids: List[str] = _snippet_post_ids(_as_dict(s) for s in snippets.values())
        sentence_maps: SentenceMap = _load_sentence_maps(app, owner, post_ids)
        payload["result"] = _annotate_read_counts(result, sentence_maps)
        payload["feed_titles"] = _feed_titles(app, owner, result)
    return payload


def _get_detail_payload(
    app: "RSSTagApplication", owner: str, anthology_id: str
) -> Optional[Dict[str, Any]]:
    doc: Optional[Dict[str, Any]] = app.anthologies.get_by_id(owner, anthology_id)
    if not doc:
        return None
    return _build_detail_payload(app, owner, doc)


# ---------------------------------------------------------------------------
# Cluster snippets
# ---------------------------------------------------------------------------


def _snippet_with_sentences(
    snippet: Dict[str, Any],
    sentence_maps: SentenceMap,
    feed_title: str = "",
    post_url: str = "",
) -> Dict[str, Any]:
    post_map: Dict[int, Dict[str, Any]] = sentence_maps.get(str(snippet.get("post_id", "")), {})
    sentences: List[Dict[str, Any]] = [
        {
            "number": index,
            "text": str(post_map[index].get("text", "")),
            "read": bool(post_map[index].get("read", False)),
        }
        for index in _snippet_indices(snippet)
        if index in post_map
    ]
    return {
        **snippet,
        "sentences": sentences,
        "read": bool(sentences) and all(s["read"] for s in sentences),
        "feed_title": feed_title,
        "post_url": post_url,
    }


def _resolve_cluster(
    result: Dict[str, Any], cluster_id: str
) -> Tuple[bool, Optional[Dict[str, Any]], List[str]]:
    """Return (found, cluster, snippet_ids); the unsorted bucket has no cluster."""
    if cluster_id == UNSORTED_ID:
        return True, None, _unsorted_ids(result)
    cluster: Any = _as_dict(result.get("clusters")).get(cluster_id)
    if not isinstance(cluster, dict):
        return False, None, []
    return True, cluster, _cluster_snippet_ids(result, cluster_id)


def _build_cluster_payload(
    app: "RSSTagApplication", owner: str, result: Dict[str, Any], cluster_id: str
) -> Optional[Dict[str, Any]]:
    found, cluster, snippet_ids = _resolve_cluster(result, cluster_id)
    if not found:
        return None
    all_snippets: Dict[str, Any] = _as_dict(result.get("snippets"))
    snippets: List[Dict[str, Any]] = [
        all_snippets[sid] for sid in snippet_ids if isinstance(all_snippets.get(sid), dict)
    ]
    post_ids: List[str] = _snippet_post_ids(snippets)
    sentence_maps: SentenceMap = _load_sentence_maps(app, owner, post_ids)
    feed_titles: Dict[str, str] = _feed_titles_for_ids(app, owner, _snippet_feed_ids(snippets))
    post_urls: Dict[str, str] = _post_urls(app, owner, post_ids)
    enriched: List[Dict[str, Any]] = [
        _snippet_with_sentences(
            snippet,
            sentence_maps,
            feed_title=feed_titles.get(str(snippet.get("feed_id", "")), ""),
            post_url=post_urls.get(str(snippet.get("post_id", "")), ""),
        )
        for snippet in snippets
    ]
    return {
        "cluster": cluster,
        "snippets": enriched,
        "feed_titles": feed_titles,
    }


# ---------------------------------------------------------------------------
# Helpers shared by handlers
# ---------------------------------------------------------------------------


def _not_found(app: "RSSTagApplication") -> Response:
    return app._json_response({"error": "Anthology not found"}, 404)


def _enqueue(app: "RSSTagApplication", owner: str, scope: Any) -> bool:
    try:
        return bool(app.tasks.add_task({"user": owner, "type": TASK_ANTHOLOGY, "scope": scope or {"mode": "all"}}))
    except Exception as exc:
        log.exception("Can't enqueue anthology task for %s: %s", owner, exc)
        return False


def _ready_result(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    result: Any = doc.get("result")
    return result if isinstance(result, dict) and result else None


def _script_json(value: Any) -> str:
    """JSON safe to embed in a <script> block (the app's tojson filter is not)."""
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


def _list_feeds(app: "RSSTagApplication", owner: str) -> List[Dict[str, str]]:
    feeds: List[Dict[str, str]] = []
    try:
        for feed in app.feeds.get_all(owner, projection={"_id": False, "feed_id": True, "title": True}):
            feed_id: str = str(feed.get("feed_id", "")).strip()
            if feed_id:
                feeds.append({"feed_id": feed_id, "title": str(feed.get("title") or feed_id).strip()})
    except Exception as exc:
        log.warning("Can't list feeds for %s: %s", owner, exc)
    return sorted(feeds, key=lambda feed: feed["title"].casefold())


def _list_summaries(app: "RSSTagApplication", owner: str, status: str) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = app.anthologies.list_by_owner(owner, status=status or None)
    return [_serialize_summary(doc) for doc in docs]


def _parse_read_request(rqst: Request) -> Tuple[Optional[Dict[str, Any]], bool]:
    payload: Dict[str, Any] = _as_dict(rqst.get_json(silent=True))
    target: Dict[str, Any] = _as_dict(payload.get("target"))
    if str(target.get("kind", "")).strip() not in READ_TARGET_KINDS:
        return None, False
    return target, bool(payload.get("readed", True))


def _mark_read(
    app: "RSSTagApplication", user: dict, source_refs: List[Dict[str, Any]], readed: bool
) -> Dict[str, Any]:
    service: ReadStateService = ReadStateService(
        app.posts, app.tags, app.letters, app.tasks, app.post_grouping
    )
    try:
        return service.mark_sentences(user["sid"], user.get("provider", ""), source_refs, readed)
    except Exception as exc:
        log.exception("Can't mark anthology sentences for %s: %s", user["sid"], exc)
        return {"ok": False, "error": "Database error"}


# ---------------------------------------------------------------------------
# Page handlers
# ---------------------------------------------------------------------------


def on_anthologies_get(app: "RSSTagApplication", user: dict, rqst: Request) -> Response:
    status_filter: str = str(rqst.args.get("status", "")).strip()
    page = app.template_env.get_template("anthologies-list.html")
    return Response(
        page.render(
            anthologies_json=_script_json(_list_summaries(app, user["sid"], status_filter)),
            status_filter=status_filter,
            feeds=_list_feeds(app, user["sid"]),
            selected_feed_id=str(rqst.args.get("feed", "")).strip(),
            initial_seed_value=str(rqst.args.get("seed_value", "")).strip(),
            **_page_context(app, user),
        ),
        mimetype="text/html",
    )


def on_anthologies_detail_get(
    app: "RSSTagApplication", user: dict, rqst: Request, anthology_id: str
) -> Response:
    payload: Optional[Dict[str, Any]] = _get_detail_payload(app, user["sid"], anthology_id)
    if not payload:
        return Response("Anthology not found", status=404)
    page = app.template_env.get_template("anthology-detail.html")
    return Response(
        page.render(anthology=payload, anthology_json=_script_json(payload), **_page_context(app, user)),
        mimetype="text/html",
    )


# ---------------------------------------------------------------------------
# API handlers
# ---------------------------------------------------------------------------


def on_anthologies_api_list_get(app: "RSSTagApplication", user: dict, rqst: Request) -> Response:
    status_filter: str = str(rqst.args.get("status", "")).strip()
    return app._json_response({"data": _list_summaries(app, user["sid"], status_filter)})


def on_anthologies_api_create_post(app: "RSSTagApplication", user: dict, rqst: Request) -> Response:
    payload: Dict[str, Any] = _parse_create_payload(rqst)
    seed_type: str = str(payload.get("seed_type", "tag")).strip() or "tag"
    seed_value: str = str(payload.get("seed_value", "")).strip()
    scope: Dict[str, Any] = _as_dict(payload.get("scope")) or {"mode": "all"}
    if seed_type != "tag":
        return app._json_response({"error": "Only tag anthologies are supported"}, 400)
    if not seed_value:
        return app._json_response({"error": "seed_value is required"}, 400)

    anthology_id: Optional[str] = app.anthologies.create(user["sid"], seed_type, seed_value, scope)
    doc: Optional[Dict[str, Any]] = (
        app.anthologies.get_by_id(user["sid"], anthology_id) if anthology_id else None
    )
    if not doc:
        log.error("Anthology creation failed for %s (%s)", user["sid"], seed_value)
        return app._json_response({"error": "Failed to create anthology"}, 500)

    status: str = str(doc.get("status", "pending"))
    if status == "pending" and not _enqueue(app, user["sid"], doc.get("scope") or scope):
        return app._json_response({"error": "Failed to queue anthology. Please retry."}, 500)
    return app._json_response(
        {"data": {"anthology_id": anthology_id, "status": status, "anthology": _serialize_summary(doc)}}
    )


def on_anthologies_api_detail_get(
    app: "RSSTagApplication", user: dict, rqst: Request, anthology_id: str
) -> Response:
    payload: Optional[Dict[str, Any]] = _get_detail_payload(app, user["sid"], anthology_id)
    if not payload:
        return _not_found(app)
    return app._json_response({"data": payload})


def on_anthologies_api_cluster_get(
    app: "RSSTagApplication", user: dict, rqst: Request, anthology_id: str, cluster_id: str
) -> Response:
    doc: Optional[Dict[str, Any]] = app.anthologies.get_by_id(user["sid"], anthology_id)
    if not doc:
        return _not_found(app)
    result: Optional[Dict[str, Any]] = _ready_result(doc)
    if result is None:
        return app._json_response({"error": "Anthology result not ready"}, 409)
    payload: Optional[Dict[str, Any]] = _build_cluster_payload(app, user["sid"], result, cluster_id)
    if payload is None:
        return app._json_response({"error": "Cluster not found"}, 404)
    return app._json_response({"data": payload})


def on_anthologies_api_read_post(
    app: "RSSTagApplication", user: dict, rqst: Request, anthology_id: str
) -> Response:
    doc: Optional[Dict[str, Any]] = app.anthologies.get_by_id(user["sid"], anthology_id)
    if not doc:
        return _not_found(app)
    result: Optional[Dict[str, Any]] = _ready_result(doc)
    if result is None:
        return app._json_response({"error": "Anthology result not ready"}, 409)
    target, readed = _parse_read_request(rqst)
    if target is None:
        return app._json_response({"error": "A valid target is required"}, 400)

    snippet_ids: List[str] = _resolve_target_snippet_ids(result, target)
    source_refs: List[Dict[str, Any]] = _source_refs(snippet_ids, _as_dict(result.get("snippets")))
    if not source_refs:
        return app._json_response({"error": "Nothing to mark for this target"}, 400)
    outcome: Dict[str, Any] = _mark_read(app, user, source_refs, readed)
    if not outcome.get("ok"):
        return app._json_response({"error": outcome.get("error", "Database error")}, 500)
    return app._json_response({"data": _build_detail_payload(app, user["sid"], doc)})


def on_anthologies_api_retry_post(
    app: "RSSTagApplication", user: dict, rqst: Request, anthology_id: str
) -> Response:
    doc: Optional[Dict[str, Any]] = app.anthologies.get_by_id(user["sid"], anthology_id)
    if not doc:
        return _not_found(app)
    if str(doc.get("status", "")) == "processing" and not is_stuck(doc):
        return app._json_response({"error": "Anthology is already processing"}, 400)
    if not app.anthologies.reset_for_retry(user["sid"], anthology_id):
        return app._json_response({"error": "Failed to reset anthology"}, 500)
    if not _enqueue(app, user["sid"], doc.get("scope")):
        return app._json_response({"error": "Failed to queue anthology. Please retry."}, 500)
    payload: Optional[Dict[str, Any]] = _get_detail_payload(app, user["sid"], anthology_id)
    return app._json_response({"data": payload})


def on_anthologies_api_delete(
    app: "RSSTagApplication", user: dict, rqst: Request, anthology_id: str
) -> Response:
    if not app.anthologies.delete(user["sid"], anthology_id):
        return _not_found(app)
    return app._json_response({"data": "ok"})
