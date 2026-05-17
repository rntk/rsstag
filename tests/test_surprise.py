import unittest
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


if __name__ == "__main__":
    unittest.main()
