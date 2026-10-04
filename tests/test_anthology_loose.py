"""Loose leftover labeling tests use a deterministic fake judge, never a live LLM."""

import unittest
from typing import List, Set

import numpy as np

from rsstag.anthology import loose
from rsstag.anthology.candidates import Cluster, Vectors, make_cluster, vectorize
from rsstag.anthology.judge import Judge
from rsstag.anthology.result import RunCounters, build_result
from rsstag.anthology.stages import Theme
from rsstag.anthology.units import Snippet
from tests.anthology_fakes import FakeDB, FakeRouter, synthetic_snippets


class TestLooseGroups(unittest.TestCase):
    def test_empty_and_single_rows(self) -> None:
        self.assertEqual(loose.loose_groups(np.zeros((0, 3))), [])
        self.assertEqual(loose.loose_groups(np.ones((1, 3))), [[0]])

    def test_unrelated_rows_stay_singletons_and_similar_rows_group(self) -> None:
        dense: np.ndarray = np.array([[1.0, 0, 0], [0.98, 0.2, 0], [0, 1.0, 0], [0, 0, 1.0]])
        groups: List[List[int]] = loose.loose_groups(dense)
        self.assertEqual(groups, [[0, 1], [2], [3]])

    def test_zero_rows_do_not_crash(self) -> None:
        groups: List[List[int]] = loose.loose_groups(np.zeros((3, 4)))
        self.assertEqual(sorted(row for group in groups for row in group), [0, 1, 2])


class TestLabelLeftovers(unittest.TestCase):
    def setUp(self) -> None:
        self.snippets: List[Snippet]
        self.truth: List[str]
        self.snippets, self.truth = synthetic_snippets(per_topic=4)
        self.vectors: Vectors = vectorize([s.vector_text for s in self.snippets])
        self.accepted: List[Cluster] = [make_cluster("c0", [0, 1, 2, 3], self.vectors)]

    def test_every_leftover_gets_a_labeled_loose_cluster(self) -> None:
        router: FakeRouter = FakeRouter(label_score=1)  # low scores must not dissolve
        counters: RunCounters = RunCounters()
        result: List[Cluster] = loose.label_leftovers(
            self.accepted, self.vectors, self.snippets, Judge(FakeDB(), router, "owner"), "seed", counters
        )
        rows: List[int] = [row for cluster in result for row in cluster.members]
        self.assertEqual(sorted(rows), list(range(4, 12)))
        self.assertTrue(all(c.loose and c.label and c.id.startswith("l") for c in result))
        self.assertTrue(all(c.centroid.shape == self.vectors.dense.shape[1:] for c in result))
        self.assertTrue(all(len({self.truth[row] for row in c.members}) == 1 for c in result))
        self.assertEqual(counters.loose_snippets, 8)
        self.assertEqual(counters.loose_clusters, len(result))
        self.assertGreater(counters.loose_llm_calls, 0)

    def test_single_leftover_becomes_one_snippet_topic(self) -> None:
        accepted: List[Cluster] = [make_cluster("c0", list(range(11)), self.vectors)]
        result: List[Cluster] = loose.label_leftovers(
            accepted, self.vectors, self.snippets,
            Judge(FakeDB(), FakeRouter(), "owner"), "seed", RunCounters(),
        )
        self.assertEqual([c.members for c in result], [[11]])
        self.assertTrue(result[0].label)

    def test_failed_judge_falls_back_to_keyword_labels(self) -> None:
        class SilentRouter(FakeRouter):
            def call(self, settings: object, user_msgs: List[str], **kwargs: object) -> str:
                return ""

        result: List[Cluster] = loose.label_leftovers(
            self.accepted, self.vectors, self.snippets,
            Judge(FakeDB(), SilentRouter(), "owner"), "seed", RunCounters(),
        )
        self.assertTrue(result)
        self.assertTrue(all(c.label for c in result))

    def test_nothing_left_means_no_loose_clusters(self) -> None:
        accepted: List[Cluster] = [make_cluster("c0", list(range(12)), self.vectors)]
        counters: RunCounters = RunCounters()
        self.assertEqual(
            loose.label_leftovers(
                accepted, self.vectors, self.snippets,
                Judge(FakeDB(), FakeRouter(), "owner"), "seed", counters,
            ),
            [],
        )
        self.assertEqual(counters.loose_snippets, 0)

    def test_result_keeps_loose_out_of_coverage(self) -> None:
        counters: RunCounters = RunCounters()
        loose_clusters: List[Cluster] = loose.label_leftovers(
            self.accepted, self.vectors, self.snippets,
            Judge(FakeDB(), FakeRouter(), "owner"), "seed", counters,
        )
        themes: List[Theme] = [
            Theme(clusters=self.accepted, label="Space"),
            loose.loose_theme(loose_clusters, self.vectors),
        ]
        result = build_result(self.snippets, themes, counters)
        loose_ids: Set[str] = {c.id for c in loose_clusters}
        self.assertEqual(result["unsorted"], [])
        self.assertEqual(result["metrics"]["snippets_assigned"], 4)
        self.assertAlmostEqual(result["metrics"]["coverage"], 4 / 12, places=4)
        self.assertEqual(result["metrics"]["clusters_final"], 1)
        self.assertEqual(result["metrics"]["loose_snippets"], 8)
        self.assertTrue(result["themes"][1]["loose"])
        self.assertEqual(result["themes"][1]["label"], loose.LOOSE_THEME_LABEL)
        self.assertTrue(all(result["clusters"][cid]["loose"] for cid in loose_ids))
        self.assertFalse(result["clusters"]["c0"]["loose"])


if __name__ == "__main__":
    unittest.main()
