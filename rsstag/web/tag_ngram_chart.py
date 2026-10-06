"""Tag n-gram chart: bigrams around a tag as rows, trigram words as circles."""

import logging
import re
from typing import TYPE_CHECKING, Any, Optional

from jinja2 import Template
from werkzeug.exceptions import BadRequest, InternalServerError, NotFound
from werkzeug.wrappers import Request, Response

from rsstag.web.posts import (
    _get_category_scope,
    _load_scoped_posts,
    _page_scope_labels,
    _serialize_canvas_posts,
    _tag_highlight_words,
    _tag_hierarchy_sentences,
)

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

LOG: logging.Logger = logging.getLogger(__name__)
WORD_PATTERN: str = r"[^\W_]+(?:[’'-][^\W_]+)*"
MAX_WORDS_PER_ROW: int = 200
MAX_SNIPPETS: int = 5
SNIPPET_RADIUS: int = 8


def _tokenize(text: str) -> list[re.Match[str]]:
    return list(re.finditer(WORD_PATTERN, text))


def _tag_spans(words: list[str], variants: list[list[str]]) -> list[tuple[int, int]]:
    """Return (start, end) token spans of every tag occurrence, longest form first."""
    spans: list[tuple[int, int]] = []
    index: int = 0
    while index < len(words):
        sizes: list[int] = [
            len(form) for form in variants if form and words[index : index + len(form)] == form
        ]
        if sizes:
            spans.append((index, index + max(sizes)))
            index += max(sizes)
        else:
            index += 1
    return spans


def _snippet(text: str, tokens: list[re.Match[str]], first: int, last: int) -> str:
    """Cut a short preview of the sentence around tokens[first:last]."""
    left: int = max(0, first - SNIPPET_RADIUS)
    right: int = min(len(tokens), last + SNIPPET_RADIUS)
    start: int = tokens[left].start()
    end: int = tokens[right - 1].end()
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def _trigrams(
    text: str, tag: str, variants: list[list[str]]
) -> list[tuple[str, str, str, str]]:
    """Return (bigram, outer word, trigram, snippet) for 3-word windows around the tag.

    The bigram is the tag with its adjacent word; the outer word extends it to
    a trigram, reading forward ("tag next outer") or backward ("outer prev tag").
    """
    tokens: list[re.Match[str]] = _tokenize(text)
    words: list[str] = [token.group().casefold() for token in tokens]
    tag_text: str = tag.casefold()
    result: list[tuple[str, str, str, str]] = []
    for start, end in _tag_spans(words, variants):
        if end + 1 < len(words):
            nxt, outer = words[end], words[end + 1]
            result.append(
                (f"{tag_text} {nxt}", outer, f"{tag_text} {nxt} {outer}",
                 _snippet(text, tokens, start, end + 2))
            )
        if start >= 2:
            prev, outer = words[start - 1], words[start - 2]
            result.append(
                (f"{prev} {tag_text}", outer, f"{outer} {prev} {tag_text}",
                 _snippet(text, tokens, start - 2, end))
            )
    return result


def _add_occurrence(
    rows: dict[str, dict[str, Any]],
    bigram: str,
    word: str,
    trigram: str,
    snippet: str,
    post: dict[str, Any],
) -> None:
    row: dict[str, Any] = rows.setdefault(bigram, {"bigram": bigram, "words": {}})
    item: dict[str, Any] = row["words"].setdefault(
        word,
        {"word": word, "trigram": trigram, "count": 0, "posts": set(), "snippets": []},
    )
    item["count"] += 1
    item["posts"].add(str(post.get("pid", "")))
    if len(item["snippets"]) < MAX_SNIPPETS and snippet not in item["snippets"]:
        item["snippets"].append(snippet)


def _finalize_word(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "word": item["word"],
        "trigram": item["trigram"],
        "count": item["count"],
        "posts_count": len(item["posts"]),
        "post_ids": sorted(item["posts"]),
        "snippets": item["snippets"],
    }


