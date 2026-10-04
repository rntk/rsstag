"""Lenient labeling of snippets that every strict pass left unsorted.

Leftovers are grouped by a loose similarity threshold (singletons allowed) and
named by the judge, but nothing is dissolved: every leftover ends up in a
labeled loose cluster so the Unsorted pile becomes browsable topics.
"""

import logging
from dataclasses import replace
from typing import Dict, List, Set

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from rsstag.anthology import stages
from rsstag.anthology.candidates import (
    Cluster,
    Vectors,
    safe_rows,
    contrastive_keywords,
    make_cluster,
    vectorize,
)
from rsstag.anthology.judge import Judge
from rsstag.anthology.recovery import map_cluster
from rsstag.anthology.result import RunCounters
from rsstag.anthology.units import Snippet

# Cosine distance under average linkage: groups whose members share ≥ 0.2 mean
# similarity stay together; anything less similar stays a single-snippet topic.
LOOSE_DISTANCE_THRESHOLD: float = 0.8
LOOSE_THEME_LABEL: str = "Loose topics"

_log: logging.Logger = logging.getLogger("anthology.loose")


def unassigned_rows(clusters: List[Cluster], n_snippets: int) -> List[int]:
    assigned: Set[int] = {row for cluster in clusters for row in cluster.members}
    return [row for row in range(n_snippets) if row not in assigned]


def loose_groups(dense: np.ndarray) -> List[List[int]]:
    """Threshold clustering of local rows; groups of any size, largest first."""
    n_rows: int = dense.shape[0]
    if n_rows < 2:
        return [list(range(n_rows))] if n_rows else []
    model: AgglomerativeClustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=LOOSE_DISTANCE_THRESHOLD,
        metric="cosine",
        linkage="average",
    )
    labels: np.ndarray = model.fit_predict(safe_rows(dense))
    groups: Dict[int, List[int]] = {}
    for row, label in enumerate(labels.tolist()):
        groups.setdefault(int(label), []).append(row)
    return sorted(groups.values(), key=lambda rows: (-len(rows), rows[0]))


def label_leftovers(
    clusters: List[Cluster],
    vectors: Vectors,
    snippets: List[Snippet],
    judge: Judge,
    seed: str,
    counters: RunCounters,
) -> List[Cluster]:
    """Return labeled loose clusters covering every snippet outside `clusters`."""
    rows: List[int] = unassigned_rows(clusters, len(snippets))
    if not rows:
        return []
    remaining: List[Snippet] = [snippets[row] for row in rows]
    local: Vectors = vectorize([s.vector_text for s in remaining], min_df=1)
    groups: List[Cluster] = [
        make_cluster(f"l{n}", members, local) for n, members in enumerate(loose_groups(local.dense))
    ]
    calls_before: int = judge.calls
    stages.label_clusters(groups, remaining, judge, seed)
    counters.loose_llm_calls = judge.calls - calls_before
    loose: List[Cluster] = [
        replace(map_cluster(c, rows, vectors, prefix="l"), loose=True, intruder_ok=None)
        for c in groups
    ]
    counters.loose_snippets = len(rows)
    counters.loose_clusters = len(loose)
    _log.info(
        "Anthology loose labels: snippets=%d clusters=%d singletons=%d llm_calls=%d",
        len(rows), len(loose), sum(1 for c in loose if c.size == 1), counters.loose_llm_calls,
    )
    return loose


def loose_theme(clusters: List[Cluster], vectors: Vectors) -> stages.Theme:
    rows: List[int] = [row for cluster in clusters for row in cluster.members]
    return stages.Theme(
        clusters=clusters,
        label=LOOSE_THEME_LABEL,
        keywords=contrastive_keywords(vectors, rows),
        loose=True,
    )
