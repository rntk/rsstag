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
CONTEXT_WORDS: int = 10


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
        sentences: list[dict[str, Any]] = _sentence_source(pid, fallback_text, grouped, only_unread)
        for sentence in sentences:
            number: int | None = sentence.get("number")
            for context in _contexts(str(sentence.get("text", "")), tag):
                yield {
                    **context, "number": number, "topics": _topics(document, number),
                    "title": (post.get("content") or {}).get("title") or "Untitled article",
                    "url": "/posts/" + quote(pid, safe=""),
                    "metadata": post.get("metadata") or {},
                }


def on_tag_concordance_get(
    app: "RSSTagApplication", user: dict[str, Any], request: Request, tag: str,
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
        rows: list[dict[str, Any]] = list(_rows(
            posts, _sentence_documents(app, user, posts), tag, _only_unread(user),
        ))
        template: Any = app.template_env.get_template("tag-concordance.html")
        return Response(template.render(
            tag=tag, rows=rows, page_number=page_number, has_more=len(selected) > page_size,
            article_count=len(posts), user_settings=user["settings"], provider=user.get("provider", ""),
        ), mimetype="text/html")
    except Exception:
        LOG.exception("Could not load tag concordance")
        return Response("Could not load tag context. Please try again.", status=500, mimetype="text/plain")
