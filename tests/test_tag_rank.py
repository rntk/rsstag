"""Tests for tag ranking: pure helpers, storage sorting and the rank handler."""

import gzip
import math
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from pymongo.database import Database
from werkzeug.wrappers import Request

from rsstag import tag_rank
from rsstag.tag_rank import (
    MAX_DF_RATIO,
    PINNED_SCORE_BONUS,
    USER_RANK_HIDDEN,
    USER_RANK_PINNED,
    W_STOPWORD,
    is_noise,
    apply_derived,
    burst,
    compute_base_rank,
    compute_noise,
    compute_score,
    df_ratio,
    legacy_temperature,
    normalize_sort_mode,
    recompute_derived,
    ridf,
    shape_junk,
    sort_fields,
    sort_names,
)
from rsstag.tags import RssTagTags
from rsstag.web.tag_list_view import (
    TagListView,
    append_list_view,
    build_sort_switcher,
    read_list_view,
)
from rsstag.workers.tag_worker import TagWorker
from tests.db_utils import DBHelper

TEST_MONGO_PORT: int = 8765


def _make_worker(db: Any) -> TagWorker:
    with patch("rsstag.workers.base.stopwords.words", side_effect=[["the"], ["и"]]):
        return TagWorker(db, {"settings": {"host_name": "localhost"}})


class TestRankFormulas(unittest.TestCase):
    def test_ridf_matches_church_gale_formula(self) -> None:
        expected: float = -math.log2(10 / 100) + math.log2(1 - math.exp(-40 / 100))
        self.assertAlmostEqual(expected, ridf(10, 40, 100))

    def test_ridf_is_higher_for_bursty_tags(self) -> None:
        self.assertGreater(ridf(10, 50, 1000), ridf(10, 10, 1000))

    def test_ridf_evenly_spread_frequent_tag_is_negative(self) -> None:
        self.assertLess(ridf(100, 100, 1000), tag_rank.MIN_RIDF)

    def test_ridf_guards_degenerate_input(self) -> None:
        self.assertEqual(0.0, ridf(0, 5, 100))
        self.assertEqual(0.0, ridf(5, 5, 0))
        self.assertTrue(math.isfinite(ridf(200, 1, 100)))

    def test_burst_and_df_ratio(self) -> None:
        self.assertEqual(2.5, burst(25, 10))
        self.assertEqual(0.0, burst(3, 0))
        self.assertEqual(0.1, df_ratio(10, 100))
        self.assertEqual(0.0, df_ratio(10, 0))

    def test_shape_junk(self) -> None:
        for junk in ("12345", "ab", "x", "http", "www", "deadbeef42", "2024г"):
            with self.subTest(tag=junk):
                self.assertTrue(shape_junk(junk))
        for good in ("covid19", "python", "x86", "kubernetes", "москв"):
            with self.subTest(tag=good):
                self.assertFalse(shape_junk(good))

    def test_legacy_temperature_is_positive(self) -> None:
        self.assertGreater(legacy_temperature(5, 0, False), 0)
        self.assertAlmostEqual(10 / math.log(11) + 0.01, legacy_temperature(10, 10, False))
        self.assertLess(legacy_temperature(10, 10, True), legacy_temperature(10, 10, False))

    def test_compute_base_rank_keys(self) -> None:
        rank: Dict[str, Any] = compute_base_rank("python", 10, 20, 100)
        self.assertEqual(
            {"ridf", "burst", "df_ratio", "shape_junk", "stopword", "ranked_at"}, set(rank)
        )
        self.assertFalse(rank["stopword"])
        self.assertTrue(compute_base_rank("the", 10, 20, 100, True)["stopword"])
        self.assertEqual(2.0, rank["burst"])
        self.assertFalse(rank["shape_junk"])


