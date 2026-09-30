"""A keyword-in-context view with sentence-specific topic metadata."""

import logging
import re
from itertools import islice
from typing import TYPE_CHECKING, Any, Iterator
from urllib.parse import quote

from werkzeug.wrappers import Request, Response

from rsstag.snippets import strip_html_markup
from rsstag.tags_builder import TagsBuilder
from rsstag.web.posts import _get_context_tags
from rsstag.web.tag_explorer import (
    _load_result_content, _only_unread, _parse_page, _posts_on_page,
    _post_text, _sentence_source,
)

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

LOG: logging.Logger = logging.getLogger(__name__)
BUILDER: TagsBuilder = TagsBuilder()
CONTEXT_WORDS: int = 20


def _contexts(text: str, tag: str) -> Iterator[dict[str, str]]:
    """Retain original spelling and punctuation around every whole-tag match."""
    text = strip_html_markup(text)
    tokens: list[re.Match[str]] = list(re.finditer(r"\w+", text))
    words: list[str] = [token.group().casefold() for token in tokens]
    stems: list[str] = [BUILDER.process_word(word) for word in words]
    terms: list[str] = BUILDER.text2words(tag)
    normalized: list[str] = [BUILDER.process_word(term) for term in terms]
    width: int = len(terms)
    if not width:
        return
    for index in range(len(tokens) - width + 1):
        if words[index:index + width] != terms and stems[index:index + width] not in (terms, normalized):
            continue
        end: int = index + width
        left: int = max(0, index - CONTEXT_WORDS)
        right: int = min(len(tokens), end + CONTEXT_WORDS)
        start_offset: int = tokens[left].start() if left else 0
        end_offset: int = tokens[right - 1].end() if right < len(tokens) else len(text)
        yield {
            "before": ("… " if left else "") + text[start_offset:tokens[index].start()].strip(),
            "match": text[tokens[index].start():tokens[end - 1].end()],
            "after": text[tokens[end - 1].end():end_offset].strip() + (" …" if right < len(tokens) else ""),
        }


