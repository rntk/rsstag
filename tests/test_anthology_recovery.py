"""Recovery pass tests use a deterministic fake judge, never a live LLM."""

import copy
import json
import re
import unittest
from typing import Callable, Dict, List, Set
from unittest.mock import MagicMock, patch

import numpy as np

from rsstag.anthology import recovery, stages
from rsstag.anthology.candidates import Cluster, Vectors, build_candidates, centroid_of, make_cluster, vectorize
from rsstag.anthology.judge import Judge, JudgeUnavailableError
from rsstag.anthology.pipeline import AnthologyPipeline
from rsstag.anthology.result import RunCounters, build_result
from rsstag.anthology.stages import Theme
from rsstag.anthology.units import Snippet, UnitsResult
from tests.anthology_fakes import FakeDB, FakeRouter, TOPIC_WORDS, synthetic_snippets


class TestAnthologyRecovery(unittest.TestCase):
    def setUp(self) -> None:
        self.snippets: List[Snippet]
        self.truth: List[str]
        self.snippets, self.truth = synthetic_snippets(per_topic=12)
        self.vectors: Vectors = vectorize([snippet.vector_text for snippet in self.snippets])
        self.router: FakeRouter = FakeRouter(merge_answer="different")
        self.judge: Judge = Judge(FakeDB(), self.router, "owner")

    def _initial(self) -> List[Cluster]:
        # Model one accepted first-pass cluster. The other 34 snippets are the
        # singleton/rejected pool passed to recovery.
        return [make_cluster("c0", [0, 1], self.vectors)]

    def test_recovery_refines_leftovers_and_preserves_global_membership(self) -> None:
        initial: List[Cluster] = self._initial()
        before: Cluster = copy.deepcopy(initial[0])
        accepted_before: Set[int] = {row for cluster in initial for row in cluster.members}
        coverage_before: float = len(accepted_before) / len(self.snippets)
        counters: RunCounters = RunCounters()

        result: List[Cluster] = recovery.recover_unsorted(
            initial, self.vectors, self.snippets, self.judge, "space", counters
        )

        members: List[int] = [row for cluster in result for row in cluster.members]
        coverage_after: float = len(set(members)) / len(self.snippets)
        purity: float = sum(
            max(sum(self.truth[row] == topic for row in cluster.members) for topic in set(self.truth))
            for cluster in result
        ) / len(members)
        self.assertIs(result[0], initial[0])
        self.assertEqual(initial[0].members, before.members)
        self.assertEqual(initial[0].centroid.tolist(), before.centroid.tolist())
        self.assertEqual(len(members), len(set(members)), "recovery duplicated snippet rows")
        self.assertEqual(set(members) & accepted_before, accepted_before)
        self.assertTrue(all(0 <= row < len(self.snippets) for row in members))
        self.assertGreater(coverage_after, coverage_before)
        self.assertGreaterEqual(purity, 0.9)
        self.assertTrue(all(cluster.id.startswith("r") for cluster in result[1:]))
        self.assertTrue(all(cluster.centroid.shape == self.vectors.dense.shape[1:] for cluster in result))
        self.assertEqual(counters.recovery_snippets_input, 34)
        self.assertEqual(counters.recovery_snippets_assigned, len(members) - 2)
        self.assertEqual(counters.recovery_clusters_final, len(result) - 1)

    def test_finer_recovery_improves_coverage_and_cluster_purity(self) -> None:
        leftover_snippets, truth = synthetic_snippets(per_topic=4)
        interleaved: List[Snippet] = [
            self.snippets[0], *leftover_snippets[:6], self.snippets[12], *leftover_snippets[6:]
        ]
        # Correct the synthetic IDs so the output serialization also proves all
        # rows map back to their original positions.
        for row, snippet in enumerate(interleaved):
            snippet.id = f"x{row}"
        accepted_rows: List[int] = [0, 7]
        accepted_cluster: Cluster = make_cluster("c0", accepted_rows, vectorize([s.vector_text for s in interleaved]))
        leftovers: List[int] = [row for row in range(len(interleaved)) if row not in set(accepted_rows)]
        local_texts: List[str] = [interleaved[row].vector_text for row in leftovers]
        first_pass_vectors = vectorize(local_texts, min_df=1)
        coarse, _ = build_candidates(first_pass_vectors, n_clusters=2)
        coarse_purity: float = self._purity(coarse, {i: truth[i] for i in range(12)})
        full_vectors = vectorize([snippet.vector_text for snippet in interleaved])
        counters: RunCounters = RunCounters()

        with patch.object(recovery, "vectorize", wraps=vectorize) as vectorizer_spy:
            recovered: List[Cluster] = recovery.recover_unsorted(
                [accepted_cluster], full_vectors, interleaved,
                Judge(FakeDB(), FakeRouter(merge_answer="different"), "owner"), "seed", counters,
            )
        vectorizer_spy.assert_called_once()
        self.assertEqual(vectorizer_spy.call_args.kwargs["min_df"], 1)
        recovered_only: List[Cluster] = recovered[1:]
        recovered_truth: Dict[int, str] = {row: truth[index] for index, row in enumerate(leftovers)}
        recovered_purity: float = self._purity(recovered_only, recovered_truth)
        baseline_coverage: float = len(accepted_rows) / len(interleaved)
        after_coverage: float = len({row for cluster in recovered for row in cluster.members}) / len(interleaved)
        result = build_result(interleaved, [Theme(clusters=recovered)], counters)

        self.assertEqual(coarse_purity, 2 / 3)
        self.assertEqual(recovered_purity, 1.0)
        self.assertEqual(baseline_coverage, 2 / 14)
        self.assertEqual(after_coverage, 1.0)
        self.assertEqual(len(result["unsorted"]) + sum(c.size for c in recovered), len(interleaved))
        self.assertEqual(counters.recovery_snippets_input, 12)
        self.assertEqual(counters.recovery_snippets_assigned, 12)

    def test_pipeline_repairs_groups_rejected_by_first_pass_label(self) -> None:
        snippets: List[Snippet]
        snippets, _truth = synthetic_snippets(per_topic=4)

        class TopicAwareRouter(FakeRouter):
            def call(self, settings: object, user_msgs: List[str], **kwargs: object) -> str:
                prompt: str = user_msgs[0]
                if prompt.startswith("TASK: LABEL"):
                    self.prompts.append(prompt)
                    blocks = re.split(r"(?m)^Cluster \d+\s*$", prompt)[1:]
                    judgments: List[str] = []
                    for number, block in enumerate(blocks, start=1):
                        words: Set[str] = set(re.findall(r"[a-z]+", block.lower()))
                        present: List[str] = [
                            topic for topic, vocabulary in TOPIC_WORDS.items()
                            if words.intersection(vocabulary)
                        ]
                        score: int = 4 if len(present) == 1 else 2
                        judgments.append(json.dumps({"id": number, "score": score, "label": present[0] if present else "mixed", "kind": "event"}))
                    return "```json\n" + "\n".join(judgments) + "\n```"
                return super().call(settings, user_msgs, **kwargs)

        db: FakeDB = FakeDB()
        pipeline: AnthologyPipeline = AnthologyPipeline(db, TopicAwareRouter(merge_answer="different"), "owner")
        store: MagicMock = MagicMock()
        store.get_by_id.return_value = {"_id": "a1", "seed_value": "news", "scope": None}
        store.save_result.return_value = True
        store.claim_run.return_value = "test-run"
        store.heartbeat.return_value = True
        pipeline._store = store
        units: UnitsResult = UnitsResult(snippets=snippets, posts_in_scope=12)
        with patch("rsstag.anthology.pipeline.load_units", return_value=units):
            self.assertTrue(pipeline.run("a1"))

        result: Dict[str, object] = store.save_result.call_args[0][1]
        metrics: Dict[str, object] = result["metrics"]
        assigned_ids: Set[str] = {
            snippet_id for cluster in result["clusters"].values() for snippet_id in cluster["snippet_ids"]
        }
        self.assertEqual(len(assigned_ids), 12)
        self.assertEqual(result["unsorted"], [])
        self.assertEqual(metrics["first_pass_unsorted"]["label_rejected"], 8)
        self.assertEqual(metrics["repair_snippets_assigned"], 8)
        self.assertEqual(metrics["repair_clusters_final"], 2)
        self.assertEqual(metrics["recovery_snippets_input"], 0)
        self.assertEqual(metrics["recovery_snippets_assigned"], 0)
        self.assertEqual(metrics["coverage"], 1.0)

    def test_recovered_themes_stay_separate_from_first_pass_theme_groups(self) -> None:
        snippets: List[Snippet]
        snippets, _truth = synthetic_snippets(per_topic=12)
        vectors: Vectors = vectorize([snippet.vector_text for snippet in snippets])
        initial: List[Cluster] = [
            make_cluster(f"c{index}", list(range(index * 4, (index + 1) * 4)), vectors)
            for index in range(7)
        ]
        expected_accepted_groups: List[tuple] = sorted(
            tuple(sorted(cluster.id for cluster in theme.clusters))
            for theme in stages.group_into_themes(initial, vectors)
        )
        router: FakeRouter = FakeRouter(merge_answer="different")
        pipeline: AnthologyPipeline = AnthologyPipeline(FakeDB(), router, "owner")
        store: MagicMock = MagicMock()
        store.get_by_id.return_value = {"_id": "a1", "seed_value": "news", "scope": None}
        store.save_result.return_value = True
        store.claim_run.return_value = "test-run"
        store.heartbeat.return_value = True
        pipeline._store = store
        units: UnitsResult = UnitsResult(snippets=snippets, posts_in_scope=len(snippets))

        with patch("rsstag.anthology.pipeline.load_units", return_value=units), patch(
            "rsstag.anthology.pipeline.build_candidates", return_value=(initial, [])
        ):
            self.assertTrue(pipeline.run("a1"))

        result: Dict[str, object] = store.save_result.call_args[0][1]
        themes: List[Dict[str, object]] = result["themes"]
        accepted_groups: List[tuple] = sorted(
            tuple(sorted(cid for cid in theme["cluster_ids"] if cid.startswith("c")))
            for theme in themes if any(cid.startswith("c") for cid in theme["cluster_ids"])
        )
        recovered_themes: List[Dict[str, object]] = [
            theme for theme in themes if any(cid.startswith("r") for cid in theme["cluster_ids"])
        ]

        self.assertEqual(accepted_groups, expected_accepted_groups)
        self.assertTrue(recovered_themes)
        self.assertTrue(all(len(theme["cluster_ids"]) == 1 for theme in recovered_themes))
        for theme in recovered_themes:
            cluster_id: str = theme["cluster_ids"][0]
            self.assertEqual(theme["label"], result["clusters"][cluster_id]["label"])
            self.assertEqual(theme["keywords"], result["clusters"][cluster_id]["keywords"])

    @staticmethod
    def _purity(clusters: List[Cluster], truth: Dict[int, str]) -> float:
        rows: List[int] = [row for cluster in clusters for row in cluster.members]
        return sum(
            max(sum(truth[row] == topic for row in cluster.members) for topic in set(truth.values()))
            for cluster in clusters
        ) / len(rows)

    def test_low_label_score_rejects_recovery_candidates(self) -> None:
        judge: Judge = Judge(FakeDB(), FakeRouter(merge_answer="different", label_score=2), "owner")
        counters: RunCounters = RunCounters()

        result: List[Cluster] = recovery.recover_unsorted(
            self._initial(), self.vectors, self.snippets, judge, "space", counters
        )

        self.assertEqual([cluster.id for cluster in result], ["c0"])
        self.assertGreater(counters.recovery_clusters_candidate, 0)
        self.assertLess(counters.recovery_clusters_final, counters.recovery_clusters_candidate)
        self.assertEqual(counters.recovery_snippets_assigned, 0)
        self.assertGreater(counters.clusters_dissolved, 0)

    def test_intruder_failure_rejects_weak_recovery_cluster(self) -> None:
        class WrongIntruder(FakeRouter):
            def call(self, settings: object, user_msgs: List[str], **kwargs: object) -> str:
                prompt: str = user_msgs[0]
                if prompt.startswith("TASK: INTRUDER"):
                    count: int = prompt.count("\nSet ")
                    self.prompts.append(prompt)
                    return "\n".join(f"{n}: 1" for n in range(1, count + 1))
                return super().call(settings, user_msgs, **kwargs)

        wrong: WrongIntruder = WrongIntruder(merge_answer="different", label_score=3)
        judge: Judge = Judge(FakeDB(), wrong, "owner")
        counters: RunCounters = RunCounters()
        original_build: Callable[[List[Cluster]], List[stages.IntruderSet]] = stages.build_intruder_sets

        def wrong_position(clusters: List[Cluster]) -> List[stages.IntruderSet]:
            sets: List[stages.IntruderSet] = original_build(clusters)
            for item in sets:
                item.answer_position = 2
            return sets

        with patch.object(stages, "build_intruder_sets", side_effect=wrong_position):
            result: List[Cluster] = recovery.recover_unsorted(
                self._initial(), self.vectors, self.snippets, judge, "space", counters
            )

        self.assertGreater(len(result), 1)  # small candidates remain below intruder-check size
        self.assertGreater(counters.recovery_clusters_candidate, 0)
        self.assertLess(counters.recovery_clusters_final, counters.recovery_clusters_candidate)
        self.assertGreater(counters.clusters_dissolved, 0)
        self.assertIsNotNone(counters.recovery_intruder_accuracy)
        self.assertLess(counters.recovery_intruder_accuracy or 0.0, 1.0)

    def test_zero_or_one_leftover_skips_recovery_calls(self) -> None:
        for members in ([list(range(len(self.snippets)))], [list(range(len(self.snippets) - 1))]):
            with self.subTest(leftovers=len(self.snippets) - len(members[0])):
                initial: List[Cluster] = [make_cluster("c0", members[0], self.vectors)]
                calls_before: int = self.judge.calls
                counters: RunCounters = RunCounters()
                result: List[Cluster] = recovery.recover_unsorted(
                    initial, self.vectors, self.snippets, self.judge, "space", counters
                )
                self.assertEqual(result, initial)
                self.assertEqual(self.judge.calls, calls_before)
                self.assertEqual(counters.recovery_snippets_input, len(self.snippets) - len(members[0]))
                self.assertEqual(counters.recovery_clusters_candidate, 0)

    def test_repeat_run_uses_judgment_cache_and_is_deterministic(self) -> None:
        first_counters: RunCounters = RunCounters()
        first: List[Cluster] = recovery.recover_unsorted(
            self._initial(), self.vectors, self.snippets, self.judge, "space", first_counters
        )
        actual_calls: int = self.judge.calls
        prompts_count: int = len(self.router.prompts)
        second_counters: RunCounters = RunCounters()
        second: List[Cluster] = recovery.recover_unsorted(
            self._initial(), self.vectors, self.snippets, self.judge, "space", second_counters
        )

        self.assertEqual([cluster.members for cluster in first], [cluster.members for cluster in second])
        self.assertEqual([cluster.id for cluster in first], [cluster.id for cluster in second])
        self.assertEqual(self.judge.calls, actual_calls)
        self.assertGreater(self.judge.cached, 0)
        self.assertEqual(len(self.router.prompts), prompts_count)
        self.assertEqual(second_counters.recovery_llm_calls, 0)

    def test_finer_cluster_count_has_no_sixty_cluster_cap(self) -> None:
        self.assertEqual(recovery.recovery_cluster_count(34), 9)
        self.assertEqual(recovery.recovery_cluster_count(300), 75)

    def test_recovery_preserves_local_judgment_metadata_and_member_order(self) -> None:
        initial: List[Cluster] = self._initial()
        remaining: List[int] = list(range(2, len(self.snippets)))
        local_vectors: Vectors = vectorize([self.snippets[row].vector_text for row in remaining], min_df=1)
        local: Cluster = Cluster(
            id="c9", members=[2, 0], centroid=np.ones(local_vectors.dense.shape[1]),
            keywords=["local", "keywords"], cohesion=0.1234, label="Local subject",
            kind="analysis", score=5, intruder_ok=True,
        )
        counters: RunCounters = RunCounters()

        with patch.object(recovery, "_validate", return_value=[local]):
            result: List[Cluster] = recovery.recover_unsorted(
                initial, self.vectors, self.snippets, self.judge, "seed", counters
            )

        mapped: Cluster = result[1]
        self.assertEqual(mapped.id, "r9")
        self.assertEqual(mapped.members, [4, 2])
        self.assertEqual(mapped.keywords, ["local", "keywords"])
        self.assertEqual(mapped.cohesion, 0.1234)
        self.assertEqual((mapped.label, mapped.kind, mapped.score, mapped.intruder_ok),
                         ("Local subject", "analysis", 5, True))
        np.testing.assert_allclose(mapped.centroid, centroid_of(self.vectors.dense, [4, 2]))

    def test_tiny_pool_keeps_a_coherent_pair_and_leaves_unrelated_singleton(self) -> None:
        snippets: List[Snippet] = [self.snippets[0], self.snippets[1], self.snippets[12]]
        vectors: Vectors = vectorize([snippet.vector_text for snippet in snippets], min_df=1)
        counters: RunCounters = RunCounters()

        result: List[Cluster] = recovery.recover_unsorted(
            [], vectors, snippets, Judge(FakeDB(), FakeRouter(), "owner"), "seed", counters
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].size, 2)
        self.assertEqual(set(result[0].members), {0, 1})
        self.assertEqual(counters.recovery_snippets_input, 3)
        self.assertEqual(counters.recovery_snippets_assigned, 2)

    def test_cached_first_pass_judgment_does_not_bless_recovery_outage(self) -> None:
        db: FakeDB = FakeDB()
        cached_judge: Judge = Judge(db, FakeRouter(), "owner")
        cached_prompt: str = "TASK: MERGE\nPair 1\nx"
        cached_judge.ask(cached_prompt)

        class Outage:
            def call(self, *args: object, **kwargs: object) -> str:
                raise RuntimeError("judge unavailable")

        judge: Judge = Judge(db, Outage(), "owner", retry_delays=())
        self.assertEqual(judge.ask(cached_prompt), cached_judge.ask(cached_prompt))
        counters: RunCounters = RunCounters()
        initial: List[Cluster] = self._initial()

        result: List[Cluster] = recovery.recover_unsorted(
            initial, self.vectors, self.snippets, judge, "seed", counters
        )
        with self.assertRaises(JudgeUnavailableError):
            judge.ensure_available()

        self.assertEqual(result, initial)
        self.assertEqual(counters.recovery_clusters_final, 0)
        self.assertGreater(counters.recovery_llm_calls, 0)
        self.assertGreater(judge.cached, 0)


if __name__ == "__main__":
    unittest.main()
