"""Cheap candidate groupings: TF-IDF (+LSA), agglomerative clusters, stats."""

import logging
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import sparse
from sklearn.cluster import AgglomerativeClustering, MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from rsstag.stopwords import stopwords

RANDOM_STATE: int = 42
KEYWORDS_PER_CLUSTER: int = 8
LSA_MIN_VOCAB: int = 500
LSA_MAX_COMPONENTS: int = 150
FINE_CLUSTER_ROWS: int = 6  # target rows per fine cluster
FINE_CLUSTER_MIN_CAP: int = 60
FINE_CLUSTER_CAP_ROWS: int = 25  # above the minimum cap, at most one cluster per 25 rows
MAX_BUCKET_ROWS: int = 1500  # largest input given to quadratic agglomerative clustering
NEIGHBOR_BLOCK_ROWS: int = 1024
_TOKEN_PATTERN: str = r"(?u)\b[^\W\d_][\w\-]+\b"

_log: logging.Logger = logging.getLogger("anthology.candidates")


@dataclass
class Vectors:
    """Row-aligned representations of the snippets."""

    tfidf: sparse.csr_matrix
    features: np.ndarray
    dense: np.ndarray  # L2-normalized rows (LSA space when vocab is large)
    _column_sums: Optional[np.ndarray] = field(default=None, repr=False)

    @property
    def column_sums(self) -> np.ndarray:
        """Per-term tf-idf totals, cached so keyword contrast stays linear."""
        if self._column_sums is None:
            self._column_sums = np.asarray(self.tfidf.sum(axis=0)).ravel()
        return self._column_sums


@dataclass
class Cluster:
    id: str
    members: List[int]  # snippet row indices, ordered by closeness to centroid
    centroid: np.ndarray
    keywords: List[str] = field(default_factory=list)
    cohesion: float = 0.0
    label: str = ""
    kind: str = "other"
    score: int = 3
    intruder_ok: Optional[bool] = None
    loose: bool = False  # lenient leftover group, not validated by score/intruder checks
    label_score_valid: bool = False  # explicit in-range score, not a fallback or clamp

    @property
    def size(self) -> int:
        return len(self.members)


def _stopword_list() -> List[str]:
    return sorted(set(stopwords.words("english")) | set(stopwords.words("russian")))


def vectorize(texts: Sequence[str], min_df: Optional[int] = None) -> Vectors:
    """TF-IDF over texts, reduced by LSA when the vocabulary is large."""
    n_docs: int = len(texts)
    vectorizer: TfidfVectorizer = TfidfVectorizer(
        sublinear_tf=True,
        stop_words=_stopword_list(),
        token_pattern=_TOKEN_PATTERN,
        lowercase=True,
        max_df=0.9 if n_docs >= 20 else 1.0,
        min_df=min_df if min_df is not None else (2 if n_docs >= 200 else 1),
        max_features=30000,
    )
    try:
        tfidf: sparse.csr_matrix = vectorizer.fit_transform(texts).tocsr()
        features: np.ndarray = vectorizer.get_feature_names_out()
    except ValueError as exc:  # empty vocabulary
        _log.warning("TF-IDF produced no vocabulary (%s); using empty vectors", exc)
        tfidf = sparse.csr_matrix((n_docs, 1))
        features = np.array([""])
    return Vectors(tfidf=tfidf, features=features, dense=_reduce(tfidf))


def _reduce(tfidf: sparse.csr_matrix) -> np.ndarray:
    n_docs, n_terms = tfidf.shape
    if n_docs == 0:
        return np.zeros((0, n_terms))
    if n_terms >= LSA_MIN_VOCAB and n_docs > 10:
        components: int = min(LSA_MAX_COMPONENTS, n_docs - 1, n_terms - 1)
        svd: TruncatedSVD = TruncatedSVD(n_components=components, random_state=RANDOM_STATE)
        reduced: np.ndarray = svd.fit_transform(tfidf)
        return normalize(reduced)
    return normalize(tfidf.toarray())


def fine_cluster_count(n_docs: int) -> int:
    """k ≈ n/6, capped at max(60, n/25) so large inputs keep proportional detail."""
    cap: int = max(FINE_CLUSTER_MIN_CAP, round(n_docs / FINE_CLUSTER_CAP_ROWS))
    return max(1, min(max(2, round(n_docs / FINE_CLUSTER_ROWS)), cap, n_docs - 1))