def _sentence_documents(
    app: "RSSTagApplication", user: dict[str, Any], posts: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    pids: list[str] = [str(post["pid"]) for post in posts]
    if not pids:
        return {}
    documents: list[dict[str, Any]] = app.post_grouping.get_by_post_ids(
        user["sid"], pids, projection={"_id": 0, "post_ids": 1, "sentences": 1, "groups": 1},
    )
    return {
        str(doc["post_ids"][0]): doc for doc in documents
        if len(doc.get("post_ids") or []) == 1 and str(doc["post_ids"][0]) in pids
    }


def _position_words(text: str, before: bool) -> list[dict[str, Any]]:
    """Pad context to twenty slots, numbered outward from the matching tag."""
    tokens: list[re.Match[str]] = list(re.finditer(r"\w+", text))
    words: list[str] = []
    for index, token in enumerate(tokens):
        start: int = token.start() if index else 0
        end: int = tokens[index + 1].start() if index + 1 < len(tokens) else len(text)
        words.append(re.sub(r"\s+", " ", text[start:end]).strip())
    padded: list[str] = ([""] * (CONTEXT_WORDS - len(words)) + words if before
                         else words + [""] * (CONTEXT_WORDS - len(words)))
    if not tokens:
        padded[-1 if before else 0] = text.strip()
    return [{"text": word, "position": CONTEXT_WORDS - index if before else index + 1}
            for index, word in enumerate(padded)]


def _topics(document: dict[str, Any], number: int | None) -> list[str]:
    """Never attribute another sentence's topics to this occurrence."""
    groups: Any = document.get("groups") or {}
    if number is None or not isinstance(groups, dict):
        return []
    return sorted(path for path, numbers in groups.items()
                  if isinstance(path, str) and isinstance(numbers, list) and number in numbers)


def _rows(
    posts: list[dict[str, Any]], documents: dict[str, dict[str, Any]],
    tag: str, only_unread: bool | None,
) -> Iterator[dict[str, Any]]:
    for post in posts:
        pid: str = str(post["pid"])
        document: dict[str, Any] = documents.get(pid, {})
        grouped: dict[str, list[dict[str, Any]]] = {pid: document.get("sentences") or []}
        fallback_text: str = "" if grouped[pid] else _post_text(post)
        sentences: list[dict[str, Any]] = _sentence_source(pid, fallback_text, grouped, None)
        for index, sentence in enumerate(sentences):
            if only_unread and sentence.get("read", False):
                continue
            contexts: list[dict[str, str]] = list(_contexts(str(sentence.get("text", "")), tag))
            if not contexts:
                continue
            number: int | None = sentence.get("number")
            topics: list[str] = _topics(document, number)
            for context in contexts:
                yield {
                    **context, "number": number, "topics": topics,
                    "pid": pid, "read": bool(sentence.get("read", False)),
                    "detail_key": f"{pid}:{index}", "sentence_index": index,
                    "title": (post.get("content") or {}).get("title") or "Untitled article",
                    "url": "/posts/" + quote(pid, safe=""),
                    "metadata": post.get("metadata") or {},
                }


def _detail_sentence(sentence: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": sentence.get("number"),
        "text": strip_html_markup(str(sentence.get("text", ""))),
        "read": bool(sentence.get("read", False)),
    }


def _detail_data(
    posts: list[dict[str, Any]], documents: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Store sentence text and topic membership once per matching article."""
    entries: dict[str, dict[str, Any]] = {
        row["detail_key"]: {key: row[key] for key in ("pid", "number", "topics", "sentence_index")}
        for row in rows
    }
    matching_pids: set[str] = {row["pid"] for row in rows}
    sources: dict[str, dict[str, Any]] = {}
    for post in posts:
        pid: str = str(post["pid"])
        if pid not in matching_pids:
            continue
        document: dict[str, Any] = documents.get(pid, {})
        grouped: dict[str, list[dict[str, Any]]] = {pid: document.get("sentences") or []}
        text: str = "" if grouped[pid] else _post_text(post)
        sources[pid] = {
            "title": (post.get("content") or {}).get("title") or "Untitled article",
            "url": "/posts/" + quote(pid, safe=""),
            "metadata": post.get("metadata") or {},
            "sentences": [_detail_sentence(sentence) for sentence in _sentence_source(pid, text, grouped, None)],
            "groups": document.get("groups") or {},
        }
    return {"posts": sources, "entries": entries}


def on_tag_concordance_get(
    app: "RSSTagApplication", user: dict[str, Any], request: Request, tag: str,
    dense: bool = False,
) -> Response:
    """Load only one page of article bodies and their sentence metadata."""
    try:
        page_number: int = _parse_page(request)
    except (ValueError, TypeError):
        return Response("Invalid page number.", status=400, mimetype="text/plain")
    try:
        page_size: int = min(_posts_on_page(user), 100)
        offset: int = (page_number - 1) * page_size
        candidates: Iterator[dict[str, Any]] = app.posts.get_by_tags(
            user["sid"], BUILDER.text2words(tag), _only_unread(user), {"_id": 0, "pid": 1},
            context_tags=_get_context_tags(user),
        )
        selected: list[dict[str, Any]] = list(islice(candidates, offset, offset + page_size + 1))
        posts: list[dict[str, Any]] = _load_result_content(app, user, selected[:page_size])
        documents: dict[str, dict[str, Any]] = _sentence_documents(app, user, posts)
        rows: list[dict[str, Any]] = list(_rows(posts, documents, tag, _only_unread(user)))
        if dense:
            for row in rows:
                row["before_words"] = _position_words(row["before"], before=True)
                row["after_words"] = _position_words(row["after"], before=False)
        template: Any = app.template_env.get_template("tag-context-wall.html" if dense else "tag-concordance.html")
        details: dict[str, Any] = _detail_data(posts, documents, rows)
        return Response(template.render(
            tag=tag, rows=rows, page_number=page_number, has_more=len(selected) > page_size,
            details=details,
            article_count=len(posts), user_settings=user["settings"], provider=user.get("provider", ""),
        ), mimetype="text/html")
    except Exception:
        LOG.exception("Could not load tag concordance")
        return Response("Could not load tag context. Please try again.", status=500, mimetype="text/plain")


def on_tag_context_wall_get(
    app: "RSSTagApplication", user: dict[str, Any], request: Request, tag: str,
) -> Response:
    return on_tag_concordance_get(app, user, request, tag, dense=True)
