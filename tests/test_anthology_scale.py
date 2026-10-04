"""Large inputs are processed completely: bucketed clustering, unbounded merges, judge accounting."""

import time
import unittest
from typing import Any, Dict, List, Set
from unittest.mock import MagicMock, patch

import numpy as np
from scipy import sparse

from rsstag.anthology import candidates
from rsstag.anthology.candidates import (
    Cluster,
    Vectors,
    bucket_rows,
    build_candidates,
    cluster_rows,
    contrastive_keywords,
    make_cluster,
    merge_pairs,
    nearest_clusters,
    threshold_rows,
    vectorize,
)
from rsstag.anthology.judge import Judge, JudgeUnavailableError
from rsstag.anthology.pipeline import AnthologyPipeline
from rsstag.anthology.result import coverage_problems
from rsstag.anthology.stages import Theme
from rsstag.anthology.units import Snippet, UnitsResult
from tests.anthology_fakes import FakeDB, FakeRouter, synthetic_texts
from tests.test_anthology_pipeline import assert_result_schema


def _unit_rows(n_rows: int, dims: int = 12, seed: int = 0) -> np.ndarray:
    rng: np.random.Generator = np.random.default_rng(seed)
    centers: np.ndarray = rng.normal(size=(8, dims))
    rows: np.ndarray = centers[rng.integers(0, 8, n_rows)] + rng.normal(scale=0.3, size=(n_rows, dims))
    return rows / np.linalg.norm(rows, axis=1, keepdims=True)


def _snippets(texts: List[str]) -> List[Snippet]:
    return [
        Snippet(
            id=f"s{i}", post_id=str(i), sentence_indices=[0], topic_path="Topic > Details",
            title=f"Post {i}", feed_id="feed", date=1_700_000_000.0 + i, text=text,
        )
        for i, text in enumerate(texts)
    ]


class TestBucketedClustering(unittest.TestCase):
    def test_bucket_rows_keeps_every_row_once_within_limit(self) -> None:
        dense: np.ndarray = _unit_rows(5000)
        buckets: List[np.ndarray] = bucket_rows(dense, max_rows=700)
        self.assertTrue(all(len(rows) <= 700 for rows in buckets))
        self.assertEqual(sorted(np.concatenate(buckets).tolist()), list(range(5000)))

    def test_identical_rows_fall_back_to_chunks(self) -> None:
        dense: np.ndarray = np.ones((50, 3)) / np.sqrt(3)
        buckets: List[np.ndarray] = bucket_rows(dense, max_rows=20)
        self.assertTrue(all(len(rows) <= 20 for rows in buckets))
        self.assertEqual(sorted(np.concatenate(buckets).tolist()), list(range(50)))

    def test_small_inputs_use_a_single_bucket(self) -> None:
        dense: np.ndarray = _unit_rows(300)
        self.assertEqual(len(bucket_rows(dense)), 1)

    def test_cluster_labels_are_unique_across_buckets(self) -> None:
        dense: np.ndarray = _unit_rows(900)
        with patch.object(candidates, "MAX_BUCKET_ROWS", 200):
            labels: np.ndarray = cluster_rows(dense, 90)
            loose: np.ndarray = threshold_rows(dense, 0.8)
        buckets: List[np.ndarray] = bucket_rows(dense, max_rows=200)
        for first in range(len(buckets)):
            for second in range(first + 1, len(buckets)):
                self.assertFalse(set(labels[buckets[first]]) & set(labels[buckets[second]]))
                self.assertFalse(set(loose[buckets[first]]) & set(loose[buckets[second]]))
        self.assertGreater(len(set(labels.tolist())), 45)

    def test_twenty_thousand_snippets_are_all_clustered(self) -> None:
        texts: List[str] = synthetic_texts(per_topic=6700, words=8)[0]
        started: float = time.time()
        vectors: Vectors = vectorize(texts)
        clusters, unsorted = build_candidates(vectors)
        elapsed: float = time.time() - started
        rows: List[int] = [row for cluster in clusters for row in cluster.members] + unsorted
        self.assertEqual(sorted(rows), list(range(len(texts))))
        self.assertGreater(len(clusters), 60)
        self.assertLess(elapsed, 240)


class TestUnboundedMergesAndNeighbors(unittest.TestCase):
    def _clusters(self, count: int) -> List[Cluster]:
        dense: np.ndarray = _unit_rows(count * 3, seed=3)
        vectors: Vectors = Vectors(sparse.csr_matrix(dense), np.array([str(i) for i in range(12)]), dense)
        return [make_cluster(f"c{i}", [3 * i, 3 * i + 1, 3 * i + 2], vectors) for i in range(count)]

    def test_nearest_clusters_matches_brute_force(self) -> None:
        clusters: List[Cluster] = self._clusters(60)
        with patch.object(candidates, "NEIGHBOR_BLOCK_ROWS", 7):
            nearest = nearest_clusters(clusters, 2)
        matrix: np.ndarray = np.vstack([c.centroid for c in clusters])
        sims: np.ndarray = matrix @ matrix.T
        np.fill_diagonal(sims, -np.inf)
        for index, neighbors in enumerate(nearest):
            self.assertEqual(neighbors[0][1], int(np.argmax(sims[index])))
            self.assertEqual(len(neighbors), 2)

    def test_merge_pairs_have_no_global_cap(self) -> None:
        pairs = merge_pairs(self._clusters(120), 0.35, 3)
        self.assertGreater(len(pairs), 30)
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertTrue(all(i < j for i, j in pairs))