def cluster_rows(
    dense: np.ndarray, n_clusters: int, split_small: bool = False
) -> np.ndarray:
    """Cosine/average clustering; large inputs are clustered bucket by bucket."""
    n_rows: int = dense.shape[0]
    if (n_rows < 4 and not split_small) or n_rows < 2 or n_clusters <= 1:
        return np.zeros(n_rows, dtype=int)

    def fit(rows: np.ndarray) -> np.ndarray:
        share: int = max(1, round(n_clusters * len(rows) / n_rows))
        return _agglomerative(dense[rows], share, split_small)

    return bucketed_labels(dense, fit)


def threshold_rows(dense: np.ndarray, distance_threshold: float) -> np.ndarray:
    """Cosine/average clustering cut at a distance, bucket by bucket."""
    def fit(rows: np.ndarray) -> np.ndarray:
        if len(rows) < 2:
            return np.zeros(len(rows), dtype=int)
        model: AgglomerativeClustering = AgglomerativeClustering(
            n_clusters=None, distance_threshold=distance_threshold,
            metric="cosine", linkage="average",
        )
        return model.fit_predict(safe_rows(dense[rows]))

    return bucketed_labels(dense, fit)


def _agglomerative(dense: np.ndarray, n_clusters: int, split_small: bool) -> np.ndarray:
    n_rows: int = dense.shape[0]
    if (n_rows < 4 and not split_small) or n_rows < 2 or n_clusters <= 1:
        return np.zeros(n_rows, dtype=int)
    model: AgglomerativeClustering = AgglomerativeClustering(
        n_clusters=min(n_clusters, n_rows), metric="cosine", linkage="average"
    )
    return model.fit_predict(safe_rows(dense))


def bucketed_labels(
    dense: np.ndarray, fit: Callable[[np.ndarray], np.ndarray],
    max_rows: Optional[int] = None,
) -> np.ndarray:
    """Run `fit` on every bucket of rows; labels are made globally unique."""
    labels: np.ndarray = np.zeros(dense.shape[0], dtype=int)
    offset: int = 0
    for rows in bucket_rows(dense, max_rows):
        local: np.ndarray = np.asarray(fit(rows), dtype=int)
        labels[rows] = local + offset
        offset += int(local.max()) + 1 if len(local) else 0
    return labels


def bucket_rows(dense: np.ndarray, max_rows: Optional[int] = None) -> List[np.ndarray]:
    """Partition rows into similar buckets of at most `max_rows`; every row kept once."""
    max_rows = MAX_BUCKET_ROWS if max_rows is None else max_rows
    pending: List[np.ndarray] = [np.arange(dense.shape[0])]
    buckets: List[np.ndarray] = []
    while pending:
        rows: np.ndarray = pending.pop()
        if len(rows) <= max_rows:
            if len(rows):
                buckets.append(rows)
            continue
        pending.extend(_split_bucket(dense, rows, max_rows))
    if len(buckets) > 1:
        _log.info("Anthology clustering: %d rows in %d buckets", dense.shape[0], len(buckets))
    return sorted(buckets, key=lambda rows: int(rows[0]))


def _split_bucket(dense: np.ndarray, rows: np.ndarray, max_rows: int) -> List[np.ndarray]:
    """Split by k-means; identical vectors fall back to contiguous chunks."""
    parts: int = max(2, math.ceil(2 * len(rows) / max_rows))
    model: MiniBatchKMeans = MiniBatchKMeans(
        n_clusters=parts, random_state=RANDOM_STATE, n_init=3,
        batch_size=min(len(rows), 4096),
    )
    labels: np.ndarray = model.fit_predict(dense[rows])
    groups: List[np.ndarray] = [rows[labels == label] for label in np.unique(labels)]
    if len(groups) > 1:
        return groups
    return [rows[start:start + max_rows] for start in range(0, len(rows), max_rows)]


def safe_rows(dense: np.ndarray) -> np.ndarray:
    """Cosine distance is undefined for zero rows; give them a tiny shared axis."""
    rows: np.ndarray = np.array(dense, dtype=float, copy=True)
    zero_rows: np.ndarray = np.linalg.norm(rows, axis=1) == 0
    if zero_rows.any():
        rows = np.hstack([rows, zero_rows.astype(float)[:, None]])
    return rows


