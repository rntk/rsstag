"""Tests for the TASK_TAGS_COOC_RANK handler: pure helpers and a Mongo run."""

import math
import random
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
from scipy import sparse

from rsstag import tag_rank, tag_rank_cooc
from rsstag.tag_rank_cooc import (
    CoocAccumulator,
    compute_scores,
    entropy_scores,
    normalized_entropy,
    post_ids,
    post_pairs,
)
from tests.db_utils import DBHelper

TEST_MONGO_PORT: int = 8765


class TestNormalizedEntropy(unittest.TestCase):
    def test_popularity_proportional_counts_are_uniform(self) -> None:
        df: np.ndarray = np.array([100.0, 50.0, 10.0, 5.0])
        self.assertAlmostEqual(1.0, normalized_entropy(df * 0.3, df, 4))

    def test_single_context_is_zero(self) -> None:
        df: np.ndarray = np.array([10.0, 10.0, 10.0])
        self.assertEqual(0.0, normalized_entropy(np.array([5.0, 0.0, 0.0]), df, 3))

    def test_degenerate_input(self) -> None:
        df: np.ndarray = np.array([10.0, 10.0])
        self.assertEqual(0.0, normalized_entropy(np.zeros(2), df, 2))
        self.assertEqual(0.0, normalized_entropy(np.ones(2), df, 1))

    def test_result_is_bounded(self) -> None:
        df: np.ndarray = np.array([3.0, 7.0, 11.0, 2.0, 9.0])
        value: float = normalized_entropy(np.array([1.0, 4.0, 0.0, 2.0, 8.0]), df, 5)
        self.assertTrue(0.0 < value < 1.0)

    def test_popular_context_does_not_make_tag_generic(self) -> None:
        df: np.ndarray = np.array([1000.0, 10.0, 10.0, 10.0])
        raw: np.ndarray = np.array([100.0, 1.0, 1.0, 1.0])
        self.assertGreater(normalized_entropy(raw, df, 4), 0.95)
        peaked: np.ndarray = np.array([1.0, 10.0, 0.0, 0.0])
        self.assertLess(normalized_entropy(peaked, df, 4), 0.5)


class TestPairs(unittest.TestCase):
    def test_post_ids_dedupes_sorts_and_caps(self) -> None:
        index: Dict[str, int] = {"a": 0, "b": 1, "c": 2, "d": 3}
        ids: np.ndarray = post_ids(["d", "b", "b", "zzz", "a"], index, 2)
        self.assertEqual([0, 1], ids.tolist())
        self.assertEqual(0, len(post_ids([""], index, 5)))
        self.assertEqual(0, len(post_ids(None, index, 5)))

    def test_post_pairs_skip_self_and_non_contexts(self) -> None:
        rows, cols = post_pairs(np.array([0, 1, 5], dtype=np.int32), 2)
        pairs = sorted(zip(rows.tolist(), cols.tolist()))
        self.assertEqual([(0, 1), (1, 0), (5, 0), (5, 1)], pairs)

    def test_accumulator_flushes_and_sums(self) -> None:
        acc: CoocAccumulator = CoocAccumulator(3, 3, flush_pairs=2)
        for _ in range(3):
            acc.add_post(np.array([0, 1], dtype=np.int32))
        matrix: sparse.csr_matrix = acc.result()
        self.assertEqual(3.0, matrix[0, 1])
        self.assertEqual(3.0, matrix[1, 0])
        self.assertEqual(0.0, matrix[0, 0])


def _synthetic_posts() -> List[List[str]]:
    rng: random.Random = random.Random(7)
    posts: List[List[str]] = []
    for i in range(1500):
        topic: int = i % 10
        tags: List[str] = [f"t{topic}_{rng.randrange(8)}" for _ in range(4)]
        tags += [f"g{rng.randrange(5)}" for _ in range(3)]
        posts.append(tags)
    return posts


def _vocab(posts: List[List[str]]) -> Any:
    df: Dict[str, int] = {}
    for tags in posts:
        for tag in set(tags):
            df[tag] = df.get(tag, 0) + 1
    names: List[str] = sorted(df, key=lambda name: (-df[name], name))
    return names, np.array([df[name] for name in names], dtype=np.float64)


