"""TASK_TAGS_CORPUS_RANK handler: writes rank.{feeds, feed_entropy, boilerplate, title_ratio, hot} for every tag of a user.

Contract: ``db.tags.bulk_write([UpdateOne(..., {"$set": {"rank.<key>": ...}})])``
for this task's own keys only, then ``tag_rank.recompute_derived(db, owner)``.

The owner's posts are streamed once; only per-tag counters are kept in memory.
"""

import logging
import math
import time
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set

from pymongo import UpdateOne
from pymongo.database import Database

from rsstag.tag_rank import recompute_derived
from rsstag.tags_builder import TagsBuilder

log: logging.Logger = logging.getLogger("tag_rank_corpus")

SECONDS_PER_DAY: float = 86400.0
# Feeds with fewer posts are ignored by the boilerplate share (too noisy).
BOILERPLATE_MIN_FEED_POSTS: int = 20
# Trending window: last N days vs the preceding M days, relative to newest post.
HOT_RECENT_DAYS: int = 3
HOT_BASELINE_DAYS: int = 30
# Added to the baseline rate (per day) so unseen-before tags do not divide by 0.
HOT_SMOOTHING: float = 0.1
WRITE_CHUNK_SIZE: int = 1000
RANK_KEYS: tuple[str, ...] = ("feeds", "feed_entropy", "boilerplate", "title_ratio", "hot")
_POST_PROJECTION: dict[str, int] = {
    "feed_id": 1,
    "unix_date": 1,
    "tags": 1,
    "content.title": 1,
}


def feed_entropy(feed_counts: Iterable[int]) -> float:
    """Shannon entropy of a tag's posts over feeds, normalized to 0..1."""
    counts: List[int] = [c for c in feed_counts if c > 0]
    if len(counts) <= 1:
        return 0.0
    total: int = sum(counts)
    entropy: float = -sum((c / total) * math.log(c / total) for c in counts)
    return max(0.0, min(1.0, entropy / math.log(len(counts))))


def boilerplate_share(
    tag_feed_counts: Dict[Any, int],
    feed_totals: Dict[Any, int],
    min_feed_posts: int = BOILERPLATE_MIN_FEED_POSTS,
) -> float:
    """Max share of a feed's posts carrying the tag, over feeds big enough."""
    best: float = 0.0
    for feed, count in tag_feed_counts.items():
        total: int = feed_totals.get(feed, 0)
        if total >= min_feed_posts:
            best = max(best, count / total)
    return best


def hot_score(
    recent_count: int,
    baseline_count: int,
    recent_days: int = HOT_RECENT_DAYS,
    baseline_days: int = HOT_BASELINE_DAYS,
    smoothing: float = HOT_SMOOTHING,
) -> float:
    """Poisson z-like trend: (recent rate - baseline rate) / sqrt(baseline + s)."""
    if recent_count <= 0 or recent_days <= 0 or baseline_days <= 0:
        return 0.0
    recent_rate: float = recent_count / recent_days
    baseline_rate: float = baseline_count / baseline_days
    return (recent_rate - baseline_rate) / math.sqrt(baseline_rate + smoothing)


def day_index(unix_date: Any) -> Optional[int]:
    """Day bucket of a unix timestamp, None for missing / invalid values."""
    if isinstance(unix_date, bool) or not isinstance(unix_date, (int, float)):
        return None
    if math.isnan(unix_date) or math.isinf(unix_date):
        return None
    return int(math.floor(unix_date / SECONDS_PER_DAY))


def title_stems(builder: TagsBuilder, title: Any) -> Set[str]:
    """Distinct stems of a post title, built the same way as post tags."""
    if not isinstance(title, str) or not title:
        return set()
    stems: Set[str] = set()
    for word in builder.text2words(title):
        stem: str = builder.process_word(word)
        if stem:
            stems.add(stem)
    return stems


def window_of(day: Optional[int], newest_day: Optional[int]) -> str:
    """Classify a post day as 'recent', 'baseline' or 'old'."""
    if day is None or newest_day is None:
        return "old"
    age: int = newest_day - day
    if 0 <= age < HOT_RECENT_DAYS:
        return "recent"
    if HOT_RECENT_DAYS <= age < HOT_RECENT_DAYS + HOT_BASELINE_DAYS:
        return "baseline"
    return "old"