def build_candidates(
    vectors: Vectors, n_clusters: Optional[int] = None, split_small: bool = False
) -> Tuple[List[Cluster], List[int]]:
    """Fine clusters of the snippets plus the singleton rows (unsorted)."""
    n_rows: int = vectors.dense.shape[0]
    if n_rows == 0:
        return [], []
    labels: np.ndarray = cluster_rows(
        vectors.dense, fine_cluster_count(n_rows) if n_clusters is None else n_clusters,
        split_small=split_small,
    )
    groups: Dict[int, List[int]] = {}
    for row, label in enumerate(labels.tolist()):
        groups.setdefault(int(label), []).append(row)
    ordered: List[List[int]] = sorted(groups.values(), key=lambda rows: (-len(rows), rows[0]))
    clusters: List[Cluster] = []
    unsorted: List[int] = []
    for rows in ordered:
        if len(rows) < 2 and n_rows > 1:
            unsorted.extend(rows)
            continue
        clusters.append(make_cluster(f"c{len(clusters)}", rows, vectors))
    return clusters, sorted(unsorted)


def make_cluster(cluster_id: str, rows: List[int], vectors: Vectors) -> Cluster:
    """Compute centroid, member order, cohesion and keywords for rows."""
    centroid: np.ndarray = centroid_of(vectors.dense, rows)
    sims: np.ndarray = vectors.dense[rows] @ centroid
    order: List[int] = [rows[i] for i in np.argsort(-sims, kind="stable")]
    cohesion: float = float(np.clip(sims.mean(), 0.0, 1.0)) if len(rows) else 0.0
    return Cluster(
        id=cluster_id,
        members=order,
        centroid=centroid,
        keywords=contrastive_keywords(vectors, rows),
        cohesion=round(cohesion, 4),
    )


def centroid_of(dense: np.ndarray, rows: Sequence[int]) -> np.ndarray:
    mean: np.ndarray = dense[list(rows)].mean(axis=0)
    norm: float = float(np.linalg.norm(mean))
    return mean / norm if norm > 0 else mean


def contrastive_keywords(
    vectors: Vectors, rows: Sequence[int], top_n: int = KEYWORDS_PER_CLUSTER
) -> List[str]:
    """Top terms by mean tf-idf inside the rows minus mean outside."""
    n_rows: int = vectors.tfidf.shape[0]
    unique_rows: List[int] = sorted(set(rows))
    inside_sum: np.ndarray = np.asarray(vectors.tfidf[unique_rows].sum(axis=0)).ravel()
    inside: np.ndarray = inside_sum / max(1, len(unique_rows))
    outside_count: int = n_rows - len(unique_rows)
    if outside_count <= 0:
        scores: np.ndarray = inside
    else:
        scores = inside - (vectors.column_sums - inside_sum) / outside_count
    top: np.ndarray = np.argsort(-scores, kind="stable")[:top_n]
    return [str(vectors.features[i]) for i in top if scores[i] > 0 and vectors.features[i]]


def centroid_similarity(clusters: Sequence[Cluster]) -> np.ndarray:
    """Pairwise cosine between cluster centroids (small inputs only)."""
    if not clusters:
        return np.zeros((0, 0))
    matrix: np.ndarray = np.vstack([c.centroid for c in clusters])
    return matrix @ matrix.T


def nearest_clusters(
    clusters: Sequence[Cluster], per_cluster: int
) -> List[List[Tuple[float, int]]]:
    """Each cluster's most similar other clusters, best first, in bounded blocks."""
    if len(clusters) < 2 or per_cluster <= 0:
        return [[] for _ in clusters]
    matrix: np.ndarray = np.vstack([c.centroid for c in clusters])
    count: int = min(per_cluster, len(clusters) - 1)
    result: List[List[Tuple[float, int]]] = []
    for start in range(0, len(clusters), NEIGHBOR_BLOCK_ROWS):
        sims: np.ndarray = matrix[start:start + NEIGHBOR_BLOCK_ROWS] @ matrix.T
        for offset, row in enumerate(sims):
            row[start + offset] = -np.inf
            top: np.ndarray = np.argsort(-row, kind="stable")[:count]
            result.append([(float(row[j]), int(j)) for j in top])
    return result


def merge_pairs(
    clusters: Sequence[Cluster], threshold: float, per_cluster: int
) -> List[Tuple[int, int]]:
    """Pairs among each cluster's nearest neighbors with cosine ≥ threshold, best first."""
    best: Dict[Tuple[int, int], float] = {}
    for i, neighbors in enumerate(nearest_clusters(clusters, per_cluster)):
        for sim, j in neighbors:
            if sim >= threshold:
                best[(min(i, j), max(i, j))] = sim
    ordered: List[Tuple[Tuple[int, int], float]] = sorted(
        best.items(), key=lambda item: (-item[1], item[0])
    )
    return [pair for pair, _sim in ordered]
