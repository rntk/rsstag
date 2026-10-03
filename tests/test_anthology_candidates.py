import unittest
from typing import List, Set

import numpy as np

from rsstag.anthology.candidates import (
    build_candidates,
    cluster_rows,
    fine_cluster_count,
    merge_pairs,
    vectorize,
)
from tests.anthology_fakes import TOPIC_WORDS, synthetic_texts


class TestAnthologyCandidates(unittest.TestCase):
    def test_separate_topics_end_up_in_different_clusters(self) -> None:
        texts, truth = synthetic_texts(per_topic=12)
        clusters, unsorted = build_candidates(vectorize(texts))

        self.assertGreaterEqual(len(clusters), 3)
        topics_per_cluster: List[Set[str]] = [{truth[row] for row in c.members} for c in clusters]
        for topics in topics_per_cluster:
            self.assertEqual(len(topics), 1, f"mixed cluster: {topics}")
        covered: Set[str] = set().union(*topics_per_cluster)
        self.assertEqual(covered, set(TOPIC_WORDS))
        assigned: int = sum(c.size for c in clusters)
        self.assertEqual(assigned + len(unsorted), len(texts))

    def test_cluster_stats(self) -> None:
        texts, truth = synthetic_texts(per_topic=12)
        clusters, _ = build_candidates(vectorize(texts))
        for cluster in clusters:
            self.assertLessEqual(len(cluster.keywords), 8)
            self.assertTrue(cluster.keywords)
            vocab: List[str] = TOPIC_WORDS[truth[cluster.members[0]]]
            self.assertIn(cluster.keywords[0], vocab)
            self.assertGreaterEqual(cluster.cohesion, 0.0)
            self.assertLessEqual(cluster.cohesion, 1.0)

    def test_deterministic(self) -> None:
        texts, _ = synthetic_texts(per_topic=10)
        first = [c.members for c in build_candidates(vectorize(texts))[0]]
        second = [c.members for c in build_candidates(vectorize(texts))[0]]
        self.assertEqual(first, second)

    def test_tiny_input_forms_one_cluster(self) -> None:
        clusters, unsorted = build_candidates(vectorize(["rocket launch", "rocket orbit", "pasta"]))
        self.assertEqual(len(clusters), 1)
        self.assertEqual(sorted(clusters[0].members), [0, 1, 2])
        self.assertEqual(unsorted, [])

    def test_empty_vocabulary_is_handled(self) -> None:
        vectors = vectorize(["the and", "a the", "и в", "the"])
        self.assertEqual(vectors.dense.shape[0], 4)
        clusters, unsorted = build_candidates(vectors)
        self.assertEqual(sum(c.size for c in clusters) + len(unsorted), 4)

    def test_empty_input(self) -> None:
        self.assertEqual(build_candidates(vectorize([])), ([], []))
        self.assertEqual(cluster_rows(np.zeros((0, 2)), 3).shape[0], 0)

    def test_fine_cluster_count_bounds(self) -> None:
        self.assertEqual(fine_cluster_count(5), 2)
        self.assertEqual(fine_cluster_count(60), 10)
        self.assertEqual(fine_cluster_count(3000), 60)
        self.assertEqual(fine_cluster_count(2), 1)

    def test_merge_pairs_only_similar(self) -> None:
        texts, truth = synthetic_texts(per_topic=12)
        clusters, _ = build_candidates(vectorize(texts))
        for i, j in merge_pairs(clusters, 0.4, 30):
            topic_i: Set[str] = {truth[r] for r in clusters[i].members}
            topic_j: Set[str] = {truth[r] for r in clusters[j].members}
            self.assertEqual(topic_i, topic_j)


if __name__ == "__main__":
    unittest.main()
