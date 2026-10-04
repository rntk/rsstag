import socket
import unittest
from threading import Event
from typing import Any, Dict, List, Set
from unittest.mock import MagicMock, patch

from rsstag.anthologies import RssTagAnthologies
from rsstag.anthology.pipeline import AnthologyPipeline
from rsstag.anthology.units import UnitsResult, load_units
from tests.anthology_fakes import FakeDB, FakeRouter, synthetic_snippets, synthetic_texts
from tests.db_utils import DBHelper

MONGO_PORT: int = 8765
CLUSTER_KINDS: Set[str] = {"event", "debate", "howto", "release", "opinion", "analysis", "other"}


def assert_result_schema(case: unittest.TestCase, result: Dict[str, Any]) -> None:
    """Check the stored result matches the contract rendered by the web layer."""
    case.assertEqual(set(result), {"themes", "clusters", "unsorted", "snippets", "metrics"})
    theme_cluster_ids: List[str] = [cid for t in result["themes"] for cid in t["cluster_ids"]]
    case.assertEqual(sorted(theme_cluster_ids), sorted(result["clusters"]))
    sizes: List[int] = [t["size"] for t in result["themes"]]
    case.assertEqual(sizes, sorted(sizes, reverse=True))
    assigned: Set[str] = set()
    for cluster in result["clusters"].values():
        case.assertIn(cluster["kind"], CLUSTER_KINDS)
        case.assertTrue(1 <= cluster["score"] <= 5)
        case.assertLessEqual(len(cluster["label"].split()), 5)
        case.assertLessEqual(len(cluster["keywords"]), 8)
        case.assertIn(cluster["start_snippet_id"], cluster["snippet_ids"])
        assigned.update(cluster["snippet_ids"])
    case.assertEqual(assigned | set(result["unsorted"]), set(result["snippets"]))
    case.assertFalse(assigned & set(result["unsorted"]))
    for snippet in result["snippets"].values():
        case.assertLessEqual(len(snippet["preview"]), 240)
    metrics: Dict[str, Any] = result["metrics"]
    case.assertEqual(metrics["snippets_total"], len(result["snippets"]))
    case.assertEqual(metrics["snippets_assigned"], len(assigned))
    case.assertEqual(metrics["clusters_final"], len(result["clusters"]))


class TestAnthologyPipelineOffline(unittest.TestCase):
    """Full pipeline with patched unit loading and a fake store/LLM."""

    def _run(self, router: FakeRouter, db: FakeDB) -> MagicMock:
        snippets, _ = synthetic_snippets(per_topic=12)
        store: MagicMock = MagicMock()
        store.get_by_id.return_value = {"_id": "a1", "seed_value": "news", "scope": {"mode": "all"}}
        store.save_result.return_value = True
        store.claim_run.return_value = "test-run"
        store.heartbeat.return_value = True
        pipeline = AnthologyPipeline(db, router, "owner")
        pipeline._store = store
        units = UnitsResult(snippets=snippets, posts_in_scope=40, ungrouped_posts=4)
        with patch("rsstag.anthology.pipeline.load_units", return_value=units):
            self.assertTrue(pipeline.run("a1"))
        return store

    def test_run_produces_schema_and_topics(self) -> None:
        store = self._run(FakeRouter(), FakeDB())
        result: Dict[str, Any] = store.save_result.call_args[0][1]
        assert_result_schema(self, result)
        stages_called: List[str] = [c[0][1] for c in store.set_stage.call_args_list]
        self.assertEqual(stages_called, ["units", "candidates", "merge", "label", "intruder", "recovery", "themes"])
        self.assertEqual(result["metrics"]["ungrouped_posts"], 4)
        self.assertGreaterEqual(len(result["themes"]), 3)
        self.assertEqual(
            sum(result["metrics"]["first_pass_unsorted"].values()),
            result["metrics"]["recovery_snippets_input"],
        )
        self.assertGreater(result["metrics"]["llm_calls"], 0)
        self.assertEqual(result["metrics"]["intruder_accuracy"], 1.0)

    def test_rerun_hits_cache(self) -> None:
        db = FakeDB()
        self._run(FakeRouter(), db)
        router = FakeRouter()
        store = self._run(router, db)
        metrics = store.save_result.call_args[0][1]["metrics"]
        self.assertEqual(metrics["llm_calls"], 0)
        self.assertGreater(metrics["llm_cached"], 0)
        self.assertEqual(router.prompts, [])

    def test_no_snippets_marks_failed(self) -> None:
        store: MagicMock = MagicMock()
        store.get_by_id.return_value = {"_id": "a1", "seed_value": "news", "scope": None}
        store.claim_run.return_value = "test-run"
        pipeline = AnthologyPipeline(FakeDB(), FakeRouter(), "owner")
        pipeline._store = store
        with patch("rsstag.anthology.pipeline.load_units", return_value=UnitsResult(posts_in_scope=3, ungrouped_posts=3)):
            self.assertFalse(pipeline.run("a1"))
        args, kwargs = store.update_status.call_args
        self.assertEqual(args[1], "failed")
        self.assertIn("grouping", kwargs["error"])
        store.save_result.assert_not_called()

    def test_missing_anthology_marks_failed(self) -> None:
        store: MagicMock = MagicMock()
        store.get_by_id.return_value = None
        pipeline = AnthologyPipeline(FakeDB(), FakeRouter(), "owner")
        pipeline._store = store
        self.assertFalse(pipeline.run("missing"))
        self.assertEqual(store.update_status.call_args[0][1], "failed")


