"""One bounded recovery pass over snippets left outside accepted clusters."""

import logging
import math
from dataclasses import replace
from typing import List, Set

from rsstag.anthology import stages
from rsstag.anthology.candidates import Cluster, Vectors, build_candidates, centroid_of, vectorize
from rsstag.anthology.judge import Judge
from rsstag.anthology.result import RunCounters
from rsstag.anthology.units import Snippet

RECOVERY_TARGET_SIZE: int = 4
_log: logging.Logger = logging.getLogger("anthology.recovery")


def recovery_cluster_count(n_docs: int) -> int:
    """Finer groups without the first pass's fixed 60-cluster ceiling."""
    return max(1, min(max(2, math.ceil(n_docs / RECOVERY_TARGET_SIZE)), n_docs - 1))


def recover_unsorted(
    clusters: List[Cluster],
    vectors: Vectors,
    snippets: List[Snippet],
    judge: Judge,
    seed: str,
    counters: RunCounters,
) -> List[Cluster]:
    """Keep accepted clusters fixed and judge new groups in a fresh local space."""
    assigned: Set[int] = {row for cluster in clusters for row in cluster.members}
    rows: List[int] = [row for row in range(len(snippets)) if row not in assigned]
    counters.recovery_snippets_input = len(rows)
    if len(rows) < 2:
        return clusters
    remaining: List[Snippet] = [snippets[row] for row in rows]
    local_vectors: Vectors = vectorize([s.vector_text for s in remaining], min_df=1)
    candidates: List[Cluster]
    _singletons: List[int]
    candidates, _singletons = build_candidates(
        local_vectors, recovery_cluster_count(len(rows)), split_small=True
    )
    counters.recovery_clusters_candidate = len(candidates)
    counters.clusters_candidate += len(candidates)
    calls_before: int = judge.calls
    recovered: List[Cluster] = _validate(candidates, local_vectors, remaining, judge, seed, counters)
    counters.recovery_llm_calls = judge.calls - calls_before
    mapped: List[Cluster] = [_map_cluster(c, rows, vectors) for c in recovered]
    counters.recovery_clusters_final = len(mapped)
    counters.recovery_snippets_assigned = sum(c.size for c in mapped)
    _log.info(
        "Anthology recovery: input=%d assigned=%d candidates=%d accepted=%d llm_calls=%d",
        len(rows), counters.recovery_snippets_assigned, len(candidates), len(mapped),
        counters.recovery_llm_calls,
    )
    return clusters + mapped


def _validate(
    clusters: List[Cluster],
    vectors: Vectors,
    snippets: List[Snippet],
    judge: Judge,
    seed: str,
    counters: RunCounters,
) -> List[Cluster]:
    merges: int
    clusters, merges = stages.merge_stage(clusters, vectors, snippets, judge)
    counters.merges += merges
    labeled: stages.Filtered = stages.label_stage(
        clusters, snippets, judge, seed, require_judgment=True
    )
    checked: stages.Filtered
    checked, counters.recovery_intruder_accuracy = stages.intruder_stage(
        labeled.kept, snippets, judge, require_judgment=True
    )
    counters.clusters_dissolved += labeled.dissolved + checked.dissolved
    return checked.kept


def _map_cluster(cluster: Cluster, rows: List[int], vectors: Vectors) -> Cluster:
    """Restore global indices while preserving the locally judged display data."""
    members: List[int] = [rows[row] for row in cluster.members]
    return replace(
        cluster,
        id=f"r{cluster.id[1:]}",
        members=members,
        centroid=centroid_of(vectors.dense, members),
    )
