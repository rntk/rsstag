"""Handlers for starting quality scans from the category page."""

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from werkzeug.wrappers import Request, Response

from rsstag.tasks import (
    SCOPE_MODE_CATEGORIES,
    SCOPE_MODE_FEEDS,
    TASK_POST_QUALITY,
)

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication


def _json_response(payload: Dict[str, Any], status: int = 200) -> Response:
    return Response(json.dumps(payload), mimetype="application/json", status=status)


def _build_scan_scope(data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    """Turn the request body into a task scope.

    Feeds win over categories when both are sent: a scope carries one mode, and
    the narrower selection is the one the user clicked most recently.
    """
    feed_ids: List[str] = [str(value) for value in data.get("feed_ids", []) if value]
    category_ids: List[str] = [
        str(value) for value in data.get("category_ids", []) if value
    ]

    if feed_ids:
        return {"mode": SCOPE_MODE_FEEDS, "feed_ids": feed_ids}, ""
    if category_ids:
        return {"mode": SCOPE_MODE_CATEGORIES, "category_ids": category_ids}, ""

    return None, "No feeds or categories selected"


def on_quality_scan_post(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    """Queue quality scoring for the selected feeds or categories."""
    try:
        data: Dict[str, Any] = json.loads(request.data or b"{}")
    except (ValueError, TypeError) as e:
        logging.warning("Bad quality scan request from %s: %s", user["sid"], e)
        return _json_response(
            {"status": "error", "message": "Invalid request body"}, status=400
        )

    scope, error = _build_scan_scope(data)
    if scope is None:
        return _json_response({"status": "error", "message": error}, status=400)

    added = app.tasks.add_task(
        {
            "user": user["sid"],
            "type": TASK_POST_QUALITY,
            "host": app.config["settings"]["host_name"],
            "provider": user.get("provider", ""),
            "scope": scope,
        }
    )
    if not added:
        logging.error("Can`t queue quality scan for %s, scope %s", user["sid"], scope)
        return _json_response(
            {"status": "error", "message": "Can`t start quality scan"}, status=500
        )

    logging.info("Queued quality scan for %s, scope %s", user["sid"], scope)
    return _json_response({"status": "success", "message": "Quality scan started"})
