"""Assignment gates and explicit judge decisions without database access."""

import json
import unittest
from typing import Any, List, Tuple
from unittest.mock import Mock

import numpy as np
from scipy import sparse

from rsstag.anthology.assignment import _answers, assign_leftovers
from rsstag.anthology.candidates import Cluster, Vectors, make_cluster
from rsstag.anthology.result import RunCounters
from rsstag.anthology.units import Snippet


class AssignmentTests(unittest.TestCase):
    def fixture(self, rows: List[List[float]]) -> Tuple[Vectors, List[Snippet], List[Cluster]]:
        dense: np.ndarray = np.asarray(rows, dtype=float)
        vectors: Vectors = Vectors(sparse.csr_matrix(dense), np.array(["rocket", "recipe"]), dense)
        snippets: List[Snippet] = [
            Snippet(f"s{i}", str(i), [0], "Space", "", "", None, f"snippet {i}")
            for i in range(len(rows))
        ]
        cluster: Cluster = make_cluster("c0", [0, 1], vectors)
        cluster.label = "Rocket launch"
        cluster.kind = "event"
        cluster.score = 5
        cluster.intruder_ok = True
        return vectors, snippets, [cluster]

    def judge(self, answer: str) -> Mock:
        judge: Mock = Mock(calls=0)

        def ask(prompt: str) -> str:
            judge.calls += 1
            return answer

        judge.ask.side_effect = ask
        return judge

    def test_confirmation_updates_metadata_without_mutating_original(self) -> None:
        vectors: Vectors
        snippets: List[Snippet]
        clusters: List[Cluster]
        vectors, snippets, clusters = self.fixture([[1, 0], [1, 0], [.8, .6], [0, 1]])
        counters: RunCounters = RunCounters()
        result: List[Cluster] = assign_leftovers(
            clusters, vectors, snippets, self.judge('[{"id":1,"same":true}]'), "space", counters,
        )
        self.assertEqual(set(result[0].members), {0, 1, 2})
        self.assertEqual(clusters[0].members, [0, 1])
        self.assertTrue(clusters[0].intruder_ok)
        self.assertIsNone(result[0].intruder_ok)
        self.assertEqual(
            (result[0].label, result[0].kind, result[0].score),
            ("Rocket launch", "event", 5),
        )
        self.assertAlmostEqual(np.linalg.norm(result[0].centroid), 1)
        self.assertEqual(
            (
                counters.assignment_snippets_input, counters.assignment_candidates,
                counters.assignment_snippets_assigned, counters.assignment_llm_calls,
            ),
            (2, 1, 1, 1),
        )

    def test_missing_malformed_and_duplicate_judgments_never_assign(self) -> None:
        answers: List[str] = [
            '', '[]', '[{"id":1,"same":"true"}]',
            '[{"id":1,"same":true},{"id":1,"same":true}]',
            '[{"id":true,"same":true}]',
        ]
        for answer in answers:
            with self.subTest(answer=answer):
                vectors: Vectors
                snippets: List[Snippet]
                clusters: List[Cluster]
                vectors, snippets, clusters = self.fixture([[1, 0], [1, 0], [1, 0]])
                counters: RunCounters = RunCounters()
                result: List[Cluster] = assign_leftovers(
                    clusters, vectors, snippets, self.judge(answer), "", counters
                )
                self.assertEqual(result[0].members, [0, 1])
                self.assertEqual(counters.assignment_judgment_missing, 1)

    def test_explicit_rejection_is_a_valid_judgment(self) -> None:
        vectors: Vectors
        snippets: List[Snippet]
        clusters: List[Cluster]
        vectors, snippets, clusters = self.fixture([[1, 0], [1, 0], [1, 0]])
        counters: RunCounters = RunCounters()
        result: List[Cluster] = assign_leftovers(
            clusters, vectors, snippets, self.judge('[{"id":1,"same":false}]'), "", counters,
        )
        self.assertEqual(result[0].members, [0, 1])
        self.assertEqual(counters.assignment_judgment_missing, 0)

    def test_ambiguous_and_unsupported_candidates_skip_judge(self) -> None:
        vectors: Vectors
        snippets: List[Snippet]
        clusters: List[Cluster]
        vectors, snippets, clusters = self.fixture([[1, 0], [0, 1], [1, 0]])
        judge: Mock = self.judge('[]')
        counters: RunCounters = RunCounters()
        # Matching only one member provides insufficient evidence at these similarities.
        vectors.dense[2] = [.6, -.8]
        assign_leftovers(clusters, vectors, snippets, judge, "", counters)
        judge.ask.assert_not_called()
        vectors.dense[1] = [1, 0]
        vectors.dense[2] = [1, 0]
        clusters[0] = make_cluster("c0", [0, 1], vectors)
        clusters.append(make_cluster("c1", [0, 1], vectors))
        assign_leftovers(clusters, vectors, snippets, judge, "", counters)
        judge.ask.assert_not_called()

    def test_batch_prompts_keep_original_representatives(self) -> None:
        vectors: Vectors
        snippets: List[Snippet]
        clusters: List[Cluster]
        vectors, snippets, clusters = self.fixture([[1, 0]] * 12)
        judge: Mock = Mock(calls=0)
        payloads: List[Any] = []

        def ask(prompt: str) -> str:
            judge.calls += 1
            payload: Any = json.loads(prompt.rsplit("\n", 1)[1])
            payloads.append(payload)
            return json.dumps([
                {"id": item["id"], "same": True} for item in payload["items"]
            ])

        judge.ask.side_effect = ask
        counters: RunCounters = RunCounters()
        result: List[Cluster] = assign_leftovers(clusters, vectors, snippets, judge, "", counters)
        self.assertEqual(result[0].size, 12)
        self.assertEqual(counters.assignment_llm_calls, 2)
        for payload in payloads:
            for item in payload["items"]:
                self.assertEqual(item["representatives"], ["snippet 0", "snippet 1"])

    def test_parser_invalid_duplicate_cannot_be_overridden(self) -> None:
        self.assertEqual(_answers('[{"id":1},{"id":1,"same":true}]', 1), {})

    def test_json_fence_and_loose_cluster_exclusion(self) -> None:
        self.assertEqual(_answers('```json\n[{"id":1,"same":true}]\n```', 1), {1: True})
        vectors: Vectors
        snippets: List[Snippet]
        clusters: List[Cluster]
        vectors, snippets, clusters = self.fixture([[1, 0], [1, 0], [1, 0]])
        clusters[0].loose = True
        judge: Mock = self.judge('[]')
        counters: RunCounters = RunCounters()
        assign_leftovers(clusters, vectors, snippets, judge, "", counters)
        judge.ask.assert_not_called()
        self.assertEqual(counters.assignment_candidates, 0)

    def test_no_clusters_needs_no_judgment(self) -> None:
        vectors: Vectors
        snippets: List[Snippet]
        clusters: List[Cluster]
        vectors, snippets, clusters = self.fixture([[1, 0], [1, 0], [1, 0]])
        judge: Mock = self.judge('[]')
        counters: RunCounters = RunCounters()
        self.assertEqual(assign_leftovers([], vectors, snippets, judge, "", counters), [])
        judge.ask.assert_not_called()
        self.assertEqual(counters.assignment_snippets_input, 3)
