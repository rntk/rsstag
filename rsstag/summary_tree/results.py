"""Persistable snapshots of a (possibly partial) summary tree.

Retries resume through the per-prompt LLM answer cache: identical evidence yields
identical prompts, so finished post summaries, topic splits and topic summaries
are replayed (and revalidated) without new model calls.
"""

from typing import Any, Dict, List, Optional

from rsstag.summary_tree.llm import SummaryLLM
from rsstag.summary_tree.model import POST, ROOT, TOPIC, Nodes, SummaryNode, claim_posts, summary_text
from rsstag.summary_tree.sources import SourcePost

SCHEMA_VERSION: int = 3


def _statements(node: SummaryNode, nodes: Nodes) -> List[Dict[str, Any]]:
    return [{"text": segment.text, "sources": claim_posts(node, index, nodes)}
            for index, segment in enumerate(node.segments or []) if segment.sources]


def _post_payload(post: SourcePost, node: SummaryNode, evidence: List[str]) -> Dict[str, Any]:
    return {**post.to_dict(), "evidence": evidence, "summary": summary_text(node), "node_id": node.id}


def snapshot(root: Optional[str], nodes: Nodes, evidence: Dict[str, List[str]],
             posts: List[SourcePost], llm: SummaryLLM,
             extra_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION, "root_id": root,
        "nodes": {node.id: {**node.to_dict(), "statements": _statements(node, nodes)} for node in nodes.values()},
        "posts": [], "skipped": [],
    }
    post_nodes: Dict[str, SummaryNode] = {node.post_ids[0]: node for node in nodes.values() if node.kind == POST}
    for post in posts:
        node: SummaryNode = post_nodes[post.pid]
        payload: Dict[str, Any] = _post_payload(post, node, evidence[post.pid])
        if node.segments == []:
            payload["reason"] = "summary failed" if node.failed else "irrelevant"
            result["skipped"].append(payload)
        else:
            result["posts"].append(payload)
    result["metrics"] = {
        "posts": len(posts), "summarized": sum(bool(node.segments) for node in post_nodes.values()),
        "skipped": len(result["skipped"]), "topics": sum(n.kind == TOPIC for n in nodes.values()),
        "completed_nodes": sum(n.segments is not None for n in nodes.values()), "total_nodes": len(nodes),
        "levels": _depth(root, nodes) if root else 0,
        "llm_attempts": llm.attempts, "llm_request_seconds": round(llm.request_seconds, 3),
        "llm_invalid_answers": llm.invalid_answers, "llm_calls": llm.calls, "llm_cached": llm.cached, "llm_failures": llm.failures,
        **(extra_metrics or {}),
    }
    return result


def _depth(node_id: str, nodes: Nodes) -> int:
    node: SummaryNode = nodes[node_id]
    if node.kind not in (TOPIC, ROOT):
        return 1
    return 1 + max((_depth(child, nodes) for child in node.children), default=0)
