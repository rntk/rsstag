"""Regression tests for evidence preservation and claim-level provenance."""

import json
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock

from rsstag.summary_tree.generation import SummaryGenerator, decode_entry, request_item
from rsstag.summary_tree.model import MAX_CHILDREN, Segment, build_hierarchy, claim_posts, relay
from rsstag.summary_tree.sources import SourcePost


class TestClaimModel(unittest.TestCase):
    def test_large_posts_keep_tail_and_bound_every_branch(self) -> None:
        posts: List[SourcePost] = [SourcePost(str(i), str(i), "word " * 10000 + "LAST FACT", "f", "", i)
                                   for i in range(70)]
        root, nodes, evidence = build_hierarchy(posts, "focus")
        self.assertEqual(len(nodes[root].post_ids), 70)
        self.assertTrue(all(len(node.children) <= MAX_CHILDREN for node in nodes.values()))
        self.assertIn("LAST FACT", " ".join(evidence["0"]))
        for pid in evidence:
            rows: List[int] = [row for node in nodes.values() if not node.children and node.post_ids == [pid]
                               for row in node.rows]
            self.assertEqual(rows, list(range(1, len(evidence[pid]) + 1)))

    def test_relay_retains_claim_positions_and_support(self) -> None:
        root, nodes, _ = build_hierarchy([SourcePost("p", "Title", "Text", "f", "", 0)], "focus")
        child = nodes[nodes[root].children[0]]
        child.segments = [Segment("Fact", [{"kind": "rows", "first": 2, "last": 2}])]
        nodes[root].segments = relay([child])
        self.assertEqual(nodes[root].segments[0].sources, [{"kind": "claim", "child": child.id, "segment": 0}])
        self.assertEqual(claim_posts(nodes[root], 0, nodes), ["p"])

    def test_invalid_citations_and_uncited_claims_rejected(self) -> None:
        allowed: Dict[str, Dict[str, Any]] = {"2": {"kind": "rows", "first": 2, "last": 2}}
        for refs in [["1"], ["2-3"], ["3-2"], ["C1.S1"], [], [False]]:
            self.assertIsNone(decode_entry({"segments": [{"text": "A fact", "from": refs}]}, allowed))
        self.assertIsNotNone(decode_entry({"segments": [{"text": "A fact", "from": ["2"]}]}, allowed))

    def test_partial_batch_saves_success_and_splits_missing(self) -> None:
        posts: List[SourcePost] = [SourcePost(str(i), str(i), "Text", "f", "", i) for i in range(3)]
        root, nodes, evidence = build_hierarchy(posts, "focus")
        llm: MagicMock = MagicMock()
        calls: List[int] = []

        def ask(prompt: str, accept: Any) -> str:
            data: Dict[str, Any] = json.loads('{"focus":' + prompt.split('\n{"focus":', 1)[1])
            batch: List[Dict[str, Any]] = data["nodes"]
            calls.append(len(batch))
            if len(batch) > 1:
                batch = batch[:1]
            entries: List[Dict[str, Any]] = []
            for item in batch:
                label: str = "1" if "evidence" in item else item["children"][0]["claims"][0]["cite"]
                entries.append({"id": item["id"], "segments": [{"text": item["title"] + " fact", "from": [label]}]})
            answer: str = json.dumps({"summaries": entries})
            accept(answer)
            return answer

        llm.ask.side_effect = ask
        save: MagicMock = MagicMock()
        SummaryGenerator(llm, "focus", nodes, evidence, save).run()
        self.assertTrue(all(node.segments is not None for node in nodes.values()))
        self.assertEqual(calls, [3, 1, 1, 1])
        self.assertGreaterEqual(save.call_count, 4)
        self.assertEqual(claim_posts(nodes[root], 0, nodes), ["0"])

    def test_resume_requires_identical_evidence_and_keeps_citations(self) -> None:
        from rsstag.summary_tree.results import input_fingerprint, restore, snapshot

        posts: List[SourcePost] = [SourcePost("p", "Title", "Evidence", "f", "", 0)]
        root, nodes, evidence = build_hierarchy(posts, "focus")
        fingerprint: str = input_fingerprint("focus", nodes, evidence)
        leaf = nodes[nodes[root].children[0]]
        leaf.segments = [Segment("Fact", [{"kind": "rows", "first": 2, "last": 2}])]
        saved: Dict[str, Any] = snapshot(root, nodes, evidence, posts, MagicMock(calls=0, cached=0, failures=0), fingerprint)
        _, fresh, _ = build_hierarchy(posts, "focus")
        restore(fresh, saved, fingerprint)
        self.assertEqual(fresh[leaf.id].segments, leaf.segments)
        self.assertIsNone(fresh[root].segments)
        _, changed, changed_evidence = build_hierarchy([SourcePost("p", "Title", "Changed", "f", "", 0)], "focus")
        restore(changed, saved, input_fingerprint("focus", changed, changed_evidence))
        self.assertTrue(all(node.segments is None for node in changed.values()))

    def test_unknown_or_duplicate_output_ids_do_not_write(self) -> None:
        posts: List[SourcePost] = [SourcePost("p", "Title", "Evidence", "f", "", 0)]
        _, nodes, evidence = build_hierarchy(posts, "focus")
        llm: MagicMock = MagicMock()
        save: MagicMock = MagicMock()

        def ask(prompt: str, accept: Any) -> str:
            node_id: str = next(iter(nodes))
            answer: Dict[str, Any] = {"id": node_id, "segments": [{"text": "Fact", "from": ["1"]}]}
            self.assertFalse(accept(json.dumps({"summaries": [answer, answer]})))
            self.assertFalse(accept(json.dumps({"summaries": [{**answer, "id": "invented"}]})))
            return ""

        llm.ask.side_effect = ask
        with self.assertRaisesRegex(ValueError, "valid cited summary"):
            SummaryGenerator(llm, "focus", nodes, evidence, save).run()
        save.assert_not_called()

    def test_relay_requires_matching_claim_positions(self) -> None:
        _, nodes, _ = build_hierarchy([
            SourcePost("p1", "One", "Text", "f", "", 0),
            SourcePost("p2", "Two", "Text", "f", "", 0),
        ], "focus")
        leaves = [node for node in nodes.values() if node.kind == "post"]
        leaves[0].segments = [Segment("and"), Segment("Fact", [{"kind": "rows", "first": 1, "last": 1}])]
        leaves[1].segments = [Segment("and", [{"kind": "rows", "first": 1, "last": 1}]), Segment("Fact")]
        self.assertIsNone(relay(leaves))
