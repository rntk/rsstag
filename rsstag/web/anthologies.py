"""Anthology web handlers."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional

from werkzeug.wrappers import Request, Response

from rsstag.read_state import ReadStateService
from rsstag.tasks import TASK_ANTHOLOGY

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication


def _parse_create_payload(rqst: Request) -> Dict[str, Any]:
    payload: Dict[str, Any] = rqst.get_json(silent=True) or {}
    if payload:
        return payload

    scope_mode = str(rqst.form.get("scope_mode", "all")).strip() or "all"
    return {
        "seed_type": rqst.form.get("seed_type", "tag"),
        "seed_value": rqst.form.get("seed_value", ""),
        "scope": {"mode": scope_mode},
    }


def _serialize_anthology(item: Dict[str, Any]) -> Dict[str, Any]:
    title: str = ""
    result = item.get("result")
    if isinstance(result, dict):
        title = str(result.get("title", "")).strip()
    if not title:
        title = str(item.get("seed_value", "")).strip()

    return {
        "id": item.get("_id", ""),
        "seed_type": item.get("seed_type", ""),
        "seed_value": item.get("seed_value", ""),
        "scope": item.get("scope", {"mode": "all"}),
        "status": item.get("status", "pending"),
        "stale": bool(item.get("stale", False)),
        "created_at": item.get("created_at", 0),
        "updated_at": item.get("updated_at", 0),
        "current_run_id": item.get("current_run_id"),
        "title": title,
        "result": item.get("result"),
        "source_snapshot": item.get("source_snapshot"),
    }


def _get_grouping_for_post(
    app: "RSSTagApplication",
    owner: str,
    post_id: str,
    cache: dict[str, Optional[dict[str, Any]]],
) -> Optional[dict[str, Any]]:
    if post_id not in cache:
        cache[post_id] = app.db.post_grouping.find_one({"owner": owner, "post_ids": post_id})
    return cache[post_id]


def _derive_source_refs_state(
    app: "RSSTagApplication",
    owner: str,
    source_refs: Iterable[dict[str, Any]],
    cache: dict[str, Optional[dict[str, Any]]],
) -> dict[str, Any]:
    total = 0
    unread = 0
    for source_ref in source_refs:
        post_id = str(source_ref.get("post_id", "")).strip()
        sentence_indices = {
            int(index)
            for index in source_ref.get("sentence_indices", [])
            if isinstance(index, int)
        }
        if not post_id or not sentence_indices:
            continue
        grouping = _get_grouping_for_post(app, owner, post_id, cache)
        if not grouping:
            continue
        sentence_map = {
            int(sentence["number"]): sentence
            for sentence in grouping.get("sentences", [])
            if isinstance(sentence, dict) and "number" in sentence
        }
        for sentence_index in sentence_indices:
            sentence = sentence_map.get(sentence_index)
            if not sentence:
                continue
            total += 1
            if not sentence.get("read", False):
                unread += 1
    return {
        "total_sentences": total,
        "unread_sentences": unread,
        "read_sentences": max(total - unread, 0),
        "all_read": total > 0 and unread == 0,
    }


def _annotate_result_with_read_state(
    app: "RSSTagApplication",
    owner: str,
    node: dict[str, Any],
    cache: dict[str, Optional[dict[str, Any]]],
) -> dict[str, Any]:
    annotated = dict(node)
    source_refs = annotated.get("source_refs", [])
    if not isinstance(source_refs, list):
        source_refs = []
    annotated["source_refs"] = [
        {
            **source_ref,
            "read_state": _derive_source_refs_state(app, owner, [source_ref], cache),
        }
        for source_ref in source_refs
        if isinstance(source_ref, dict)
    ]
    children = annotated.get("sub_anthologies", [])
    if not isinstance(children, list):
        children = []
    annotated["sub_anthologies"] = [
        _annotate_result_with_read_state(app, owner, child, cache)
        for child in children
        if isinstance(child, dict)
    ]
    annotated["read_state"] = _derive_source_refs_state(app, owner, annotated["source_refs"], cache)
    return annotated


def _collect_source_refs(node: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    source_refs = node.get("source_refs", [])
    if isinstance(source_refs, list):
        refs.extend(ref for ref in source_refs if isinstance(ref, dict))
    for child in node.get("sub_anthologies", []):
        if isinstance(child, dict):
            refs.extend(_collect_source_refs(child))
    return refs


def _find_node_by_id(node: dict[str, Any], node_id: str) -> Optional[dict[str, Any]]:
    if str(node.get("node_id", "")).strip() == node_id:
        return node
    for child in node.get("sub_anthologies", []):
        if isinstance(child, dict):
            found = _find_node_by_id(child, node_id)
            if found:
                return found
    return None


def _resolve_read_target(result: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    kind = str(target.get("kind", "")).strip()
    if kind == "anthology":
        return _collect_source_refs(result)
    if kind == "node":
        node_id = str(target.get("node_id", "")).strip()
        node = _find_node_by_id(result, node_id) if node_id else None
        return _collect_source_refs(node) if node else []
    if kind == "topic":
        topic_path = str(target.get("topic_path", "")).strip()
        return [
            ref
            for ref in _collect_source_refs(result)
            if str(ref.get("topic_path", "")).strip() == topic_path
        ]
    if kind == "snippet":
        post_id = str(target.get("post_id", "")).strip()
        return [
            ref
            for ref in _collect_source_refs(result)
            if str(ref.get("post_id", "")).strip() == post_id
        ]
    if kind == "sentences":
        post_id = str(target.get("post_id", "")).strip()
        requested = {
            int(index)
            for index in target.get("sentence_indices", [])
            if isinstance(index, int)
        }
        if not post_id or not requested:
            return []
        resolved: list[dict[str, Any]] = []
        for source_ref in _collect_source_refs(result):
            if str(source_ref.get("post_id", "")).strip() != post_id:
                continue
            overlap = requested & {
                int(index)
                for index in source_ref.get("sentence_indices", [])
                if isinstance(index, int)
            }
            if overlap:
                resolved.append(
                    {
                        "post_id": post_id,
                        "sentence_indices": sorted(overlap),
                        "topic_path": source_ref.get("topic_path", ""),
                        "tag": source_ref.get("tag", ""),
                    }
                )
        return resolved
    return []


def _render_markdown(node: dict[str, Any], level: int = 1) -> str:
    heading = "#" * max(1, min(level, 6))
    lines = [
        f"{heading} {node.get('title', 'Anthology')}",
        "",
        str(node.get("summary", "")).strip(),
        "",
    ]
    for child in node.get("sub_anthologies", []):
        if isinstance(child, dict):
            lines.append(_render_markdown(child, level + 1))
    return "\n".join(lines).strip()


def _get_anthology_detail_payload(
    app: "RSSTagApplication", user: dict, anthology_id: str
) -> Optional[Dict[str, Any]]:
    anthology = app.anthologies.get_by_id(user["sid"], anthology_id)
    if not anthology:
        return None

    payload: Dict[str, Any] = _serialize_anthology(anthology)
    if isinstance(payload.get("result"), dict):
        payload["result"] = _annotate_result_with_read_state(
            app, user["sid"], payload["result"], {}
        )
    latest_run: Optional[Dict[str, Any]] = app.anthology_runs.get_latest_for_anthology(
        user["sid"], anthology_id
    )
    if latest_run:
        payload["latest_run"] = latest_run

    return payload


def on_anthologies_get(app: "RSSTagApplication", user: dict, rqst: Request) -> Response:
    status_filter: str = str(rqst.args.get("status", "")).strip()
    seed_value: str = str(rqst.args.get("seed_value", "")).strip()
    anthologies = [
        _serialize_anthology(item)
        for item in app.anthologies.list_by_owner(user["sid"], status=status_filter or None)
    ]
    page = app.template_env.get_template("anthologies-list.html")
    return Response(
        page.render(
            anthologies=anthologies,
            initial_seed_value=seed_value,
            user_settings=user["settings"],
            provider=user["provider"],
            support=app.config["settings"]["support"],
            version=app.config["settings"]["version"],
        ),
        mimetype="text/html",
    )


def on_anthologies_detail_get(
    app: "RSSTagApplication", user: dict, rqst: Request, anthology_id: str
) -> Response:
    anthology_payload = _get_anthology_detail_payload(app, user, anthology_id)
    if not anthology_payload:
        return Response("Anthology not found", status=404)

    page = app.template_env.get_template("anthology-detail.html")
    return Response(
        page.render(
            anthology=anthology_payload,
            detail_api_url=f"/api/anthologies/{anthology_id}",
            retry_api_url=f"/api/anthologies/{anthology_id}/retry",
            export_api_url=f"/api/anthologies/{anthology_id}/export",
            user_settings=user["settings"],
            provider=user["provider"],
            support=app.config["settings"]["support"],
            version=app.config["settings"]["version"],
        ),
        mimetype="text/html",
    )


def on_anthologies_api_list_get(
    app: "RSSTagApplication", user: dict, rqst: Request
) -> Response:
    status_filter: str = str(rqst.args.get("status", "")).strip()
    data = [
        _serialize_anthology(item)
        for item in app.anthologies.list_by_owner(user["sid"], status=status_filter or None)
    ]
    return app._json_response({"data": data})


def on_anthologies_api_create_post(
    app: "RSSTagApplication", user: dict, rqst: Request
) -> Response:
    payload = _parse_create_payload(rqst)
    seed_type: str = str(payload.get("seed_type", "tag")).strip() or "tag"
    seed_value: str = str(payload.get("seed_value", "")).strip()
    scope: Dict[str, Any] = payload.get("scope") if isinstance(payload.get("scope"), dict) else {"mode": "all"}

    if seed_type != "tag":
        return app._json_response({"error": "Only tag anthologies are supported for now"}, 400)
    if not seed_value:
        return app._json_response({"error": "seed_value is required"}, 400)

    anthology_id = app.anthologies.create(user["sid"], seed_type, seed_value, scope)
    if not anthology_id:
        return app._json_response({"error": "Failed to create anthology"}, 500)

    anthology = app.anthologies.get_by_id(user["sid"], anthology_id)
    if not anthology:
        return app._json_response({"error": "Anthology was created but could not be loaded"}, 500)

    status = str(anthology.get("status", "pending"))
    if status == "pending":
        app.tasks.add_task({"user": user["sid"], "type": TASK_ANTHOLOGY, "scope": scope})

    return app._json_response(
        {
            "data": {
                "anthology_id": anthology_id,
                "status": status,
                "anthology": _serialize_anthology(anthology),
            }
        }
    )


def on_anthologies_api_detail_get(
    app: "RSSTagApplication", user: dict, rqst: Request, anthology_id: str
) -> Response:
    payload = _get_anthology_detail_payload(app, user, anthology_id)
    if not payload:
        return app._json_response({"error": "Anthology not found"}, 404)

    return app._json_response({"data": payload})


def on_anthologies_api_run_get(
    app: "RSSTagApplication", user: dict, rqst: Request, anthology_id: str
) -> Response:
    latest_run: Optional[Dict[str, Any]] = app.anthology_runs.get_latest_for_anthology(
        user["sid"], anthology_id
    )
    if not latest_run:
        return app._json_response({"error": "Run not found"}, 404)
    return app._json_response({"data": latest_run})


def on_anthologies_api_retry_post(
    app: "RSSTagApplication", user: dict, rqst: Request, anthology_id: str
) -> Response:
    anthology = app.anthologies.get_by_id(user["sid"], anthology_id)
    if not anthology:
        return app._json_response({"error": "Anthology not found"}, 404)

    if str(anthology.get("status", "")).strip() == "processing":
        return app._json_response({"error": "Anthology is already processing"}, 400)

    app.db.anthologies.update_one(
        {"_id": app.anthologies._to_object_id(anthology_id), "owner": user["sid"]},
        {
            "$set": {
                "status": "pending",
                "updated_at": time.time(),
                "result": None,
                "current_run_id": None,
            }
        },
    )
    app.tasks.add_task(
        {
            "user": user["sid"],
            "type": TASK_ANTHOLOGY,
            "scope": anthology.get("scope", {"mode": "all"}),
        }
    )
    payload = _get_anthology_detail_payload(app, user, anthology_id)
    return app._json_response({"data": payload})


def on_anthologies_api_read_post(
    app: "RSSTagApplication", user: dict, rqst: Request, anthology_id: str
) -> Response:
    anthology = app.anthologies.get_by_id(user["sid"], anthology_id)
    if not anthology:
        return app._json_response({"error": "Anthology not found"}, 404)
    result = anthology.get("result")
    if not isinstance(result, dict):
        return app._json_response({"error": "Anthology result not ready"}, 400)

    payload = rqst.get_json(silent=True) or {}
    target = payload.get("target")
    if not isinstance(target, dict):
        return app._json_response({"error": "target is required"}, 400)

    source_refs = _resolve_read_target(result, target)
    if not source_refs:
        return app._json_response({"error": "No source refs resolved for target"}, 400)

    service = ReadStateService(
        app.posts,
        app.tags,
        app.bi_grams,
        app.letters,
        app.tasks,
        app.post_grouping,
    )
    service_result = service.mark_sentences(
        user["sid"],
        user.get("provider", ""),
        source_refs,
        bool(payload.get("readed", False)),
    )
    if not service_result.get("ok"):
        return app._json_response({"error": service_result.get("error", "Database error")}, 500)
    return on_anthologies_api_detail_get(app, user, rqst, anthology_id)


def on_anthologies_api_export_get(
    app: "RSSTagApplication", user: dict, rqst: Request, anthology_id: str
) -> Response:
    anthology = app.anthologies.get_by_id(user["sid"], anthology_id)
    if not anthology:
        return app._json_response({"error": "Anthology not found"}, 404)
    result = anthology.get("result")
    if not isinstance(result, dict):
        return app._json_response({"error": "Anthology result not ready"}, 400)

    export_format = str(rqst.args.get("format", "json")).strip().lower() or "json"
    title = str(result.get("title", anthology.get("seed_value", "anthology"))).strip() or "anthology"
    safe_title = title[:50].encode("ascii", "ignore").decode("ascii") or "anthology"
    if export_format == "markdown":
        content = _render_markdown(result) + "\n"
        mimetype = "text/markdown"
        suffix = "md"
    elif export_format == "json":
        content = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
        mimetype = "application/json"
        suffix = "json"
    else:
        return app._json_response({"error": "Unsupported export format"}, 400)

    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{anthology_id}_{safe_title}.{suffix}"'},
    )


def on_anthologies_api_delete(
    app: "RSSTagApplication", user: dict, rqst: Request, anthology_id: str
) -> Response:
    deleted = app.anthologies.delete(user["sid"], anthology_id)
    if not deleted:
        return app._json_response({"error": "Anthology not found"}, 404)

    app.anthology_runs.delete_for_anthology(user["sid"], anthology_id)
    return app._json_response({"data": "ok"})
