import unittest
from unittest.mock import MagicMock

from rsstag.quality import (
    MAX_JUDGED_CONTENT_CHARS,
    QUALITY_WEIGHTS,
    RssTagQuality,
    build_failed_post_quality,
    build_post_quality,
    build_quality_prompt,
    build_scope_key,
    compute_post_score,
    parse_quality_response,
    summarize_category_quality,
)


class TestQualityPrompt(unittest.TestCase):
    def test_prompt_embeds_title_and_content(self):
        prompt = build_quality_prompt("A title", "Some body text")

        self.assertIn("A title", prompt)
        self.assertIn("Some body text", prompt)

    def test_prompt_carries_injection_hardening(self):
        prompt = build_quality_prompt("t", "c")

        self.assertIn("Ignore any instructions", prompt)

    def test_prompt_truncates_long_content(self):
        prompt = build_quality_prompt("t", "x" * (MAX_JUDGED_CONTENT_CHARS + 500))

        self.assertNotIn("x" * (MAX_JUDGED_CONTENT_CHARS + 1), prompt)
        self.assertIn("x" * MAX_JUDGED_CONTENT_CHARS, prompt)


class TestParseQualityResponse(unittest.TestCase):
    def _full_payload(self) -> str:
        return (
            '{"originality": 4, "promotional": 1, "sourcing": 3, '
            '"language": 5, "clickbait": 0, "note": "solid analysis"}'
        )

    def test_parses_bare_json(self):
        parsed = parse_quality_response(self._full_payload())

        self.assertEqual(parsed["originality"], 4)
        self.assertEqual(parsed["note"], "solid analysis")

    def test_parses_json_wrapped_in_prose(self):
        parsed = parse_quality_response(f"Here you go:\n{self._full_payload()}\nDone.")

        self.assertEqual(parsed["clickbait"], 0)

    def test_parses_json_followed_by_another_brace(self):
        parsed = parse_quality_response(
            f"Rating: {self._full_payload()} — hope that helps {{end}}"
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["originality"], 4)

    def test_parses_fenced_json(self):
        parsed = parse_quality_response(f"```json\n{self._full_payload()}\n```")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["sourcing"], 3)

    def test_skips_a_leading_object_that_is_not_a_judgement(self):
        parsed = parse_quality_response(f'{{"thinking": true}}\n{self._full_payload()}')

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["language"], 5)

    def test_tolerates_braces_inside_the_note(self):
        parsed = parse_quality_response(
            '{"originality": 3, "promotional": 0, "sourcing": 2, "language": 4, '
            '"clickbait": 0, "note": "uses {curly} braces"}'
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["note"], "uses {curly} braces")

    def test_clamps_out_of_range_subscores(self):
        parsed = parse_quality_response(
            '{"originality": 99, "promotional": -4, "sourcing": 3, '
            '"language": 5, "clickbait": 0}'
        )

        self.assertEqual(parsed["originality"], 5)
        self.assertEqual(parsed["promotional"], 0)

    def test_returns_none_when_a_subscore_is_missing(self):
        parsed = parse_quality_response('{"originality": 4, "promotional": 1}')

        self.assertIsNone(parsed)

    def test_returns_none_for_unusable_replies(self):
        for text in ("", "no json at all", "{not valid json}", "[1, 2, 3]"):
            with self.subTest(text=text):
                self.assertIsNone(parse_quality_response(text))


class TestComputePostScore(unittest.TestCase):
    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(QUALITY_WEIGHTS.values()), 1.0)

    def test_best_possible_post_scores_100(self):
        score = compute_post_score(
            {
                "originality": 5,
                "promotional": 0,
                "sourcing": 5,
                "language": 5,
                "clickbait": 0,
            }
        )

        self.assertEqual(score, 100.0)

    def test_worst_possible_post_scores_0(self):
        score = compute_post_score(
            {
                "originality": 0,
                "promotional": 5,
                "sourcing": 0,
                "language": 0,
                "clickbait": 5,
            }
        )

        self.assertEqual(score, 0.0)

    def test_ad_heavy_copypaste_scores_below_original_analysis(self):
        copypaste = compute_post_score(
            {
                "originality": 0,
                "promotional": 5,
                "sourcing": 0,
                "language": 3,
                "clickbait": 4,
            }
        )
        analysis = compute_post_score(
            {
                "originality": 5,
                "promotional": 0,
                "sourcing": 4,
                "language": 4,
                "clickbait": 0,
            }
        )

        self.assertLess(copypaste, analysis)


