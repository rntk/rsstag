"""Tests for TASK_TAGS_EMBED_RANK: frequency-binned embedding norms."""

import math
import os
import random
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

from gensim.models.word2vec import Word2Vec
from pymongo.database import Database

from rsstag import tag_rank_embed
from rsstag.tag_rank_embed import emb_norm_zscores, load_norms
from tests.db_utils import DBHelper

TEST_MONGO_PORT: int = 8765


class TestRunFailure(unittest.TestCase):
    def test_derived_failure_is_retryable(self) -> None:
        db: MagicMock = MagicMock()
        db.tags.find.return_value = [{"_id": "tag-id", "tag": "python", "freq": 5}]
        with patch.object(tag_rank_embed, "_find_norms", return_value=({"python": 1.0}, True)), patch.object(
            tag_rank_embed, "_apply_zscores", return_value={"python": 0.5}
        ), patch.object(tag_rank_embed, "recompute_derived", side_effect=RuntimeError("write failed")):
            self.assertFalse(tag_rank_embed.run(db, {}, "alice"))
        update: Any = db.tags.bulk_write.call_args.args[0][0]
        self.assertTrue(update._doc["$set"]["rank_pending"])


class TestEmbNormZscores(unittest.TestCase):
    def test_empty_input(self) -> None:
        self.assertEqual({}, emb_norm_zscores([]))

    def test_zscore_is_computed_within_frequency_bin(self) -> None:
        entries: List[Tuple[str, int, float]] = [
            ("rare_a", 2, 1.0),
            ("rare_b", 2, 3.0),
            ("common_a", 1000, 10.0),
            ("common_b", 1000, 14.0),
        ]
        scores: Dict[str, float] = emb_norm_zscores(entries, bins=2)
        self.assertAlmostEqual(-1.0, scores["rare_a"])
        self.assertAlmostEqual(1.0, scores["rare_b"])
        self.assertAlmostEqual(-1.0, scores["common_a"])
        self.assertAlmostEqual(1.0, scores["common_b"])

    def test_high_raw_norm_of_frequent_tag_is_not_rewarded(self) -> None:
        entries: List[Tuple[str, int, float]] = [
            ("rare", 2, 1.0),
            ("rare_x", 2, 2.0),
            ("common", 1000, 50.0),
            ("common_x", 1000, 100.0),
        ]
        scores: Dict[str, float] = emb_norm_zscores(entries, bins=2)
        self.assertLess(scores["common"], scores["rare_x"])

    def test_constant_or_single_bin_member_scores_zero(self) -> None:
        scores: Dict[str, float] = emb_norm_zscores(
            [("a", 5, 2.0), ("b", 5, 2.0), ("c", 5000, 7.0), ("d", 5000, 7.0)], bins=2
        )
        self.assertEqual({"a": 0.0, "b": 0.0, "c": 0.0, "d": 0.0}, scores)
        self.assertEqual({"solo": 0.0}, emb_norm_zscores([("solo", 9, 4.0)]))

    def test_equal_frequencies_share_one_bin(self) -> None:
        entries: List[Tuple[str, int, float]] = [(f"t{i}", 3, float(i)) for i in range(10)]
        scores: Dict[str, float] = emb_norm_zscores(entries, bins=5)
        self.assertAlmostEqual(0.0, sum(scores.values()))
        self.assertAlmostEqual(1.0, sum(v * v for v in scores.values()) / 10)

    def test_non_positive_freq_does_not_break_binning(self) -> None:
        scores: Dict[str, float] = emb_norm_zscores([("a", 0, 1.0), ("b", -4, 2.0)])
        self.assertEqual({"a", "b"}, set(scores))
        self.assertTrue(all(math.isfinite(v) for v in scores.values()))


