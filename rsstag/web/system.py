import gzip
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import rsstag.web.users as users_handlers

from werkzeug.wrappers import Request, Response
from werkzeug.utils import redirect

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication


def _json_response(payload: Dict[str, Any], status: int = 200) -> Response:
    return Response(
        json.dumps(payload, default=str),
        mimetype="application/json",
        status=status,
    )


def _delete_owner_collection(
    app: "RSSTagApplication", collection_name: str, owner: str
) -> int:
    result = app.db[collection_name].delete_many({"owner": owner})
    return int(result.deleted_count)


def _prune_owner_data(app: "RSSTagApplication", owner: str) -> Dict[str, int]:
    collection_names: List[str] = [
        "posts",
        "raw_posts",
        "raw_download_state",
        "tags",
        "bi_grams",
        "letters",
        "words",
        "post_grouping",
        "snippet_clusters",
        "topic_aliases",
        "anthologies",
        "anthology_runs",
        "llm_batch_results",
        "llm_cache",
    ]
    deleted_counts: Dict[str, int] = {}
    for collection_name in collection_names:
        deleted_counts[collection_name] = _delete_owner_collection(
            app, collection_name, owner
        )
    deleted_counts["tasks"] = _delete_tasks_for_owner(app, owner)
    app.users.update_by_sid(owner, {"in_queue": {}})
    return deleted_counts


def _delete_tasks_for_owner(app: "RSSTagApplication", owner: str) -> int:
    result = app.db.tasks.delete_many({"user": owner})
    return int(result.deleted_count)


