"""Tag informativeness ranking helpers.

Every tag doc may carry a ``rank`` subdocument. Each rank task writes only its
own keys:

* TASK_TAGS_RANK: ``ridf``, ``burst``, ``df_ratio``, ``shape_junk``, ``ranked_at``
* TASK_TAGS_CORPUS_RANK: ``feeds``, ``feed_entropy``, ``boilerplate``,
  ``title_ratio``, ``hot``
* TASK_TAGS_COOC_RANK: ``cooc_entropy``
* TASK_TAGS_EMBED_RANK: ``emb_norm``
* TASK_TAGS_LLM_RANK: ``llm_score``

``rank.score`` and ``rank.noise`` are derived from the keys above and must be
recomputed (``recompute_derived``) after any task writes its own keys.
"""

import logging
import math
import re
import time
from typing import Any, List, Optional, Sequence, Tuple

from pymongo import ASCENDING, DESCENDING, UpdateOne

log: logging.Logger = logging.getLogger("tag_rank")

TAG_SORT_MODES: Tuple[str, ...] = ("count", "informative", "hot")
DEFAULT_SORT_MODE: str = "count"

# Manual per-tag override stored as ``user_rank`` on the tag doc. Hidden tags
# count as noise regardless of metrics, pinned tags are never noise and are
# lifted to the top of the "informative" ordering via PINNED_SCORE_BONUS;
# hidden tags sink to the bottom by the same amount.
USER_RANK_HIDDEN: str = "hidden"
USER_RANK_PINNED: str = "pinned"
USER_RANKS: Tuple[str, ...] = (USER_RANK_HIDDEN, USER_RANK_PINNED)

# Mongo filter excluding tags flagged as generic / not informative. The
# ``rank.noise`` flag already folds in ``user_rank`` (see ``compute_noise``).
NOISE_FILTER: dict[str, Any] = {"rank.noise": {"$ne": True}}

# --- score weights -------------------------------------------------------
# Residual IDF is the base signal (Church & Gale): bursty, topical words > 0.
W_RIDF: float = 1.0
# Spread over many sources multiplies a positive ridf: 1 + W_FEEDS*log(feeds).
W_FEEDS: float = 0.5
# Share of a single feed's posts carrying the tag (signatures, footers).
W_BOILERPLATE: float = 2.0
# Normalized co-occurrence entropy: high means the tag pairs with anything.
W_COOC: float = 1.5
# Stopwords carry no topical information.
W_STOPWORD: float = 3.0
# Added to a pinned tag's score so it sorts first (scores are far below this).
PINNED_SCORE_BONUS: float = 1000.0
# Shape junk (numbers, URL/hex fragments) is a strong penalty.
W_SHAPE: float = 3.0
# Appearing in titles signals a headline-worthy term.
W_TITLE: float = 1.0
# Named entities are usually informative.
W_ENTITY: float = 0.75
# LLM 1..5 score, centered on 3 so a missing / neutral score adds nothing.
W_LLM: float = 0.5
LLM_NEUTRAL: float = 3.0
# Frequency-normalized embedding norm z-score, clamped to +-EMB_CLAMP.
W_EMB: float = 0.25
EMB_CLAMP: float = 3.0

# --- noise thresholds ----------------------------------------------------
# Tags present in more than this share of posts are too generic.
MAX_DF_RATIO: float = 0.25
MAX_BOILERPLATE: float = 0.8
MAX_COOC_ENTROPY: float = 0.9
MAX_LLM_NOISE_SCORE: float = 1.5
# A tag spread evenly (freq == df) gets a slightly negative ridf that grows with
# df/N; -0.05 flags evenly spread tags that occur in more than ~7% of posts.
MIN_RIDF: float = -0.05
MIN_POSTS_COUNT: int = 2