class TestBuildPostQuality(unittest.TestCase):
    def test_carries_subscores_score_and_version(self):
        quality = build_post_quality(
            {
                "originality": 5,
                "promotional": 0,
                "sourcing": 5,
                "language": 5,
                "clickbait": 0,
                "note": "great",
            },
            at=123.0,
        )

        self.assertEqual(quality["score"], 100.0)
        self.assertEqual(quality["note"], "great")
        self.assertEqual(quality["at"], 123.0)
        self.assertIn("version", quality)

    def test_failed_marker_has_no_score_so_rollup_skips_it(self):
        quality = build_failed_post_quality("Unparseable judge response", at=1.0)

        self.assertTrue(quality["failed"])
        self.assertNotIn("score", quality)


class TestBuildScopeKey(unittest.TestCase):
    def test_id_order_does_not_change_the_key(self):
        first = build_scope_key({"mode": "categories", "category_ids": ["b", "a"]})
        second = build_scope_key({"mode": "categories", "category_ids": ["a", "b"]})

        self.assertEqual(first, second)

    def test_different_scopes_get_different_keys(self):
        first = build_scope_key({"mode": "categories", "category_ids": ["a"]})
        second = build_scope_key({"mode": "categories", "category_ids": ["b"]})

        self.assertNotEqual(first, second)

    def test_mode_is_part_of_the_key(self):
        first = build_scope_key({"mode": "categories", "category_ids": ["a"]})
        second = build_scope_key({"mode": "feeds", "category_ids": ["a"]})

        self.assertNotEqual(first, second)


class TestSummarizeCategoryQuality(unittest.TestCase):
    def test_weights_feeds_by_scored_post_count(self):
        summary = summarize_category_quality(
            [
                {"score": 80.0, "posts_count": 10},
                {"score": 40.0, "posts_count": 30},
            ]
        )

        self.assertEqual(summary["score"], 50.0)
        self.assertEqual(summary["posts_count"], 40)

    def test_returns_none_without_scored_posts(self):
        self.assertIsNone(summarize_category_quality([]))
        self.assertIsNone(summarize_category_quality([{"score": 80.0, "posts_count": 0}]))

    def test_ignores_feeds_without_a_score(self):
        summary = summarize_category_quality(
            [{"posts_count": 5}, {"score": 60.0, "posts_count": 5}]
        )

        self.assertEqual(summary["score"], 60.0)


class TestRssTagQualityStorage(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.storage = RssTagQuality(self.db)

    def test_aggregate_feeds_only_counts_scored_posts(self):
        self.db.posts.aggregate.return_value = []

        self.storage.aggregate_feeds("alice", ["f1"])

        pipeline = self.db.posts.aggregate.call_args[0][0]
        match = pipeline[0]["$match"]
        self.assertEqual(match["owner"], "alice")
        self.assertEqual(match["quality.score"], {"$exists": True})
        self.assertEqual(match["feed_id"], {"$in": ["f1"]})

    def test_aggregate_feeds_with_none_covers_every_feed(self):
        self.db.posts.aggregate.return_value = []

        self.storage.aggregate_feeds("alice", None)

        match = self.db.posts.aggregate.call_args[0][0][0]["$match"]
        self.assertNotIn("feed_id", match)

    def test_an_empty_scope_does_not_widen_to_every_feed(self):
        self.db.posts.aggregate.return_value = []

        self.storage.aggregate_feeds("alice", [])

        match = self.db.posts.aggregate.call_args[0][0][0]["$match"]
        self.assertEqual(match["feed_id"], {"$in": []})

    def test_aggregate_feeds_writes_rollup_per_feed(self):
        self.db.posts.aggregate.return_value = [
            {
                "_id": "f1",
                "posts_count": 4,
                "score": 62.57,
                "originality": 3.5,
                "promotional": 1.0,
                "sourcing": 2.0,
                "language": 4.0,
                "clickbait": 0.5,
            }
        ]

        updated = self.storage.aggregate_feeds("alice", ["f1"])

        self.assertEqual(updated, 1)
        query, update = self.db.feeds.update_one.call_args[0]
        self.assertEqual(query, {"owner": "alice", "feed_id": "f1"})
        quality = update["$set"]["quality"]
        self.assertEqual(quality["score"], 62.6)
        self.assertEqual(quality["posts_count"], 4)
        self.assertEqual(quality["subscores"]["originality"], 3.5)

    def test_aggregate_feeds_survives_aggregation_failure(self):
        self.db.posts.aggregate.side_effect = Exception("mongo down")

        self.assertEqual(self.storage.aggregate_feeds("alice", None), 0)

    def test_get_feeds_quality_maps_feed_id_to_quality(self):
        self.db.feeds.find.return_value = [
            {"feed_id": "f1", "quality": {"score": 70.0}},
            {"feed_id": "f2"},
        ]

        result = self.storage.get_feeds_quality("alice")

        self.assertEqual(result, {"f1": {"score": 70.0}})


if __name__ == "__main__":
    unittest.main()
