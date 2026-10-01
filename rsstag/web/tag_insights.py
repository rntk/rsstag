"""Quick insights about a tag's contexts: collocates, trends, duplicates and novelty."""

import logging
import math
from collections import Counter
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterable

from rsstag.stopwords import stopwords
from rsstag.tags_builder import TagsBuilder
from rsstag.web.posts import _get_context_tags
from rsstag.web.tag_explorer import _decode_lemmas, _only_unread

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

LOG: logging.Logger = logging.getLogger(__name__)
BUILDER: TagsBuilder = TagsBuilder()
SAMPLE_LIMIT: int = 2000
WINDOW: int = 5
DAY: int = 86400
TIMELINE_DAYS: int = 30
RECENT_DAYS: int = 7
MIN_COUNT: int = 2
MIN_FADING_COUNT: int = 3
CHANGE_RATIO: float = 2.0
TOP_TERMS: int = 8
TOP_CHANGES: int = 6
TOP_UNUSUAL: int = 5
MIN_NOVELTY_POSTS: int = 10
MIN_NOVELTY_WORDS: int = 3
VOCABULARY_CANDIDATES: int = 300
SURFACE_WORDS: int = 20
SNIPPET_WORDS: int = 8
DUPLICATE_SIMILARITY: float = 0.6
BAR_LEVELS: int = 10
_RAW_STOPWORDS: list[str] = stopwords.words("english") + stopwords.words("russian")
STOPWORDS: frozenset[str] = frozenset(_RAW_STOPWORDS + [BUILDER.process_word(word) for word in _RAW_STOPWORDS])


def _occurrences(lemmas: list[str], terms: list[str]) -> list[int]:
    width: int = len(terms)
    return [index for index in range(len(lemmas) - width + 1) if lemmas[index:index + width] == terms]


def _is_content(lemma: str, terms: list[str]) -> bool:
    return len(lemma) > 1 and not lemma.isdigit() and lemma not in STOPWORDS and lemma not in terms


def _post_windows(lemmas: list[str], terms: list[str]) -> tuple[set[str], set[str]] | None:
    """Content lemmas near any occurrence, counted once per post; None without a match."""
    indices: list[int] = _occurrences(lemmas, terms)
    if not indices:
        return None
    left: set[str] = set()
    right: set[str] = set()
    for index in indices:
        end: int = index + len(terms)
        left.update(word for word in lemmas[max(0, index - WINDOW):index] if _is_content(word, terms))
        right.update(word for word in lemmas[end:end + WINDOW] if _is_content(word, terms))
    return left, right


def _aggregate(posts: Iterable[dict[str, Any]], terms: list[str]) -> dict[str, Any]:
    left: Counter[str] = Counter()
    right: Counter[str] = Counter()
    dated: list[tuple[float, set[str]]] = []
    sampled: int = 0
    matched: int = 0
    for post in posts:
        sampled += 1
        windows: tuple[set[str], set[str]] | None = _post_windows(_decode_lemmas(post), terms)
        matched += windows is not None
        near: set[str] = set().union(*windows) if windows else set()
        left.update(windows[0] if windows else ())
        right.update(windows[1] if windows else ())
        date: Any = post.get("unix_date")
        if isinstance(date, (int, float)) and not isinstance(date, bool):
            dated.append((float(date), near))
    return {"sampled": sampled, "matched": matched, "left": left, "right": right, "dated": dated}


def _day_label(day: int) -> str:
    return datetime.fromtimestamp(day * DAY, tz=timezone.utc).strftime("%Y-%m-%d")


