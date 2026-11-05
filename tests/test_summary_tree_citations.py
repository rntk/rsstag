"""Regression tests for evidence preservation and claim-level provenance."""

import json
import threading
import time
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock

from rsstag.summary_tree.generation import SummaryGenerationError, SummaryGenerator, decode_entry, level_of
from rsstag.summary_tree.model import MAX_CHILDREN, ROOT, Segment, SummaryNode, add_node, build_post_nodes, claim_posts, relay
from rsstag.summary_tree.sources import SourcePost


def build_hierarchy(posts: List[SourcePost], focus: str) -> Any:
    """Posts under one root, the shape the pipeline produces for small sets."""
    post_nodes, nodes, evidence = build_post_nodes(posts)
    root: str = add_node(nodes, ROOT, focus, list(post_nodes.values()))
    return root, nodes, evidence


class TestClaimModel(unittest.TestCase):
    def test_large_posts_keep_tail_and_bound_every_branch(self) -> None:
        posts: List[SourcePost] = [SourcePost(str(i), str(i), "word " * 10000 + "LAST FACT", "f", "", i)
                                   for i in range(70)]
        root, nodes, evidence = build_hierarchy(posts, "focus")
        self.assertEqual(len(nodes[root].post_ids), 70)
        self.assertTrue(all(len(node.children) <= MAX_CHILDREN for node in nodes.values() if node.kind != ROOT))
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

    def test_generates_one_item_per_request(self) -> None:
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
        self.assertEqual(calls, [1, 1, 1, 1])
        self.assertGreaterEqual(save.call_count, 4)
        self.assertEqual(claim_posts(nodes[root], 0, nodes), ["0"])

    def test_generation_concurrency_is_bounded_by_workers(self) -> None:
        posts: List[SourcePost] = [SourcePost(str(i), str(i), "Text", "f", "", i) for i in range(8)]
        post_nodes, nodes, evidence = build_post_nodes(posts)
        gate: threading.Barrier = threading.Barrier(2)
        lock: threading.Lock = threading.Lock()
        active: int = 0
        maximum: int = 0

        def ask(prompt: str, accept: Any) -> str:
            nonlocal active, maximum
            data: Dict[str, Any] = json.loads('{"focus":' + prompt.split('\n{"focus":', 1)[1])
            item: Dict[str, Any] = data["nodes"][0]
            with lock:
                active += 1
                maximum = max(maximum, active)
            try:
                gate.wait(timeout=3)
                time.sleep(0.02)
                answer: str = json.dumps({"summaries": [{"id": "item", "segments": [
                    {"text": item["title"] + " fact", "from": ["1"]}]}]})
                accept(answer)
                return answer
            finally:
                with lock:
                    active -= 1

        llm: MagicMock = MagicMock()
        llm.ask.side_effect = ask
        save_threads: List[int] = []
        caller_thread: int = threading.get_ident()
        SummaryGenerator(llm, "focus", nodes, evidence,
                         lambda: save_threads.append(threading.get_ident()),
                         list(post_nodes.values()), workers=2).run()
        self.assertEqual(maximum, 2)
        self.assertEqual(llm.ask.call_count, 8)
        self.assertTrue(save_threads)
        self.assertEqual(set(save_threads), {caller_thread})

    def test_only_coordinator_mutates_and_saves_completed_nodes(self) -> None:
        posts: List[SourcePost] = [SourcePost(str(i), str(i), "Text", "f", "", i) for i in range(4)]
        post_nodes, nodes, evidence = build_post_nodes(posts)
        main_thread: int = threading.get_ident()
        observed: List[bool] = []
        save_threads: List[int] = []
        llm: MagicMock = MagicMock()

        def ask(prompt: str, accept: Any) -> str:
            data: Dict[str, Any] = json.loads('{"focus":' + prompt.split('\n{"focus":', 1)[1])
            item: Dict[str, Any] = data["nodes"][0]
            # Workers must not publish their result into the shared node map.
            requested: SummaryNode = next(node for node in nodes.values() if node.title == item["title"])
            observed.append(requested.segments is None)
            answer: str = json.dumps({"summaries": [{"id": "item", "segments": [
                {"text": item["title"] + " fact", "from": ["1"]}]}]})
            accept(answer)
            return answer

        llm.ask.side_effect = ask
        def save() -> None:
            save_threads.append(threading.get_ident())
            self.assertTrue(any(node.segments is not None for node in nodes.values()))
        SummaryGenerator(llm, "focus", nodes, evidence, save, list(post_nodes.values()), workers=3).run()
        self.assertTrue(all(observed))
        self.assertTrue(save_threads)
        self.assertEqual(set(save_threads), {main_thread})

    def test_failed_item_is_bounded_and_successful_siblings_are_not_regenerated(self) -> None:
        posts: List[SourcePost] = [SourcePost(str(i), str(i), "Text", "f", "", i) for i in range(3)]
        post_nodes, nodes, evidence = build_post_nodes(posts)
        calls: Dict[str, int] = {}

        def ask(prompt: str, accept: Any) -> str:
            data: Dict[str, Any] = json.loads('{"focus":' + prompt.split('\n{"focus":', 1)[1])
            item: Dict[str, Any] = data["nodes"][0]
            title: str = item["title"]
            calls[title] = calls.get(title, 0) + 1
            if title == "1":
                return ""
            answer: str = json.dumps({"summaries": [{"id": "item", "segments": [
                {"text": title + " fact", "from": ["1"]}]}]})
            accept(answer)
            return answer

        llm: MagicMock = MagicMock()
        llm.ask.side_effect = ask
        generator: SummaryGenerator = SummaryGenerator(
            llm, "focus", nodes, evidence, MagicMock(), list(post_nodes.values()),
            tolerate_failures=True, workers=2)
        generator.run()
        generator.run()
        self.assertEqual(calls, {str(i): 1 for i in range(3)})
        self.assertTrue(nodes[post_nodes["1"]].failed)

    def test_per_item_prompt_and_cache_key_ignore_tree_local_ids(self) -> None:
        prompt_cache: Dict[str, str] = {}
        prompts: List[str] = []
        llm: MagicMock = MagicMock()

        def ask(prompt: str, accept: Any) -> str:
            prompts.append(prompt)
            cached: str = prompt_cache.get(prompt, "")
            if cached and accept(cached):
                return cached
            answer: str = json.dumps({"summaries": [{"id": "item", "segments": [
                {"text": "Title fact", "from": ["1"]}]}]})
            accept(answer)
            prompt_cache[prompt] = answer
            return answer

        llm.ask.side_effect = ask
        target: SourcePost = SourcePost("target-id", "Title", "Same evidence", "f", "", 0)
        trees: List[List[SourcePost]] = [
            [target],
            [SourcePost("preceding-id", "Unrelated", "Other evidence", "f", "", 1), target],
        ]
        target_node_ids: List[str] = []
        for posts in trees:
            post_nodes, nodes, evidence = build_post_nodes(posts)
            target_node_ids.append(post_nodes["target-id"])
            SummaryGenerator(llm, "focus", nodes, evidence, MagicMock(),
                             [post_nodes["target-id"]]).run()
        self.assertNotEqual(target_node_ids[0], target_node_ids[1])
        self.assertEqual(prompts[0], prompts[1])
        payload: Dict[str, Any] = json.loads('{"focus":' + prompts[0].split('\n{"focus":', 1)[1])
        self.assertEqual(payload["required_output_ids"], ["item"])

    def test_failed_post_is_marked_when_tolerated(self) -> None:
        post_nodes, nodes, evidence = build_post_nodes([SourcePost("p", "Title", "Evidence", "f", "", 0)])
        llm: MagicMock = MagicMock()
        llm.ask.return_value = ""
        SummaryGenerator(llm, "focus", nodes, evidence, MagicMock(), tolerate_failures=True).run()
        self.assertTrue(nodes[post_nodes["p"]].failed)
        self.assertEqual(nodes[post_nodes["p"]].segments, [])

    def test_levels_get_their_own_prompt(self) -> None:
        root, nodes, _ = build_hierarchy([SourcePost("p", "Title", "Evidence", "f", "", 0)], "focus")
        post_id: str = nodes[root].children[0]
        topic: str = add_node(nodes, "topic", "Sub", [post_id])
        category: str = add_node(nodes, "topic", "Cat", [topic])
        top: str = add_node(nodes, ROOT, "focus", [category])
        self.assertEqual([level_of(nodes[i], nodes) for i in (post_id, topic, category, top, root)],
                         ["post", "detail", "overview", "root", "detail"])

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
        with self.assertRaisesRegex(SummaryGenerationError, "valid cited summary"):
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