class TestKeywords(unittest.TestCase):
    def test_contrastive_keywords_match_mask_formula(self) -> None:
        texts: List[str] = synthetic_texts(per_topic=12)[0]
        vectors: Vectors = vectorize(texts)
        rows: List[int] = list(range(0, 12)) + [20]
        mask: np.ndarray = np.zeros(len(texts), dtype=bool)
        mask[rows] = True
        scores: np.ndarray = (
            np.asarray(vectors.tfidf[mask].mean(axis=0)).ravel()
            - np.asarray(vectors.tfidf[~mask].mean(axis=0)).ravel()
        )
        top: np.ndarray = np.argsort(-scores, kind="stable")[:8]
        expected: List[str] = [str(vectors.features[i]) for i in top if scores[i] > 0]
        self.assertEqual(contrastive_keywords(vectors, rows), expected)
        inside: np.ndarray = np.asarray(vectors.tfidf.mean(axis=0)).ravel()
        everything: List[str] = [
            str(vectors.features[i]) for i in np.argsort(-inside, kind="stable")[:8] if inside[i] > 0
        ]
        self.assertEqual(contrastive_keywords(vectors, list(range(len(texts)))), everything)


class Flaky:
    def __init__(self, failures: int, answer: str = "ok") -> None:
        self.failures: int = failures
        self.answer: str = answer
        self.calls: int = 0

    def call(self, *args: Any, **kwargs: Any) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("temporary outage")
        return self.answer


class TestJudgeReliability(unittest.TestCase):
    def test_retries_recover_transient_failures(self) -> None:
        router: Flaky = Flaky(failures=2)
        judge: Judge = Judge(FakeDB(), router, "owner", retry_delays=(0.0, 0.0))
        self.assertEqual(judge.ask("p"), "ok")
        self.assertEqual((judge.calls, judge.retries, judge.failures, router.calls), (1, 2, 0, 3))

    def test_exhausted_retries_count_one_failure(self) -> None:
        judge: Judge = Judge(FakeDB(), Flaky(failures=10), "owner", retry_delays=(0.0,))
        self.assertEqual(judge.ask("p"), "")
        self.assertEqual((judge.calls, judge.retries, judge.failures), (1, 1, 1))
        with self.assertRaises(JudgeUnavailableError):
            judge.ensure_available()

    def test_unusable_answers_leave_the_cache(self) -> None:
        db: FakeDB = FakeDB()
        judge: Judge = Judge(db, Flaky(failures=0, answer="garbage"), "owner", retry_delays=())
        judge.ask("p")
        judge.record("p", 3, 0)
        judge.ask("p")
        self.assertEqual((judge.calls, judge.cached), (2, 0))

    def test_incomplete_answers_leave_the_cache_but_complete_ones_stay(self) -> None:
        db: FakeDB = FakeDB()
        judge: Judge = Judge(db, Flaky(failures=0, answer="partial"), "owner", retry_delays=())
        judge.ask("partial")
        judge.record("partial", 3, 2)
        judge.ask("complete")
        judge.record("complete", 3, 3)
        judge.ask("partial")
        judge.ask("complete")
        self.assertEqual((judge.calls, judge.cached), (3, 1))

    def test_too_many_missing_judgments_fail_the_run(self) -> None:
        judge: Judge = Judge(FakeDB(), FakeRouter(), "owner", retry_delays=())
        judge.ask("TASK: MERGE\nPair 1\nx")
        judge.record("TASK: MERGE\nPair 1\nx", 10, 9)
        judge.ensure_available()
        judge.record("TASK: MERGE\nPair 1\nx", 10, 6)
        with self.assertRaises(JudgeUnavailableError):
            judge.ensure_available()


class TestCoverageInvariant(unittest.TestCase):
    def test_duplicates_and_unknown_rows_are_reported(self) -> None:
        centroid: np.ndarray = np.ones(2)
        themes: List[Theme] = [
            Theme(clusters=[Cluster("a", [0, 1], centroid), Cluster("b", [1, 9], centroid)])
        ]
        problems: List[str] = coverage_problems(5, themes)
        self.assertEqual(len(problems), 2)
        self.assertEqual(coverage_problems(5, [Theme(clusters=[Cluster("a", [0, 1], centroid)])]), [])


class TestPipelineAtScale(unittest.TestCase):
    def test_pipeline_places_every_snippet_beyond_old_cap(self) -> None:
        snippets: List[Snippet] = _snippets(synthetic_texts(per_topic=1400, words=8)[0])
        store: MagicMock = MagicMock()
        store.get_by_id.return_value = {"_id": "a1", "seed_value": "news", "scope": {"mode": "all"}}
        store.save_result.return_value = True
        store.claim_run.return_value = "test-run"
        store.heartbeat.return_value = True
        router: FakeRouter = FakeRouter()
        pipeline: AnthologyPipeline = AnthologyPipeline(FakeDB(), router, "owner")
        pipeline._store = store
        units: UnitsResult = UnitsResult(snippets=snippets, posts_in_scope=len(snippets))
        with patch("rsstag.anthology.pipeline.load_units", return_value=units):
            self.assertTrue(pipeline.run("a1"), store.update_status.call_args)
        result: Dict[str, Any] = store.save_result.call_args[0][1]
        assert_result_schema(self, result)
        placed: Set[str] = set(result["unsorted"])
        for cluster in result["clusters"].values():
            self.assertFalse(placed & set(cluster["snippet_ids"]))
            placed |= set(cluster["snippet_ids"])
        self.assertEqual(placed, {s.id for s in snippets})
        self.assertEqual(result["metrics"]["snippets_total"], 4200)
        self.assertEqual(result["metrics"]["judgments_missing"], 0)


if __name__ == "__main__":
    unittest.main()