def on_prune_data_post(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    try:
        deleted_counts: Dict[str, int] = _prune_owner_data(app, user["sid"])
        logging.info(
            "Pruned downloaded data for user %s. Deleted counts: %s",
            user["sid"],
            deleted_counts,
        )
    except Exception as e:
        logging.error(
            "Can`t prune downloaded data for user %s. Info: %s",
            user.get("sid"),
            e,
        )
        return users_handlers.on_root_get(
            app,
            user,
            ["Unable to prune downloaded data. Please check logs and try again."],
        )

    return redirect(app.routes.get_url_by_endpoint("on_root_get"))


def _prune_provider_data(
    app: "RSSTagApplication", owner: str, provider: str
) -> Dict[str, int]:
    collection_names: List[str] = ["posts", "raw_posts", "raw_download_state"]
    deleted_counts: Dict[str, int] = {}
    for collection_name in collection_names:
        result = app.db[collection_name].delete_many(
            {"owner": owner, "provider": provider}
        )
        deleted_counts[collection_name] = int(result.deleted_count)
    tasks_result = app.db.tasks.delete_many({"user": owner, "provider": provider})
    deleted_counts["tasks"] = int(tasks_result.deleted_count)
    app.users.update_by_sid(owner, {f"in_queue.{provider}": False})
    return deleted_counts


def on_provider_prune_data_post(
    app: "RSSTagApplication", user: dict, request: Request, provider: str
) -> Response:
    if provider not in app.providers:
        return redirect(app.routes.get_url_by_endpoint(endpoint="on_data_sources_get"))

    try:
        deleted_counts: Dict[str, int] = _prune_provider_data(
            app, user["sid"], provider
        )
        logging.info(
            "Pruned downloaded data for user %s, provider %s. Deleted counts: %s",
            user["sid"],
            provider,
            deleted_counts,
        )
    except Exception as e:
        logging.error(
            "Can`t prune downloaded data for user %s, provider %s. Info: %s",
            user.get("sid"),
            provider,
            e,
        )
        return users_handlers.on_provider_detail_get(
            app,
            user,
            provider,
            err=["Unable to prune downloaded data for this provider. Please check logs and try again."],
        )

    return redirect(
        app.routes.get_url_by_endpoint(
            endpoint="on_provider_detail_get", params={"provider": provider}
        )
    )


def _get_worker_token_context(
    app: "RSSTagApplication", request: Request
) -> Optional[Dict[str, str]]:
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    if not token:
        token = request.headers.get("X-Worker-Token", "").strip()

    if not token and request.is_json:
        payload = request.get_json(silent=True) or {}
        token = str(payload.get("token", "")).strip()

    if not token:
        return None

    token_doc = app.tokens.validate(token)
    if not token_doc:
        return None
    owner = token_doc.get("owner")
    token_id = token_doc.get("_id")
    if not owner or token_id is None:
        return None

    return {"owner": owner, "token_id": str(token_id)}


def on_workers_get(app: "RSSTagApplication", user: dict, _: Request) -> Response:
    workers = app.workers.get_all_workers()
    page = app.template_env.get_template("workers.html")
    return Response(
        page.render(
            workers=workers,
            user_settings=user["settings"],
            provider=user.get("provider", ""),
        ),
        mimetype="text/html",
    )


def on_workers_spawn_post(app: "RSSTagApplication", user: dict, _: Request) -> Response:
    app.workers.add_spawn_command()
    return Response(json.dumps({"success": True}), mimetype="application/json")


def on_workers_kill_post(
    app: "RSSTagApplication", user: dict, _: Request, worker_id: int
) -> Response:
    if not app.workers.is_known_worker(worker_id):
        return Response(
            json.dumps({"success": False, "error": "Unknown worker id"}),
            mimetype="application/json",
            status=404,
        )
    app.workers.add_kill_command(worker_id)
    return Response(json.dumps({"success": True}), mimetype="application/json")


def on_workers_delete_post(
    app: "RSSTagApplication", user: dict, _: Request, worker_id: int
) -> Response:
    if not app.workers.is_known_worker(worker_id):
        return Response(
            json.dumps({"success": False, "error": "Unknown worker id"}),
            mimetype="application/json",
            status=404,
        )
    deleted: bool = app.workers.delete_worker(worker_id)
    if not deleted:
        return Response(
            json.dumps({"success": False, "error": "Unable to delete worker"}),
            mimetype="application/json",
            status=500,
        )
    return Response(json.dumps({"success": True}), mimetype="application/json")


def on_statistics_get(app: "RSSTagApplication", user: dict, _: Request) -> Response:
    total_posts = app.db.posts.count_documents({"owner": user["sid"]})
    total_tokens = 0
    for post in app.db.posts.find({"owner": user["sid"]}, {"content.title": 1, "content.content": 1}):
        title = post.get("content", {}).get("title", "")
        content = post.get("content", {}).get("content", b"")
        if isinstance(content, bytes):
            content = gzip.decompress(content).decode("utf-8", "ignore")
        text = f"{title} {content}"
        total_tokens += len(text) // 4

    raw_stats = []
    try:
        pipeline = [
            {"$match": {"owner": user["sid"]}},
            {
                "$group": {
                    "_id": "$provider",
                    "total": {"$sum": 1},
                    "converted": {
                        "$sum": {
                            "$cond": [
                                {"$ifNull": ["$posts_converted", False]},
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
            {"$sort": {"_id": 1}},
        ]
        for row in app.db.raw_posts.aggregate(pipeline):
            total = row.get("total", 0)
            converted = row.get("converted", 0)
            raw_stats.append(
                {
                    "provider": row.get("_id") or "unknown",
                    "total": total,
                    "converted": converted,
                    "pending": total - converted,
                }
            )
    except Exception as e:
        logging.warning("Can`t aggregate raw_posts stats: %s", e)

    page = app.template_env.get_template("statistics.html")
    return Response(
        page.render(
            total_posts=total_posts,
            total_tokens=total_tokens,
            raw_stats=raw_stats,
            user_settings=user["settings"],
            provider=user.get("provider", ""),
        ),
        mimetype="text/html",
    )


def on_tokens_get(app: "RSSTagApplication", user: dict, _: Request) -> Response:
    tokens = list(app.tokens.get_all(user["sid"]))

    # Ensure token.expires is offset-aware (UTC) to match now()
    for token in tokens:
        if "expires" in token and token["expires"].tzinfo is None:
            token["expires"] = token["expires"].replace(tzinfo=timezone.utc)
        if "created" in token and token["created"].tzinfo is None:
            token["created"] = token["created"].replace(tzinfo=timezone.utc)

    page = app.template_env.get_template("tokens.html")
    return Response(
        page.render(
            tokens=tokens,
            now=lambda: datetime.now(timezone.utc),
            user_settings=user["settings"],
            provider=user.get("provider", ""),
        ),
        mimetype="text/html",
    )


def on_tokens_create_post(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    expires_days = int(request.form.get("expires_days", 30))
    app.tokens.create(user["sid"], expires_days)
    return redirect("/tokens")


def on_tokens_delete_post(
    app: "RSSTagApplication", user: dict, _: Request, token: str
) -> Response:
    app.tokens.delete(user["sid"], token)
    return redirect("/tokens")


def on_external_workers_claim_post(
    app: "RSSTagApplication", _: Optional[dict], request: Request
) -> Response:
    worker_ctx = _get_worker_token_context(app, request)
    if not worker_ctx:
        return _json_response({"success": False, "error": "Unauthorized"}, 401)

    task = app.tasks.claim_external_task(
        worker_ctx["owner"],
        worker_token_id=worker_ctx["token_id"],
    )
    return _json_response({"success": True, "task": task})


def on_external_workers_submit_post(
    app: "RSSTagApplication", _: Optional[dict], request: Request
) -> Response:
    worker_ctx = _get_worker_token_context(app, request)
    if not worker_ctx:
        return _json_response({"success": False, "error": "Unauthorized"}, 401)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _json_response({"success": False, "error": "Invalid JSON"}, 400)

    task_type = payload.get("task_type")
    item_id = payload.get("item_id")
    success = payload.get("success")
    result_payload = payload.get("result")
    error = payload.get("error", "")

    if not isinstance(task_type, int):
        return _json_response(
            {"success": False, "error": "task_type must be integer"},
            400,
        )
    if not isinstance(item_id, str) or not item_id.strip():
        return _json_response(
            {"success": False, "error": "item_id must be non-empty string"},
            400,
        )
    if not isinstance(success, bool):
        return _json_response(
            {"success": False, "error": "success must be boolean"},
            400,
        )
    if result_payload is not None and not isinstance(result_payload, dict):
        return _json_response(
            {"success": False, "error": "result must be object"},
            400,
        )
    if not isinstance(error, str):
        return _json_response(
            {"success": False, "error": "error must be string"},
            400,
        )

    submitted = app.tasks.submit_external_task_result(
        owner=worker_ctx["owner"],
        task_type=task_type,
        item_id=item_id.strip(),
        success=success,
        result=result_payload,
        error=error,
        worker_token_id=worker_ctx["token_id"],
    )
    if not submitted:
        return _json_response(
            {"success": False, "error": "Task submission rejected"},
            400,
        )

    return _json_response({"success": True})