def _finalize_row(row: dict[str, Any]) -> dict[str, Any]:
    words: list[dict[str, Any]] = sorted(
        (_finalize_word(item) for item in row["words"].values()),
        key=lambda item: (-item["count"], item["word"]),
    )[:MAX_WORDS_PER_ROW]
    return {
        "bigram": row["bigram"],
        "count": sum(item["count"] for item in row["words"].values()),
        "words": words,
    }


def build_ngram_chart(
    app: "RSSTagApplication",
    user: dict[str, Any],
    posts: list[dict[str, Any]],
    tag: str,
    match_topic: bool = False,
    match_sentences: bool = False,
    only_unread: bool = False,
) -> list[dict[str, Any]]:
    """Group trigram words under every tag bigram, sorted by occurrence count."""
    forms: list[str] = _tag_highlight_words(app, user["sid"], tag)
    if len(tag.split()) > 1:
        forms = [form for form in forms if len(form.split()) >= len(tag.split())]
    variants: list[list[str]] = [re.findall(WORD_PATTERN, form.casefold()) for form in forms]
    rows: dict[str, dict[str, Any]] = {}
    for post in posts:
        sentences: list[dict[str, Any]] = _tag_hierarchy_sentences(
            app, user["sid"], post, tag, match_topic, match_sentences, only_unread
        )
        for sentence in sentences:
            for bigram, word, trigram, snippet in _trigrams(sentence["text"], tag, variants):
                _add_occurrence(rows, bigram, word, trigram, snippet, post)
    finalized: list[dict[str, Any]] = [_finalize_row(row) for row in rows.values()]
    finalized.sort(key=lambda row: (-row["count"], row["bigram"]))
    return finalized


def _resolve_scope(
    app: "RSSTagApplication", user: dict[str, Any], request: Request
) -> tuple[Optional[dict[str, Any]], Optional[dict[str, str]], Optional[Exception]]:
    feed_id: str = request.args.get("feed", "").strip()
    category_id: str = request.args.get("category", "").strip()
    feed: Optional[dict[str, Any]] = (
        app.feeds.get_by_feed_id(user["sid"], feed_id) if feed_id else None
    )
    if feed_id and not feed:
        return None, None, NotFound("Feed not found.")
    category: Optional[dict[str, str]] = _get_category_scope(app, user["sid"], category_id)
    if category_id and not category:
        return None, None, NotFound("Category not found.")
    return feed, category, None


def on_tag_ngram_chart_get(
    app: "RSSTagApplication", user: dict[str, Any], request: Request
) -> Response:
    """Render tag bigrams as rows with their trigram completions as circles."""
    tag: str = request.args.get("tag", "").strip()
    if not tag:
        return app.on_error(user, request, BadRequest("Select a tag to view its n-gram chart."))
    feed, category, error = _resolve_scope(app, user, request)
    if error:
        return app.on_error(user, request, error)
    match_topic: bool = request.args.get("topic", "").strip() == "1"
    match_sentences: bool = request.args.get("sentences", "").strip() == "1"
    only_unread: Optional[bool] = user["settings"].get("only_unread") or None
    projection: dict[str, bool] = {
        "_id": False, "pid": True, "url": True, "read": True,
        "content.title": True, "content.content": True, "tags": True, "feed_id": True,
    }
    try:
        posts: list[dict[str, Any]] = _load_scoped_posts(
            app, user, feed, category, tag, match_topic or match_sentences,
            True, only_unread, projection,
        )
        rows: list[dict[str, Any]] = build_ngram_chart(
            app, user, posts, tag, match_topic, match_sentences, bool(only_unread)
        )
    except Exception as exc:
        LOG.exception("Unable to build n-gram chart for tag %s: %s", tag, exc)
        return app.on_error(
            user, request, InternalServerError("The n-gram chart could not be loaded.")
        )
    page_scope, page_title = _page_scope_labels(feed, category, tag)
    page: Template = app.template_env.get_template("tag-ngram-chart.html")
    return Response(
        page.render(
            tag=tag,
            rows=rows,
            rows_json=_serialize_canvas_posts(rows),
            feed=feed,
            category=category,
            page_scope=page_scope,
            page_title=page_title,
            user_settings=user["settings"],
            provider=user.get("provider", ""),
        ),
        mimetype="text/html",
    )
