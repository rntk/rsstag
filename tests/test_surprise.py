import unittest
from unittest.mock import patch
import numpy as np
from rsstag.surprise import (
    _dirichlet_kl,
    BayesianSurprise,
    TagBayesianSurprise,
    LeaveOneOutSurprise,
)


class TestDirichletKL(unittest.TestCase):
    def test_identical_distributions(self):
        alpha = np.ones(3)
        kl = _dirichlet_kl(alpha, alpha)
        self.assertAlmostEqual(kl, 0.0, places=5)

    def test_different_distributions(self):
        alpha_post = np.array([2.0, 1.0, 1.0])
        alpha_prior = np.ones(3)
        kl = _dirichlet_kl(alpha_post, alpha_prior)
        self.assertGreater(kl, 0.0)

    def test_non_negative(self):
        alpha_post = np.array([5.0, 2.0, 3.0])
        alpha_prior = np.ones(3)
        kl = _dirichlet_kl(alpha_post, alpha_prior)
        self.assertGreaterEqual(kl, 0.0)

    def test_returns_float(self):
        alpha = np.ones(2)
        kl = _dirichlet_kl(alpha, alpha)
        self.assertIsInstance(kl, float)


class TestBayesianSurprise(unittest.TestCase):
    def test_empty_input(self):
        bs = BayesianSurprise()
        self.assertEqual(bs.compute([]), [])

    def test_single_document(self):
        bs = BayesianSurprise()
        scores = bs.compute(["hello world"])
        self.assertEqual(len(scores), 1)
        self.assertIsInstance(scores[0], float)

    def test_multiple_documents(self):
        bs = BayesianSurprise()
        scores = bs.compute(["hello world", "foo bar baz"])
        self.assertEqual(len(scores), 2)

    def test_repeated_documents_decreasing_surprise(self):
        bs = BayesianSurprise()
        scores = bs.compute(["hello world"] * 5)
        # Surprise should generally decrease as the prior stabilizes
        self.assertGreater(scores[0], scores[-1])

    def test_empty_document(self):
        bs = BayesianSurprise()
        scores = bs.compute(["hello world", "", "foo bar"])
        self.assertEqual(len(scores), 3)
        self.assertEqual(scores[1], 0.0)

    def test_max_features_limit(self):
        bs = BayesianSurprise(max_features=2)
        scores = bs.compute(["a b c d e f g h i j"])
        self.assertEqual(len(scores), 1)


class TestTagBayesianSurprise(unittest.TestCase):
    def test_empty_input(self):
        tbs = TagBayesianSurprise()
        result = tbs.compute([])
        self.assertEqual(result, {})

    def test_single_post(self):
        tbs = TagBayesianSurprise()
        result = tbs.compute([["tag1", "tag2"]])
        self.assertIn("tag1", result)
        self.assertIn("tag2", result)

    def test_posts_with_same_tags(self):
        tbs = TagBayesianSurprise()
        result = tbs.compute([["a", "b"], ["a", "b"], ["a", "b"]])
        # Surprise should decrease over time
        self.assertIn("a", result)
        self.assertIn("b", result)

    def test_post_with_single_tag_skipped(self):
        tbs = TagBayesianSurprise()
        result = tbs.compute([["only"]])
        self.assertEqual(result, {})

    def test_zeta_parameter(self):
        tbs = TagBayesianSurprise(zeta=0.5)
        result = tbs.compute([["x", "y"]])
        self.assertIn("x", result)
        self.assertIn("y", result)


