"""Judge-driven pipeline stages: merge, label, intruder check, themes."""

import hashlib
import logging
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

from rsstag.anthology import parsers, prompts
from rsstag.anthology.candidates import (
    Cluster,
    Vectors,
    centroid_similarity,
    cluster_rows,
    contrastive_keywords,
    make_cluster,
    merge_pairs,
)
from rsstag.anthology.judge import Judge
from rsstag.anthology.units import Snippet
from rsstag.topic_merge import _union_groups

MERGE_THRESHOLD: float = 0.35
MAX_MERGE_PAIRS: int = 30
MERGE_PAIRS_PER_CALL: int = 10
LABEL_CLUSTERS_PER_CALL: int = 8
INTRUDER_SETS_PER_CALL: int = 6
INTRUDER_MIN_SIZE: int = 4
DISSOLVE_SCORE: int = 2
INTRUDER_DISSOLVE_SCORE: int = 3
MAX_THEMES: int = 10

_log: logging.Logger = logging.getLogger("anthology.stages")


@dataclass
class Theme:
    clusters: List[Cluster]
    label: str = ""
    keywords: List[str] = field(default_factory=list)
    loose: bool = False

    @property
    def size(self) -> int:
        return sum(c.size for c in self.clusters)


@dataclass
class Filtered:
    """Clusters that survived a stage plus rows released to unsorted."""

    kept: List[Cluster]
    released: List[int] = field(default_factory=list)
    dissolved: int = 0


def _chunks(items: Sequence, size: int) -> List[Sequence]:
    return [items[start : start + size] for start in range(0, len(items), size)]


def _previews(cluster: Cluster, snippets: Sequence[Snippet], count: int) -> List[str]:
    return [snippets[row].text for row in cluster.members[:count]]


def default_label(cluster: Cluster, snippets: Sequence[Snippet]) -> str:
    if cluster.keywords:
        return parsers.clip_words(" ".join(cluster.keywords[:3]), 5)
    topic: str = snippets[cluster.members[0]].topic_path if cluster.members else ""
    return parsers.clip_words(topic.split(">")[-1], 5) or cluster.id


# --- merge -------------------------------------------------------------------


def merge_stage(
    clusters: List[Cluster], vectors: Vectors, snippets: Sequence[Snippet], judge: Judge
) -> Tuple[List[Cluster], int]:
    """Ask the judge about similar cluster pairs and union the 'same' ones."""
    pairs: List[Tuple[int, int]] = merge_pairs(clusters, MERGE_THRESHOLD, MAX_MERGE_PAIRS)
    same: List[List[int]] = []
    for batch in _chunks(pairs, MERGE_PAIRS_PER_CALL):
        same += _judge_pairs(batch, clusters, snippets, judge)
    if not same:
        return clusters, 0
    return apply_merges(clusters, same, vectors)


def _judge_pairs(
    batch: Sequence[Tuple[int, int]],
    clusters: List[Cluster],
    snippets: Sequence[Snippet],
    judge: Judge,
) -> List[List[int]]:
    payload = [
        (
            clusters[i].keywords,
            _previews(clusters[i], snippets, 2),
            clusters[j].keywords,
            _previews(clusters[j], snippets, 2),
        )
        for i, j in batch
    ]
    answers: Dict[int, bool] = parsers.parse_pair_answers(
        judge.ask(prompts.merge_prompt(payload)), len(batch)
    )
    return [list(batch[n - 1]) for n, is_same in sorted(answers.items()) if is_same]


def apply_merges(
    clusters: List[Cluster], groups: List[List[int]], vectors: Vectors
) -> Tuple[List[Cluster], int]:
    """Union-find merge of cluster index groups; returns clusters and merge count."""
    components: List[List[int]] = _union_groups(groups)
    owner_of: Dict[int, int] = {idx: comp[0] for comp in components for idx in comp}
    merged: List[Cluster] = []
    merges: int = 0
    for idx, cluster in enumerate(clusters):
        head: int = owner_of.get(idx, idx)
        if head != idx:
            continue
        component: List[int] = next((c for c in components if c[0] == idx), [idx])
        if len(component) == 1:
            merged.append(cluster)
            continue
        rows: List[int] = sorted(row for member in component for row in clusters[member].members)
        merged.append(make_cluster(cluster.id, rows, vectors))
        merges += len(component) - 1
    return merged, merges


# --- label -------------------------------------------------------------------


def label_stage(
    clusters: List[Cluster], snippets: Sequence[Snippet], judge: Judge, seed: str,
    require_judgment: bool = False,
) -> Filtered:
    """Score and name clusters; low scores dissolve into unsorted."""
    label_clusters(clusters, snippets, judge, seed, require_judgment=require_judgment)
    result: Filtered = Filtered(kept=[])
    for cluster in clusters:
        if cluster.score <= DISSOLVE_SCORE:
            result.released += cluster.members
            result.dissolved += 1
        else:
            result.kept.append(cluster)
    return result


def label_clusters(
    clusters: List[Cluster], snippets: Sequence[Snippet], judge: Judge, seed: str,
    require_judgment: bool = False,
) -> None:
    """Score and name clusters in batches without dissolving any of them."""
    for batch in _chunks(clusters, LABEL_CLUSTERS_PER_CALL):
        _judge_labels(batch, snippets, judge, seed, require_judgment=require_judgment)


