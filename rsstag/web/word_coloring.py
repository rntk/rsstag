"""Context-wall coloring strategies. Register a strategy without changing the page.

Each factory prepares its data once, then returns a resolver for individual words.
TF-IDF uses full articles on the current page as documents, stemmed content words,
smoothed IDF, and per-article maximum normalization. Repeated rows never alter IDF.
"""

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, TypedDict

from rsstag.web.tag_insights import BUILDER, STOPWORDS

LOG: logging.Logger = logging.getLogger(__name__)
TFIDF_THRESHOLD: float = 0.8


class Highlight(TypedDict):
    color: str
    score: float


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


def _tfidf(context: ColoringContext) -> Resolver:
    scores: dict[str, dict[str, float]] = tfidf_scores(context.documents, context.tag)

    def resolve(row: dict[str, Any], side: str, text: str) -> Highlight | None:
        _, lemma = _word_keys(text)
        score: float | None = scores.get(str(row["pid"]), {}).get(lemma)
        return {"color": "tfidf", "score": score} if score is not None else None

    return resolve


def _none(context: ColoringContext) -> Resolver:
    def resolve(row: dict[str, Any], side: str, text: str) -> None:
        return None

    return resolve


# Add one definition and a factory here to expose a new mode in the selector.
COLORING_STRATEGIES: tuple[ColoringStrategy, ...] = (
    ColoringStrategy("important", "Important words", "Typical words use their side's insight color; rising and fading terms use trend colors.", _important),
    ColoringStrategy("tfidf", "TF-IDF", "Full articles on this page form the corpus. Scores are relative to each article's highest score; stopwords and the matching tag are excluded.", _tfidf, TFIDF_THRESHOLD),
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
