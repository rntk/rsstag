"""Evidence hierarchy and explicit claim links, independent of the display tree."""

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from rsstag.summary_tree.sources import SourcePost

MAX_CHILDREN: int = 8
PASSAGE_CHARS: int = 800
CHUNK_CHARS: int = 6000


@dataclass
class Segment:
    text: str
    sources: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SummaryNode:
    id: str
    kind: str
    title: str
    post_ids: List[str]
    children: List[str] = field(default_factory=list)
    rows: List[int] = field(default_factory=list)
    segments: Optional[List[Segment]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evidence_rows(post: SourcePost) -> List[str]:
    """Stable numbered passages, including the title; never discard long-post tails."""
    rows: List[str] = []
    paragraphs: List[str] = [post.title] + re.split(r"(?<=[.!?…])\s+|\n+", post.text)
    paragraph: str
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        while paragraph:
            end: int = min(len(paragraph), PASSAGE_CHARS)
            if end < len(paragraph):
                space: int = paragraph.rfind(" ", 0, end)
                end = space if space > PASSAGE_CHARS // 2 else end
            rows.append(paragraph[:end])
            paragraph = paragraph[end:].lstrip()
    return rows


def build_hierarchy(posts: Sequence[SourcePost], focus: str) -> Tuple[str, Dict[str, SummaryNode], Dict[str, List[str]]]:
    """Posts in source order, bounded evidence chunks and balanced collection groups.

    Groups organize evidence, not inferred topics. The citation view supplies the
    thematic paths, so a post can support multiple independent claims.
    """
    nodes: Dict[str, SummaryNode] = {}
    evidence: Dict[str, List[str]] = {}

    def group(ids: List[str], kind: str) -> List[str]:
        current: List[str] = ids
        while len(current) > MAX_CHILDREN:
            count: int = (len(current) + MAX_CHILDREN - 1) // MAX_CHILDREN
            base, extra = divmod(len(current), count)
            start: int = 0
            next_level: List[str] = []
            for index in range(count):
                members: List[str] = current[start:start + base + (index < extra)]
                start += len(members)
                if len(members) == 1:
                    next_level.extend(members)
                else:
                    next_level.append(add(kind, "Post passages" if kind == "chunk" else "Post group", members))
            current = next_level
        return current

    def add(kind: str, title: str, children: List[str], pids: Optional[List[str]] = None,
            rows: Optional[List[int]] = None) -> str:
        node_id: str = f"n{len(nodes)}"
        ids: List[str] = pids if pids is not None else list(dict.fromkeys(
            pid for child in children for pid in nodes[child].post_ids
        ))
        nodes[node_id] = SummaryNode(node_id, kind, title, ids, children, rows or [])
        return node_id

    leaves: List[str] = []
    post: SourcePost
    for post in posts:
        passages: List[str] = evidence_rows(post)
        evidence[post.pid] = passages
        chunks: List[List[int]] = []
        size: int = 0
        for row, passage in enumerate(passages, 1):
            if not chunks or size + len(passage) > CHUNK_CHARS:
                chunks.append([])
                size = 0
            chunks[-1].append(row)
            size += len(passage) + 1
        children: List[str] = []
        if len(chunks) > 1:
            children = [add("chunk", f"Passages {rows[0]}–{rows[-1]}", [], [post.pid], rows)
                        for rows in chunks]
        leaves.append(add("post", post.title, group(children, "chunk"), [post.pid],
                          list(range(1, len(passages) + 1)) if not children else []))
    root: str = add("root", focus, group(leaves, "group"))
    return root, nodes, evidence


def relay(children: List[SummaryNode]) -> Optional[List[Segment]]:
    """Reuse identical prose only when segment positions match exactly."""
    first: Optional[List[Segment]] = children[0].segments if children else None
    if first is None or any(child.segments is None or
                            [(s.text, bool(s.sources)) for s in child.segments] !=
                            [(s.text, bool(s.sources)) for s in first]
                            for child in children):
        return None
    return [Segment(segment.text, [
        {"kind": "claim", "child": child.id, "segment": index}
        for child in children
    ] if segment.sources else []) for index, segment in enumerate(first)]


def claim_posts(node: SummaryNode, index: int, nodes: Dict[str, SummaryNode]) -> List[str]:
    """Resolve persisted links, never infer support from shared words or membership."""
    sources: List[Dict[str, Any]] = (node.segments or [])[index].sources
    pids: List[str] = []
    for source in sources:
        if source["kind"] == "rows":
            pids.extend(node.post_ids)
        else:
            pids.extend(claim_posts(nodes[source["child"]], source["segment"], nodes))
    return list(dict.fromkeys(pids))
