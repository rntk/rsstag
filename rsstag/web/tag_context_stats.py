"""Pure counting and statistics for the tag context chart.

Contrasts use sentence presence: a word counts once per sentence. Scores are
the log-odds ratio with an informative Dirichlet prior (Monroe, Colaresi &
Quinn, "Fightin' Words", 2008): rare words are shrunk toward no difference,
so a word seen twice cannot outrank a word seen in fifty sentences on lift
alone. Lift and its 95% interval are reported alongside for readability.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

WORD_PATTERN: str = r"[^\W_]+(?:[’'-][^\W_]+)*"
SENTENCE_BREAK: str = r"(?<=[.!?…])\s+|\n+"
PRIOR_WEIGHT: float = 0.1
Z_95: float = 1.96
SNIPPET_RADIUS: int = 8


@dataclass(frozen=True)
class Contrast:
    """Comparison of one word between a focus group and a reference group."""

    focus: int
    reference: int
    lift: float
    lift_low: float
    lift_high: float
    z: float


@dataclass
class WordCounts:
    """Sentence presence counts for a vocabulary in one group of sentences."""

    sentences: int = 0
    presence: Counter = field(default_factory=Counter)

    def add(self, words: Iterable[str]) -> None:
        self.sentences += 1
        self.presence.update(set(words))

    @property
    def events(self) -> int:
        return sum(self.presence.values())


def tokenize(text: str) -> list[re.Match[str]]:
    return list(re.finditer(WORD_PATTERN, text))


def split_sentences(text: str) -> list[str]:
    """Conservatively split body text at terminal punctuation and line breaks."""
    return [part.strip() for part in re.split(SENTENCE_BREAK, text) if part.strip()]


def tag_variants(forms: list[str]) -> list[list[str]]:
    return [re.findall(WORD_PATTERN, form.casefold()) for form in forms]


def tag_spans(words: list[str], variants: list[list[str]]) -> list[tuple[int, int]]:
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


def context_words(words: list[str], spans: list[tuple[int, int]]) -> list[str]:
    """Words of a sentence outside the tag spans, skipping one-letter tokens."""
    inside: set[int] = {index for start, end in spans for index in range(start, end)}
    return [word for index, word in enumerate(words) if index not in inside and len(word) > 1]


def snippet(text: str, tokens: list[re.Match[str]], first: int, last: int) -> str:
    """Cut a short preview of the text around tokens[first:last]."""
    left: int = max(0, first - SNIPPET_RADIUS)
    right: int = min(len(tokens), last + SNIPPET_RADIUS)
    start: int = tokens[left].start()
    end: int = tokens[right - 1].end()
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def word_snippet(text: str, word: str) -> str:
    """Preview around the first case-folded occurrence of `word`."""
    tokens: list[re.Match[str]] = tokenize(text)
    for index, token in enumerate(tokens):
        if token.group().casefold() == word:
            return snippet(text, tokens, index, index + 1)
    return text[: SNIPPET_RADIUS * 16]


def lift_interval(focus: int, focus_n: int, ref: int, ref_n: int) -> tuple[float, float, float]:
    """Sentence-share ratio with a Katz log interval and Haldane correction."""
    a: float = focus + 0.5
    c: float = ref + 0.5
    n1: float = focus_n + 1.0
    n2: float = ref_n + 1.0
    log_lift: float = math.log((a / n1) / (c / n2))
    se: float = math.sqrt(max(0.0, 1 / a - 1 / n1 + 1 / c - 1 / n2))
    return (
        math.exp(log_lift),
        math.exp(log_lift - Z_95 * se),
        math.exp(log_lift + Z_95 * se),
    )


def log_odds_z(focus: int, focus_events: int, ref: int, ref_events: int, prior: float) -> float:
    """Z-score of the log-odds ratio with an informative Dirichlet prior."""
    prior_total: float = PRIOR_WEIGHT * (focus_events + ref_events)
    focus_odds: float = (focus + prior) / max(focus_events + prior_total - focus - prior, 1e-9)
    ref_odds: float = (ref + prior) / max(ref_events + prior_total - ref - prior, 1e-9)
    delta: float = math.log(focus_odds) - math.log(ref_odds)
    variance: float = 1 / (focus + prior) + 1 / (ref + prior)
    return delta / math.sqrt(variance)


def contrast(word: str, focus: WordCounts, reference: WordCounts) -> Contrast:
    """Compare a word's sentence presence in `focus` against `reference`."""
    in_focus: int = focus.presence[word]
    in_ref: int = reference.presence[word]
    prior: float = max(PRIOR_WEIGHT * (in_focus + in_ref), 0.01)
    lift, low, high = lift_interval(in_focus, focus.sentences, in_ref, reference.sentences)
    score: float = log_odds_z(in_focus, focus.events, in_ref, reference.events, prior)
    return Contrast(in_focus, in_ref, lift, low, high, score)


def branching(counts: list[int]) -> dict[str, float]:
    """Entropy of the next-word distribution and how fixed the phrase is.

    Fixedness is 1 minus normalised entropy: 1 means a single completion
    (a set expression), values near 0 mean an open slot with even choices.
    """
    total: int = sum(counts)
    distinct: int = len([count for count in counts if count > 0])
    if not total:
        return {"entropy": 0.0, "fixedness": 0.0, "top_share": 0.0, "distinct": 0}
    entropy: float = -sum(c / total * math.log2(c / total) for c in counts if c > 0)
    normalised: float = entropy / math.log2(distinct) if distinct > 1 else 0.0
    return {
        "entropy": round(entropy, 3),
        "fixedness": round(1 - normalised, 3),
        "top_share": round(max(counts) / total, 3),
        "distinct": distinct,
    }
