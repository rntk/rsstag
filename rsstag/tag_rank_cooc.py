"""TASK_TAGS_COOC_RANK handler: writes rank.cooc_entropy for every tag of a user.

``cooc_entropy`` (0..1) tells how "generic" a tag is by how evenly it co-occurs
with a fixed set of context tags. High: pairs with anything. Low: peaked
neighbours (a specific, topical tag).

Bounds: posts are streamed once. Only tags with ``posts_count >= COOC_MIN_DF``
(at most ``COOC_MAX_VOCAB`` of them) are considered, at most
``COOC_MAX_TAGS_PER_POST`` per post (most frequent kept), and pairs are only
counted against the ``COOC_CONTEXT_SIZE`` most frequent tags. Time is
O(posts * COOC_MAX_TAGS_PER_POST * min(COOC_CONTEXT_SIZE, per-post tags)); the
accumulator is a scipy CSR matrix (vocab x contexts) flushed every
``COOC_FLUSH_PAIRS`` pairs, so peak memory is the matrix nnz (<= vocab*contexts
in the worst case, a few million in practice) plus one pair buffer.

Contract: ``db.tags.bulk_write([UpdateOne(..., {"$set": {"rank.cooc_entropy": ...}})])``
for this task's own key only, then ``tag_rank.recompute_derived(db, owner)``.
"""

import logging
import math
import time
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

import numpy as np
from pymongo import ASCENDING, DESCENDING, UpdateOne
from pymongo.database import Database
from scipy import sparse

from rsstag import tag_rank

log: logging.Logger = logging.getLogger("tag_rank_cooc")

COOC_MIN_DF: int = 3
COOC_MAX_VOCAB: int = 20000
COOC_CONTEXT_SIZE: int = 2000
COOC_MAX_TAGS_PER_POST: int = 50
COOC_MIN_PAIRS: int = 20
COOC_FLUSH_PAIRS: int = 2_000_000
COOC_WRITE_BATCH: int = 1000
POSTS_BATCH_SIZE: int = 1000

Vocab = Tuple[List[str], np.ndarray]


def normalized_entropy(counts: np.ndarray, context_df: np.ndarray, n_contexts: int) -> float:
    """Entropy of popularity-corrected co-occurrence counts, scaled to 0..1.

    ``counts[i] / context_df[i]`` removes the bias towards popular contexts: a
    tag that pairs with every context in proportion to its popularity gets a
    uniform distribution (1.0), one tied to a few contexts gets close to 0.
    """
    if n_contexts <= 1:
        return 0.0
    mask: np.ndarray = (counts > 0) & (context_df > 0)
    if not mask.any():
        return 0.0
    weighted: np.ndarray = counts[mask] / context_df[mask]
    probs: np.ndarray = weighted / weighted.sum()
    entropy: float = float(-(probs * np.log(probs)).sum())
    return min(1.0, max(0.0, entropy / math.log(n_contexts)))


def entropy_scores(
    matrix: sparse.csr_matrix, context_df: np.ndarray, min_pairs: int
) -> Dict[int, float]:
    """Normalized entropy per row index with at least ``min_pairs`` pairs."""
    n_contexts: int = int((np.asarray(matrix.sum(axis=0)).ravel() > 0).sum())
    totals: np.ndarray = np.asarray(matrix.sum(axis=1)).ravel()
    result: Dict[int, float] = {}
    for row in np.flatnonzero(totals >= max(min_pairs, 1)):
        start, end = matrix.indptr[row], matrix.indptr[row + 1]
        counts: np.ndarray = np.zeros(matrix.shape[1], dtype=np.float64)
        counts[matrix.indices[start:end]] = matrix.data[start:end]
        result[int(row)] = normalized_entropy(counts, context_df, n_contexts)
    return result


def load_vocab(db: Database, owner: str) -> Vocab:
    """Tags with enough posts, most frequent first, plus their post counts."""
    cursor = (
        db.tags.find(
            {"owner": owner, "posts_count": {"$gte": COOC_MIN_DF}},
            projection={"tag": True, "posts_count": True},
        )
        .sort([("posts_count", DESCENDING), ("tag", ASCENDING)])
        .limit(COOC_MAX_VOCAB)
    )
    names: List[str] = []
    counts: List[int] = []
    for doc in cursor:
        names.append(doc["tag"])
        counts.append(int(doc["posts_count"]))
    return names, np.asarray(counts, dtype=np.float64)


def post_ids(tags: Any, index: Dict[str, int], cap: int) -> np.ndarray:
    """Sorted vocab ids of a post's tags; ids are df ranks, so the cap keeps frequent ones."""
    if not isinstance(tags, (list, tuple, set)):
        return np.empty(0, dtype=np.int32)
    ids: List[int] = sorted({index[tag] for tag in tags if tag in index})
    return np.asarray(ids[:cap], dtype=np.int32)


