import unittest
from typing import List, Set

from rsstag.anthology import stages
from rsstag.anthology.candidates import Cluster, build_candidates, make_cluster, vectorize
from rsstag.anthology.judge import Judge, JudgeUnavailableError
from tests.anthology_fakes import FakeDB, FakeRouter, synthetic_snippets


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.snippets, self.truth = synthetic_snippets(per_topic=12)
        self.vectors = vectorize([s.vector_text for s in self.snippets])
        self.clusters, _ = build_candidates(self.vectors)
        self.router = FakeRouter()
        self.judge = Judge(FakeDB(), self.router, "owner")


class TestUnionMerge(_Base):
    def test_apply_merges_unions_transitively(self) -> None:
        rows = [[0, 1], [2, 3], [4, 5], [6, 7]]
        clusters = [make_cluster(f"c{i}", r, self.vectors) for i, r in enumerate(rows)]
        merged, merges = stages.apply_merges(clusters, [[0, 1], [1, 2]], self.vectors)
        self.assertEqual(merges, 2)
        self.assertEqual([c.id for c in merged], ["c0", "c3"])
        self.assertEqual(sorted(merged[0].members), [0, 1, 2, 3, 4, 5])

    def test_merge_stage_joins_only_same_topic(self) -> None:
        merged, merges = stages.merge_stage(self.clusters, self.vectors, self.snippets, self.judge)
        self.assertGreaterEqual(merges, 1)
        self.assertEqual(len(merged), len(self.clusters) - merges)
        for cluster in merged:
            self.assertEqual(len({self.truth[r] for r in cluster.members}), 1)

    def test_merge_stage_respects_different(self) -> None:
        judge = Judge(FakeDB(), FakeRouter(merge_answer="different"), "owner")
        merged, merges = stages.merge_stage(self.clusters, self.vectors, self.snippets, judge)
        self.assertEqual(merges, 0)
        self.assertEqual(len(merged), len(self.clusters))


class TestLabelAndIntruder(_Base):
    def test_label_previews_include_boundary_members(self) -> None:
        cluster: Cluster = make_cluster("mixed", list(range(8)), self.vectors)
        expected_rows: List[int] = cluster.members[:2] + cluster.members[-2:]
        self.assertEqual(stages._label_previews(cluster, self.snippets),
                         [self.snippets[row].text for row in expected_rows])
        small: Cluster = make_cluster("small", [0, 1, 2], self.vectors)
        self.assertEqual(stages._label_previews(small, self.snippets),
                         [self.snippets[row].text for row in small.members])

    def test_label_stage_assigns_labels(self) -> None:
        result = stages.label_stage(self.clusters, self.snippets, self.judge, "seed")
        self.assertEqual(result.dissolved, 0)
        for cluster in result.kept:
            self.assertTrue(cluster.label.endswith("story"))
            self.assertEqual(cluster.score, 4)
            self.assertEqual(cluster.kind, "event")

    def test_invalid_low_label_scores_do_not_authorize_repair(self) -> None:
        class Scores:
            def call(self, settings: object, msgs: List[str], **kwargs: object) -> str:
                return '{"id": 1, "score": 0, "label": "invalid", "kind": "event"}\n{"id": 2, "score": 2, "label": "mixed", "kind": "event"}'

        clusters: List[Cluster] = self.clusters[:2]
        stages.label_stage(clusters, self.snippets, Judge(FakeDB(), Scores(), "owner"), "seed")
        self.assertEqual(clusters[0].score, 1)
        self.assertFalse(clusters[0].label_score_valid)
        self.assertEqual(clusters[1].score, 2)
        self.assertTrue(clusters[1].label_score_valid)

    def test_low_scores_dissolve(self) -> None:
        judge = Judge(FakeDB(), FakeRouter(label_score=2), "owner")
        result = stages.label_stage(self.clusters, self.snippets, judge, "seed")
        self.assertEqual(result.kept, [])
        self.assertEqual(result.dissolved, len(self.clusters))
        self.assertEqual(len(result.released), sum(c.size for c in self.clusters))

    def test_unparseable_label_answer_uses_defaults(self) -> None:
        class Silent:
            def call(self, *args: object, **kwargs: object) -> str:
                return "I cannot help"

        judge = Judge(FakeDB(), Silent(), "owner")
        result = stages.label_stage(self.clusters, self.snippets, judge, "seed")
        for cluster in result.kept:
            self.assertEqual(cluster.score, 3)
            self.assertEqual(cluster.label, " ".join(cluster.keywords[:3]))

    def test_strict_labeling_rejects_missing_or_invalid_scores(self) -> None:
        class PartialLabels:
            def call(self, settings: object, msgs: List[str], **kwargs: object) -> str:
                return (
                    '```json\n{"id": 1, "score": 4, "label": "valid", "kind": "event"}\n'
                    '{"id": 2, "label": "missing score", "kind": "event"}\n'
                    '{"id": 3, "score": "garbage", "label": "invalid score", "kind": "event"}\n'
                    '{"id": 4, "score": 3.7, "label": "fractional score", "kind": "event"}\n'
                    '{"id": 5, "score": 99, "label": "out of range", "kind": "event"}\n```'
                )

        clusters: List[Cluster] = [
            make_cluster(f"strict{number}", [number * 2, number * 2 + 1], self.vectors)
            for number in range(5)
        ]
        judge: Judge = Judge(FakeDB(), PartialLabels(), "owner")

        result = stages.label_stage(
            clusters, self.snippets, judge, "seed", require_judgment=True
        )

        self.assertEqual(result.kept, [clusters[0]])
        self.assertEqual(result.released, [row for cluster in clusters[1:] for row in cluster.members])
        self.assertEqual(clusters[0].score, 4)
        self.assertEqual([cluster.score for cluster in clusters[1:]], [1, 1, 1, 1])

    def test_strict_labeling_empty_answer_rejects_every_candidate(self) -> None:
        class Empty:
            def call(self, *args: object, **kwargs: object) -> str:
                return ""

        result = stages.label_stage(
            self.clusters[:2], self.snippets, Judge(FakeDB(), Empty(), "owner", retry_delays=()),
            "seed", require_judgment=True,
        )

        self.assertEqual(result.kept, [])
        self.assertEqual(result.released, [row for cluster in self.clusters[:2] for row in cluster.members])

    def test_intruder_sets_are_deterministic(self) -> None:
        first = [(s.rows, s.answer_position) for s in stages.build_intruder_sets(self.clusters)]
        second = [(s.rows, s.answer_position) for s in stages.build_intruder_sets(self.clusters)]
        self.assertEqual(first, second)
        self.assertTrue(first)

    def test_intruder_stage_accuracy(self) -> None:
        stages.label_stage(self.clusters, self.snippets, self.judge, "seed")
        result, accuracy = stages.intruder_stage(self.clusters, self.snippets, self.judge)
        self.assertEqual(accuracy, 1.0)
        self.assertEqual(result.dissolved, 0)

    def test_wrong_intruder_dissolves_weak_cluster(self) -> None:
        class Wrong:
            def call(self, settings: object, msgs: List[str], **kwargs: object) -> str:
                return "\n".join(f"{n}: 1" for n in range(1, 20))

        for cluster in self.clusters:
            cluster.score = 3
        sets = stages.build_intruder_sets(self.clusters)
        judge = Judge(FakeDB(), Wrong(), "owner")
        result, _ = stages.intruder_stage(self.clusters, self.snippets, judge)
        wrong: Set[str] = {s.cluster.id for s in sets if s.answer_position != 1}
        self.assertEqual({c.id for c in self.clusters} - {c.id for c in result.kept}, wrong)

    def test_strict_intruder_check_rejects_missing_answers_but_allows_untested(self) -> None:
        class Empty:
            def call(self, *args: object, **kwargs: object) -> str:
                return ""

        tested: List[Cluster] = [
            make_cluster("c0", list(range(4)), self.vectors),
            make_cluster("c1", list(range(4, 8)), self.vectors),
        ]
        for cluster in tested:
            cluster.score = 4
        judge: Judge = Judge(FakeDB(), Empty(), "owner", retry_delays=())
        result, accuracy = stages.intruder_stage(
            tested, self.snippets, judge, require_judgment=True
        )
        self.assertEqual(result.kept, [])
        self.assertEqual(result.released, [row for cluster in tested for row in cluster.members])
        self.assertIsNone(accuracy)

        untested: List[Cluster] = [make_cluster("c2", list(range(4)), self.vectors)]
        untested[0].score = 4
        no_comparison, no_accuracy = stages.intruder_stage(
            untested, self.snippets, Judge(FakeDB(), Empty(), "owner", retry_delays=()), require_judgment=True
        )
        self.assertEqual(no_comparison.kept, untested)
        self.assertEqual(no_comparison.released, [])
        self.assertIsNone(no_accuracy)


