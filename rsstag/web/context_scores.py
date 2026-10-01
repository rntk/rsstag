"""Page-local words associated with the selected tag's article contexts.

Compare content-token occurrences within five original word tokens of each
complete, stemmed tag match against the disjoint remainder of page articles.
Overlapping windows count a token only once. Scores describe this page's
sample, so they can change when its article selection changes.
"""

import math
from collections import Counter
from dataclasses import dataclass

from rsstag.web.tag_insights import BUILDER, STOPWORDS

CONTEXT_WINDOW: int = 5
PRIOR_MASS: float = 100.0
MIN_ARTICLE_SUPPORT: int = 2


@dataclass(frozen=True)
class ContextScore:
    score: float
    z_score: float
    support: int


def _stems(text: str) -> list[str]:
    return [BUILDER.process_word(word) for word in BUILDER.text2words(text)]


def _near_mask(words: list[str], terms: list[str]) -> list[bool]:
    mask: list[bool] = [False] * len(words)
    width: int = len(terms)
    for index in range(len(words) - width + 1):
        if words[index:index + width] == terms:
            start: int = max(0, index - CONTEXT_WINDOW)
            end: int = min(len(words), index + width + CONTEXT_WINDOW)
            mask[start:end] = [True] * (end - start)
    return mask


def _article_counts(words: list[str], terms: list[str]) -> tuple[Counter[str], Counter[str]]:
    near: Counter[str] = Counter()
    background: Counter[str] = Counter()
    excluded: set[str] = set(terms)
    for word, is_near in zip(words, _near_mask(words, terms)):
        if len(word) > 1 and not word.isdigit() and word not in STOPWORDS and word not in excluded:
            (near if is_near else background)[word] += 1
    return near, background


def _z_score(
    word: str, near: Counter[str], background: Counter[str], prior: dict[str, float],
    near_total: int, background_total: int,
) -> float:
    """Weighted log odds with an empirical Dirichlet prior and normal variance.

    alpha_w = PRIOR_MASS * (pooled_count_w + 1) / (pooled_total + V).
    z_w = [log((near_w+alpha_w)/(near_other+alpha_0-alpha_w))
           - log((background_w+alpha_w)/(background_other+alpha_0-alpha_w))]
          / sqrt(1/(near_w+alpha_w) + 1/(background_w+alpha_w)).
    """
    alpha: float = prior[word]
    near_word: float = near[word] + alpha
    background_word: float = background[word] + alpha
    near_other: float = near_total - near[word] + PRIOR_MASS - alpha
    background_other: float = background_total - background[word] + PRIOR_MASS - alpha
    difference: float = math.log(near_word / near_other) - math.log(background_word / background_other)
    return difference / math.sqrt(1.0 / near_word + 1.0 / background_word)


def context_log_odds(documents: dict[str, str], tag: str) -> dict[str, ContextScore]:
    """Score page stems enriched near a tag, requiring two distinct articles.

    Uses an add-one pooled empirical prior of fixed mass 100. Scores are
    positive z scores divided by the largest supported positive z score.
    The article set is page-local; these are relative, not corpus-wide scores.
    """
    terms: list[str] = _stems(tag)
    if not terms:
        return {}
    near: Counter[str] = Counter()
    background: Counter[str] = Counter()
    support: Counter[str] = Counter()
    for text in documents.values():
        article_near, article_background = _article_counts(_stems(text), terms)
        near.update(article_near)
        background.update(article_background)
        support.update(article_near.keys())
    vocabulary: set[str] = set(near) | set(background)
    if not near or not background or len(vocabulary) < 2:
        return {}
    pooled: Counter[str] = near + background
    near_total: int = sum(near.values())
    background_total: int = sum(background.values())
    denominator: int = near_total + background_total + len(vocabulary)
    prior: dict[str, float] = {
        word: PRIOR_MASS * (pooled[word] + 1) / denominator for word in vocabulary
    }
    positive: dict[str, float] = {}
    for word in near:
        if support[word] >= MIN_ARTICLE_SUPPORT:
            z: float = _z_score(word, near, background, prior, near_total, background_total)
            if z > 0:
                positive[word] = z
    maximum: float = max(positive.values(), default=0.0)
    return {
        word: ContextScore(z / maximum, z, support[word])
        for word, z in positive.items()
    } if maximum > 0 else {}