def _train_model(path: str) -> List[str]:
    """Tiny deterministic Word2Vec; returns its vocabulary."""
    rnd: random.Random = random.Random(7)
    vocab: List[str] = ["alpha", "beta", "gamma", "delta", "epsilon"]
    sentences: List[List[str]] = [
        [rnd.choice(vocab) for _ in range(6)] for _ in range(60)
    ]
    model: Word2Vec = Word2Vec(
        sentences, vector_size=8, window=2, min_count=1, workers=1, epochs=3, seed=1
    )
    model.save(path)
    return list(model.wv.key_to_index)


class TestLoadNorms(unittest.TestCase):
    def test_missing_file_returns_none(self) -> None:
        self.assertIsNone(load_norms("/nonexistent/model.w2v"))

    def test_norms_match_vectors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path: str = os.path.join(tmp, "m.w2v")
            vocab: List[str] = _train_model(path)
            norms: Optional[Dict[str, float]] = load_norms(path)
            model: Word2Vec = Word2Vec.load(path)
        self.assertIsNotNone(norms)
        assert norms is not None
        self.assertEqual(set(vocab), set(norms))
        for word in vocab:
            self.assertAlmostEqual(
                float(sum(x * x for x in model.wv[word]) ** 0.5), norms[word], places=5
            )


class MongoTestCase(unittest.TestCase):
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

    def _seed_tag(self, tag: str, freq: int) -> None:
        self.db.tags.insert_one(
            {
                "owner": self.owner,
                "tag": tag,
                "posts_count": 3,
                "freq": freq,
                "rank": {"ridf": 1.0},
            }
        )

    def _rank(self, tag: str) -> Dict[str, Any]:
        doc: Optional[Dict[str, Any]] = self.db.tags.find_one(
            {"owner": self.owner, "tag": tag}
        )
        assert doc is not None
        return doc["rank"]


class TestRunWithMongo(MongoTestCase):
    def test_run_writes_emb_norm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vocab: List[str] = _train_model(os.path.join(tmp, "u.w2v"))
            self.db.users.insert_one({"sid": self.owner, "w2v": "u.w2v"})
            for i, tag in enumerate(vocab):
                self._seed_tag(tag, 5 + i)
            self._seed_tag("missingtag", 4)
            config: Dict[str, Any] = {"settings": {"w2v_dir": tmp}}
            self.assertTrue(tag_rank_embed.run(self.db, config, self.owner))
        for tag in vocab:
            rank: Dict[str, Any] = self._rank(tag)
            self.assertIn("emb_norm", rank)
            self.assertIn("score", rank)
            self.assertAlmostEqual(1.0, rank["ridf"])
        missing: Dict[str, Any] = self._rank("missingtag")
        self.assertNotIn("emb_norm", missing)

    def test_run_without_model_skips_emb_norm(self) -> None:
        self.db.users.insert_one({"sid": self.owner, "w2v": "absent.w2v"})
        self._seed_tag("house", 5)
        with tempfile.TemporaryDirectory() as tmp:
            config: Dict[str, Any] = {"settings": {"w2v_dir": tmp}}
            self.assertTrue(tag_rank_embed.run(self.db, config, self.owner))
        rank: Dict[str, Any] = self._rank("house")
        self.assertNotIn("emb_norm", rank)
        self.assertIn("score", rank)

    def test_run_with_corrupt_model_returns_false(self) -> None:
        self.db.users.insert_one({"sid": self.owner, "w2v": "bad.w2v"})
        self._seed_tag("house", 5)
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "bad.w2v"), "wb") as handle:
                handle.write(b"not a model")
            config: Dict[str, Any] = {"settings": {"w2v_dir": tmp}}
            self.assertFalse(tag_rank_embed.run(self.db, config, self.owner))
        self.assertNotIn("emb_norm", self._rank("house"))

    def test_run_without_tags_is_ok(self) -> None:
        config: Dict[str, Any] = {"settings": {"w2v_dir": "/nonexistent"}}
        self.assertTrue(tag_rank_embed.run(self.db, config, self.owner))


if __name__ == "__main__":
    unittest.main()