class TestThemesAndJudge(_Base):
    def test_small_cluster_count_gives_one_theme_each(self) -> None:
        stages.label_stage(self.clusters[:3], self.snippets, self.judge, "seed")
        themes = stages.themes_stage(self.clusters[:3], self.vectors, self.judge, "seed")
        self.assertEqual(len(themes), 3)
        for theme in themes:
            self.assertEqual(theme.label, theme.clusters[0].label)
        self.assertFalse(any(p.startswith("TASK: THEMES") for p in self.router.prompts))

    def test_many_clusters_grouped_into_labeled_themes(self) -> None:
        fine: List[Cluster] = [
            make_cluster(f"c{i}", [i * 2, i * 2 + 1], self.vectors) for i in range(18)
        ]
        stages.label_stage(fine, self.snippets, self.judge, "seed")
        themes = stages.themes_stage(fine, self.vectors, self.judge, "seed")
        self.assertLessEqual(len(themes), stages.MAX_THEMES)
        self.assertEqual(sorted(c.id for t in themes for c in t.clusters), sorted(c.id for c in fine))
        sizes = [t.size for t in themes]
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        for theme in themes:
            if len(theme.clusters) > 1:
                self.assertTrue(theme.label.startswith("Theme"))

    def test_judge_caches_answers(self) -> None:
        self.judge.ask("TASK: MERGE\nPair 1\nx")
        self.judge.ask("TASK: MERGE\nPair 1\nx")
        self.assertEqual((self.judge.calls, self.judge.cached), (1, 1))
        self.assertEqual(len(self.router.prompts), 1)

    def test_judge_unavailable(self) -> None:
        class Broken:
            def call(self, *args: object, **kwargs: object) -> str:
                raise RuntimeError("down")

        judge = Judge(FakeDB(), Broken(), "owner", retry_delays=())
        self.assertEqual(judge.ask("p"), "")
        with self.assertRaises(JudgeUnavailableError):
            judge.ensure_available()


if __name__ == "__main__":
    unittest.main()
