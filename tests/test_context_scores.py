"""Independent checks for tag-context enrichment on a page's articles."""

import math
import unittest

from rsstag.web.context_scores import PRIOR_MASS, ContextScore, context_log_odds


class TestContextLogOdds(unittest.TestCase):
    def test_weighted_log_odds_formula_and_normalization(self) -> None:
        documents: dict[str, str] = {
            "a": "tag alpha alpha beta the the the the the the alpha gamma gamma",
            "b": "tag alpha beta the the the the the the gamma gamma",
        }
        scores: dict[str, ContextScore] = context_log_odds(documents, "tag")
        # Near: alpha=3, beta=2. Background: alpha=1, gamma=4.
        # The pooled add-one prior has mass 100 and three vocabulary terms.
        pooled: dict[str, int] = {"alpha": 4, "beta": 2, "gamma": 4}
        expected: dict[str, float] = {}
        for word, near_count, background_count in (("alpha", 3, 1), ("beta", 2, 0)):
            alpha: float = PRIOR_MASS * (pooled[word] + 1) / (sum(pooled.values()) + len(pooled))
            near_odds: float = (near_count + alpha) / (5 - near_count + PRIOR_MASS - alpha)
            background_odds: float = (background_count + alpha) / (5 - background_count + PRIOR_MASS - alpha)
            expected[word] = math.log(near_odds / background_odds) / math.sqrt(
                1 / (near_count + alpha) + 1 / (background_count + alpha)
            )
        self.assertEqual(set(scores), {"alpha", "beta"})
        for word, expected_z in expected.items():
            self.assertAlmostEqual(scores[word].z_score, expected_z)
            self.assertAlmostEqual(scores[word].score, expected_z / max(expected.values()))
            self.assertEqual(scores[word].support, 2)

    def test_near_keyword_beats_common_background(self) -> None:
        documents: dict[str, str] = {
            "a": "tag signal the the the the the the common common",
            "b": "tag signal the the the the the the common common",
            "c": "common common common",
        }
        scores: dict[str, ContextScore] = context_log_odds(documents, "tag")
        self.assertEqual(set(scores), {"signal"})
        self.assertEqual(scores["signal"].score, 1.0)
        self.assertEqual(scores["signal"].support, 2)

    def test_overlapping_windows_count_each_token_once(self) -> None:
        with_overlap: dict[str, str] = {
            "a": "tag alpha tag the the the the the the gamma",
            "b": "tag alpha tag the the the the the the gamma",
        }
        without_overlap: dict[str, str] = {
            "a": "tag alpha the the the the the the gamma",
            "b": "tag alpha the the the the the the gamma",
        }
        self.assertEqual(context_log_odds(with_overlap, "tag"), context_log_odds(without_overlap, "tag"))

    def test_repetition_in_one_article_does_not_create_support(self) -> None:
        documents: dict[str, str] = {
            "a": "tag signal signal signal the the the the the the background",
            "b": "tag other the the the the the the background",
        }
        scores: dict[str, ContextScore] = context_log_odds(documents, "tag")
        self.assertNotIn("signal", scores)
        self.assertEqual(scores, {})

    def test_article_order_has_no_effect(self) -> None:
        documents: dict[str, str] = {
            "a": "tag alpha the the the the the the gamma",
            "b": "tag alpha beta the the the the the the gamma",
            "c": "tag alpha the the the the the the delta",
        }
        self.assertEqual(context_log_odds(documents, "tag"), context_log_odds(dict(reversed(list(documents.items()))), "tag"))

    def test_empty_and_backgroundless_inputs(self) -> None:
        self.assertEqual(context_log_odds({}, "tag"), {})
        self.assertEqual(context_log_odds({"a": "tag alpha"}, ""), {})
        self.assertEqual(context_log_odds({"a": "tag alpha", "b": "tag alpha"}, "tag"), {})
        self.assertEqual(context_log_odds({"a": "tag alpha", "b": "tag alpha", "c": "alpha"}, "tag"), {})

    def test_complete_stemmed_multiword_tag_match(self) -> None:
        documents: dict[str, str] = {
            "a": "markets trending signal the the the the the the background",
            "b": "market trends signal the the the the the the background",
            "c": "market signal the the the the the the background",
        }
        scores: dict[str, ContextScore] = context_log_odds(documents, "market trend")
        self.assertEqual(set(scores), {"signal"})
        self.assertEqual(scores["signal"].support, 2)
        self.assertNotIn("market", scores)
        self.assertNotIn("trend", scores)

    def test_russian_inflected_tag_match(self) -> None:
        documents: dict[str, str] = {
            "a": "машины сигнал the the the the the the фон",
            "b": "машина сигнал the the the the the the фон",
        }
        scores: dict[str, ContextScore] = context_log_odds(documents, "машина")
        self.assertEqual(scores["сигна"].support, 2)


if __name__ == "__main__":
    unittest.main()