def _timeline(dates: list[float]) -> list[dict[str, Any]]:
    """Daily mention bars for the last month of available data."""
    if not dates:
        return []
    counts: Counter[int] = Counter(int(date // DAY) for date in dates)
    last: int = int(max(dates) // DAY)
    days: list[int] = list(range(last - TIMELINE_DAYS + 1, last + 1))
    peak: int = max(counts[day] for day in days)
    return [{"date": _day_label(day), "count": counts[day],
             "level": math.ceil(counts[day] * BAR_LEVELS / peak) if peak else 0,
             "peak": peak > 0 and counts[day] == peak} for day in days]


def _split_periods(dated: list[tuple[float, set[str]]]) -> tuple[Counter[str], int, Counter[str], int]:
    cutoff: float = max(date for date, _ in dated) - RECENT_DAYS * DAY
    recent: Counter[str] = Counter()
    earlier: Counter[str] = Counter()
    for date, words in dated:
        (recent if date > cutoff else earlier).update(words)
    recent_posts: int = sum(1 for date, _ in dated if date > cutoff)
    return recent, recent_posts, earlier, len(dated) - recent_posts


def _changes(dated: list[tuple[float, set[str]]]) -> dict[str, list[tuple[str, int, int]]]:
    """Context words that appear much more (rising) or less (fading) in the latest week."""
    if not dated:
        return {"rising": [], "fading": []}
    recent, recent_posts, earlier, earlier_posts = _split_periods(dated)
    if not recent_posts or not earlier_posts:
        return {"rising": [], "fading": []}

    def ratio(word: str) -> float:
        return ((recent[word] + 0.5) / recent_posts) / ((earlier[word] + 0.5) / earlier_posts)

    rising: list[str] = [word for word in recent if recent[word] >= MIN_COUNT and ratio(word) >= CHANGE_RATIO]
    fading: list[str] = [word for word in earlier
                         if earlier[word] >= MIN_FADING_COUNT and ratio(word) <= 1 / CHANGE_RATIO]
    rising.sort(key=lambda word: (-recent[word] * math.log(ratio(word)), word))
    fading.sort(key=lambda word: (earlier[word] * math.log(ratio(word)), word))
    return {key: [(word, recent[word], earlier[word]) for word in words[:TOP_CHANGES]]
            for key, words in (("rising", rising), ("fading", fading))}


def _vocabulary(app: "RSSTagApplication", user: dict[str, Any], lemmas: list[str]) -> dict[str, dict[str, Any]]:
    if not lemmas:
        return {}
    return {str(item["tag"]): item for item in app.tags.get_by_tags(
        user["sid"], lemmas, projection={"_id": 0, "tag": 1, "posts_count": 1, "words": 1},
    )}


def _term(lemma: str, vocabulary: dict[str, dict[str, Any]], **counts: int) -> dict[str, Any]:
    """Show a readable surface word and keep every spelling for row filtering."""
    words: list[str] = sorted({str(word) for word in vocabulary.get(lemma, {}).get("words") or []} or {lemma},
                              key=lambda word: (len(word), word))
    return {"lemma": lemma, "label": words[0], "words": words[:SURFACE_WORDS], **counts}


def _collocates(
    counter: Counter[str], vocabulary: dict[str, dict[str, Any]], total_posts: int,
) -> list[dict[str, Any]]:
    """Rank frequent neighbors by how specific they are to this tag (tf-idf style)."""
    def salience(word: str) -> float:
        document_frequency: int = int(vocabulary.get(word, {}).get("posts_count") or counter[word])
        return counter[word] * math.log((total_posts + 1) / (document_frequency + 1))

    frequent: list[str] = [word for word, count in counter.items() if count >= MIN_COUNT]
    ranked: list[str] = sorted(frequent, key=lambda word: (-salience(word), word))[:TOP_TERMS]
    return [_term(word, vocabulary, count=counter[word]) for word in ranked]


def _candidates(aggregate: dict[str, Any], changes: dict[str, list[tuple[str, int, int]]]) -> list[str]:
    frequent: list[str] = [word for word, _ in (aggregate["left"] + aggregate["right"]).most_common(VOCABULARY_CANDIDATES)]
    changed: list[str] = [word for items in changes.values() for word, _, _ in items]
    return list(dict.fromkeys(frequent + changed))


def aggregate_insights(app: "RSSTagApplication", user: dict[str, Any], tag: str) -> dict[str, Any]:
    """Summarize the newest matching posts, independent of the displayed page."""
    terms: list[str] = BUILDER.text2words(tag)
    posts: Iterable[dict[str, Any]] = app.posts.get_recent_by_tags(
        user["sid"], terms, SAMPLE_LIMIT, _only_unread(user),
        {"_id": 0, "pid": 1, "unix_date": 1, "lemmas": 1}, context_tags=_get_context_tags(user),
    )
    aggregate: dict[str, Any] = _aggregate(posts, terms)
    changes: dict[str, list[tuple[str, int, int]]] = _changes(aggregate["dated"])
    vocabulary: dict[str, dict[str, Any]] = _vocabulary(app, user, _candidates(aggregate, changes))
    total_posts: int = max(app.posts.count(user["sid"]), aggregate["sampled"])
    return {
        "sampled": aggregate["sampled"], "matched": aggregate["matched"],
        "limited": aggregate["sampled"] >= SAMPLE_LIMIT, "recent_days": RECENT_DAYS,
        "timeline": _timeline([date for date, _ in aggregate["dated"]]),
        "left": _collocates(aggregate["left"], vocabulary, total_posts),
        "right": _collocates(aggregate["right"], vocabulary, total_posts),
        **{key: [_term(word, vocabulary, recent=recent, earlier=earlier) for word, recent, earlier in items]
           for key, items in changes.items()},
        "context_counts": aggregate["left"] + aggregate["right"],
    }


def _shingles(row: dict[str, Any]) -> set[tuple[str, str]]:
    words: list[str] = BUILDER.text2words(f"{row['before']} {row['match']} {row['after']}")
    return set(zip(words, words[1:]))


def _similarity(first: set[tuple[str, str]], second: set[tuple[str, str]]) -> float:
    union: int = len(first | second)
    return len(first & second) / union if union else 0.0


def mark_duplicates(rows: list[dict[str, Any]]) -> int:
    """Fold near-identical contexts (e.g. syndicated wire text) into their first occurrence."""
    representatives: list[tuple[int, set[tuple[str, str]]]] = []
    for index, row in enumerate(rows):
        row["duplicates"], row["duplicate_of"] = 0, None
        shingles: set[tuple[str, str]] = _shingles(row)
        for rep_index, rep_shingles in representatives:
            if rows[rep_index]["detail_key"] != row["detail_key"] and \
                    _similarity(shingles, rep_shingles) >= DUPLICATE_SIMILARITY:
                row["duplicate_of"] = rep_index
                rows[rep_index]["duplicates"] += 1
                break
        else:
            representatives.append((index, shingles))
    return len(rows) - len(representatives)


def _near_words(row: dict[str, Any]) -> list[str]:
    return BUILDER.text2words(row["before"])[-WINDOW:] + BUILDER.text2words(row["after"])[:WINDOW]


def _novelty(words: list[str], terms: list[str], counts: Counter[str], total: int) -> tuple[float, list[str]]:
    """Mean surprisal of nearby words given how often they surround this tag."""
    pairs: list[tuple[str, str]] = [(word, BUILDER.process_word(word)) for word in words]
    content: list[tuple[str, str]] = [(word, lemma) for word, lemma in pairs if _is_content(lemma, terms)]
    if len(content) < MIN_NOVELTY_WORDS:
        return 0.0, []
    score: float = sum(-math.log((counts[lemma] + 1) / (total + 2)) for _, lemma in content) / len(content)
    rare: list[str] = list(dict.fromkeys(word for word, lemma in content if counts[lemma] <= 1))
    return score, rare[:3]


def _snippet(row: dict[str, Any], score: float, rare: list[str]) -> dict[str, Any]:
    return {
        "detail_key": row["detail_key"], "title": row["title"], "match": row["match"],
        "before": " ".join(row["before"].split()[-SNIPPET_WORDS:]),
        "after": " ".join(row["after"].split()[:SNIPPET_WORDS]),
        "score": round(score, 2), "rare": rare,
    }


def unusual_rows(rows: list[dict[str, Any]], tag: str, aggregate: dict[str, Any]) -> list[dict[str, Any]]:
    """Pick page contexts whose nearby words rarely accompany the tag elsewhere."""
    total: int = aggregate["matched"]
    if total < MIN_NOVELTY_POSTS:
        return []
    terms: list[str] = BUILDER.text2words(tag)
    scored: list[tuple[float, int, list[str]]] = []
    for index, row in enumerate(rows):
        if row.get("duplicate_of") is None:
            score, rare = _novelty(_near_words(row), terms, aggregate["context_counts"], total)
            if rare:
                scored.append((score, index, rare))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [_snippet(rows[index], score, rare) for score, index, rare in scored[:TOP_UNUSUAL]]


def wall_insights(
    app: "RSSTagApplication", user: dict[str, Any], tag: str, rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Never let the optional summary break the context wall itself."""
    try:
        insights: dict[str, Any] = aggregate_insights(app, user, tag)
        insights["unusual"] = unusual_rows(rows, tag, insights)
        del insights["context_counts"]
        return insights
    except Exception:
        LOG.exception("Could not build tag insights for the context wall")
        return None
