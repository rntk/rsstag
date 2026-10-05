"""Tests for the TASK_TAGS_CORPUS_RANK handler: pure helpers and DB run."""

import math
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from pymongo.database import Database

from rsstag import tag_rank_corpus
from rsstag.tag_rank_corpus import (
    CorpusStats,
    boilerplate_share,
    day_index,
    feed_entropy,
    hot_score,
    title_stems,
    window_of,
)
from rsstag.tags_builder import TagsBuilder
from tests.db_utils import DBHelper

TEST_MONGO_PORT: int = 8765
DAY: float = 86400.0
NOW: float = 20000 * DAY + 3600.0


class TestFeedEntropy(unittest.TestCase):
    def test_single_or_no_feed_is_zero(self) -> None:
        self.assertEqual(0.0, feed_entropy([]))
        self.assertEqual(0.0, feed_entropy([10]))

    def test_uniform_is_one(self) -> None:
        self.assertAlmostEqual(1.0, feed_entropy([4, 4, 4]))

    def test_skewed_is_between_zero_and_one(self) -> None:
        expected: float = -(2 / 3 * math.log(2 / 3) + 1 / 3 * math.log(1 / 3)) / math.log(2)
        self.assertAlmostEqual(expected, feed_entropy([2, 1]))
        self.assertLess(feed_entropy([99, 1]), feed_entropy([50, 50]))


class TestBoilerplate(unittest.TestCase):
    def test_ignores_small_feeds(self) -> None:
        self.assertEqual(0.0, boilerplate_share({"a": 3}, {"a": 4}))

    def test_max_over_big_feeds(self) -> None:
        share: float = boilerplate_share(
            {"a": 3, "b": 9}, {"a": 6, "b": 10, "c": 50}, min_feed_posts=5
        )
        self.assertAlmostEqual(0.9, share)

    def test_empty(self) -> None:
        self.assertEqual(0.0, boilerplate_share({}, {}))


class TestHotScore(unittest.TestCase):
    def test_zero_without_recent(self) -> None:
        self.assertEqual(0.0, hot_score(0, 50))

    def test_formula(self) -> None:
        expected: float = (6 / 3 - 30 / 30) / math.sqrt(1.0 + tag_rank_corpus.HOT_SMOOTHING)
        self.assertAlmostEqual(expected, hot_score(6, 30))

    def test_new_tag_beats_steady_tag(self) -> None:
        self.assertGreater(hot_score(3, 0), hot_score(3, 90))

    def test_falling_tag_is_negative(self) -> None:
        self.assertLess(hot_score(1, 90), 0.0)


class TestWindows(unittest.TestCase):
    def test_day_index_rejects_garbage(self) -> None:
        self.assertIsNone(day_index(None))
        self.assertIsNone(day_index("1"))
        self.assertIsNone(day_index(float("nan")))
        self.assertEqual(20000, day_index(NOW))

    def test_window_boundaries(self) -> None:
        newest: int = 100
        recent: int = tag_rank_corpus.HOT_RECENT_DAYS
        base: int = tag_rank_corpus.HOT_BASELINE_DAYS
        self.assertEqual("recent", window_of(newest, newest))
        self.assertEqual("recent", window_of(newest - recent + 1, newest))
        self.assertEqual("baseline", window_of(newest - recent, newest))
        self.assertEqual("baseline", window_of(newest - recent - base + 1, newest))
        self.assertEqual("old", window_of(newest - recent - base, newest))
        self.assertEqual("old", window_of(None, newest))
        self.assertEqual("old", window_of(newest, None))


class TestStats(unittest.TestCase):
    def test_title_stems_match_tag_stems(self) -> None:
        builder: TagsBuilder = TagsBuilder()
        self.assertIn(builder.process_word("Launches"), title_stems(builder, "Rocket Launches!"))
        self.assertEqual(set(), title_stems(builder, None))

    def test_add_post_counts_each_tag_once_per_post(self) -> None:
        stats: CorpusStats = CorpusStats(day_index(NOW))
        stats.add_post(
            {"feed_id": "a", "unix_date": NOW, "tags": ["x", "x", ""], "content": {"title": "x"}}
        )
        rank: dict[str, float] = stats.rank_for("x")
        self.assertEqual(1, rank["feeds"])
        self.assertEqual(1.0, rank["title_ratio"])
        self.assertGreater(rank["hot"], 0.0)

    def test_unknown_tag_is_all_zero(self) -> None:
        rank: dict[str, float] = CorpusStats(None).rank_for("nope")
        self.assertEqual({k: 0 for k in tag_rank_corpus.RANK_KEYS}, rank)

    def test_post_without_content_or_date(self) -> None:
        stats: CorpusStats = CorpusStats(None)
        stats.add_post({"feed_id": "a", "tags": ["x"]})
        self.assertEqual(1, stats.rank_for("x")["feeds"])
        self.assertEqual(0.0, stats.rank_for("x")["hot"])


