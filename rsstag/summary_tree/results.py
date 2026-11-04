"""Persistable snapshots and resumption for the post evidence hierarchy."""

import hashlib
import json
from typing import Any, Dict, List

from rsstag.summary_tree.generation import INSTRUCTIONS
from rsstag.summary_tree.llm import SummaryLLM
from rsstag.summary_tree.model import Segment, SummaryNode, claim_posts
from rsstag.summary_tree.sources import SourcePost


def input_fingerprint(focus: str, nodes: Dict[str, SummaryNode], evidence: Dict[str, List[str]]) -> str:
    data: Dict[str, Any] = {"instructions": INSTRUCTIONS, "focus": focus, "evidence": evidence,
                            "structure": [node.to_dict() for node in nodes.values()]}
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def restore(nodes: Dict[str, SummaryNode], previous: Dict[str, Any], fingerprint: str) -> None:
    """A checkpoint is reusable only for the exact evidence, structure and instructions."""
    if previous.get("input_fingerprint") != fingerprint:
        return
    for node in nodes.values():
        saved: Any = previous.get("nodes", {}).get(node.id, {}).get("segments")
        if isinstance(saved, list):
            node.segments = [Segment(part["text"], part["sources"]) for part in saved]


def snapshot(root: str, nodes: Dict[str, SummaryNode], evidence: Dict[str, List[str]],
             posts: List[SourcePost], llm: SummaryLLM, fingerprint: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "schema_version": 2, "input_fingerprint": fingerprint, "root_id": root,
        "nodes": {node.id: node.to_dict() for node in nodes.values()}, "posts": [], "skipped": [],
    }
    for node in nodes.values():
        result["nodes"][node.id]["statements"] = [
            {"text": segment.text, "sources": claim_posts(node, index, nodes)}
            for index, segment in enumerate(node.segments or []) if segment.sources
        ]
    post_nodes: Dict[str, SummaryNode] = {node.post_ids[0]: node for node in nodes.values() if node.kind == "post"}
    for post in posts:
        node = post_nodes[post.pid]
        payload: Dict[str, Any] = {**post.to_dict(), "evidence": evidence[post.pid],
                                   "summary": "".join(s.text for s in node.segments or [])}
        if node.segments == []:
            payload["reason"] = "irrelevant"
            result["skipped"].append(payload)
        else:
            result["posts"].append(payload)
    result["metrics"] = {
        "posts": len(posts), "summarized": sum(bool(node.segments) for node in post_nodes.values()),
        "skipped": len(result["skipped"]), "topics": sum(n.kind in {"root", "group"} for n in nodes.values()),
        "completed_nodes": sum(n.segments is not None for n in nodes.values()), "total_nodes": len(nodes),
        "llm_calls": llm.calls, "llm_cached": llm.cached, "llm_failures": llm.failures,
    }
    return result
