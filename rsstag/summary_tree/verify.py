"""Check generated claims against the evidence they cite.

Per sourced segment, a Noul asks whether its cited text supports it:

  supported >= NO  -> keep the segment
  supported <  NO  -> drop it (and connector prose left dangling)
  every claim dropped -> reject the answer (bounded LLM retries)
  judge failure    -> keep the answer as validated by citations alone
"""

import logging
import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple

from rsstag.summary_tree import questions as q
from rsstag.summary_tree.judge import Answers, Request, SummaryJudge, noul
from rsstag.summary_tree.model import Nodes, Segment, SummaryNode

VERIFIED_LEVELS: Tuple[str, ...] = ("post", "detail")
CITED_CHARS: int = 4000

_log: logging.Logger = logging.getLogger("summary_tree.verify")


class ClaimVerifier:
    def __init__(self, judge: SummaryJudge, focus: str, nodes: Nodes, evidence: Dict[str, List[str]]) -> None:
        self._judge: SummaryJudge = judge
        self._focus: str = focus
        self._nodes: Nodes = nodes
        self._evidence: Dict[str, List[str]] = evidence
        self._lock: threading.Lock = threading.Lock()
        self.dropped: int = 0

    def filter(self, level: str, parsed: Dict[str, Optional[List[Segment]]]
               ) -> Dict[str, Optional[List[Segment]]]:
        if level not in VERIFIED_LEVELS or not self._judge.active:
            return parsed
        ids: List[str] = [node_id for node_id, segments in parsed.items()
                          if segments and any(s.sources for s in segments)]
        answers: List[Optional[Answers]] = self._judge.ask_many(
            [self._request(self._nodes[node_id], parsed[node_id] or []) for node_id in ids])
        result: Dict[str, Optional[List[Segment]]] = dict(parsed)
        for node_id, item in zip(ids, answers):
            if item is not None:
                result[node_id] = self._apply(level, self._nodes[node_id], parsed[node_id] or [], item)
        return result

    def _request(self, node: SummaryNode, segments: Sequence[Segment]) -> Request:
        claims: Dict[str, Any] = {}
        for index, segment in enumerate(segments):
            if segment.sources:
                claims[f"s{index}"] = {"claim": segment.text.strip(), "cited": self._cited(node, segment)}
        state: Dict[str, Any] = {"focus": self._focus, "claims": claims}
        return state, {key: q.claim_supported(key) for key in claims}

    def _cited(self, node: SummaryNode, segment: Segment) -> List[str]:
        texts: List[str] = []
        for source in segment.sources:
            if source["kind"] == "rows":
                rows: List[str] = self._evidence[node.post_ids[0]][source["first"] - 1:source["last"]]
                texts.append(" ".join(rows))
            else:
                child: SummaryNode = self._nodes[source["child"]]
                texts.append((child.segments or [])[source["segment"]].text.strip())
        cited: List[str] = []
        size: int = 0
        for text in texts:
            cited.append(text[:max(0, CITED_CHARS - size)])
            size += len(cited[-1])
        return [text for text in cited if text]

    def _apply(self, level: str, node: SummaryNode, segments: List[Segment],
               answers: Answers) -> Optional[List[Segment]]:
        kept: List[Segment] = []
        for index, segment in enumerate(segments):
            score: Optional[float] = noul(answers, f"s{index}") if segment.sources else None
            if score is not None and score < q.NO:
                with self._lock:
                    self.dropped += 1
                _log.info("Unsupported claim dropped from %s: %s", node.id, segment.text.strip()[:120])
                continue
            kept.append(segment)
        if len(kept) == len(segments):
            return segments
        if any(s.sources for s in kept):
            return _tidy(kept)
        _log.warning("Every claim of %s looked unsupported; rejecting the answer", node.id)
        return None


def _tidy(segments: List[Segment]) -> List[Segment]:
    """Drop connector prose left at the edges and re-join the remaining text."""
    start: int = next(i for i, s in enumerate(segments) if s.sources)
    end: int = max(i for i, s in enumerate(segments) if s.sources) + 1
    tidy: List[Segment] = [Segment(s.text, s.sources) for s in segments[start:end]]
    tidy[0].text = tidy[0].text.lstrip()
    return tidy