class TestLeaveOneOutSurprise(unittest.TestCase):
    def test_normalized_background_uses_neighbor_events(self) -> None:
        posts: list[list[str]] = [
            ["alpha", "beta", "gamma"],
            ["alpha", "beta", "delta"],
        ]
        scores: dict[str, float] = LeaveOneOutSurprise().compute(posts)
        # For alpha in the first post, p=(1,2,2,1)/6 and the background
        # q=(1,2,1,2)/6 over alpha, beta, gamma, delta.
        expected: float = np.log(2.0) / 6.0
        self.assertAlmostEqual(expected, 0.1155245301, places=10)
        self.assertAlmostEqual(scores["alpha"], expected, places=12)
        self.assertAlmostEqual(scores["beta"], expected, places=12)

    def test_identical_two_post_contexts_have_zero_surprise(self) -> None:
        scores: dict[str, float] = LeaveOneOutSurprise().compute(
            [["alpha", "beta"], ["alpha", "beta"]]
        )
        self.assertAlmostEqual(scores["alpha"], 0.0, places=12)
        self.assertAlmostEqual(scores["beta"], 0.0, places=12)

    def test_empty_input(self):
        loos = LeaveOneOutSurprise()
        result = loos.compute([])
        self.assertEqual(result, {})

    def test_single_post(self):
        loos = LeaveOneOutSurprise()
        # Each tag must appear in at least 2 posts for bg_total > 0
        result = loos.compute(
            [["tag1", "tag2"], ["tag1", "tag2"], ["tag1", "tag3"]]
        )
        self.assertIn("tag1", result)
        self.assertIn("tag2", result)

    def test_post_with_single_tag_filtered(self):
        loos = LeaveOneOutSurprise()
        # Tag 'b' must appear in 2+ posts to have bg_total > 0
        result = loos.compute(
            [["only"], ["a", "b"], ["a", "b"], ["a", "c"]]
        )
        self.assertNotIn("only", result)
        self.assertIn("a", result)
        self.assertIn("b", result)

    def test_specific_post_index(self):
        loos = LeaveOneOutSurprise()
        # Tag 'b' must appear in 2+ posts for bg_total > 0
        result = loos.compute(
            [["a", "b"], ["a", "b"], ["c", "d"]], post_idx=0
        )
        self.assertIn("a", result)
        self.assertIn("b", result)
        self.assertNotIn("c", result)

    def test_invalid_post_index(self):
        loos = LeaveOneOutSurprise()
        # All tags must appear in 2+ posts for bg_total > 0
        result = loos.compute(
            [["a", "b"], ["a", "b"], ["c", "d"], ["c", "d"]], post_idx=-1
        )
        self.assertIn("a", result)
        self.assertIn("b", result)
        self.assertIn("c", result)
        self.assertIn("d", result)

    def test_smoothing_parameter(self):
        loos = LeaveOneOutSurprise(smoothing=0.5)
        result = loos.compute([["x", "y"], ["x", "z"], ["y", "z"]])
        self.assertIn("x", result)
        self.assertIn("y", result)
        self.assertIn("z", result)


class TestLeaveOneOutSurpriseMemory(unittest.TestCase):
    @staticmethod
    def _dense_reference(
        posts: list[list[str]], smoothing: float, post_idx: int
    ) -> dict[str, float]:
        """Original dense calculation, restricted to small regression fixtures."""
        filtered: list[list[str]] = [list(set(post)) for post in posts if len(set(post)) >= 2]
        vocabulary: list[str] = sorted({tag for post in filtered for tag in post})
        scores: dict[str, list[float]] = {}
        selected: list[list[str]] = [filtered[post_idx]] if 0 <= post_idx < len(filtered) else filtered
        for post in selected:
            for tag in post:
                containing: list[list[str]] = [other for other in filtered if tag in other]
                if len(containing) < 2:
                    continue
                counts: np.ndarray = np.array([
                    sum(other != tag and other in tags for tags in containing)
                    - int(other != tag and other in post)
                    for other in vocabulary
                ], dtype=np.float64)
                background: np.ndarray = (counts + smoothing) / (counts.sum() + smoothing * len(vocabulary))
                distribution: np.ndarray = np.array([
                    smoothing + int(other != tag and other in post) for other in vocabulary
                ], dtype=np.float64)
                distribution /= len(post) - 1 + smoothing * len(vocabulary)
                score: float = max(float(np.sum(distribution * np.log(distribution / background))), 0.0)
                scores.setdefault(tag, []).append(score)
        return {tag: sum(values) / len(values) for tag, values in scores.items()}

    def test_matches_dense_scores(self) -> None:
        random: np.random.Generator = np.random.default_rng(42)
        posts: list[list[str]] = [[], ["single"], ["duplicate", "duplicate"]]
        posts.extend([
            [str(value) for value in random.integers(0, 18, size=int(random.integers(2, 8)))]
            for _ in range(40)
        ])
        posts.extend([["rare", "0"], ["0", "1"], ["0", "1"]])
        for smoothing in (0.01, 0.5, 1.0, 3.0):
            for post_idx in (-2, -1, 0, 9, 41, 100):
                with self.subTest(smoothing=smoothing, post_idx=post_idx):
                    expected: dict[str, float] = self._dense_reference(posts, smoothing, post_idx)
                    actual: dict[str, float] = LeaveOneOutSurprise(smoothing).compute(posts, post_idx)
                    self.assertEqual(actual.keys(), expected.keys())
                    for tag in expected:
                        self.assertAlmostEqual(actual[tag], expected[tag], places=12)

    def test_large_vocabulary_without_dense_allocation(self) -> None:
        # Match the reported vocabulary and post counts. Only the shared tag
        # has a background; unique neighbors must not allocate pairwise rows.
        posts: list[list[str]] = [["shared"] for _ in range(6608)]
        for index in range(105181):
            posts[index % len(posts)].append(f"tag-{index}")
        with patch("rsstag.surprise.np.zeros", side_effect=AssertionError("Dense allocation")):
            scores: dict[str, float] = LeaveOneOutSurprise().compute(posts)
            selected: dict[str, float] = LeaveOneOutSurprise().compute(posts, post_idx=0)
        self.assertEqual(set(scores), {"shared"})
        self.assertEqual(set(selected), {"shared"})
        self.assertTrue(np.isfinite(scores["shared"]))
        self.assertTrue(np.isfinite(selected["shared"]))


if __name__ == "__main__":
    unittest.main()
