"""Context-wall coloring strategies. Register a strategy without changing the page.

Each factory prepares its data once, then returns a resolver for individual words.
TF-IDF uses full articles on the current page as documents, stemmed content words,
smoothed IDF, and per-article maximum normalization. Keyword modes reuse the
endpoint extractors. PMI, surprise and tag-context log-odds use the page corpus;
repeated rows never alter corpus statistics.
"""

import logging
import math
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NotRequired, TypedDict

from rsstag.web.context_scores import ContextScore, context_log_odds
from rsstag.web.keywords import (
    KeywordItem,
    _extract_rake_keywords,
    _extract_yake_keywords,
)
from rsstag.web.tag_insights import BUILDER, STOPWORDS

LOG: logging.Logger = logging.getLogger(__name__)
TFIDF_THRESHOLD: float = 0.8
SCORE_THRESHOLD: float = 0.8
PMI_WINDOW: int = 5
PMI_MIN_COUNT: int = 2
PHRASE_BOUNDARY: str = "\u241e\u241e"

KeywordExtractor = Callable[[list[str], set[str], int], list[KeywordItem]]


class Highlight(TypedDict):
    color: str
    score: float
    support: NotRequired[int]
    z_score: NotRequired[float]


@dataclass(frozen=True)
class ColoringContext:
    tag: str
    documents: dict[str, str]
    insights: dict[str, Any] | None


Resolver = Callable[[dict[str, Any], str, str], Highlight | None]
Factory = Callable[[ColoringContext], Resolver]


@dataclass(frozen=True)
class ColoringStrategy:
    key: str
    label: str
    description: str
    prepare: Factory
    threshold: float | None = None


def _word_keys(text: str) -> tuple[str, str]:
    token: re.Match[str] | None = re.search(r"\w+", text)
    key: str = token.group().casefold() if token else ""
    return key, BUILDER.process_word(key) if key else ""


def _insight_colors(insights: dict[str, Any] | None, side: str) -> dict[str, str]:
    """Side colors take precedence over trend colors, preserving the original mode."""
    colors: dict[str, str] = {}
    if insights is None:
        return colors
    for key, color in (("rising", "rising"), ("fading", "fading"), (side, "before" if side == "left" else "after")):
        for term in insights.get(key, []):
            colors[term["lemma"]] = color
            for word in term["words"]:
                colors[word.casefold()] = color
    return colors


def _important(context: ColoringContext) -> Resolver:
    colors: dict[str, dict[str, str]] = {
        "before": _insight_colors(context.insights, "left"),
        "after": _insight_colors(context.insights, "right"),
    }

    def resolve(row: dict[str, Any], side: str, text: str) -> Highlight | None:
        key, lemma = _word_keys(text)
        color: str | None = colors[side].get(key) or colors[side].get(lemma)
        return {"color": color, "score": 1.0} if color else None

    return resolve