# --- shape junk ----------------------------------------------------------
MAX_JUNK_LENGTH: int = 2
MAX_DIGIT_SHARE: float = 0.7
MIN_HEX_LENGTH: int = 6
URL_FRAGMENTS: frozenset[str] = frozenset(
    {"http", "https", "www", "com", "html", "htm", "php", "utm", "amp", "href"}
)
_HEX_RE: re.Pattern[str] = re.compile(r"[0-9a-f]+")

LEGACY_TEMPERATURE_OFFSET: float = 0.01
RECOMPUTE_BATCH_SIZE: int = 1000


def ridf(df: int, freq: int, total_posts: int) -> float:
    """Residual IDF: observed IDF minus the IDF a Poisson model predicts."""
    if df <= 0 or total_posts <= 0:
        return 0.0
    df = min(df, total_posts)
    freq = max(freq, df)
    observed: float = -math.log2(df / total_posts)
    predicted: float = -math.log2(1.0 - math.exp(-freq / total_posts))
    return observed - predicted


def burst(freq: int, df: int) -> float:
    """Average occurrences per post containing the tag."""
    return freq / df if df > 0 else 0.0


def df_ratio(df: int, total_posts: int) -> float:
    """Share of the user's posts containing the tag."""
    return df / total_posts if total_posts > 0 else 0.0


def _is_hex_fragment(tag: str) -> bool:
    has_digit: bool = any(ch.isdigit() for ch in tag)
    has_alpha: bool = any(ch.isalpha() for ch in tag)
    return (
        len(tag) >= MIN_HEX_LENGTH
        and has_digit
        and has_alpha
        and _HEX_RE.fullmatch(tag) is not None
    )


def _digit_share(tag: str) -> float:
    return sum(1 for ch in tag if ch.isdigit()) / len(tag) if tag else 0.0


def shape_junk(tag: str) -> bool:
    """True for numbers, very short tokens, URL pieces and hex-like fragments."""
    value: str = tag.strip().casefold()
    if len(value) <= MAX_JUNK_LENGTH or value.isdigit():
        return True
    if value in URL_FRAGMENTS or _is_hex_fragment(value):
        return True
    return _digit_share(value) > MAX_DIGIT_SHARE


def legacy_temperature(posts_count: int, freq: int, is_stopword: bool) -> float:
    """Old TASK_TAGS_RANK temperature, always > 0 so the claim query moves on."""
    freq = max(freq, 1)
    temperature: float = posts_count / math.log(1 + freq)
    if is_stopword:
        temperature /= freq
    return max(temperature, 0.0) + LEGACY_TEMPERATURE_OFFSET


def compute_base_rank(
    tag: str, posts_count: int, freq: int, total_posts: int, is_stopword: bool = False
) -> dict[str, Any]:
    """Rank keys owned by TASK_TAGS_RANK."""
    return {
        "ridf": ridf(posts_count, freq, total_posts),
        "burst": burst(freq, posts_count),
        "df_ratio": df_ratio(posts_count, total_posts),
        "shape_junk": shape_junk(tag),
        "stopword": bool(is_stopword),
        "ranked_at": time.time(),
    }


def _num(rank: dict[str, Any], key: str, default: float = 0.0) -> float:
    value: Any = rank.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    if math.isnan(value) or math.isinf(value):
        return default
    return float(value)


def _ridf_part(rank: dict[str, Any]) -> float:
    base: float = W_RIDF * _num(rank, "ridf")
    feeds: float = _num(rank, "feeds")
    if base > 0 and feeds >= 1:
        base *= 1.0 + W_FEEDS * math.log(feeds)
    return base


def _penalties(rank: dict[str, Any]) -> float:
    penalty: float = W_BOILERPLATE * _num(rank, "boilerplate")
    penalty += W_COOC * _num(rank, "cooc_entropy")
    if rank.get("shape_junk") is True:
        penalty += W_SHAPE
    if rank.get("stopword") is True:
        penalty += W_STOPWORD
    return penalty


