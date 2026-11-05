"""Topic taxonomy: validation of model groupings and recursive splitting."""

import json
import threading
import time
import unittest
from typing import Any, Callable, Dict, List
from unittest.mock import MagicMock

from rsstag.summary_tree import topics
from rsstag.summary_tree.model import ROOT, TOPIC, Segment, build_post_nodes
from rsstag.summary_tree.sources import SourcePost
from rsstag.summary_tree.topics import OTHER_TITLE, TopicBuilder, decode_assignment


def _summarized(titles: List[str]) -> Any:
    posts: List[SourcePost] = [SourcePost(str(i), title, "t", "f", "", i) for i, title in enumerate(titles)]
    post_nodes, nodes, _ = build_post_nodes(posts)
    for node in nodes.values():
        node.segments = [Segment(node.title + " news.", [{"kind": "rows", "first": 1, "last": 1}])]
    return [post_nodes[p.pid] for p in posts], nodes


def _payload(prompt: str) -> Dict[str, Any]:
    return json.loads('{"focus":' + prompt.split('\n{"focus":', 1)[1])


def _by_first_word(prompt: str, accept: Callable[[str], bool]) -> str:
    """Group posts by the first word of their summary (the 'category')."""
    data: Dict[str, Any] = _payload(prompt)
    depth: int = data["path"].count("›")
    groups: Dict[str, List[str]] = {}
    for post in data["posts"]:
        words: List[str] = post["summary"].split()
        groups.setdefault(words[min(depth, len(words) - 1)], []).append(post["id"])
    answer: str = json.dumps({"topics": [{"title": t, "posts": ids} for t, ids in groups.items()]})
    accept(answer)
    return answer


class TestDecodeAssignment(unittest.TestCase):
    local: Dict[str, str] = {"P1": "a", "P2": "b", "P3": "c", "P4": "d"}

    def test_valid_answer_maps_local_ids(self) -> None:
        raw: str = json.dumps({"topics": [{"title": " iPhone. ", "posts": ["P1", "P2", "P3"]},
                                          {"title": "Mac", "posts": ["P4"]}]})
        decoded = decode_assignment(raw, self.local, [], 7)
        self.assertEqual(decoded.topics, {"iPhone": ["a", "b", "c"], "Mac": ["d"]})

    def test_rejects_unknown_duplicate_low_coverage_and_too_many_new(self) -> None:
        for topics_list, max_new in [
            ([{"title": "A", "posts": ["P9"]}], 7),
            ([{"title": "A", "posts": ["P1", "P2"]}, {"title": "B", "posts": ["P2", "P3"]}], 7),
            ([{"title": "A", "posts": ["P1", "P2"]}], 7),
            ([{"title": "A", "posts": ["P1", "P2"]}, {"title": "B", "posts": ["P3", "P4"]}], 1),
            ([{"title": "", "posts": ["P1", "P2", "P3", "P4"]}], 7),
        ]:
            self.assertIsNone(decode_assignment(json.dumps({"topics": topics_list}), self.local, [], max_new))

    def test_existing_titles_are_reused_case_insensitively(self) -> None:
        raw: str = json.dumps({"topics": [{"title": "iphone", "posts": ["P1", "P2", "P3", "P4"]}]})
        self.assertEqual(decode_assignment(raw, self.local, ["iPhone"], 0).topics, {"iPhone": ["a", "b", "c", "d"]})


