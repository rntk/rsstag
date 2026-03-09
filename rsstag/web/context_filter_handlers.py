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
    "topic": "topic",
    "subtopic": "subtopic",
}


def _iter_group_topics(app: "RSSTagApplication", owner: str):
    for topic in _collect_topic_stats(app, owner):
        yield topic


def _collect_topic_stats(app: "RSSTagApplication", owner: str) -> dict[str, int]:
    stats: dict[str, int] = {}
    for doc in app.post_grouping.get_all_by_owner(owner, projection={"groups": 1, "_id": 0}):
        groups = doc.get("groups") if isinstance(doc, dict) else None
        if not isinstance(groups, dict):
            continue
        for topic_path, sentence_indices in groups.items():
            topic = str(topic_path).strip()
            if not topic:
                continue
            count = len(sentence_indices) if isinstance(sentence_indices, list) else 0
            stats[topic] = stats.get(topic, 0) + count
    return stats


def _format_count_label(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _normalize_string_list(values) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        item = str(value).strip()
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _normalize_single_path(value) -> str:
    if not value:
        return ""
    return " > ".join(part.strip() for part in str(value).split(">") if part.strip())


def _extract_tags(filter_data: dict) -> list[str]:
    tags_data = filter_data.get("tags", {})
    if isinstance(tags_data, dict):
        return _normalize_string_list(tags_data.get("tags", []))
    if isinstance(tags_data, list):
        return _normalize_string_list(tags_data)
    return []


def _normalize_context_filter_data(filter_data: dict) -> dict:
    if not isinstance(filter_data, dict):
        return {}

    tags = _extract_tags(filter_data)

    feeds_data = filter_data.get("feeds", {})
    if isinstance(feeds_data, dict):
        feed_ids = _normalize_string_list(feeds_data.get("feed_ids") or feeds_data.get("feeds") or [])
    elif isinstance(feeds_data, list):
        feed_ids = _normalize_string_list(feeds_data)
    else:
        feed_ids = []

    categories_data = filter_data.get("categories", {})
    if isinstance(categories_data, dict):
        category_ids = _normalize_string_list(
            categories_data.get("category_ids") or categories_data.get("categories") or []
        )
    elif isinstance(categories_data, list):
        category_ids = _normalize_string_list(categories_data)
    else:
        category_ids = []

    topic_data = filter_data.get("topic", {})
    topic_path = ""
    if isinstance(topic_data, dict):
        topic_path = _normalize_single_path(topic_data.get("topic_path") or topic_data.get("topic"))
    elif isinstance(topic_data, str):
        topic_path = _normalize_single_path(topic_data)
    if not topic_path:
        topics_legacy = filter_data.get("topics", [])
        if isinstance(topics_legacy, list):
            topic_path = _normalize_single_path(topics_legacy[0] if topics_legacy else "")

    subtopic_data = filter_data.get("subtopic", {})
    subtopic_path = ""
    parent_topic_path = ""
    node = ""
    if isinstance(subtopic_data, dict):
        subtopic_path = _normalize_single_path(
            subtopic_data.get("topic_path") or subtopic_data.get("subtopic_path")
        )
        parent_topic_path = _normalize_single_path(subtopic_data.get("parent_topic_path"))
        node = str(subtopic_data.get("node") or subtopic_data.get("subtopic_node") or "").strip()
    elif isinstance(subtopic_data, str):
        subtopic_path = _normalize_single_path(subtopic_data)
    if not subtopic_path:
        subtopics_legacy = filter_data.get("subtopics", [])
        if isinstance(subtopics_legacy, list):
            subtopic_path = _normalize_single_path(subtopics_legacy[0] if subtopics_legacy else "")

    normalized = {}
    if tags:
        normalized["tags"] = {"type": "tags", "tags": tags}
    if feed_ids:
        normalized["feeds"] = {"type": "feeds", "feed_ids": feed_ids}
    if category_ids:
        normalized["categories"] = {"type": "categories", "category_ids": category_ids}
    if topic_path:
        normalized["topic"] = {"type": "topic", "topic_path": topic_path}
    if subtopic_path or parent_topic_path or node:
        normalized["subtopic"] = {
            "type": "subtopic",
            "topic_path": subtopic_path,
            "parent_topic_path": parent_topic_path,
            "node": node,
        }
    return normalized


def _get_unified_filters(filter_data: dict) -> dict:
    normalized = _normalize_context_filter_data(filter_data)
    feeds = normalized.get("feeds", {})
    categories = normalized.get("categories", {})
    topic = normalized.get("topic", {})
    subtopic = normalized.get("subtopic", {})
    return {
        "tags": _extract_tags(normalized),
        "feeds": _normalize_string_list(feeds.get("feed_ids", [])),
        "categories": _normalize_string_list(categories.get("category_ids", [])),
        "topics": [topic.get("topic_path")] if topic.get("topic_path") else [],
        "subtopics": [subtopic.get("topic_path")] if subtopic.get("topic_path") else [],
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
    elif item_type == "topic":
        requested = value.strip()
        if not any(topic == requested for topic in _iter_group_topics(app, user["sid"])):
            return Response(
                json.dumps({"error": "Topic not found"}),
                mimetype="application/json",
                status=404,
            )
    elif item_type == "subtopic":
        requested = value.strip()
        if not any(
            topic == requested and " > " in topic
            for topic in _iter_group_topics(app, user["sid"])
        ):
            return Response(
                json.dumps({"error": "Subtopic not found"}),
                mimetype="application/json",
                status=404,
            )
    return None


def on_context_filter_suggestions(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    item_type = str(request.form.get("type", "")).strip().lower()
    query = str(request.form.get("req", "")).strip().casefold()
    if item_type not in {"feed", "category", "topic", "subtopic"}:
        return Response(
            json.dumps({"error": "Unknown item type"}),
            mimetype="application/json",
            status=400,
        )
    if not query:
        return Response(json.dumps({"data": []}), mimetype="application/json", status=200)

    suggestions = []
    if item_type == "feed":
        for feed in app.feeds.get_all(
            user["sid"], projection={"_id": 0, "feed_id": 1, "title": 1}
        ):
            feed_id = str(feed.get("feed_id", "")).strip()
            feed_title = str(feed.get("title", "")).strip()
            if not feed_id:
                continue
            if query not in feed_title.casefold() and query not in feed_id.casefold():
                continue
            label = feed_title or feed_id
            suggestions.append(
                {
                    "value": feed_id,
                    "label": label,
                    "meta": feed_id if label != feed_id else "",
                }
            )
    elif item_type == "category":
        category_titles = {}
        category_counts = {}
        for feed in app.feeds.get_all(
            user["sid"], projection={"_id": 0, "category_id": 1, "category_title": 1}
        ):
            category_id = str(feed.get("category_id", "")).strip()
            if not category_id:
                continue
            category_counts[category_id] = category_counts.get(category_id, 0) + 1
            title = str(feed.get("category_title", "")).strip()
            if title:
                category_titles[category_id] = title

        for category_id, count in category_counts.items():
            label = category_titles.get(category_id) or category_id
            haystack = f"{label} {category_id}".casefold()
            if query not in haystack:
                continue
            suggestions.append(
                {
                    "value": category_id,
                    "label": label,
                    "meta": _format_count_label(count, "feed", "feeds"),
                }
            )
    else:
        topic_stats = _collect_topic_stats(app, user["sid"])
        for topic, count in topic_stats.items():
            if item_type == "subtopic" and " > " not in topic:
                continue
            if query not in topic.casefold():
                continue
            suggestions.append(
                {
                    "value": topic,
                    "label": topic,
                    "meta": _format_count_label(count, "sentence", "sentences"),
                }
            )

    normalized = {
        item["value"]: item
        for item in sorted(suggestions, key=lambda item: item["label"].casefold())
    }
    return Response(
        json.dumps({"data": list(normalized.values())[:20]}),
        mimetype="application/json",
        status=200,
    )


def get_context_filter_manager(user: dict) -> ContextFilterManager:
    """Extract ContextFilterManager from user settings.

    This is a helper function used by both handlers and other modules.
    """
    filter_data = user.get("settings", {}).get("context_filter", {})
    return ContextFilterManager.from_dict(_normalize_context_filter_data(filter_data))


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

    filter_data = _normalize_context_filter_data(user.get("settings", {}).get("context_filter", {}))
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

    filter_data = _normalize_context_filter_data(user.get("settings", {}).get("context_filter", {}))
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

    filter_data = _normalize_context_filter_data(user.get("settings", {}).get("context_filter", {}))
    filter_key = ITEM_TYPE_TO_FILTER_KEY[item_type]

    if filter_key == "tags":
        manager = ContextFilterManager.from_dict(filter_data)
        tag_filter = manager.get_tag_filter()
        tag_filter.add_tag(value)
        filter_data["tags"] = tag_filter.to_dict()
    elif filter_key == "feeds":
        values = _normalize_string_list(filter_data.get("feeds", {}).get("feed_ids", []))
        if value not in values:
            values.append(value)
        filter_data["feeds"] = {"type": "feeds", "feed_ids": values}
    elif filter_key == "categories":
        values = _normalize_string_list(filter_data.get("categories", {}).get("category_ids", []))
        if value not in values:
            values.append(value)
        filter_data["categories"] = {"type": "categories", "category_ids": values}
    elif filter_key == "topic":
        filter_data["topic"] = {"type": "topic", "topic_path": _normalize_single_path(value)}
    elif filter_key == "subtopic":
        filter_data["subtopic"] = {"type": "subtopic", "topic_path": _normalize_single_path(value)}

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

    filter_data = _normalize_context_filter_data(user.get("settings", {}).get("context_filter", {}))
    filter_key = ITEM_TYPE_TO_FILTER_KEY[item_type]

    if filter_key == "tags":
        manager = ContextFilterManager.from_dict(filter_data)
        tag_filter = manager.get_filter("tags")
        if tag_filter:
            tag_filter.remove_tag(value)
            filter_data["tags"] = tag_filter.to_dict()
    elif filter_key == "feeds":
        values = _normalize_string_list(filter_data.get("feeds", {}).get("feed_ids", []))
        if value in values:
            values.remove(value)
        filter_data["feeds"] = {"type": "feeds", "feed_ids": values}
    elif filter_key == "categories":
        values = _normalize_string_list(filter_data.get("categories", {}).get("category_ids", []))
        if value in values:
            values.remove(value)
        filter_data["categories"] = {"type": "categories", "category_ids": values}
    elif filter_key == "topic":
        topic_path = _normalize_single_path(filter_data.get("topic", {}).get("topic_path"))
        if _normalize_single_path(value) == topic_path:
            filter_data.pop("topic", None)
    elif filter_key == "subtopic":
        subtopic_path = _normalize_single_path(filter_data.get("subtopic", {}).get("topic_path"))
        if _normalize_single_path(value) == subtopic_path:
            filter_data.pop("subtopic", None)

    app.users.update_settings(user["sid"], {"context_filter": filter_data})
    user.setdefault("settings", {})["context_filter"] = filter_data

    return Response(
        json.dumps({"data": "ok", "state": _build_state_payload(user)}),
        mimetype="application/json",
    )