def _judge_labels(
    batch: Sequence[Cluster], snippets: Sequence[Snippet], judge: Judge, seed: str,
    require_judgment: bool = False,
) -> None:
    payload = [(c.keywords, _previews(c, snippets, 4)) for c in batch]
    judgments: Dict[int, parsers.LabelJudgment] = parsers.parse_labels(
        judge.ask(prompts.label_prompt(seed, payload)), len(batch), require_score=require_judgment
    )
    for number, cluster in enumerate(batch, start=1):
        judgment: Optional[parsers.LabelJudgment] = judgments.get(number)
        cluster.score = judgment.score if judgment else (1 if require_judgment else 3)
        cluster.kind = judgment.kind if judgment else "other"
        cluster.label = (judgment.label if judgment else "") or default_label(cluster, snippets)


# --- intruder ----------------------------------------------------------------


@dataclass
class IntruderSet:
    cluster: Cluster
    rows: List[int]
    answer_position: int  # 1-based position of the intruder


def intruder_stage(
    clusters: List[Cluster], snippets: Sequence[Snippet], judge: Judge,
    require_judgment: bool = False,
) -> Tuple[Filtered, Optional[float]]:
    """Word-intrusion style check; wrong answers on weak clusters dissolve them."""
    sets: List[IntruderSet] = build_intruder_sets(clusters)
    for batch in _chunks(sets, INTRUDER_SETS_PER_CALL):
        _judge_intruders(batch, snippets, judge)
    answered: List[bool] = [s.cluster.intruder_ok for s in sets if s.cluster.intruder_ok is not None]
    accuracy: Optional[float] = round(sum(answered) / len(answered), 4) if answered else None
    result: Filtered = Filtered(kept=[])
    tested: Set[str] = {item.cluster.id for item in sets}
    for cluster in clusters:
        missing: bool = require_judgment and cluster.id in tested and cluster.intruder_ok is None
        if missing or (cluster.intruder_ok is False and cluster.score <= INTRUDER_DISSOLVE_SCORE):
            result.released += cluster.members
            result.dissolved += 1
        else:
            result.kept.append(cluster)
    return result, accuracy


def build_intruder_sets(clusters: List[Cluster]) -> List[IntruderSet]:
    """Four medoids plus the medoid of the nearest other cluster, seeded shuffle."""
    if len(clusters) < 2:
        return []
    sims: np.ndarray = centroid_similarity(clusters)
    np.fill_diagonal(sims, -np.inf)
    sets: List[IntruderSet] = []
    for idx, cluster in enumerate(clusters):
        if cluster.size < INTRUDER_MIN_SIZE:
            continue
        intruder: int = clusters[int(np.argmax(sims[idx]))].members[0]
        rows: List[int] = cluster.members[:4] + [intruder]
        _seeded_rng(cluster).shuffle(rows)
        sets.append(IntruderSet(cluster, rows, rows.index(intruder) + 1))
    return sets


def _seeded_rng(cluster: Cluster) -> random.Random:
    key: str = cluster.id + ":" + ",".join(str(row) for row in cluster.members[:4])
    return random.Random(int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16))


def _judge_intruders(batch: Sequence[IntruderSet], snippets: Sequence[Snippet], judge: Judge) -> None:
    payload: List[List[str]] = [[snippets[row].text for row in s.rows] for s in batch]
    answers: Dict[int, int] = parsers.parse_intruders(
        judge.ask(prompts.intruder_prompt(payload)), len(batch)
    )
    for number, item in enumerate(batch, start=1):
        choice: Optional[int] = answers.get(number)
        item.cluster.intruder_ok = None if choice is None else choice == item.answer_position


# --- themes ------------------------------------------------------------------


def theme_count(cluster_count: int) -> int:
    return max(1, min(round(math.sqrt(cluster_count)), MAX_THEMES))


def group_into_themes(clusters: List[Cluster], vectors: Vectors) -> List[Theme]:
    """Cluster centroids into themes; ≤4 clusters keep a theme each."""
    if len(clusters) <= 4:
        groups: List[List[Cluster]] = [[c] for c in clusters]
    else:
        centroids: np.ndarray = np.vstack([c.centroid for c in clusters])
        labels: np.ndarray = cluster_rows(centroids, theme_count(len(clusters)))
        by_label: Dict[int, List[Cluster]] = {}
        for cluster, label in zip(clusters, labels.tolist()):
            by_label.setdefault(int(label), []).append(cluster)
        groups = list(by_label.values())
    themes: List[Theme] = []
    for members in groups:
        ordered: List[Cluster] = sorted(members, key=lambda c: (-c.size, c.id))
        rows: List[int] = [row for c in ordered for row in c.members]
        themes.append(Theme(clusters=ordered, keywords=contrastive_keywords(vectors, rows)))
    return sorted(themes, key=lambda t: (-t.size, t.clusters[0].id))


def themes_stage(clusters: List[Cluster], vectors: Vectors, judge: Judge, seed: str) -> List[Theme]:
    """Group clusters into themes and name the multi-cluster ones in one call."""
    themes: List[Theme] = group_into_themes(clusters, vectors)
    multi: List[Theme] = [t for t in themes if len(t.clusters) > 1]
    for theme in themes:
        theme.label = parsers.clip_words(theme.clusters[0].label, 5 if len(theme.clusters) == 1 else 4)
    if multi:
        payload = [([c.label for c in t.clusters], t.keywords) for t in multi]
        labels: Dict[int, str] = parsers.parse_theme_labels(
            judge.ask(prompts.theme_prompt(seed, payload)), len(multi)
        )
        for number, theme in enumerate(multi, start=1):
            theme.label = labels.get(number) or theme.label
    return themes