class TestTopicBuilder(unittest.TestCase):
    def test_independent_topic_splits_run_in_parallel_and_assemble_stably(self) -> None:
        titles: List[str] = [f"{group} {color} {index}" for group in ("Alpha", "Beta")
                             for color in ("red", "blue") for index in range(3)]
        ids, nodes = _summarized(titles)
        gate: threading.Barrier = threading.Barrier(2)
        lock: threading.Lock = threading.Lock()
        active: int = 0
        maximum: int = 0

        def answer(prompt: str, accept: Callable[[str], bool]) -> str:
            nonlocal active, maximum
            data: Dict[str, Any] = _payload(prompt)
            if data["path"].count("›"):
                with lock:
                    active += 1
                    maximum = max(maximum, active)
                try:
                    gate.wait(timeout=3)
                    time.sleep(0.01 if data["path"].endswith("Alpha") else 0.02)
                finally:
                    with lock:
                        active -= 1
            return _by_first_word(prompt, accept)

        llm: MagicMock = MagicMock()
        llm.ask.side_effect = answer
        root: str = TopicBuilder(llm, "apple", nodes, MagicMock(), workers=2).build(ids)
        hierarchy: List[Any] = [
            (nodes[category].title,
             [(nodes[subtopic].title, [nodes[post].title for post in nodes[subtopic].children])
              for subtopic in nodes[category].children])
            for category in nodes[root].children
        ]
        self.assertEqual(maximum, 2)
        self.assertEqual([title for title, _ in hierarchy], ["Alpha", "Beta"])
        self.assertEqual([[title for title, _ in subtopics] for _, subtopics in hierarchy],
                         [["red", "blue"], ["red", "blue"]])

    def test_builds_categories_then_subtopics(self) -> None:
        titles: List[str] = [f"iPhone battery {i}" for i in range(3)] + [f"iPhone camera {i}" for i in range(3)] + [
            f"Mac M5 {i}" for i in range(2)]
        ids, nodes = _summarized(titles)
        llm: MagicMock = MagicMock()
        llm.ask.side_effect = _by_first_word
        root: str = TopicBuilder(llm, "apple", nodes, MagicMock()).build(ids)
        self.assertEqual(nodes[root].kind, ROOT)
        categories = [nodes[c] for c in nodes[root].children]
        self.assertEqual([c.title for c in categories], ["iPhone", "Mac"])
        iphone = categories[0]
        self.assertEqual([nodes[c].title for c in iphone.children], ["battery", "camera"])
        self.assertEqual(nodes[iphone.children[0]].path, ["apple", "iPhone", "battery"])
        self.assertTrue(all(nodes[c].kind == "post" for c in categories[1].children))

    def test_small_sets_and_failed_splits_stay_flat(self) -> None:
        ids, nodes = _summarized(["a", "b", "c"])
        llm: MagicMock = MagicMock()
        self.assertEqual(nodes[TopicBuilder(llm, "x", nodes, MagicMock()).build(ids)].children, ids)
        llm.ask.assert_not_called()
        ids, nodes = _summarized([str(i) for i in range(6)])
        llm.ask.return_value = ""
        root: str = TopicBuilder(llm, "x", nodes, MagicMock()).build(ids)
        self.assertEqual(nodes[root].children, ids)

    def test_unassigned_posts_go_to_other(self) -> None:
        ids, nodes = _summarized([f"A {i}" for i in range(4)] + ["B 0", "C 0"])

        def answer(prompt: str, accept: Callable[[str], bool]) -> str:
            posts: List[str] = [p["id"] for p in _payload(prompt)["posts"]]
            raw: str = json.dumps({"topics": [{"title": "A", "posts": posts[:4]}, {"title": "B", "posts": [posts[4]]}]})
            accept(raw)
            return raw

        llm: MagicMock = MagicMock()
        llm.ask.side_effect = answer
        groups = TopicBuilder(llm, "x", nodes, MagicMock()).split(ids, ["x"])
        self.assertEqual([(t, len(m)) for t, m in groups], [("A", 4), ("B", 1), (OTHER_TITLE, 1)])

    def test_large_sets_are_assigned_in_batches_against_existing_topics(self) -> None:
        ids, nodes = _summarized([f"{'A' if i % 2 else 'B'} {i}" for i in range(40)])
        seen: List[List[str]] = []

        def answer(prompt: str, accept: Callable[[str], bool]) -> str:
            seen.append(_payload(prompt)["existing_topics"])
            return _by_first_word(prompt, accept)

        llm: MagicMock = MagicMock()
        llm.ask.side_effect = answer
        old: int = topics.BATCH_CHARS
        topics.BATCH_CHARS = 200
        try:
            groups = TopicBuilder(llm, "x", nodes, MagicMock()).split(ids, ["x"])
        finally:
            topics.BATCH_CHARS = old
        self.assertGreater(len(seen), 1)
        self.assertEqual(seen[0], [])
        self.assertEqual(sorted(seen[1]), ["A", "B"])
        self.assertEqual(sorted((t, len(m)) for t, m in groups), [("A", 20), ("B", 20)])
        self.assertTrue(all(nodes[i].kind != TOPIC for i in ids))


if __name__ == "__main__":
    unittest.main()
