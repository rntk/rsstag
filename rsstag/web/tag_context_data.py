"""Load scoped sentences for the tag context chart with batched lookups."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from rsstag.web.posts import _post_scope_sentences, _tag_highlight_words
from rsstag.web.tag_context_stats import (
    context_words,
    split_sentences,
    tag_spans,
    tag_variants,
    tokenize,
)

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

LOG: logging.Logger = logging.getLogger(__name__)
GROUPING_BATCH: int = 500


@dataclass(frozen=True)
class Sentence:
    """One sentence with its owner post, tag spans and context words."""

    post_id: str
    feed_id: str
    text: str
    words: tuple[str, ...]
    spans: tuple[tuple[int, int], ...]

    @property
    def context(self) -> list[str]:
        return context_words(list(self.words), list(self.spans))


@dataclass(frozen=True)
class SentenceScope:
    """Inputs that decide which sentences of a post are in scope."""

    tag: str
    variants: list[list[str]]
    match_topic: bool = False
    match_sentences: bool = False
    only_unread: bool = False


def scope_for_tag(
    app: "RSSTagApplication",
    owner: str,
    tag: str,
    match_topic: bool,
    match_sentences: bool,
    only_unread: bool,
) -> SentenceScope:
    """Collect stored surface forms; multiword tags only match whole phrases."""
    forms: list[str] = _tag_highlight_words(app, owner, tag)
    if len(tag.split()) > 1:
        forms = [form for form in forms if len(form.split()) >= len(tag.split())]
    return SentenceScope(tag, tag_variants(forms), match_topic, match_sentences, only_unread)


def load_groupings(
    app: "RSSTagApplication", owner: str, post_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """Single-post sentence documents by post id; multi-post groupings are ambiguous."""
    result: dict[str, dict[str, Any]] = {}
    projection: dict[str, bool] = {"post_ids": True, "sentences": True, "groups": True}
    for start in range(0, len(post_ids), GROUPING_BATCH):
        batch: list[str] = post_ids[start : start + GROUPING_BATCH]
        for doc in app.post_grouping.get_by_post_ids(owner, batch, projection):
            ids: list[Any] = doc.get("post_ids") or []
            if len(ids) == 1:
                result[str(ids[0])] = doc
    return result


def _make_sentence(post: dict[str, Any], text: str, variants: list[list[str]]) -> Sentence:
    words: tuple[str, ...] = tuple(token.group().casefold() for token in tokenize(text))
    return Sentence(
        str(post.get("pid", "")),
        str(post.get("feed_id", "")),
        text,
        words,
        tuple(tag_spans(list(words), variants)),
    )


def post_sentences(
    post: dict[str, Any], grouped: Optional[dict[str, Any]], scope: SentenceScope
) -> list[Sentence]:
    """Scoped sentences of a post; stored or body text is split conservatively."""
    stored: list[dict[str, Any]] = _post_scope_sentences(
        grouped, post, scope.tag, scope.match_topic, scope.match_sentences, scope.only_unread
    )
    return [
        _make_sentence(post, part, scope.variants)
        for sentence in stored
        for part in split_sentences(sentence["text"])
    ]


def scan_sentences(
    app: "RSSTagApplication",
    owner: str,
    posts: list[dict[str, Any]],
    scope: SentenceScope,
) -> list[Sentence]:
    """Sentences of every post in scope, using one batched grouping lookup."""
    groupings: dict[str, dict[str, Any]] = load_groupings(
        app, owner, [str(post.get("pid", "")) for post in posts]
    )
    result: list[Sentence] = []
    for post in posts:
        result.extend(post_sentences(post, groupings.get(str(post.get("pid", ""))), scope))
    LOG.debug("Scanned %d sentences in %d posts", len(result), len(posts))
    return result


def tag_sentences(sentences: list[Sentence]) -> list[Sentence]:
    return [sentence for sentence in sentences if sentence.spans]


def feed_titles(
    app: "RSSTagApplication", owner: str, feed_ids: list[str]
) -> dict[str, str]:
    if not feed_ids:
        return {}
    feeds = app.feeds.get_by_feed_ids(owner, feed_ids, {"feed_id": True, "title": True})
    return {str(feed["feed_id"]): str(feed.get("title") or feed["feed_id"]) for feed in feeds}
