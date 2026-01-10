"""Context Filter API handlers."""
import json
import logging
from typing import TYPE_CHECKING, Optional

from werkzeug.wrappers import Request, Response

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

from rsstag.context_filter import ContextFilterManager, TagContextFilter


def get_context_filter_manager(user: dict) -> ContextFilterManager:
    """Extract ContextFilterManager from user settings.

    This is a helper function used by both handlers and other modules.
    """
    filter_data = user.get("settings", {}).get("context_filter", {})
    return ContextFilterManager.from_dict(filter_data)


def on_context_filter_get(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    """GET /api/context-filter - Get current context filter state."""
    manager = get_context_filter_manager(user)
    tag_filter = manager.get_filter("tags")

    result = {
        "data": {
            "active": manager.has_active_filters(),
            "tags": tag_filter.tags if tag_filter else [],
        }
    }
    return Response(json.dumps(result), mimetype="application/json")


def on_context_filter_add_tag(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    """POST /api/context-filter/tag - Add a tag to context filter."""
    try:
        data = json.loads(request.get_data(as_text=True))
        tag = data.get("tag", "").strip()
    except (json.JSONDecodeError, AttributeError) as e:
        logging.warning("Bad context filter request: %s", e)
        return Response(
            json.dumps({"error": "Invalid request body"}),
            mimetype="application/json",
            status=400,
        )

    if not tag:
        return Response(
            json.dumps({"error": "Tag cannot be empty"}),
            mimetype="application/json",
            status=400,
        )

    # Verify tag exists in user's tags
    tag_data = app.tags.get_by_tag(user["sid"], tag)
    if not tag_data:
        return Response(
            json.dumps({"error": "Tag not found"}),
            mimetype="application/json",
            status=404,
        )

    manager = get_context_filter_manager(user)
    tag_filter = manager.get_tag_filter()
    tag_filter.add_tag(tag)

    # Save to user settings
    app.users.update_settings(user["sid"], {"context_filter": manager.to_dict()})

    return Response(
        json.dumps({"data": "ok", "tags": tag_filter.tags}),
        mimetype="application/json",
    )


def on_context_filter_remove_tag(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    """DELETE /api/context-filter/tag - Remove a tag from context filter."""
    try:
        data = json.loads(request.get_data(as_text=True))
        tag = data.get("tag", "").strip()
    except (json.JSONDecodeError, AttributeError) as e:
        logging.warning("Bad context filter request: %s", e)
        return Response(
            json.dumps({"error": "Invalid request body"}),
            mimetype="application/json",
            status=400,
        )

    manager = get_context_filter_manager(user)
    tag_filter = manager.get_filter("tags")
    tags = []
    if tag_filter:
        tag_filter.remove_tag(tag)
        tags = tag_filter.tags
        app.users.update_settings(user["sid"], {"context_filter": manager.to_dict()})

    return Response(
        json.dumps({"data": "ok", "tags": tags}),
        mimetype="application/json",
    )


def on_context_filter_clear(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    """POST /api/context-filter/clear - Clear all context filters."""
    # Clear by saving empty dict
    app.users.update_settings(user["sid"], {"context_filter": {}})

    return Response(
        json.dumps({"data": "ok", "tags": []}),
        mimetype="application/json",
    )