def _boosts(rank: dict[str, Any]) -> float:
    boost: float = W_TITLE * _num(rank, "title_ratio")
    if rank.get("is_entity") is True:
        boost += W_ENTITY
    boost += W_LLM * (_num(rank, "llm_score", LLM_NEUTRAL) - LLM_NEUTRAL)
    emb: float = max(-EMB_CLAMP, min(EMB_CLAMP, _num(rank, "emb_norm")))
    return boost + W_EMB * emb


def compute_score(rank: dict[str, Any], user_rank: Optional[str] = None) -> float:
    """Composite "informative" score; missing keys contribute neutrally."""
    score: float = _ridf_part(rank) + _boosts(rank) - _penalties(rank)
    if user_rank == USER_RANK_PINNED:
        return score + PINNED_SCORE_BONUS
    if user_rank == USER_RANK_HIDDEN:
        return score - PINNED_SCORE_BONUS
    return score


def _metrics_noise(rank: dict[str, Any], posts_count: int) -> bool:
    if posts_count < MIN_POSTS_COUNT or rank.get("shape_junk") is True:
        return True
    if rank.get("stopword") is True:
        return True
    if _num(rank, "df_ratio") > MAX_DF_RATIO:
        return True
    if _num(rank, "boilerplate") > MAX_BOILERPLATE:
        return True
    if _num(rank, "cooc_entropy") > MAX_COOC_ENTROPY:
        return True
    if "llm_score" in rank and _num(rank, "llm_score", LLM_NEUTRAL) <= MAX_LLM_NOISE_SCORE:
        return True
    return "ridf" in rank and _num(rank, "ridf") < MIN_RIDF


def compute_noise(
    rank: dict[str, Any], posts_count: int, user_rank: Optional[str] = None
) -> bool:
    """True when the tag is generic / not informative; ``user_rank`` overrides metrics."""
    if user_rank == USER_RANK_HIDDEN:
        return True
    if user_rank == USER_RANK_PINNED:
        return False
    return _metrics_noise(rank, posts_count)


def apply_derived(
    rank: dict[str, Any], posts_count: int, user_rank: Optional[str] = None
) -> dict[str, Any]:
    """Return a copy of ``rank`` with ``score`` and ``noise`` recomputed."""
    result: dict[str, Any] = dict(rank or {})
    result["score"] = compute_score(result, user_rank)
    result["noise"] = compute_noise(result, posts_count, user_rank)
    return result


def rank_snapshot_filter(doc: dict[str, Any]) -> dict[str, Any]:
    """Match the exact inputs read, including missing fields, before deriving."""
    return {
        key: doc[key] if key in doc else {"$exists": False}
        for key in ("rank", "posts_count", "user_rank", "rank_pending")
    }


def pending_base_rank_query(owner: str) -> dict[str, Any]:
    """Include legacy tags and interrupted derived writes in base-rank claims."""
    return {
        "owner": owner,
        "$or": [
            {"temperature": 0},
            {"rank.ranked_at": {"$exists": False}},
            {"rank_pending": True},
        ],
    }


def _derived_update(doc: dict[str, Any]) -> UpdateOne:
    rank: Any = doc.get("rank")
    derived: dict[str, Any] = apply_derived(
        rank if isinstance(rank, dict) else {},
        int(doc.get("posts_count") or 0),
        normalize_user_rank(doc.get("user_rank")),
    )
    return UpdateOne(
        {"_id": doc["_id"], **rank_snapshot_filter(doc)},
        {
            "$set": {"rank.score": derived["score"], "rank.noise": derived["noise"]},
            "$unset": {"rank_pending": ""},
        },
    )


