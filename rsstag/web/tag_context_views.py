"""Chart data for the three tag context views: phrases, words and feed framing."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from rsstag.web.tag_context_data import Sentence
from rsstag.web.tag_context_stats import (
    Contrast,
    WordCounts,
    branching,
    contrast,
    snippet,
    tokenize,
    word_snippet,
)

MAX_SNIPPETS: int = 5
MAX_EXAMPLES: int = 3
MAX_POST_IDS: int = 200
MAX_WORDS: int = 300
MAX_FEEDS: int = 16
FEED_WORDS: int = 30
MIN_FEED_SENTENCES: int = 3

Trigram = tuple[str, str, str, str]


@dataclass
class Support:
    """Where a word occurs among the focus sentences."""

    articles: set[str] = field(default_factory=set)
    feeds: Counter = field(default_factory=Counter)
    examples: list[Sentence] = field(default_factory=list)


@dataclass(frozen=True)
class PostMeta:
    """Lookup data used to link examples to their articles."""

    posts: dict[str, dict[str, str]]
    feeds: dict[str, str]

    def example(self, sentence: Sentence, word: str) -> dict[str, str]:
        post: dict[str, str] = self.posts.get(sentence.post_id, {})
        return {
            "text": word_snippet(sentence.text, word),
            "post_id": sentence.post_id,
            "url": post.get("url", ""),
            "title": post.get("title", ""),
            "feed": self.feeds.get(sentence.feed_id, sentence.feed_id),
        }


def post_meta(posts: list[dict[str, Any]], feeds: dict[str, str]) -> PostMeta:
    return PostMeta(
        {
            str(post.get("pid", "")): {
                "url": str(post.get("url", "")),
                "title": str((post.get("content") or {}).get("title", "")),
            }
            for post in posts
        },
        feeds,
    )


# Phrases ---------------------------------------------------------------------


def trigrams(sentence: Sentence, tag: str) -> list[Trigram]:
    """(pair, outer word, phrase, snippet) for 3-word windows around the tag.

    The pair is the tag with its adjacent word; the outer word extends it,
    reading forward ("tag next outer") or backward ("outer prev tag").
    """
    tokens = tokenize(sentence.text)
    words: tuple[str, ...] = sentence.words
    tag_text: str = tag.casefold()
    result: list[Trigram] = []
    for start, end in sentence.spans:
        if end + 1 < len(words):
            nxt, outer = words[end], words[end + 1]
            result.append((f"{tag_text} {nxt}", outer, f"{tag_text} {nxt} {outer}",
                           snippet(sentence.text, tokens, start, end + 2)))
        if start >= 2:
            prev, outer = words[start - 1], words[start - 2]
            result.append((f"{prev} {tag_text}", outer, f"{outer} {prev} {tag_text}",
                           snippet(sentence.text, tokens, start - 2, end)))
    return result


def _add_completion(rows: dict[str, dict[str, Any]], gram: Trigram, post_id: str) -> None:
    pair, word, phrase, text = gram
    row: dict[str, Any] = rows.setdefault(pair, {"bigram": pair, "words": {}, "posts": set()})
    item: dict[str, Any] = row["words"].setdefault(
        word, {"word": word, "trigram": phrase, "count": 0, "posts": set(), "snippets": []}
    )
    item["count"] += 1
    item["posts"].add(post_id)
    row["posts"].add(post_id)
    if len(item["snippets"]) < MAX_SNIPPETS and text not in item["snippets"]:
        item["snippets"].append(text)


def _finalize_completion(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "word": item["word"],
        "trigram": item["trigram"],
        "count": item["count"],
        "posts_count": len(item["posts"]),
        "post_ids": sorted(item["posts"])[:MAX_POST_IDS],
        "snippets": item["snippets"],
    }


def _finalize_phrase_row(row: dict[str, Any]) -> dict[str, Any]:
    words: list[dict[str, Any]] = sorted(
        (_finalize_completion(item) for item in row["words"].values()),
        key=lambda item: (-item["count"], item["word"]),
    )
    return {
        "bigram": row["bigram"],
        "count": sum(item["count"] for item in words),
        "posts_count": len(row["posts"]),
        **branching([item["count"] for item in words]),
        "words": words,
    }


def build_phrases(sentences: list[Sentence], tag: str) -> list[dict[str, Any]]:
    """Group completions under every tag word pair, most frequent pair first."""
    rows: dict[str, dict[str, Any]] = {}
    for sentence in sentences:
        for gram in trigrams(sentence, tag):
            _add_completion(rows, gram, sentence.post_id)
    finalized: list[dict[str, Any]] = [_finalize_phrase_row(row) for row in rows.values()]
    finalized.sort(key=lambda row: (-row["count"], row["bigram"]))
    return finalized


# Contrasts -------------------------------------------------------------------


def count_words(sentences: list[Sentence]) -> WordCounts:
    counts: WordCounts = WordCounts()
    for sentence in sentences:
        counts.add(sentence.context)
    return counts


def collect_support(sentences: list[Sentence]) -> dict[str, Support]:
    supports: dict[str, Support] = defaultdict(Support)
    for sentence in sentences:
        for word in set(sentence.context):
            support: Support = supports[word]
            support.articles.add(sentence.post_id)
            support.feeds[sentence.feed_id] += 1
            if len(support.examples) < MAX_EXAMPLES:
                support.examples.append(sentence)
    return supports


def word_item(word: str, stats: Contrast, support: Support, meta: PostMeta) -> dict[str, Any]:
    largest: int = max(support.feeds.values(), default=0)
    return {
        "word": word,
        "sentences": stats.focus,
        "reference_sentences": stats.reference,
        "articles": len(support.articles),
        "post_ids": sorted(support.articles)[:MAX_POST_IDS],
        "feeds": [
            {"title": meta.feeds.get(feed_id, feed_id), "count": count}
            for feed_id, count in support.feeds.most_common(5)
        ],
        "feed_count": len(support.feeds),
        "top_feed_share": round(largest / max(stats.focus, 1), 3),
        "lift": round(stats.lift, 4),
        "lift_low": round(stats.lift_low, 4),
        "lift_high": round(stats.lift_high, 4),
        "z": round(stats.z, 3),
        "examples": [meta.example(sentence, word) for sentence in support.examples],
    }


def ranked_words(
    focus_sentences: list[Sentence], reference: WordCounts, meta: PostMeta, limit: int
) -> list[dict[str, Any]]:
    """Words of the focus sentences ranked by shrunk log-odds z, strongest first."""
    focus: WordCounts = count_words(focus_sentences)
    supports: dict[str, Support] = collect_support(focus_sentences)
    scored: list[tuple[str, Contrast]] = [
        (word, contrast(word, focus, reference)) for word in focus.presence
    ]
    scored.sort(key=lambda pair: (-pair[1].z, pair[0]))
    return [word_item(word, stats, supports[word], meta) for word, stats in scored[:limit]]


def _sentence_key(sentence: Sentence) -> tuple[str, str]:
    return sentence.post_id, sentence.text


def build_words(
    focus: list[Sentence], background: list[Sentence], meta: PostMeta
) -> dict[str, Any]:
    """Distinctive words of tag sentences against other sentences in scope."""
    keys: set[tuple[str, str]] = {_sentence_key(sentence) for sentence in focus}
    rest: list[Sentence] = [s for s in background if _sentence_key(s) not in keys]
    words: list[dict[str, Any]] = (
        ranked_words(focus, count_words(rest), meta, MAX_WORDS) if rest else []
    )
    return {"reference_sentences": len(rest), "words": words}


def _feed_row(
    feed_id: str, own: list[Sentence], others: list[Sentence], total: int, meta: PostMeta
) -> dict[str, Any]:
    words: list[dict[str, Any]] = ranked_words(own, count_words(others), meta, FEED_WORDS)
    return {
        "feed_id": feed_id,
        "title": meta.feeds.get(feed_id, feed_id),
        "sentences": len(own),
        "articles": len({sentence.post_id for sentence in own}),
        "share": round(len(own) / max(total, 1), 3),
        "words": [word for word in words if word["z"] > 0],
    }


def build_feeds(focus: list[Sentence], meta: PostMeta) -> dict[str, Any]:
    """Per-feed distinctive words: each feed's tag sentences against other feeds'."""
    by_feed: dict[str, list[Sentence]] = defaultdict(list)
    for sentence in focus:
        by_feed[sentence.feed_id].append(sentence)
    eligible: list[str] = sorted(
        (feed_id for feed_id, items in by_feed.items() if len(items) >= MIN_FEED_SENTENCES),
        key=lambda feed_id: (-len(by_feed[feed_id]), feed_id),
    )
    if len(by_feed) < 2 or not eligible:
        return {"feeds_total": len(by_feed), "hidden_feeds": len(eligible), "rows": []}
    rows: list[dict[str, Any]] = [
        _feed_row(
            feed_id, by_feed[feed_id],
            [s for s in focus if s.feed_id != feed_id], len(focus), meta,
        )
        for feed_id in eligible[:MAX_FEEDS]
    ]
    return {
        "feeds_total": len(by_feed),
        "hidden_feeds": len(by_feed) - len(rows),
        "rows": rows,
    }