def _content_counts(text: str, excluded: set[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for token in re.finditer(r"\w+", text):
        key, lemma = _word_keys(token.group())
        if len(key) > 1 and not key.isdigit() and key not in STOPWORDS and lemma not in STOPWORDS and lemma not in excluded:
            counts[lemma] += 1
    return counts


def tfidf_scores(documents: dict[str, str], tag: str) -> dict[str, dict[str, float]]:
    """Compute (1 + log TF) * smoothed IDF, scaled to each article's maximum."""
    excluded: set[str] = {BUILDER.process_word(word) for word in BUILDER.text2words(tag)}
    counts: dict[str, Counter[str]] = {pid: _content_counts(text, excluded) for pid, text in documents.items()}
    frequencies: Counter[str] = Counter(word for count in counts.values() for word in count)
    scores: dict[str, dict[str, float]] = {}
    for pid, count in counts.items():
        weighted: dict[str, float] = {
            word: (1 + math.log(tf)) * (1 + math.log((1 + len(counts)) / (1 + frequencies[word])))
            for word, tf in count.items()
        }
        maximum: float = max(weighted.values(), default=0.0)
        scores[pid] = {word: value / maximum for word, value in weighted.items()} if maximum else {}
    return scores


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    """Keep positive evidence and scale it to the highest score."""
    maximum: float = max(scores.values(), default=0.0)
    return {word: value / maximum for word, value in scores.items() if value > 0} if maximum > 0 else {}


def _excluded(tag: str) -> set[str]:
    return {BUILDER.process_word(word) for word in BUILDER.text2words(tag)}


def _lemma_text(text: str) -> str:
    """Stem the article's word tokens for content-word co-occurrence windows."""
    return " ".join(_word_keys(token.group())[1] for token in re.finditer(r"\w+", text))


def _keyword_text(text: str) -> str:
    """Keep phrase breaks in one article, preserving YAKE-style document counts.

    The extractors discard short/numeric tokens before checking stopwords, so
    represent those and punctuation with a dedicated stopword boundary.
    """
    words: list[str] = []
    for token in re.finditer(r"\w+|[^\w\s]+|\n+", text):
        key, lemma = _word_keys(token.group())
        words.append(lemma if len(key) > 1 and not key.isdigit() else PHRASE_BOUNDARY)
    return " ".join(words)


def keyword_scores(
    documents: dict[str, str], tag: str, extractor: KeywordExtractor,
) -> dict[str, dict[str, float]]:
    """Project each article's keyword phrases onto their words by maximum score."""
    excluded: set[str] = _excluded(tag)
    scores: dict[str, dict[str, float]] = {}
    for pid, text in documents.items():
        lemmas: str = _keyword_text(text)
        candidates: list[KeywordItem] = extractor(
            [lemmas], set(STOPWORDS) | excluded | {PHRASE_BOUNDARY}, max(1, len(lemmas.split()) * 3),
        )
        weighted: dict[str, float] = {}
        allowed: Counter[str] = _content_counts(text, excluded)
        for item in candidates:
            for word in item.phrase.split():
                if word in allowed:
                    weighted[word] = max(weighted.get(word, 0.0), item.score)
        scores[pid] = _normalize(weighted)
    return scores


def pmi_scores(documents: dict[str, str], tag: str) -> dict[str, dict[str, float]]:
    """Positive log2 PMI of directed pairs in five-content-word windows.

    Marginals and joint probabilities use the same pair-event space. Require
    two occurrences in each direction and never create pairs across articles.
    A word receives its strongest pair score present in its own article.
    """
    excluded: set[str] = _excluded(tag)
    article_pairs: dict[str, set[tuple[str, str]]] = {}
    pairs: Counter[tuple[str, str]] = Counter()
    for pid, text in documents.items():
        allowed: Counter[str] = _content_counts(text, excluded)
        words: list[str] = [lemma for lemma in _lemma_text(text).split() if lemma in allowed]
        local: Counter[tuple[str, str]] = Counter()
        for index, word in enumerate(words):
            for other in words[index + 1:index + PMI_WINDOW + 1]:
                if word != other:
                    local[(word, other)] += 1
                    local[(other, word)] += 1
        pairs.update(local)
        article_pairs[pid] = set(local)
    marginals: Counter[str] = Counter()
    for (word, _), count in pairs.items():
        marginals[word] += count
    total: int = sum(pairs.values())
    weighted: dict[tuple[str, str], float] = {
        pair: math.log2(count * total / (marginals[pair[0]] * marginals[pair[1]]))
        for pair, count in pairs.items() if count >= PMI_MIN_COUNT
    }
    maximum: float = max(weighted.values(), default=0.0)
    scores: dict[str, dict[str, float]] = {}
    for pid, local_pairs in article_pairs.items():
        local_scores: dict[str, float] = {}
        for pair in local_pairs:
            value: float = weighted.get(pair, 0.0)
            if value > 0 and maximum > 0:
                for word in pair:
                    local_scores[word] = max(local_scores.get(word, 0.0), value / maximum)
        scores[pid] = local_scores
    return scores


def surprise_scores(documents: dict[str, str], tag: str) -> dict[str, dict[str, float]]:
    """Reuse the tag endpoint's order-independent leave-one-out KL calculation."""
    from rsstag.surprise import LeaveOneOutSurprise

    excluded: set[str] = _excluded(tag)
    counts: dict[str, Counter[str]] = {pid: _content_counts(text, excluded) for pid, text in documents.items()}
    weighted: dict[str, float] = LeaveOneOutSurprise().compute([list(count) for count in counts.values()])
    normalized: dict[str, float] = _normalize(weighted)
    return {pid: {word: normalized[word] for word in count if word in normalized}
            for pid, count in counts.items()}


def _score_resolver(scores: dict[str, dict[str, float]], color: str) -> Resolver:
    def resolve(row: dict[str, Any], side: str, text: str) -> Highlight | None:
        _, lemma = _word_keys(text)
        score: float | None = scores.get(str(row["pid"]), {}).get(lemma)
        return {"color": color, "score": score} if score is not None else None

    return resolve


def _tfidf(context: ColoringContext) -> Resolver:
    return _score_resolver(tfidf_scores(context.documents, context.tag), "tfidf")


def _pmi(context: ColoringContext) -> Resolver:
    return _score_resolver(pmi_scores(context.documents, context.tag), "pmi")


def _rake(context: ColoringContext) -> Resolver:
    return _score_resolver(keyword_scores(context.documents, context.tag, _extract_rake_keywords), "rake")


def _yake(context: ColoringContext) -> Resolver:
    return _score_resolver(keyword_scores(context.documents, context.tag, _extract_yake_keywords), "yake")


def _surprise(context: ColoringContext) -> Resolver:
    return _score_resolver(surprise_scores(context.documents, context.tag), "surprise")


def _log_odds(context: ColoringContext) -> Resolver:
    scores: dict[str, ContextScore] = context_log_odds(context.documents, context.tag)

    def resolve(row: dict[str, Any], side: str, text: str) -> Highlight | None:
        _, lemma = _word_keys(text)
        term: ContextScore | None = scores.get(lemma)
        if term is None:
            return None
        return {"color": "log_odds", "score": term.score,
                "support": term.support, "z_score": term.z_score}

    return resolve


def _none(context: ColoringContext) -> Resolver:
    def resolve(row: dict[str, Any], side: str, text: str) -> None:
        return None

    return resolve


# Add one definition and a factory here to expose a new mode in the selector.
COLORING_STRATEGIES: tuple[ColoringStrategy, ...] = (
    ColoringStrategy("important", "Important words", "Typical words use their side's insight color; rising and fading terms use trend colors.", _important),
    ColoringStrategy("tfidf", "TF-IDF", "Full articles on this page form the corpus. Scores are relative to each article's highest score; stopwords and the matching tag are excluded.", _tfidf, TFIDF_THRESHOLD),
    ColoringStrategy("pmi", "PMI", "Positive pointwise mutual information for word pairs within five content words in the page's articles. Pairs must occur twice; words use their strongest pair, scaled to the page maximum.", _pmi, SCORE_THRESHOLD),
    ColoringStrategy("rake", "RAKE", "Uses the existing RAKE extractor for each article. Words inherit their highest phrase score, relative to the article maximum; punctuation, stopwords and the matching tag split phrases.", _rake, SCORE_THRESHOLD),
    ColoringStrategy("yake", "YAKE-style", "Uses a frequency-and-position keyword heuristic for each article. Punctuation and stopwords split phrases. Words inherit their highest phrase score, relative to the article maximum.", _yake, SCORE_THRESHOLD),
    ColoringStrategy("surprise", "Co-occurrence surprise", "Leave-one-out comparison of article word sets on this page. Words with unusual co-occurrence contexts score higher, relative to the page maximum; at least two articles must contain a word. This does not measure change over time.", _surprise, SCORE_THRESHOLD),
    ColoringStrategy("log_odds", "Tag-context log-odds", "Words enriched within five words of the tag versus the remaining text in this page's articles. Requires support near the tag in at least two articles. Positive standardized scores are scaled to the page maximum; hover for article support. No scores without background text.", _log_odds, SCORE_THRESHOLD),
    ColoringStrategy("none", "No coloring", "Only the matching tag and hovered words are highlighted.", _none),
)


def apply_coloring(rows: list[dict[str, Any]], context: ColoringContext) -> list[dict[str, Any]]:
    """Attach serializable word results and selector options through one pipeline."""
    options: list[dict[str, Any]] = []
    for strategy in COLORING_STRATEGIES:
        try:
            resolver: Resolver = strategy.prepare(context)
            for row in rows:
                for side in ("before", "after"):
                    for word in row[f"{side}_words"]:
                        highlight: Highlight | None = resolver(row, side, word["text"])
                        word.setdefault("colorings", {})[strategy.key] = highlight
                        if strategy.key == "important":
                            word["color"] = highlight["color"] if highlight else None
            options.append({"key": strategy.key, "label": strategy.label,
                            "description": strategy.description, "threshold": strategy.threshold})
        except Exception:
            LOG.exception("Could not prepare context-wall coloring strategy %s", strategy.key)
    return options
