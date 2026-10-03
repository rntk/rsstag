"""Serialize pipeline state into the stored anthology result schema."""

from dataclasses import dataclass
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
    duration_sec: float = 0.0


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
        "ungrouped_posts": counters.ungrouped_posts,
        "clusters_candidate": counters.clusters_candidate,
        "clusters_final": final_clusters,
        "clusters_dissolved": counters.clusters_dissolved,
        "merges": counters.merges,
        "duration_sec": round(counters.duration_sec, 3),
    }


def build_result(
    snippets: Sequence[Snippet], themes: Sequence[Theme], counters: RunCounters
) -> Dict[str, Any]:
    """Assemble the result dict; every snippet not in a final cluster is unsorted."""
    clusters: List[Cluster] = [c for theme in themes for c in theme.clusters]
    assigned: set = {row for c in clusters for row in c.members}
    return {
        "themes": [theme_to_dict(i, theme) for i, theme in enumerate(themes)],
        "clusters": {c.id: cluster_to_dict(c, snippets) for c in clusters},
        "unsorted": [s.id for row, s in enumerate(snippets) if row not in assigned],
        "snippets": {s.id: s.to_dict() for s in snippets},
        "metrics": build_metrics(len(snippets), len(assigned), len(clusters), counters),
    }