class TestAnthologyRunOwnership(unittest.TestCase):
    def setUp(self) -> None:
        self.store: MagicMock = MagicMock()
        self.store.get_by_id.return_value = {
            "seed_value": "news", "status": "processing", "run_id": "current-run",
        }
        self.store.heartbeat.return_value = True
        self.store.save_result.return_value = True
        self.pipeline: AnthologyPipeline = AnthologyPipeline(FakeDB(), FakeRouter(), "owner")
        self.pipeline._store = self.store
        self.result: Dict[str, Any] = {"metrics": {}}

    def test_stale_task_cannot_start_or_mark_current_run_failed(self) -> None:
        with patch.object(self.pipeline, "_build") as build:
            self.assertFalse(self.pipeline.run("a1", run_id="old-run"))
        build.assert_not_called()
        self.store.save_result.assert_not_called()
        self.store.update_status.assert_not_called()
        self.store.claim_run.assert_not_called()

    def test_background_heartbeat_refreshes_a_blocking_build(self) -> None:
        refreshed: Event = Event()

        def heartbeat(anthology_id: str, owner: str, run_id: str) -> bool:
            self.assertEqual((anthology_id, owner, run_id), ("a1", "owner", "current-run"))
            refreshed.set()
            return True

        def blocking_build(*args: Any) -> Dict[str, Any]:
            self.assertTrue(refreshed.wait(timeout=1.0), "no heartbeat during blocking work")
            return self.result

        self.store.heartbeat.side_effect = heartbeat
        with patch("rsstag.anthology.pipeline.HEARTBEAT_INTERVAL_SECONDS", 0.01), patch.object(
            self.pipeline, "_build", side_effect=blocking_build
        ):
            self.assertTrue(self.pipeline.run("a1", run_id="current-run"))
        self.store.save_result.assert_called_once_with(
            "a1", self.result, run_id="current-run", owner="owner"
        )
        self.assertIsNone(self.pipeline._judge.on_progress)

    def test_lost_ownership_before_publish_does_not_write_result_or_failure(self) -> None:
        self.store.heartbeat.return_value = False
        with patch.object(self.pipeline, "_build", return_value=self.result):
            self.assertFalse(self.pipeline.run("a1", run_id="current-run"))
        self.store.save_result.assert_not_called()
        self.store.update_status.assert_not_called()

    def test_lost_ownership_during_judge_call_stops_after_call(self) -> None:
        def slow_answer(*args: Any, **kwargs: Any) -> str:
            self.store.heartbeat.return_value = False
            return "an answer from the superseded run"

        def build_with_judge(*args: Any) -> Dict[str, Any]:
            self.pipeline._judge.ask("a new prompt")
            self.fail("superseded judge call should stop this build")
            return self.result

        with patch.object(self.pipeline._judge._llm, "call", side_effect=slow_answer), patch.object(
            self.pipeline, "_build", side_effect=build_with_judge
        ):
            self.assertFalse(self.pipeline.run("a1", run_id="current-run"))
        self.store.save_result.assert_not_called()
        self.store.update_status.assert_not_called()

    def test_build_failure_is_fenced_to_its_claim(self) -> None:
        with patch.object(self.pipeline, "_build", side_effect=RuntimeError("failed build")):
            self.assertFalse(self.pipeline.run("a1", run_id="current-run"))
        self.store.update_status.assert_called_once_with(
            "a1", "failed", error="Anthology pipeline error: failed build",
            run_id="current-run", owner="owner",
        )

    def test_failed_direct_claim_leaves_other_run_untouched(self) -> None:
        self.store.claim_run.return_value = None
        with patch.object(self.pipeline, "_build") as build:
            self.assertFalse(self.pipeline.run("a1"))
        build.assert_not_called()
        self.store.save_result.assert_not_called()
        self.store.update_status.assert_not_called()