class TestDerivedScore(unittest.TestCase):
    def test_missing_keys_are_neutral(self) -> None:
        self.assertEqual(0.0, compute_score({}))
        self.assertAlmostEqual(1.2, compute_score({"ridf": 1.2}))
        self.assertAlmostEqual(
            1.2, compute_score({"ridf": 1.2, "llm_score": tag_rank.LLM_NEUTRAL})
        )

    def test_boosts_and_penalties(self) -> None:
        base: float = compute_score({"ridf": 1.0})
        for boosted in (
            {"feeds": 5},
            {"title_ratio": 0.5},
            {"is_entity": True},
            {"llm_score": 5},
            {"emb_norm": 1.0},
        ):
            with self.subTest(boost=boosted):
                self.assertGreater(compute_score({"ridf": 1.0, **boosted}), base)
        for penalized in (
            {"boilerplate": 0.5},
            {"cooc_entropy": 0.9},
            {"shape_junk": True},
            {"llm_score": 1},
        ):
            with self.subTest(penalty=penalized):
                self.assertLess(compute_score({"ridf": 1.0, **penalized}), base)

    def test_feeds_do_not_amplify_negative_ridf(self) -> None:
        self.assertEqual(compute_score({"ridf": -0.5}), compute_score({"ridf": -0.5, "feeds": 9}))

    def test_bad_values_are_ignored(self) -> None:
        self.assertEqual(0.0, compute_score({"ridf": float("nan"), "boilerplate": "x"}))

    def test_compute_noise_rules(self) -> None:
        good: Dict[str, Any] = {"ridf": 0.5, "df_ratio": 0.01}
        self.assertFalse(compute_noise(good, 10))
        self.assertTrue(compute_noise(good, 1))
        cases: List[Dict[str, Any]] = [
            {"df_ratio": MAX_DF_RATIO + 0.01},
            {"shape_junk": True},
            {"boilerplate": 0.9},
            {"cooc_entropy": 0.97},
            {"llm_score": 1.0},
            {"ridf": -0.2},
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertTrue(compute_noise({**good, **case}, 10))

    def test_stopword_is_noise_and_penalized(self) -> None:
        good: Dict[str, Any] = {"ridf": 0.5, "df_ratio": 0.01}
        stop: Dict[str, Any] = {**good, "stopword": True}
        self.assertTrue(compute_noise(stop, 10))
        self.assertFalse(compute_noise({**good, "stopword": False}, 10))
        self.assertAlmostEqual(compute_score(good) - W_STOPWORD, compute_score(stop))

    def test_user_rank_overrides_metrics(self) -> None:
        generic: Dict[str, Any] = {"df_ratio": 0.9, "shape_junk": True, "stopword": True}
        good: Dict[str, Any] = {"ridf": 0.5, "df_ratio": 0.01}
        self.assertFalse(compute_noise(generic, 10, USER_RANK_PINNED))
        self.assertTrue(compute_noise(good, 10, USER_RANK_HIDDEN))
        self.assertFalse(compute_noise(good, 10, None))
        self.assertTrue(compute_noise(generic, 10, "bogus"))

    def test_user_rank_score_bonus(self) -> None:
        good: Dict[str, Any] = {"ridf": 0.5}
        self.assertAlmostEqual(
            compute_score(good) - PINNED_SCORE_BONUS, compute_score(good, USER_RANK_HIDDEN)
        )
        self.assertEqual(compute_score(good), compute_score(good, "bogus"))
        self.assertAlmostEqual(
            compute_score(good) + PINNED_SCORE_BONUS, compute_score(good, USER_RANK_PINNED)
        )
        derived: Dict[str, Any] = apply_derived({"shape_junk": True}, 10, USER_RANK_PINNED)
        self.assertFalse(derived["noise"])
        self.assertGreater(derived["score"], PINNED_SCORE_BONUS / 2)

    def test_is_noise_honours_user_rank(self) -> None:
        self.assertTrue(is_noise({"user_rank": "hidden", "rank": {"noise": False}}))
        self.assertFalse(is_noise({"user_rank": "pinned", "rank": {"noise": True}}))
        self.assertTrue(is_noise({"rank": {"noise": True}}))
        self.assertTrue(is_noise({"user_rank": "bogus", "rank": {"noise": True}}))
        self.assertFalse(is_noise({"rank": {"noise": False}}))
        self.assertFalse(is_noise(None))

    def test_pinned_sorts_first_in_informative_in_memory(self) -> None:
        counts: Dict[str, int] = {"a": 5, "b": 5}
        docs: Dict[str, Dict[str, Any]] = {
            "a": {"rank": {"score": 2.0}},
            "b": {"rank": {"score": 0.1 + PINNED_SCORE_BONUS}, "user_rank": "pinned"},
        }
        self.assertEqual(["b", "a"], sort_names(["a", "b"], counts, docs, "informative"))

    def test_apply_derived_returns_copy(self) -> None:
        rank: Dict[str, Any] = {"ridf": 1.0}
        derived: Dict[str, Any] = apply_derived(rank, 5)
        self.assertNotIn("score", rank)
        self.assertEqual(1.0, derived["score"])
        self.assertFalse(derived["noise"])


class TestSortHelpers(unittest.TestCase):
    def test_sort_fields(self) -> None:
        self.assertEqual([("posts_count", -1), ("tag", 1)], sort_fields("count", False))
        self.assertEqual(
            [("rank.score", -1), ("unread_count", -1), ("tag", 1)],
            sort_fields("informative", True),
        )
        self.assertEqual(
            [("rank.hot", -1), ("temperature", -1), ("posts_count", -1), ("tag", 1)],
            sort_fields("hot", False),
        )
        self.assertEqual(sort_fields("count", False), sort_fields("bogus", False))

    def test_normalize_sort_mode(self) -> None:
        self.assertEqual("hot", normalize_sort_mode(" HOT "))
        self.assertEqual("count", normalize_sort_mode("evil"))
        self.assertEqual("count", normalize_sort_mode(None))

    def test_sort_names_in_memory(self) -> None:
        counts: Dict[str, int] = {"a": 5, "b": 9, "c": 5}
        docs: Dict[str, Dict[str, Any]] = {
            "a": {"rank": {"score": 2.0, "hot": 0.1}, "temperature": 1},
            "b": {"rank": {"score": 0.5}, "temperature": 3},
        }
        self.assertEqual(["b", "a", "c"], sort_names(["a", "b", "c"], counts, docs, "count"))
        self.assertEqual(["a", "b", "c"], sort_names(["c", "b", "a"], counts, docs, "informative"))
        self.assertEqual(["a", "b", "c"], sort_names(["c", "b", "a"], counts, docs, "hot"))


class TestListView(unittest.TestCase):
    def test_read_list_view_validates_params(self) -> None:
        view: TagListView = read_list_view(
            Request.from_values(query_string="sort=hot&hide_noise=1&topics=yes")
        )
        self.assertEqual(TagListView(topics=True, sort="hot", hide_noise=True), view)
        self.assertEqual(
            TagListView(), read_list_view(Request.from_values(query_string="sort=x"))
        )
        self.assertEqual(TagListView(), read_list_view(None))

    def test_append_list_view_keeps_params(self) -> None:
        view: TagListView = TagListView(topics=True, sort="informative", hide_noise=True)
        self.assertEqual(
            "/group/tag/2?topics=1&sort=informative&hide_noise=1",
            append_list_view("/group/tag/2", view),
        )
        self.assertEqual("/group/tag/2", append_list_view("/group/tag/2", TagListView()))

    def test_build_sort_switcher(self) -> None:
        switcher: Dict[str, Any] = build_sort_switcher(
            "/group/tag/1", TagListView(sort="hot")
        )
        modes: Dict[str, Dict[str, Any]] = {m["mode"]: m for m in switcher["modes"]}
        self.assertTrue(modes["hot"]["active"])
        self.assertEqual("/group/tag/1", modes["count"]["url"])
        self.assertEqual("/group/tag/1?sort=informative", modes["informative"]["url"])
        self.assertEqual("/group/tag/1?sort=hot&hide_noise=1", switcher["noise"]["url"])
        self.assertIsNone(
            build_sort_switcher("/x", TagListView(), show_noise_toggle=False)["noise"]
        )


class TestStorageSortWithMocks(unittest.TestCase):
    def setUp(self) -> None:
        self.db: MagicMock = MagicMock()
        self.cursor: MagicMock = MagicMock()
        self.cursor.allow_disk_use.return_value = self.cursor
        self.cursor.sort.return_value = self.cursor
        self.db.tags.find.return_value = self.cursor
        self.storage: RssTagTags = RssTagTags(self.db)

    def test_get_all_informative_hides_noise(self) -> None:
        self.storage.get_all("alice", False, "informative", hide_noise=True)
        self.db.tags.find.assert_called_once_with(
            {"owner": "alice", "rank.noise": {"$ne": True}}
        )
        self.cursor.sort.assert_called_once_with(
            [("rank.score", -1), ("posts_count", -1), ("tag", 1)]
        )

    def test_count_hide_noise(self) -> None:
        self.storage.count("alice", True, hide_noise=True)
        self.db.tags.count_documents.assert_called_once_with(
            {"owner": "alice", "unread_count": {"$gt": 0}, "rank.noise": {"$ne": True}}
        )

    def test_set_user_rank_pins_and_rederives(self) -> None:
        self.db.tags.find_one.return_value = {"rank": {"ridf": 0.5}, "posts_count": 10}
        self.db.tags.update_one.return_value.matched_count = 1
        self.assertTrue(self.storage.set_user_rank("alice", "python", "pinned"))
        query, update = self.db.tags.update_one.call_args.args
        self.assertEqual(
            {
                "owner": "alice",
                "tag": "python",
                "rank": {"ridf": 0.5},
                "posts_count": 10,
                "user_rank": {"$exists": False},
                "rank_pending": {"$exists": False},
            },
            query,
        )
        self.assertEqual("pinned", update["$set"]["user_rank"])
        self.assertFalse(update["$set"]["rank.noise"])
        self.assertGreater(update["$set"]["rank.score"], PINNED_SCORE_BONUS / 2)
        self.assertNotIn("$unset", update)

    def test_set_user_rank_hidden_marks_noise_without_rank_doc(self) -> None:
        self.db.tags.find_one.return_value = {"posts_count": 10}
        self.db.tags.update_one.return_value.matched_count = 1
        self.assertTrue(self.storage.set_user_rank("alice", "python", "hidden"))
        update = self.db.tags.update_one.call_args.args[1]
        self.assertTrue(update["$set"]["rank.noise"])

    def test_set_user_rank_none_unsets_override(self) -> None:
        self.db.tags.find_one.return_value = {"rank": {"ridf": 0.5}, "posts_count": 10}
        self.db.tags.update_one.return_value.matched_count = 1
        self.assertTrue(self.storage.set_user_rank("alice", "python", None))
        update = self.db.tags.update_one.call_args.args[1]
        self.assertEqual({"user_rank": ""}, update["$unset"])
        self.assertNotIn("user_rank", update["$set"])
        self.assertFalse(update["$set"]["rank.noise"])

    def test_set_user_rank_rejects_bad_value_and_missing_tag(self) -> None:
        self.assertFalse(self.storage.set_user_rank("alice", "python", "bogus"))
        self.db.tags.update_one.assert_not_called()
        self.db.tags.find_one.return_value = None
        self.assertFalse(self.storage.set_user_rank("alice", "python", "hidden"))
        self.db.tags.update_one.assert_not_called()

    def test_set_user_rank_db_error_returns_false(self) -> None:
        self.db.tags.find_one.side_effect = RuntimeError("down")
        self.assertFalse(self.storage.set_user_rank("alice", "python", "hidden"))

    def test_mark_entities_never_touches_temperature(self) -> None:
        self.storage.mark_entities("alice", {"python": 2})
        update = self.db.tags.bulk_write.call_args.args[0][0]
        self.assertEqual(
            {"$set": {"rank.is_entity": True, "rank_pending": True}, "$inc": {"ner": 2}}, update._doc
        )

    def test_rank_indexes_declared(self) -> None:
        for index in ("rank.score", "rank.hot", "rank.noise"):
            self.assertIn(index, RssTagTags.indexes)


class TestHandlersWithMocks(unittest.TestCase):
    def test_recompute_derived_writes_score_and_noise(self) -> None:
        db: MagicMock = MagicMock()
        db.tags.find.return_value = [
            {"_id": 1, "posts_count": 10, "rank": {"ridf": 1.0, "df_ratio": 0.01}},
            {"_id": 2, "posts_count": 1},
        ]
        db.tags.bulk_write.return_value.matched_count = 2
        self.assertEqual(2, recompute_derived(db, "alice", ["a", "b"]))
        query = db.tags.find.call_args.args[0]
        self.assertEqual({"owner": "alice", "tag": {"$in": ["a", "b"]}}, query)
        updates = db.tags.bulk_write.call_args.args[0]
        self.assertEqual(
            {"$set": {"rank.score": 1.0, "rank.noise": False}, "$unset": {"rank_pending": ""}}, updates[0]._doc
        )
        self.assertEqual(
            {"$set": {"rank.score": 0.0, "rank.noise": True}, "$unset": {"rank_pending": ""}}, updates[1]._doc
        )

    def test_recompute_derived_empty_names_is_noop(self) -> None:
        db: MagicMock = MagicMock()
        self.assertEqual(0, recompute_derived(db, "alice", []))
        db.tags.find.assert_not_called()

    def test_recompute_derived_logs_errors(self) -> None:
        db: MagicMock = MagicMock()
        db.tags.find.side_effect = RuntimeError("boom")
        with self.assertLogs("tag_rank", level="ERROR"):
            with self.assertRaises(RuntimeError):
                recompute_derived(db, "alice")

    def test_recompute_retries_changed_override(self) -> None:
        db: MagicMock = MagicMock()
        original: dict[str, Any] = {"_id": 1, "rank": {"ridf": 1.0}, "posts_count": 10}
        pinned: dict[str, Any] = {**original, "user_rank": "pinned"}
        db.tags.find.side_effect = [[original], [pinned]]
        db.tags.bulk_write.side_effect = [MagicMock(matched_count=0), MagicMock(matched_count=1)]
        self.assertEqual(1, recompute_derived(db, "alice"))
        first: Any = db.tags.bulk_write.call_args_list[0].args[0][0]
        last: Any = db.tags.bulk_write.call_args_list[1].args[0][0]
        self.assertEqual({"$exists": False}, first._filter["user_rank"])
        self.assertEqual("pinned", last._filter["user_rank"])
        self.assertEqual(PINNED_SCORE_BONUS + 1.0, last._doc["$set"]["rank.score"])

    def test_base_rank_reports_derived_failure_and_marks_retry(self) -> None:
        db: MagicMock = MagicMock()
        worker: TagWorker = _make_worker(db)
        task: dict[str, Any] = {"user": {"sid": "alice"}, "data": [
            {"_id": 1, "tag": "python", "posts_count": 10, "freq": 40}
        ]}
        with patch.object(worker, "_total_posts", return_value=100), patch(
            "rsstag.workers.tag_worker.recompute_derived", side_effect=RuntimeError("down")
        ):
            self.assertFalse(worker.make_tags_rank(task))
        update: Any = db.tags.bulk_write.call_args.args[0][0]
        self.assertTrue(update._doc["$set"]["rank_pending"])

    def test_make_ner_marks_stemmed_entities(self) -> None:
        db: MagicMock = MagicMock()
        db.tags.find.return_value = []
        worker: TagWorker = _make_worker(db)
        post: Dict[str, Any] = {
            "owner": "alice",
            "content": {"title": "t", "content": gzip.compress(b"Running Apples")},
        }
        extractor: MagicMock = MagicMock()
        extractor.extract_entities.return_value = [["Running", "Apples"]]
        extractor.clean_entity.return_value = ["Running", "Apples"]
        with patch("rsstag.workers.tag_worker.RssTagEntityExtractor", return_value=extractor):
            self.assertTrue(worker.make_ner([post]))
        updates = db.tags.bulk_write.call_args_list[0].args[0]
        tags: set[str] = {update._filter["tag"] for update in updates}
        self.assertEqual({"run", "appl"}, tags)
        for update in updates:
            self.assertNotIn("temperature", str(update._doc))


class TestRankTaskScaffolding(unittest.TestCase):
    def test_phase_two_tasks_are_registered_global_whole_user_tasks(self) -> None:
        from rsstag import tasks as task_module
        from rsstag.observability.worker_instrumentation import TASK_TYPE_NAMES

        storage = task_module.RssTagTasks(MagicMock())
        for task_type in (
            task_module.TASK_TAGS_CORPUS_RANK,
            task_module.TASK_TAGS_COOC_RANK,
            task_module.TASK_TAGS_EMBED_RANK,
            task_module.TASK_TAGS_LLM_RANK,
        ):
            with self.subTest(task_type=task_type):
                self.assertTrue(storage.get_task_title(task_type))
                self.assertIn(task_type, TASK_TYPE_NAMES)
                self.assertEqual(7200.0, task_module.TASK_LEASE_SECONDS[task_type])
                self.assertEqual(
                    task_module.SCOPE_CAPABILITY_GLOBAL_ONLY,
                    task_module.get_task_scope_capability(task_type),
                )

    def test_base_rank_task_waits_for_processing_pending_tags(self) -> None:
        from rsstag.tasks import RssTagTasks, TASK_NOOP, TASK_TAGS_RANK

        db: MagicMock = MagicMock()
        storage: RssTagTasks = RssTagTasks(db)
        users: MagicMock = MagicMock()
        users.get_by_sid.return_value = {"sid": "alice"}
        storage._state = MagicMock()
        storage._state.claim.return_value = {
            "_id": "task", "user": "alice", "type": TASK_TAGS_RANK
        }
        db.tags.find.return_value.limit.return_value = []
        db.tags.count_documents.return_value = 1
        task: dict[str, Any] = storage.get_task(users)
        self.assertEqual(TASK_NOOP, task["type"])
        storage._state.complete.assert_not_called()
        storage._state.release.assert_called_once_with("task")
        query: dict[str, Any] = db.tags.find.call_args.args[0]
        self.assertEqual(tag_rank.pending_base_rank_query("alice")["$or"], query["$or"])

    def test_handlers_delegate_to_stub_modules(self) -> None:
        worker: TagWorker = _make_worker(MagicMock())
        task: Dict[str, Any] = {"user": {"sid": "alice"}}
        for method, module in (
            ("handle_tags_corpus_rank", "tag_rank_corpus"),
            ("handle_tags_cooc_rank", "tag_rank_cooc"),
            ("handle_tags_embed_rank", "tag_rank_embed"),
            ("handle_tags_llm_rank", "tag_rank_llm"),
        ):
            with self.subTest(method=method):
                with patch(f"rsstag.workers.tag_worker.{module}.run", return_value=True) as run:
                    self.assertTrue(getattr(worker, method)(task))
                run.assert_called_once_with(worker._db, worker._config, "alice")


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

    def _seed_tag(self, tag: str, posts_count: int, freq: int, **extra: Any) -> None:
        doc: Dict[str, Any] = {
            "owner": self.owner,
            "tag": tag,
            "posts_count": posts_count,
            "unread_count": posts_count,
            "freq": freq,
            "temperature": 0,
            "processing": 0,
        }
        doc.update(extra)
        self.db.tags.insert_one(doc)


class TestRankWithMongo(MongoTestCase):
    def test_recompute_derived_persists_fields(self) -> None:
        self._seed_tag("python", 5, 15, rank={"ridf": 1.5, "df_ratio": 0.05})
        self._seed_tag("once", 1, 1, rank={"ridf": 0.1})
        self.assertEqual(2, recompute_derived(self.db, self.owner))
        python: Dict[str, Any] = self.db.tags.find_one({"tag": "python"})
        self.assertAlmostEqual(1.5, python["rank"]["score"])
        self.assertFalse(python["rank"]["noise"])
        self.assertTrue(self.db.tags.find_one({"tag": "once"})["rank"]["noise"])

    def test_claim_query_backfills_legacy_and_retries_pending_tags(self) -> None:
        self._seed_tag("legacy", 10, 40, temperature=1.0)
        self._seed_tag("pending", 10, 40, temperature=1.0,
                       rank={"ranked_at": 1.0}, rank_pending=True)
        self._seed_tag("done", 10, 40, temperature=1.0, rank={"ranked_at": 1.0})
        names: set[str] = {doc["tag"] for doc in self.db.tags.find(
            tag_rank.pending_base_rank_query(self.owner)
        )}
        self.assertEqual({"legacy", "pending"}, names)

    def test_stale_derived_update_cannot_undo_override(self) -> None:
        self._seed_tag("python", 10, 40, rank={"ridf": 1.0}, rank_pending=True)
        original: dict[str, Any] = self.db.tags.find_one({"tag": "python"})
        self.assertTrue(RssTagTags(self.db).set_user_rank(self.owner, "python", "hidden"))
        result: Any = self.db.tags.bulk_write([tag_rank._derived_update(original)])
        self.assertEqual(0, result.matched_count)
        self.assertEqual(1, recompute_derived(self.db, self.owner))
        hidden: dict[str, Any] = self.db.tags.find_one({"tag": "python"})
        self.assertTrue(hidden["rank"]["noise"])
        self.assertLess(hidden["rank"]["score"], 0)
        self.assertNotIn("rank_pending", hidden)

    def test_failed_derived_write_remains_claimable(self) -> None:
        self.db.posts.insert_one({"owner": self.owner})
        self._seed_tag("python", 10, 40)
        worker: TagWorker = _make_worker(self.db)
        batch: list[dict[str, Any]] = list(self.db.tags.find({}))
        task: dict[str, Any] = {"user": {"sid": self.owner}, "data": batch}
        with patch("rsstag.workers.tag_worker.recompute_derived", side_effect=RuntimeError("down")):
            self.assertFalse(worker.make_tags_rank(task))
        self.assertEqual(1, self.db.tags.count_documents(tag_rank.pending_base_rank_query(self.owner)))
        self.assertTrue(worker.make_tags_rank(task))
        self.assertEqual(0, self.db.tags.count_documents(tag_rank.pending_base_rank_query(self.owner)))

    def test_make_tags_rank_writes_rank_and_temperature(self) -> None:
        self.db.posts.insert_many([{"owner": self.owner, "n": i} for i in range(100)])
        self._seed_tag("python", 10, 40)
        self._seed_tag("12345", 3, 3)
        worker: TagWorker = _make_worker(self.db)
        batch: List[Dict[str, Any]] = list(
            self.db.tags.find({}, projection={"tag": 1, "posts_count": 1, "freq": 1})
        )
        task: Dict[str, Any] = {"user": {"sid": self.owner}, "data": batch, "_id": "t"}

        self.assertTrue(worker.make_tags_rank(task))

        python: Dict[str, Any] = self.db.tags.find_one({"tag": "python"})
        self.assertAlmostEqual(ridf(10, 40, 100), python["rank"]["ridf"])
        self.assertEqual(4.0, python["rank"]["burst"])
        self.assertEqual(0.1, python["rank"]["df_ratio"])
        self.assertGreater(python["temperature"], 0)
        self.assertIn("score", python["rank"])
        self.assertFalse(python["rank"]["noise"])
        junk: Dict[str, Any] = self.db.tags.find_one({"tag": "12345"})
        self.assertTrue(junk["rank"]["shape_junk"])
        self.assertTrue(junk["rank"]["noise"])
        self.assertEqual(0, self.db.tags.count_documents({"temperature": 0}))

    def test_storage_sort_and_hide_noise(self) -> None:
        self._seed_tag("common", 50, 50, rank={"score": 0.1, "noise": True})
        self._seed_tag("topical", 10, 40, rank={"score": 3.0, "noise": False, "hot": 1.0})
        self._seed_tag("trend", 5, 5, rank={"score": 1.0, "hot": 4.0}, temperature=1)
        storage: RssTagTags = RssTagTags(self.db)

        def names(sort: str, hide_noise: bool = False) -> List[str]:
            return [
                doc["tag"]
                for doc in storage.get_all(self.owner, False, sort, hide_noise=hide_noise)
            ]

        self.assertEqual(["common", "topical", "trend"], names("count"))
        self.assertEqual(["topical", "trend", "common"], names("informative"))
        self.assertEqual(["trend", "topical", "common"], names("hot"))
        self.assertEqual(["topical", "trend"], names("informative", hide_noise=True))
        self.assertEqual(2, storage.count(self.owner, hide_noise=True))

    def test_user_rank_hide_and_pin_semantics(self) -> None:
        self._seed_tag("common", 50, 50, rank={"score": 0.1, "noise": True})
        self._seed_tag("topical", 10, 40, rank={"ridf": 2.0, "score": 2.0, "noise": False})
        self._seed_tag("trend", 5, 5, rank={"ridf": 1.0, "score": 1.0, "noise": False})
        storage: RssTagTags = RssTagTags(self.db)

        def names(sort: str, hide_noise: bool = False) -> List[str]:
            return [
                d["tag"] for d in storage.get_all(self.owner, False, sort, hide_noise=hide_noise)
            ]

        self.assertTrue(storage.set_user_rank(self.owner, "topical", "hidden"))
        self.assertTrue(storage.set_user_rank(self.owner, "common", "pinned"))
        self.assertFalse(storage.set_user_rank(self.owner, "missing", "pinned"))
        self.assertEqual(["common", "trend"], names("informative", hide_noise=True))
        self.assertEqual(["common", "trend", "topical"], names("informative"))
        self.assertEqual(2, storage.count(self.owner, hide_noise=True))
        self.assertTrue(storage.set_user_rank(self.owner, "topical", None))
        self.assertNotIn("user_rank", self.db.tags.find_one({"tag": "topical"}))
        self.assertEqual(
            ["common", "topical", "trend"], names("informative", hide_noise=True)
        )
        self.assertFalse(self.db.tags.find_one({"tag": "topical"})["rank"]["noise"])


if __name__ == "__main__":
    unittest.main()
