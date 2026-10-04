"""Serialize pipeline state into the stored anthology result schema."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from rsstag.anthology.candidates import Cluster
from rsstag.anthology.stages import Theme
from rsstag.anthology.units import Snippet


@dataclass
class RunCounters:
    ungrouped_posts: int = 0
    clusters_candidate: int = 0
    clusters_dissolved: int = 0
    merges: int = 0
    intruder_accuracy: Optional[float] = None
    llm_calls: int = 0
    llm_cached: int = 0
    llm_retries: int = 0
    llm_failures: int = 0
    judgments_expected: int = 0
    judgments_missing: int = 0
    duration_sec: float = 0.0
    first_pass_unsorted: Dict[str, int] = field(default_factory=dict)
    repair_clusters_input: int = 0
    repair_clusters_candidate: int = 0
    repair_clusters_final: int = 0
    repair_snippets_assigned: int = 0
    repair_llm_calls: int = 0
    assignment_snippets_input: int = 0
    assignment_candidates: int = 0
    assignment_snippets_assigned: int = 0
    assignment_llm_calls: int = 0
    assignment_judgment_missing: int = 0
    recovery_snippets_input: int = 0
    recovery_snippets_assigned: int = 0
    recovery_clusters_candidate: int = 0
    recovery_clusters_final: int = 0
    recovery_llm_calls: int = 0
    recovery_intruder_accuracy: Optional[float] = None
    loose_snippets: int = 0
    loose_clusters: int = 0
    loose_llm_calls: int = 0


def cluster_to_dict(cluster: Cluster, snippets: Sequence[Snippet]) -> Dict[str, Any]:
    members: List[Snippet] = [snippets[row] for row in cluster.members]
    dates: List[float] = [s.date for s in members if s.date is not None]
    feed_ids: List[str] = list(dict.fromkeys(s.feed_id for s in members if s.feed_id))
    return {
        "id": cluster.id,
        "label": cluster.label,
        "kind": cluster.kind,
        "score": int(cluster.score),
        "intruder_ok": cluster.intruder_ok,
        "loose": cluster.loose,
        "keywords": list(cluster.keywords[:8]),
        "cohesion": float(cluster.cohesion),
        "snippet_ids": [s.id for s in members],
        "start_snippet_id": members[0].id if members else "",
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
        "feed_ids": feed_ids,
    }


def theme_to_dict(index: int, theme: Theme) -> Dict[str, Any]:
    return {
        "id": f"t{index}",
        "label": theme.label,
        "keywords": list(theme.keywords[:8]),
        "size": theme.size,
        "cluster_ids": [c.id for c in theme.clusters],
        "loose": theme.loose,
    }


def build_metrics(
    snippets_total: int, assigned: int, final_clusters: int, counters: RunCounters
) -> Dict[str, Any]:
    unsorted: int = snippets_total - assigned
    return {
        "snippets_total": snippets_total,
        "snippets_assigned": assigned,
        "coverage": round(assigned / snippets_total, 4) if snippets_total else 0.0,
        "noise_ratio": round(unsorted / snippets_total, 4) if snippets_total else 0.0,
        "intruder_accuracy": counters.intruder_accuracy,
        "llm_calls": counters.llm_calls,
        "llm_cached": counters.llm_cached,
        "llm_retries": counters.llm_retries,
        "llm_failures": counters.llm_failures,
        "judgments_expected": counters.judgments_expected,
        "judgments_missing": counters.judgments_missing,
        "ungrouped_posts": counters.ungrouped_posts,
        "clusters_candidate": counters.clusters_candidate,
        "clusters_final": final_clusters,
        "clusters_dissolved": counters.clusters_dissolved,
        "merges": counters.merges,
        "duration_sec": round(counters.duration_sec, 3),
        "first_pass_unsorted": dict(counters.first_pass_unsorted),
        "repair_clusters_input": counters.repair_clusters_input,
        "repair_clusters_candidate": counters.repair_clusters_candidate,
        "repair_clusters_final": counters.repair_clusters_final,
        "repair_snippets_assigned": counters.repair_snippets_assigned,
        "repair_llm_calls": counters.repair_llm_calls,
        "assignment_snippets_input": counters.assignment_snippets_input,
        "assignment_candidates": counters.assignment_candidates,
        "assignment_snippets_assigned": counters.assignment_snippets_assigned,
        "assignment_llm_calls": counters.assignment_llm_calls,
        "assignment_judgment_missing": counters.assignment_judgment_missing,
        "recovery_snippets_input": counters.recovery_snippets_input,
        "recovery_snippets_assigned": counters.recovery_snippets_assigned,
        "recovery_clusters_candidate": counters.recovery_clusters_candidate,
        "recovery_clusters_final": counters.recovery_clusters_final,
        "recovery_llm_calls": counters.recovery_llm_calls,
        "recovery_intruder_accuracy": counters.recovery_intruder_accuracy,
        "loose_snippets": counters.loose_snippets,
        "loose_clusters": counters.loose_clusters,
        "loose_llm_calls": counters.loose_llm_calls,
    }


def coverage_problems(n_snippets: int, themes: Sequence[Theme]) -> List[str]:
    """Every snippet must be in at most one final cluster; rows must be valid."""
    seen: Dict[int, str] = {}
    problems: List[str] = []
    for cluster in (c for theme in themes for c in theme.clusters):
        for row in cluster.members:
            if not 0 <= row < n_snippets:
                problems.append(f"cluster {cluster.id} has unknown snippet row {row}")
            elif row in seen:
                problems.append(f"snippet row {row} is in clusters {seen[row]} and {cluster.id}")
            else:
                seen[row] = cluster.id
    return problems


def build_result(
    snippets: Sequence[Snippet], themes: Sequence[Theme], counters: RunCounters
) -> Dict[str, Any]:
    """Assemble the result dict; every snippet not in a final cluster is unsorted.

    Loose clusters label leftovers for browsing but don't count as coverage.
    """
    clusters: List[Cluster] = [c for theme in themes for c in theme.clusters]
    placed: set = {row for c in clusters for row in c.members}
    strict: List[Cluster] = [c for c in clusters if not c.loose]
    assigned: set = {row for c in strict for row in c.members}
    return {
        "themes": [theme_to_dict(i, theme) for i, theme in enumerate(themes)],
        "clusters": {c.id: cluster_to_dict(c, snippets) for c in clusters},
        "unsorted": [s.id for row, s in enumerate(snippets) if row not in placed],
        "snippets": {s.id: s.to_dict() for s in snippets},
        "metrics": build_metrics(len(snippets), len(assigned), len(strict), counters),
    }