class TestRunErrors(unittest.TestCase):
    def test_db_error_returns_false(self) -> None:
        db: MagicMock = MagicMock()
        db.posts.find_one.side_effect = RuntimeError("boom")
        self.assertFalse(tag_rank_corpus.run(db, {}, "alice"))

    def test_derived_failure_is_retryable(self) -> None:
        db: MagicMock = MagicMock()
        stats: CorpusStats = CorpusStats(None)
        stats.add_post({"tags": ["python"]})
        db.tags.find.return_value = [{"_id": "tag-id", "tag": "python"}]
        with patch.object(tag_rank_corpus, "collect_stats", return_value=stats), patch.object(
            tag_rank_corpus, "recompute_derived", side_effect=RuntimeError("write failed")
        ):
            self.assertFalse(tag_rank_corpus.run(db, {}, "alice"))
        update: Any = db.tags.bulk_write.call_args.args[0][0]
        self.assertTrue(update._doc["$set"]["rank_pending"])


class TestRunWithDb(unittest.TestCase):
    db_helper: DBHelper
    db: Database

    def setUp(self) -> None:
        self.db_helper = DBHelper(port=TEST_MONGO_PORT)
        try:
            self.db_helper.client.admin.command("ping")
        except Exception as exc:
            self.db_helper.close()
            self.skipTest(f"MongoDB on port {TEST_MONGO_PORT} is required: {exc}")
        self.db = self.db_helper.create_test_db()
        self.owner: str = "alice"

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()

    def _post(self, pid: int, feed: str, age_days: float, tags: List[str], title: str) -> Dict[str, Any]:
        return {
            "owner": self.owner,
            "pid": pid,
            "feed_id": feed,
            "category_id": "c",
            "unix_date": NOW - age_days * DAY,
            "tags": tags or [""],
            "content": {"title": title},
            "read": False,
        }

    def _seed(self) -> None:
        posts: List[Dict[str, Any]] = [
            self._post(1, "a", 0, ["alpha", "common"], "Alpha launch"),
            self._post(2, "a", 10, ["alpha", "common"], "Weekly digest"),
            *[self._post(10 + i, "a", 11 + i, ["common"], "Digest") for i in range(4)],
            self._post(20, "b", 0, ["common", "beta"], "Something"),
            self._post(21, "b", 12, ["common"], "Something"),
            self._post(22, "b", 13, ["common"], "Something"),
            self._post(30, "c", 14, ["alpha"], "Alpha again"),
            self._post(31, "c", 200, [], "Ancient"),
        ]
        other: Dict[str, Any] = self._post(99, "z", 0, ["alpha"], "Alpha")
        other["owner"] = "bob"
        self.db.posts.insert_many(posts + [other])
        self.db.tags.insert_many(
            [
                {"owner": self.owner, "tag": t, "posts_count": n}
                for t, n in (("alpha", 3), ("common", 9), ("beta", 1), ("unseen", 0))
            ]
        )

    def _rank(self, tag: str) -> dict[str, Any]:
        doc: Any = self.db.tags.find_one({"owner": self.owner, "tag": tag})
        return doc["rank"]

    @patch.object(tag_rank_corpus, "BOILERPLATE_MIN_FEED_POSTS", 5)
    def test_run_writes_rank_fields(self) -> None:
        self._seed()
        self.assertTrue(tag_rank_corpus.run(self.db, {}, self.owner))
        alpha: dict[str, Any] = self._rank("alpha")
        self.assertEqual(2, alpha["feeds"])
        self.assertAlmostEqual(feed_entropy([2, 1]), alpha["feed_entropy"])
        self.assertAlmostEqual(2 / 6, alpha["boilerplate"])
        self.assertAlmostEqual(2 / 3, alpha["title_ratio"])
        self.assertAlmostEqual(hot_score(1, 2), alpha["hot"])
        common: dict[str, Any] = self._rank("common")
        self.assertEqual(2, common["feeds"])
        self.assertAlmostEqual(1.0, common["boilerplate"])
        self.assertAlmostEqual(hot_score(2, 7), common["hot"])

    def test_run_handles_unseen_tag_and_sets_derived(self) -> None:
        self._seed()
        self.assertTrue(tag_rank_corpus.run(self.db, {}, self.owner))
        unseen: dict[str, Any] = self._rank("unseen")
        self.assertEqual(0, unseen["feeds"])
        self.assertEqual(0.0, unseen["hot"])
        for tag in ("alpha", "common", "beta", "unseen"):
            rank: dict[str, Any] = self._rank(tag)
            self.assertIn("score", rank)
            self.assertIn("noise", rank)

    def test_other_owner_untouched(self) -> None:
        self._seed()
        self.db.tags.insert_one({"owner": "bob", "tag": "alpha", "posts_count": 1})
        tag_rank_corpus.run(self.db, {}, self.owner)
        bob: Any = self.db.tags.find_one({"owner": "bob"})
        self.assertNotIn("rank", bob)

    def test_no_posts_is_success(self) -> None:
        self.db.tags.insert_one({"owner": self.owner, "tag": "alpha", "posts_count": 1})
        self.assertTrue(tag_rank_corpus.run(self.db, {}, self.owner))
        self.assertNotIn("rank", self.db.tags.find_one({"owner": self.owner}))


if __name__ == "__main__":
    unittest.main()