class TestScores(unittest.TestCase):
    def test_generic_tags_score_above_specific(self) -> None:
        posts: List[List[str]] = _synthetic_posts()
        names, counts = _vocab(posts)
        scores: Dict[str, float] = compute_scores(posts, names, counts)
        generic: List[float] = [v for k, v in scores.items() if k.startswith("g")]
        specific: List[float] = [v for k, v in scores.items() if k.startswith("t")]
        self.assertTrue(generic and specific)
        self.assertGreater(min(generic), 0.9)
        self.assertLess(max(specific), 0.5)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in scores.values()))

    def test_min_pairs_leaves_rare_tags_unscored(self) -> None:
        matrix: sparse.csr_matrix = sparse.csr_matrix(
            np.array([[1.0, 1.0, 0.0], [5.0, 5.0, 5.0]], dtype=np.float32)
        )
        scores: Dict[int, float] = entropy_scores(matrix, np.ones(3), 10)
        self.assertEqual([1], list(scores))
        self.assertAlmostEqual(1.0, scores[1])

    def test_tiny_vocab_yields_no_scores(self) -> None:
        self.assertEqual({}, compute_scores([["a"]], ["a"], np.array([5.0])))

    def test_noise_threshold_constant_is_sane(self) -> None:
        self.assertTrue(0.0 < tag_rank.MAX_COOC_ENTROPY < 1.0)
        self.assertTrue(math.isfinite(tag_rank_cooc.COOC_FLUSH_PAIRS))


class TestRunFailure(unittest.TestCase):
    def test_db_error_returns_false(self) -> None:
        db: MagicMock = MagicMock()
        db.tags.find.side_effect = RuntimeError("boom")
        self.assertFalse(tag_rank_cooc.run(db, {}, "alice"))

    def test_derived_failure_is_retryable(self) -> None:
        db: MagicMock = MagicMock()
        with patch.object(tag_rank_cooc, "load_vocab", return_value=([], np.array([]))), patch.object(
            tag_rank_cooc, "compute_scores", return_value={"python": 0.5}
        ), patch.object(tag_rank, "recompute_derived", side_effect=RuntimeError("write failed")):
            self.assertFalse(tag_rank_cooc.run(db, {}, "alice"))
        update: Any = db.tags.bulk_write.call_args.args[0][0]
        self.assertTrue(update._doc["$set"]["rank_pending"])


class TestRunWithMongo(unittest.TestCase):
    def setUp(self) -> None:
        self.db_helper: DBHelper = DBHelper(port=TEST_MONGO_PORT)
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

    def test_run_writes_entropy_and_derived_rank(self) -> None:
        posts: List[List[str]] = _synthetic_posts()
        names, counts = _vocab(posts)
        self.db.posts.insert_many([{"owner": self.owner, "tags": t} for t in posts])
        self.db.posts.insert_one({"owner": "bob", "tags": ["g0", "g1"]})
        self.db.tags.insert_many(
            [
                {"owner": self.owner, "tag": n, "posts_count": int(c), "rank": {}}
                for n, c in zip(names, counts)
            ]
        )
        self.db.tags.insert_one({"owner": self.owner, "tag": "rare", "posts_count": 1})

        self.assertTrue(tag_rank_cooc.run(self.db, {}, self.owner))

        generic = self.db.tags.find_one({"owner": self.owner, "tag": "g0"})
        specific = self.db.tags.find_one({"owner": self.owner, "tag": "t0_0"})
        rare = self.db.tags.find_one({"owner": self.owner, "tag": "rare"})
        self.assertGreater(generic["rank"]["cooc_entropy"], specific["rank"]["cooc_entropy"])
        self.assertIn("score", generic["rank"])
        self.assertNotIn("cooc_entropy", rare.get("rank", {}))

    def test_run_without_data_is_ok(self) -> None:
        self.assertTrue(tag_rank_cooc.run(self.db, {}, self.owner))


if __name__ == "__main__":
    unittest.main()
