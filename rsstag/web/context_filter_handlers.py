"""Context Filter API handlers."""

import json
import logging
from typing import TYPE_CHECKING

from werkzeug.wrappers import Request, Response

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

from rsstag.context_filter import ContextFilterManager


ITEM_TYPE_TO_FILTER_KEY = {
    "tag": "tags",
    "feed": "feeds",
    "category": "categories",
    "topic": "topics",
    "subtopic": "subtopics",
}


def _extract_tags(filter_data: dict) -> list:
    tags_data = filter_data.get("tags", {})
    if isinstance(tags_data, dict):
        return tags_data.get("tags", [])
    if isinstance(tags_data, list):
        return tags_data
    return []


def _get_unified_filters(filter_data: dict) -> dict:
    return {
        "tags": _extract_tags(filter_data),
        "feeds": filter_data.get("feeds", []),
        "categories": filter_data.get("categories", []),
        "topics": filter_data.get("topics", []),
        "subtopics": filter_data.get("subtopics", []),
    }


def _build_state_payload(user: dict) -> dict:
    filter_data = user.get("settings", {}).get("context_filter", {})
    filters = _get_unified_filters(filter_data)
    active = any(filters.values())
    return {
        "active": active,
        "filters": filters,
        # Backward-compatible shortcut for existing frontend consumers.
        "tags": filters["tags"],
    }


def _parse_item_payload(request: Request) -> tuple:
    try:
        data = json.loads(request.get_data(as_text=True))
        if not isinstance(data, dict):
            raise AttributeError("Request body must be a JSON object")
    except (json.JSONDecodeError, AttributeError) as e:
        logging.warning("Bad context filter request: %s", e)
        return None, Response(
            json.dumps({"error": "Invalid request body"}),
            mimetype="application/json",
            status=400,
        )

    item_type = str(data.get("type", "")).strip().lower()
    value = str(data.get("value", "")).strip()

    if item_type not in ITEM_TYPE_TO_FILTER_KEY:
        return None, Response(
            json.dumps({"error": "Unknown item type"}),
            mimetype="application/json",
            status=400,
        )
    if not value:
        return None, Response(
            json.dumps({"error": "Value cannot be empty"}),
            mimetype="application/json",
            status=400,
        )

    return (item_type, value), None


def _validate_item_exists(app: "RSSTagApplication", user: dict, item_type: str, value: str):
    if item_type == "tag":
        if not app.tags.get_by_tag(user["sid"], value):
            return Response(
                json.dumps({"error": "Tag not found"}),
                mimetype="application/json",
                status=404,
            )
    elif item_type == "feed":
        if not app.feeds.get_by_feed_id(user["sid"], value):
            return Response(
                json.dumps({"error": "Feed not found"}),
                mimetype="application/json",
                status=404,
            )
    elif item_type == "category":
        if not next(app.feeds.get_by_category(user["sid"], value, projection={"_id": 1}), None):
            return Response(
                json.dumps({"error": "Category not found"}),
                mimetype="application/json",
                status=404,
            )
    return None


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
    result = {"data": _build_state_payload(user)}
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

    filter_data = user.get("settings", {}).get("context_filter", {}).copy()
    manager = ContextFilterManager.from_dict(filter_data)
    tag_filter = manager.get_tag_filter()
    tag_filter.add_tag(tag)
    filter_data["tags"] = tag_filter.to_dict()

    app.users.update_settings(user["sid"], {"context_filter": filter_data})

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

    filter_data = user.get("settings", {}).get("context_filter", {}).copy()
    manager = ContextFilterManager.from_dict(filter_data)
    tag_filter = manager.get_filter("tags")
    tags = []
    if tag_filter:
        tag_filter.remove_tag(tag)
        tags = tag_filter.tags
        filter_data["tags"] = tag_filter.to_dict()
        app.users.update_settings(user["sid"], {"context_filter": filter_data})

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


def on_context_filter_add_item(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    """POST /api/context-filter/item - Add typed item to context filter."""
    parsed, error = _parse_item_payload(request)
    if error:
        return error
    item_type, value = parsed

    validation_error = _validate_item_exists(app, user, item_type, value)
    if validation_error:
        return validation_error

    filter_data = user.get("settings", {}).get("context_filter", {}).copy()
    filter_key = ITEM_TYPE_TO_FILTER_KEY[item_type]

    if filter_key == "tags":
        manager = ContextFilterManager.from_dict(filter_data)
        tag_filter = manager.get_tag_filter()
        tag_filter.add_tag(value)
        filter_data["tags"] = tag_filter.to_dict()
    else:
        values = list(filter_data.get(filter_key, []))
        if value not in values:
            values.append(value)
        filter_data[filter_key] = values

    app.users.update_settings(user["sid"], {"context_filter": filter_data})
    user.setdefault("settings", {})["context_filter"] = filter_data

    return Response(
        json.dumps({"data": "ok", "state": _build_state_payload(user)}),
        mimetype="application/json",
    )


def on_context_filter_remove_item(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    """DELETE /api/context-filter/item - Remove typed item from context filter."""
    parsed, error = _parse_item_payload(request)
    if error:
        return error
    item_type, value = parsed

    filter_data = user.get("settings", {}).get("context_filter", {}).copy()
    filter_key = ITEM_TYPE_TO_FILTER_KEY[item_type]

    if filter_key == "tags":
        manager = ContextFilterManager.from_dict(filter_data)
        tag_filter = manager.get_filter("tags")
        if tag_filter:
            tag_filter.remove_tag(value)
            filter_data["tags"] = tag_filter.to_dict()
    else:
        values = list(filter_data.get(filter_key, []))
        if value in values:
            values.remove(value)
        filter_data[filter_key] = values

    app.users.update_settings(user["sid"], {"context_filter": filter_data})
    user.setdefault("settings", {})["context_filter"] = filter_data

    return Response(
        json.dumps({"data": "ok", "state": _build_state_payload(user)}),
        mimetype="application/json",
    )