def _recompute_chunk(db: Any, docs: List[dict[str, Any]]) -> int:
    """Retry snapshots invalidated by concurrent metrics or override writes."""
    ids: List[Any] = [doc["_id"] for doc in docs]
    for attempt in range(3):
        result: Any = db.tags.bulk_write(
            [_derived_update(doc) for doc in docs], ordered=False
        )
        if result.matched_count == len(docs):
            return len(docs)
        docs = list(
            db.tags.find(
                {"_id": {"$in": ids}},
                projection={
                    "rank": True, "posts_count": True,
                    "user_rank": True, "rank_pending": True,
                },
            )
        )
        if not docs:
            return 0
    raise RuntimeError("Tag rank inputs kept changing during recomputation")


def recompute_derived(db: Any, owner: str, tag_names: Optional[List[str]] = None) -> int:
    """Recompute derived ranks; raise on failure so task retries remain possible."""
    if tag_names is not None and not tag_names:
        return 0
    query: dict[str, Any] = {"owner": owner}
    if tag_names is not None:
        query["tag"] = {"$in": list(tag_names)}
    written: int = 0
    try:
        cursor: Any = db.tags.find(
            query,
            projection={
                "rank": True, "posts_count": True,
                "user_rank": True, "rank_pending": True,
            },
        )
        docs: List[dict[str, Any]] = []
        for doc in cursor:
            docs.append(doc)
            if len(docs) >= RECOMPUTE_BATCH_SIZE:
                written += _recompute_chunk(db, docs)
                docs = []
        if docs:
            written += _recompute_chunk(db, docs)
    except Exception:
        log.exception("Can`t recompute tag rank for owner %s", owner)
        raise
    return written


def normalize_sort_mode(value: Optional[str]) -> str:
    """Validate a ``?sort=`` value against TAG_SORT_MODES."""
    mode: str = (value or "").strip().casefold()
    return mode if mode in TAG_SORT_MODES else DEFAULT_SORT_MODE


def _count_field(only_unread: bool) -> str:
    return "unread_count" if only_unread else "posts_count"


def sort_fields(mode: str, only_unread: bool) -> List[Tuple[str, int]]:
    """Mongo sort spec for a tag list sort mode."""
    tail: List[Tuple[str, int]] = [
        (_count_field(only_unread), DESCENDING),
        ("tag", ASCENDING),
    ]
    if mode == "informative":
        return [("rank.score", DESCENDING), *tail]
    if mode == "hot":
        return [("rank.hot", DESCENDING), ("temperature", DESCENDING), *tail]
    return tail


def _desc(value: Any) -> float:
    """Descending-sort key; missing values sort last like Mongo nulls."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return math.inf
    return -float(value)


def sort_key(mode: str, tag: str, count: int, doc: Optional[dict[str, Any]]) -> Tuple[Any, ...]:
    """Python sort key equivalent to ``sort_fields`` for in-memory lists."""
    rank: Any = (doc or {}).get("rank")
    rank = rank if isinstance(rank, dict) else {}
    tail: Tuple[Any, ...] = (-count, tag)
    if mode == "informative":
        return (_desc(rank.get("score")), *tail)
    if mode == "hot":
        return (_desc(rank.get("hot")), _desc((doc or {}).get("temperature")), *tail)
    return tail


def normalize_user_rank(value: Any) -> Optional[str]:
    """``value`` when it is a known user rank, otherwise None."""
    return value if value in USER_RANKS else None


def is_noise(doc: Optional[dict[str, Any]]) -> bool:
    """Whether a tag doc is hidden by the user or flagged as generic."""
    user_rank: Optional[str] = normalize_user_rank((doc or {}).get("user_rank"))
    if user_rank is not None:
        return user_rank == USER_RANK_HIDDEN
    rank: Any = (doc or {}).get("rank")
    return isinstance(rank, dict) and rank.get("noise") is True


def sort_names(
    names: Sequence[str],
    counts: dict[str, int],
    docs: dict[str, dict[str, Any]],
    mode: str,
) -> List[str]:
    """Order tag names by ``mode`` using in-memory counts and tag docs."""
    return sorted(
        names,
        key=lambda name: sort_key(mode, name, counts.get(name, 0), docs.get(name)),
    )