def post_pairs(ids: np.ndarray, n_contexts: int) -> Tuple[np.ndarray, np.ndarray]:
    """(row, context) pairs of one post; context ids are the first ``n_contexts`` vocab ids."""
    contexts: np.ndarray = ids[ids < n_contexts]
    rows: np.ndarray = np.repeat(ids, len(contexts))
    cols: np.ndarray = np.tile(contexts, len(ids))
    keep: np.ndarray = rows != cols
    return rows[keep], cols[keep]


class CoocAccumulator:
    """Accumulates (tag, context) pair counts in a CSR matrix, flushing in bulk."""

    def __init__(self, n_tags: int, n_contexts: int, flush_pairs: int = COOC_FLUSH_PAIRS):
        self.n_contexts: int = n_contexts
        self.flush_pairs: int = flush_pairs
        self.matrix: sparse.csr_matrix = sparse.csr_matrix(
            (n_tags, n_contexts), dtype=np.float32
        )
        self._rows: List[np.ndarray] = []
        self._cols: List[np.ndarray] = []
        self._buffered: int = 0

    def add_post(self, ids: np.ndarray) -> None:
        rows, cols = post_pairs(ids, self.n_contexts)
        if len(rows) == 0:
            return
        self._rows.append(rows)
        self._cols.append(cols)
        self._buffered += len(rows)
        if self._buffered >= self.flush_pairs:
            self.flush()

    def flush(self) -> None:
        if not self._buffered:
            return
        rows: np.ndarray = np.concatenate(self._rows)
        cols: np.ndarray = np.concatenate(self._cols)
        delta: sparse.csr_matrix = sparse.coo_matrix(
            (np.ones(len(rows), dtype=np.float32), (rows, cols)),
            shape=self.matrix.shape,
        ).tocsr()
        self.matrix = (self.matrix + delta).tocsr()
        self._rows, self._cols, self._buffered = [], [], 0

    def result(self) -> sparse.csr_matrix:
        self.flush()
        return self.matrix


def iter_post_tags(db: Database, owner: str) -> Iterator[Any]:
    cursor = db.posts.find(
        {"owner": owner}, projection={"tags": True}, batch_size=POSTS_BATCH_SIZE
    )
    for post in cursor:
        yield post.get("tags")


def build_matrix(
    posts_tags: Iterable[Any], names: List[str], n_contexts: int
) -> sparse.csr_matrix:
    index: Dict[str, int] = {name: i for i, name in enumerate(names)}
    acc: CoocAccumulator = CoocAccumulator(len(names), n_contexts)
    for tags in posts_tags:
        acc.add_post(post_ids(tags, index, COOC_MAX_TAGS_PER_POST))
    return acc.result()


def compute_scores(
    posts_tags: Iterable[Any], names: List[str], counts: np.ndarray
) -> Dict[str, float]:
    """Tag name -> normalized co-occurrence entropy for tags with enough pairs."""
    n_contexts: int = min(COOC_CONTEXT_SIZE, len(names))
    if n_contexts < 2:
        return {}
    matrix: sparse.csr_matrix = build_matrix(posts_tags, names, n_contexts)
    rows: Dict[int, float] = entropy_scores(matrix, counts[:n_contexts], COOC_MIN_PAIRS)
    return {names[row]: value for row, value in rows.items()}


def _updates(owner: str, scores: Dict[str, float]) -> Iterator[UpdateOne]:
    for tag, value in scores.items():
        yield UpdateOne(
            {"owner": owner, "tag": tag},
            {"$set": {"rank.cooc_entropy": value, "rank_pending": True}},
        )


def write_scores(db: Database, owner: str, scores: Dict[str, float]) -> int:
    """Bulk-write ``rank.cooc_entropy`` in chunks; returns the number of updates sent."""
    batch: List[UpdateOne] = []
    written: int = 0
    for update in _updates(owner, scores):
        batch.append(update)
        if len(batch) >= COOC_WRITE_BATCH:
            db.tags.bulk_write(batch, ordered=False)
            written += len(batch)
            batch = []
    if batch:
        db.tags.bulk_write(batch, ordered=False)
        written += len(batch)
    return written


def _process(db: Database, owner: str) -> Optional[int]:
    names, counts = load_vocab(db, owner)
    scores: Dict[str, float] = compute_scores(iter_post_tags(db, owner), names, counts)
    if not scores:
        return 0
    written: int = write_scores(db, owner, scores)
    tag_rank.recompute_derived(db, owner)
    return written


def run(db: Database, config: dict[str, Any], owner: str) -> bool:
    """Compute this task's rank keys for ``owner``; True when the task is done."""
    started: float = time.monotonic()
    try:
        written: Optional[int] = _process(db, owner)
    except Exception as exc:
        log.exception("Can`t compute cooc rank for owner %s. Info: %s", owner, exc)
        return False
    log.info(
        "TASK_TAGS_COOC_RANK for owner %s: %s tags scored in %.2fs",
        owner,
        written,
        time.monotonic() - started,
    )
    return True