class _MongoCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        try:
            with socket.create_connection(("127.0.0.1", MONGO_PORT), timeout=1):
                pass
        except OSError as exc:
            raise unittest.SkipTest(f"MongoDB on port {MONGO_PORT} is required: {exc}")

    def setUp(self) -> None:
        self.db_helper = DBHelper(port=MONGO_PORT)
        try:
            self.db_helper.client.admin.command("ping")
        except Exception as exc:
            self.db_helper.close()
            raise unittest.SkipTest(f"MongoDB on port {MONGO_PORT} is required: {exc}")
        self.db = self.db_helper.create_test_db()
        self.owner = "anthology-owner"
        self.store = RssTagAnthologies(self.db)
        self.store.prepare()

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()

    def _seed_posts(self, tag: str = "news") -> List[str]:
        texts, truth = synthetic_texts(per_topic=10)
        posts: List[Dict[str, Any]] = []
        groupings: List[Dict[str, Any]] = []
        for i, text in enumerate(texts):
            pid = str(1000 + i)
            posts.append({
                "owner": self.owner, "pid": pid, "feed_id": f"f-{truth[i]}",
                "unix_date": 1_700_000_000 + i, "tags": [tag, truth[i]],
                "content": {"title": f"Post {i}"},
            })
            groupings.append({
                "owner": self.owner, "post_ids": [pid], "post_ids_hash": f"h{i}",
                "sentences": [{"number": 0, "text": text, "read": False},
                              {"number": 1, "text": "unrelated footer", "read": False}],
                "groups": {f"{truth[i].title()} > Main": [0], "Footer": [1]},
            })
        posts.append({"owner": self.owner, "pid": "9999", "tags": [tag], "content": {"title": "x"}})
        posts.append({"owner": self.owner, "pid": "8888", "tags": ["other"], "content": {"title": "y"}})
        self.db_helper.init_db_from_dict(self.db, {"posts": posts, "post_grouping": groupings})
        return [p["pid"] for p in posts]


class TestAnthologyPipelineMongo(_MongoCase):
    def test_load_units_filters_by_seed_and_counts_ungrouped(self) -> None:
        self._seed_posts()
        units = load_units(self.db, self.owner, "news", {"mode": "all"})
        self.assertEqual(units.posts_in_scope, 31)
        self.assertEqual(units.ungrouped_posts, 1)
        # Seed "news" matches no snippet, so every snippet of the post is kept.
        self.assertEqual(len(units.snippets), 60)
        units = load_units(self.db, self.owner, "Footer", {"mode": "posts", "post_ids": ["1000", "1001"]})
        self.assertEqual(units.posts_in_scope, 2)
        self.assertEqual(len(units.snippets), 4)

    def test_seed_matching_snippets_only(self) -> None:
        self._seed_posts(tag="space")
        units = load_units(self.db, self.owner, "space", {"mode": "all"})
        space_paths = {s.topic_path for s in units.snippets if s.post_id in {"1000", "1001"}}
        self.assertEqual(space_paths, {"Space > Main"})

    def test_end_to_end(self) -> None:
        self._seed_posts()
        anthology_id = self.store.create(self.owner, "tag", "news", {"mode": "all"})
        pipeline = AnthologyPipeline(self.db, FakeRouter(), self.owner)
        self.assertTrue(pipeline.run(anthology_id))
        doc = self.store.get_by_id(self.owner, anthology_id)
        self.assertEqual((doc["status"], doc["stage"], doc["stale"], doc["error"]), ("done", "done", False, None))
        assert_result_schema(self, doc["result"])
        self.assertEqual(len(doc["post_ids"]), 30)
        self.assertGreater(self.db.anthology_judgments.count_documents({"owner": self.owner}), 0)
        self.assertEqual(self.store.mark_stale_for_source_change(self.owner, ["1000"]), 1)
        self.assertTrue(self.store.get_by_id(self.owner, anthology_id)["stale"])
        for theme in doc["result"]["themes"]:
            self.assertTrue(theme["label"])

    def test_end_to_end_without_groupings_fails(self) -> None:
        self.db.posts.insert_one({"owner": self.owner, "pid": "1", "tags": ["news"]})
        anthology_id = self.store.create(self.owner, "tag", "news", None)
        self.assertFalse(AnthologyPipeline(self.db, FakeRouter(), self.owner).run(anthology_id))
        doc = self.store.get_by_id(self.owner, anthology_id)
        self.assertEqual(doc["status"], "failed")
        self.assertTrue(doc["error"])


if __name__ == "__main__":
    unittest.main()
