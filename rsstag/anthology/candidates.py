"""Cheap candidate groupings: TF-IDF (+LSA), agglomerative clusters, stats."""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import sparse
from sklearn.cluster import AgglomerativeClustering
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from rsstag.stopwords import stopwords

RANDOM_STATE: int = 42
KEYWORDS_PER_CLUSTER: int = 8
LSA_MIN_VOCAB: int = 500
LSA_MAX_COMPONENTS: int = 150
_TOKEN_PATTERN: str = r"(?u)\b[^\W\d_][\w\-]+\b"

_log: logging.Logger = logging.getLogger("anthology.candidates")


@dataclass
class Vectors:
    """Row-aligned representations of the snippets."""

    tfidf: sparse.csr_matrix
    features: np.ndarray
    dense: np.ndarray  # L2-normalized rows (LSA space when vocab is large)


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
    """k ≈ clamp(n/6, 2, 60), never above n-1."""
    return max(1, min(max(2, round(n_docs / 6)), 60, n_docs - 1))


def cluster_rows(
    dense: np.ndarray, n_clusters: int, split_small: bool = False
) -> np.ndarray:
    """Cosine/average clustering; optionally split tiny inputs for recovery."""
    n_rows: int = dense.shape[0]
    if (n_rows < 4 and not split_small) or n_rows < 2 or n_clusters <= 1:
        return np.zeros(n_rows, dtype=int)
    model: AgglomerativeClustering = AgglomerativeClustering(
        n_clusters=min(n_clusters, n_rows), metric="cosine", linkage="average"
    )
    return model.fit_predict(_safe_rows(dense))


def _safe_rows(dense: np.ndarray) -> np.ndarray:
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
    inside_mask: np.ndarray = np.zeros(n_rows, dtype=bool)
    inside_mask[list(rows)] = True
    inside: np.ndarray = np.asarray(vectors.tfidf[inside_mask].mean(axis=0)).ravel()
    if inside_mask.all():
        scores: np.ndarray = inside
    else:
        outside: np.ndarray = np.asarray(vectors.tfidf[~inside_mask].mean(axis=0)).ravel()
        scores = inside - outside
    top: np.ndarray = np.argsort(-scores, kind="stable")[:top_n]
    return [str(vectors.features[i]) for i in top if scores[i] > 0 and vectors.features[i]]


def centroid_similarity(clusters: Sequence[Cluster]) -> np.ndarray:
    """Pairwise cosine between cluster centroids."""
    if not clusters:
        return np.zeros((0, 0))
    matrix: np.ndarray = np.vstack([c.centroid for c in clusters])
    return matrix @ matrix.T


def merge_pairs(
    clusters: Sequence[Cluster], threshold: float, max_pairs: int
) -> List[Tuple[int, int]]:
    """Index pairs of clusters with centroid cosine ≥ threshold, best first."""
    sims: np.ndarray = centroid_similarity(clusters)
    pairs: List[Tuple[float, int, int]] = []
    for i in range(len(clusters)):
        for j in range(i + 1, len(clusters)):
            if sims[i, j] >= threshold:
                pairs.append((float(sims[i, j]), i, j))
    pairs.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [(i, j) for _, i, j in pairs[:max_pairs]]
