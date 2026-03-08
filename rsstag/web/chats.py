"""Chat API handlers for persistent multi-turn chat."""

import json
import logging
from typing import TYPE_CHECKING

from werkzeug.wrappers import Request, Response

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

log = logging.getLogger("chats_handlers")


def _json_response(data, status=200):
    return Response(json.dumps(data), mimetype="application/json", status=status)


def on_chats_list_get(app: "RSSTagApplication", user: dict, rqst: Request) -> Response:
    try:
        limit = int(rqst.args.get("limit", 50))
        skip = int(rqst.args.get("skip", 0))
    except (ValueError, TypeError):
        limit, skip = 50, 0
    chats = app.chats.list_chats_with_count(user["sid"], limit=limit, skip=skip)
    return _json_response({"data": chats})


def on_chats_create_post(app: "RSSTagApplication", user: dict, rqst: Request) -> Response:
    data = rqst.get_json() or {}
    title = data.get("title", "New Chat")
    context = data.get("context", None)
    chat_id = app.chats.create(user["sid"], title, context)
    if not chat_id:
        return _json_response({"error": "Failed to create chat"}, 500)
    return _json_response({"data": {"chat_id": chat_id}})


def on_chats_detail_get(app: "RSSTagApplication", user: dict, rqst: Request, chat_id: str) -> Response:
    chat = app.chats.get_by_id(user["sid"], chat_id)
    if not chat:
        return _json_response({"error": "Chat not found"}, 404)
    return _json_response({"data": chat})


def on_chats_message_post(app: "RSSTagApplication", user: dict, rqst: Request, chat_id: str) -> Response:
    data = rqst.get_json() or {}
    content = data.get("content", "").strip()
    if not content:
        return _json_response({"error": "No content"}, 400)

    chat = app.chats.get_by_id(user["sid"], chat_id)
    if not chat:
        return _json_response({"error": "Chat not found"}, 404)

    # Auto-title on first message
    if not chat.get("messages"):
        title = content[:50] + ("..." if len(content) > 50 else "")
        app.chats.rename(user["sid"], chat_id, title)

    # Append user message
    app.chats.add_message(user["sid"], chat_id, "user", content)

    # Build prompt
    context_obj = chat.get("context", {})
    context_type = context_obj.get("type", "empty")
    context_text = context_obj.get("text", "")

    system_lines = []
    if context_type != "empty" and context_text:
        system_lines.append(f"Context:\n{context_text}\n")

    history = chat.get("messages", [])
    conversation_lines = []
    for msg in history:
        role = msg.get("role", "user")
        msg_content = msg.get("content", "")
        if role == "user":
            conversation_lines.append(f"User: {msg_content}")
        else:
            conversation_lines.append(f"Assistant: {msg_content}")
    # Add current user message
    conversation_lines.append(f"User: {content}")
    conversation_lines.append("Assistant:")

    parts = system_lines + conversation_lines
    prompt = "\n".join(parts)

    try:
        response_text = app.llm.call(user["settings"], [prompt], provider_key="realtime_llm")
    except Exception as e:
        log.error("LLM call failed: %s", e)
        return _json_response({"error": "LLM error"}, 500)

    if not response_text:
        response_text = ""

    app.chats.add_message(user["sid"], chat_id, "assistant", response_text)
    return _json_response({"data": {"role": "assistant", "content": response_text}})


def on_chats_rename_post(app: "RSSTagApplication", user: dict, rqst: Request, chat_id: str) -> Response:
    data = rqst.get_json() or {}
    title = data.get("title", "").strip()
    if not title:
        return _json_response({"error": "No title"}, 400)
    ok = app.chats.rename(user["sid"], chat_id, title)
    if not ok:
        return _json_response({"error": "Chat not found"}, 404)
    return _json_response({"data": "ok"})


def on_chats_delete_post(app: "RSSTagApplication", user: dict, rqst: Request, chat_id: str) -> Response:
    ok = app.chats.delete(user["sid"], chat_id)
    if not ok:
        return _json_response({"error": "Chat not found"}, 404)
    return _json_response({"data": "ok"})


def on_chats_fork_post(app: "RSSTagApplication", user: dict, rqst: Request, chat_id: str) -> Response:
    data = rqst.get_json() or {}
    try:
        message_index = int(data.get("message_index", 0))
    except (ValueError, TypeError):
        return _json_response({"error": "Invalid message_index"}, 400)
    new_id = app.chats.fork(user["sid"], chat_id, message_index)
    if not new_id:
        return _json_response({"error": "Fork failed"}, 404)
    return _json_response({"data": {"chat_id": new_id}})


def on_chats_context_post(app: "RSSTagApplication", user: dict, rqst: Request, chat_id: str) -> Response:
    data = rqst.get_json() or {}
    context = data.get("context")
    if not isinstance(context, dict):
        return _json_response({"error": "Invalid context"}, 400)
    ok = app.chats.update_context(user["sid"], chat_id, context)
    if not ok:
        return _json_response({"error": "Chat not found"}, 404)
    return _json_response({"data": "ok"})
