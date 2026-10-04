"""Bounded repair checks with deterministic vectors and a mocked judge."""

import copy
import json
import unittest
from typing import List, Tuple
from unittest.mock import MagicMock, patch

import numpy as np
from scipy import sparse

from rsstag.anthology import repair, stages
from rsstag.anthology.candidates import Cluster, Vectors, make_cluster
from rsstag.anthology.judge import Judge
from rsstag.anthology.result import RunCounters
from rsstag.anthology.units import Snippet


def fixture(core_size: int, other_size: int) -> Tuple[List[Snippet], Vectors, Cluster]:
    dense: np.ndarray = np.array([[1.0, 0.0]] * core_size + [[0.0, 1.0]] * other_size)
    snippets: List[Snippet] = [
        Snippet(f"s{row}", str(row), [0], "", "", "", None,
                "rocket orbit" if row < core_size else "pasta recipe")
        for row in range(len(dense))
    ]
    vectors: Vectors = Vectors(sparse.csr_matrix(dense), np.array(["rocket", "pasta"]), dense)
    parent: Cluster = make_cluster("c7", list(range(len(dense))), vectors)
    parent.score = 1
    parent.label = "mixed"
    return snippets, vectors, parent


def label_answer(scores: List[int]) -> str:
    return json.dumps([
        {"id": index, "score": score, "label": "subject", "kind": "event"}
        for index, score in enumerate(scores, start=1)
    ])


class TestAnthologyRepair(unittest.TestCase):
    def _judge(self, answer: str) -> Judge:
        judge: Judge = MagicMock(spec=Judge)
        judge.calls = 0

        def ask(prompt: str) -> str:
            judge.calls += 1
            return answer

        judge.ask.side_effect = ask
        return judge

    def test_coherent_core_survives_and_outlier_remains_unassigned(self) -> None:
        snippets, vectors, parent = fixture(4, 1)
        counters: RunCounters = RunCounters()
        result: List[Cluster] = repair.repair_rejected(
            [parent], vectors, snippets, self._judge(label_answer([4])), "space", counters
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(set(result[0].members), {0, 1, 2, 3})
        self.assertEqual(result[0].id, "c7s0")
        self.assertEqual(counters.repair_snippets_assigned, 4)
        self.assertEqual(counters.repair_clusters_candidate, 1)

    def test_two_distinct_cores_survive_without_mutating_parent(self) -> None:
        snippets, vectors, parent = fixture(3, 3)
        before: Cluster = copy.deepcopy(parent)
        counters: RunCounters = RunCounters()
        result: List[Cluster] = repair.repair_rejected(
            [parent], vectors, snippets, self._judge(label_answer([4, 4])), "topics", counters
        )
        self.assertEqual({frozenset(c.members) for c in result},
                         {frozenset({0, 1, 2}), frozenset({3, 4, 5})})
        self.assertEqual(len({c.id for c in result}), 2)
        members: List[int] = [row for c in result for row in c.members]
        self.assertEqual(len(members), len(set(members)))
        self.assertEqual(parent.members, before.members)
        self.assertEqual(parent.label, before.label)
        self.assertEqual(parent.score, before.score)
        np.testing.assert_array_equal(parent.centroid, before.centroid)
        self.assertEqual(counters.repair_clusters_final, 2)

    def test_low_missing_and_invalid_judgments_cannot_accept_children(self) -> None:
        snippets, vectors, parent = fixture(3, 3)
        answers: List[str] = [label_answer([1, 2]), "", "garbage",
                              '[{"id":1,"label":"subject"}]']
        for answer in answers:
            with self.subTest(answer=answer):
                judge: Judge = self._judge(answer)
                counters: RunCounters = RunCounters()
                with patch.object(repair, "cluster_rows", wraps=repair.cluster_rows) as split:
                    result: List[Cluster] = repair.repair_rejected(
                        [parent], vectors, snippets, judge, "topics", counters
                    )
                self.assertEqual(result, [])
                self.assertEqual(split.call_count, 1)
                self.assertEqual(judge.calls, 1)
                self.assertEqual(counters.repair_llm_calls, 1)
                self.assertEqual(counters.clusters_dissolved, 2)

    def test_tiny_reject_has_no_split_or_judge_cost(self) -> None:
        snippets, vectors, parent = fixture(1, 1)
        judge: Judge = self._judge(label_answer([4]))
        counters: RunCounters = RunCounters()
        with patch.object(repair, "cluster_rows") as split:
            result: List[Cluster] = repair.repair_rejected(
                [parent], vectors, snippets, judge, "topics", counters
            )
        self.assertEqual(result, [])
        split.assert_not_called()
        judge.ask.assert_not_called()

    def test_missing_intruder_judgments_reject_tested_children(self) -> None:
        snippets, vectors, parent = fixture(4, 4)
        judge: Judge = self._judge(label_answer([4, 4]))
        counters: RunCounters = RunCounters()
        result: List[Cluster] = repair.repair_rejected(
            [parent], vectors, snippets, judge, "topics", counters
        )
        self.assertEqual(result, [])
        self.assertEqual(judge.calls, 2)
        self.assertEqual(counters.repair_llm_calls, 2)
        self.assertEqual(counters.clusters_dissolved, 2)

    def test_successful_intruder_checks_keep_both_children(self) -> None:
        snippets, vectors, parent = fixture(4, 4)
        children: List[Cluster] = repair._split(parent, vectors)
        answer: str = "\n".join(
            f"{number}: {item.answer_position}"
            for number, item in enumerate(stages.build_intruder_sets(children), start=1)
        )
        judge: Judge = self._judge(label_answer([4, 4]))

        def ask(prompt: str) -> str:
            judge.calls += 1
            return answer if prompt.startswith("TASK: INTRUDER") else label_answer([4, 4])

        judge.ask.side_effect = ask
        counters: RunCounters = RunCounters()
        result: List[Cluster] = repair.repair_rejected(
            [parent], vectors, snippets, judge, "topics", counters
        )
        self.assertEqual(len(result), 2)
        self.assertTrue(all(cluster.intruder_ok for cluster in result))
        self.assertEqual(counters.repair_snippets_assigned, 8)
        self.assertEqual(counters.repair_llm_calls, 2)


if __name__ == "__main__":
    unittest.main()