class CorpusStats:
    """Per-tag counters accumulated during the single pass over posts."""

    def __init__(self, newest_day: Optional[int]) -> None:
        self.newest_day: Optional[int] = newest_day
        self.posts: int = 0
        self.feed_totals: Counter = Counter()
        self.tag_feeds: Dict[str, Counter] = defaultdict(Counter)
        self.title_hits: Counter = Counter()
        self.recent: Counter = Counter()
        self.baseline: Counter = Counter()
        self._builder: TagsBuilder = TagsBuilder()

    def add_post(self, post: dict[str, Any]) -> None:
        tags: Set[str] = {t for t in (post.get("tags") or []) if t}
        feed: Any = post.get("feed_id")
        self.posts += 1
        self.feed_totals[feed] += 1
        if not tags:
            return
        titles: Set[str] = title_stems(self._builder, (post.get("content") or {}).get("title"))
        window: str = window_of(day_index(post.get("unix_date")), self.newest_day)
        for tag in tags:
            self.tag_feeds[tag][feed] += 1
            if tag in titles:
                self.title_hits[tag] += 1
            if window == "recent":
                self.recent[tag] += 1
            elif window == "baseline":
                self.baseline[tag] += 1

    def rank_for(self, tag: str) -> dict[str, float]:
        """Rank keys for ``tag``; zeros when the tag never occurs in posts."""
        feeds: Counter = self.tag_feeds.get(tag) or Counter()
        total: int = sum(feeds.values())
        return {
            "feeds": len(feeds),
            "feed_entropy": feed_entropy(feeds.values()),
            "boilerplate": boilerplate_share(
                feeds, self.feed_totals, BOILERPLATE_MIN_FEED_POSTS
            ),
            "title_ratio": self.title_hits[tag] / total if total else 0.0,
            "hot": hot_score(self.recent[tag], self.baseline[tag]),
        }


def newest_post_day(db: Database, owner: str) -> Optional[int]:
    """Day of the owner's newest post, None when there are no dated posts."""
    doc: Optional[dict[str, Any]] = db.posts.find_one(
        {"owner": owner, "unix_date": {"$type": "number"}},
        projection={"unix_date": 1},
        sort=[("unix_date", -1)],
    )
    return day_index(doc.get("unix_date")) if doc else None


def collect_stats(db: Database, owner: str, newest_day: Optional[int]) -> CorpusStats:
    """Stream the owner's posts once and accumulate counters."""
    stats: CorpusStats = CorpusStats(newest_day)
    for post in db.posts.find({"owner": owner}, projection=_POST_PROJECTION):
        stats.add_post(post)
    return stats


def build_updates(db: Database, owner: str, stats: CorpusStats) -> Iterator[UpdateOne]:
    """One ``$set`` per tag doc of the owner."""
    for doc in db.tags.find({"owner": owner}, projection={"tag": 1}):
        values: dict[str, float] = stats.rank_for(doc["tag"])
        fields: dict[str, Any] = {f"rank.{key}": values[key] for key in RANK_KEYS}
        fields["rank_pending"] = True
        yield UpdateOne(
            {"_id": doc["_id"]},
            {"$set": fields},
        )


def write_updates(db: Database, updates: Iterable[UpdateOne]) -> int:
    """Bulk write updates in chunks; returns number of tags written."""
    written: int = 0
    chunk: List[UpdateOne] = []
    for update in updates:
        chunk.append(update)
        if len(chunk) >= WRITE_CHUNK_SIZE:
            db.tags.bulk_write(chunk, ordered=False)
            written += len(chunk)
            chunk = []
    if chunk:
        db.tags.bulk_write(chunk, ordered=False)
        written += len(chunk)
    return written


def run(db: Database, config: dict[str, Any], owner: str) -> bool:
    """Compute this task's rank keys for ``owner``; True when the task is done."""
    started: float = time.monotonic()
    try:
        stats: CorpusStats = collect_stats(db, owner, newest_post_day(db, owner))
        if stats.posts == 0:
            log.info("TASK_TAGS_CORPUS_RANK: owner %s has no posts", owner)
            return True
        written: int = write_updates(db, build_updates(db, owner, stats))
        recompute_derived(db, owner)
    except Exception as exc:
        log.error("Can`t compute corpus rank for owner %s. Info: %s", owner, exc)
        return False
    log.info(
        "TASK_TAGS_CORPUS_RANK owner %s: %s posts, %s feeds, %s tags ranked in %.2fs",
        owner,
        stats.posts,
        len(stats.feed_totals),
        written,
        time.monotonic() - started,
    )
    return True
