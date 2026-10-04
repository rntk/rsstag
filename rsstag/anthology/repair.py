"""One bounded split of explicitly rejected anthology clusters."""

import logging
from typing import Dict, List

import numpy as np

from rsstag.anthology import stages
from rsstag.anthology.candidates import Cluster, Vectors, cluster_rows, make_cluster
from rsstag.anthology.judge import Judge
from rsstag.anthology.result import RunCounters
from rsstag.anthology.units import Snippet

_log: logging.Logger = logging.getLogger("anthology.repair")


def _split(parent: Cluster, vectors: Vectors) -> List[Cluster]:
    """Preserve global rows and leave singleton children outside accepted groups."""
    if parent.size < 3:
        return []
    labels: np.ndarray = cluster_rows(vectors.dense[parent.members], 2, split_small=True)
    groups: Dict[int, List[int]] = {}
    for row, label in zip(parent.members, labels.tolist()):
        groups.setdefault(int(label), []).append(row)
    ordered: List[List[int]] = sorted(groups.values(), key=lambda rows: (-len(rows), min(rows)))
    return [
        make_cluster(f"{parent.id}s{index}", rows, vectors)
        for index, rows in enumerate(ordered) if len(rows) >= 2
    ]


def repair_rejected(
    rejected: List[Cluster],
    vectors: Vectors,
    snippets: List[Snippet],
    judge: Judge,
    seed: str,
    counters: RunCounters,
) -> List[Cluster]:
    """Split semantic rejects once and require fresh judgments for their children.

    Callers supply only explicit semantic rejections, never missing judgments.
    Parent objects are unchanged; unaccepted children remain available for later
    assignment or recovery. No child is recursively split or merged back.
    """
    counters.repair_clusters_input = len(rejected)
    candidates: List[Cluster] = [child for parent in rejected for child in _split(parent, vectors)]
    counters.repair_clusters_candidate = len(candidates)
    counters.clusters_candidate += len(candidates)
    if not candidates:
        return []
    calls_before: int = judge.calls
    labeled: stages.Filtered = stages.label_stage(
        candidates, snippets, judge, seed, require_judgment=True
    )
    checked: stages.Filtered
    checked, _accuracy = stages.intruder_stage(
        labeled.kept, snippets, judge, require_judgment=True
    )
    counters.clusters_dissolved += labeled.dissolved + checked.dissolved
    counters.repair_llm_calls = judge.calls - calls_before
    counters.repair_clusters_final = len(checked.kept)
    counters.repair_snippets_assigned = sum(cluster.size for cluster in checked.kept)
    _log.info(
        "Anthology repair: input=%d candidates=%d accepted=%d assigned=%d llm_calls=%d",
        len(rejected), len(candidates), len(checked.kept),
        counters.repair_snippets_assigned, counters.repair_llm_calls,
    )
    return checked.kept
