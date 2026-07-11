"""Tests for the TASK_TOPIC_MERGE correctness fixes.

Pure-logic tests run everywhere. DB-backed tests follow the same SkipTest
pattern as tests/test_worker_task_dispatch.py (they require MongoDB on port
8765 and skip otherwise).
"""

import socket
import time
import unittest
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

from rsstag.tasks import (
    TASK_FREEZED,
    TASK_NOT_IN_PROCESSING,
    TASK_TOPIC_MERGE,
    RssTagTasks,
)
from rsstag.topic_aliases import RssTagTopicAliases, rewrite_canonical_id_prefix
from rsstag.topic_merge import (
    TOPIC_MERGE_VERSION,
    TopicMergeAgent,
    select_anchors_for_prompt,
)
from tests.db_utils import DBHelper


class TestSelectAnchorsForPrompt(unittest.TestCase):
    def test_small_pool_returns_all_sorted(self) -> None:
        anchors = select_anchors_for_prompt(
            ["Zebra", "Alpha", "Beta"], ["gamma"], max_anchors=80
        )
        self.assertEqual(anchors, ["Alpha", "Beta", "Zebra"])

    def test_caps_and_prefers_related_labels(self) -> None:
        existing = [f"Unrelated {i}" for i in range(100)]
        existing.extend(["Government IT", "Government Services", "GPU Drivers"])
        selected = select_anchors_for_prompt(
            existing,
            ["GovernmentIT", "Gov Services", "GPU"],
            max_anchors=10,
        )
        self.assertEqual(len(selected), 10)
        # Related government / GPU anchors must survive the cap.
        self.assertIn("Government IT", selected)
        self.assertIn("Government Services", selected)
        self.assertIn("GPU Drivers", selected)

    def test_empty_existing_returns_empty(self) -> None:
        self.assertEqual(select_anchors_for_prompt([], ["a"], max_anchors=10), [])


class TestEmptyLlmOutputAdvancesChunk(unittest.TestCase):
    def test_empty_response_returns_no_merges_instead_of_raising(self) -> None:
        llm_router = MagicMock()
        llm_router.call.return_value = ""
        agent = TopicMergeAgent(MagicMock(), llm_router, "owner-1")
        agent._aliases = MagicMock()

        result = agent._merge_with_llm(
            "Technology",
            ["Alpha", "Beta"],
            ["gamma", "delta"],
            anchor_ids={"Alpha": "a", "Beta": "b"},
        )

        self.assertEqual(result, {})
        llm_router.call.assert_called_once()

    def test_resolve_bucket_writes_aliases_after_empty_llm(self) -> None:
        """Empty LLM must still mint self-canonical aliases so the chunk
        is not re-sent on the next run."""
        llm_router = MagicMock()
        llm_router.call.return_value = ""
        agent = TopicMergeAgent(MagicMock(), llm_router, "u")
        aliases = MagicMock()
        aliases.get_alias.return_value = None
        aliases.get_existing_canonicals.return_value = [
            {"canonical_id": "p/alpha", "canonical_label": "Alpha"},
        ]
        aliases.get_alias_by_normal_form.return_value = None
        aliases.make_canonical_id.side_effect = (
            RssTagTopicAliases.make_canonical_id
        )
        agent._aliases = aliases

        resolved = agent._resolve_bucket(
            0, "p", "Parent", ["Brand New Label"], False
        )

        self.assertIn("Brand New Label", resolved)
        aliases.upsert_alias.assert_called()
        self.assertEqual(
            resolved["Brand New Label"]["canonical_label"], "Brand New Label"
        )


class TestPrefixRewrite(unittest.TestCase):
    """Pure-function coverage for hierarchical canonical-id prefix rewrites."""

    def test_exact_match_maps_to_target(self) -> None:
        self.assertEqual(
            rewrite_canonical_id_prefix("tech", "tech", "science"), "science"
        )

    def test_descendant_prefix_is_replaced(self) -> None:
        self.assertEqual(
            rewrite_canonical_id_prefix("tech/ai/llm", "tech", "science"),
            "science/ai/llm",
        )

    def test_unrelated_id_is_untouched(self) -> None:
        self.assertEqual(
            rewrite_canonical_id_prefix("technology", "tech", "science"),
            "technology",
        )

    def test_only_true_path_boundary_matches(self) -> None:
        # "tech-news" must not be treated as nested under "tech".
        self.assertEqual(
            rewrite_canonical_id_prefix("tech-news/x", "tech", "science"),
            "tech-news/x",
        )


class TestAnchorRedirectDispatch(unittest.TestCase):
    """_merge_with_llm redirects losing anchors without needing a database."""

    def _build_agent(self, llm_response: str) -> TopicMergeAgent:
        llm_router = MagicMock()
        llm_router.call.return_value = llm_response
        agent = TopicMergeAgent(MagicMock(), llm_router, "owner-1")
        agent._aliases = MagicMock()
        agent._aliases.redirect_canonical.return_value = 1
        return agent

    def test_two_anchor_component_redirects_loser_to_winner(self) -> None:
        agent = self._build_agent("1: 2, 3")
        anchor_ids = {"Alpha": "p/alpha", "Beta": "p/beta"}

        result: Dict[str, str] = agent._merge_with_llm(
            "Parent", ["Alpha", "Beta"], ["alpha thing"], anchor_ids=anchor_ids
        )

        # Winner is the min anchor number (Alpha); Beta is the loser.
        agent._aliases.redirect_canonical.assert_called_once_with(
            "owner-1", "p/beta", "p/alpha", "Alpha"
        )
        self.assertEqual(result.get("alpha thing"), "Alpha")

    def test_anchor_only_component_still_redirects(self) -> None:
        # The model may merge two [E] anchors without any [N] member in the
        # component (here "1: 2"; the [N] label is left unmerged). The loser's
        # aliases must still be repaired even though the component contributes
        # nothing to the returned mapping.
        agent = self._build_agent("1: 2")
        anchor_ids = {"Alpha": "p/alpha", "Beta": "p/beta"}

        result: Dict[str, str] = agent._merge_with_llm(
            "Parent", ["Alpha", "Beta"], ["unrelated label"], anchor_ids=anchor_ids
        )

        agent._aliases.redirect_canonical.assert_called_once_with(
            "owner-1", "p/beta", "p/alpha", "Alpha"
        )
        self.assertEqual(agent._last_redirects, [("p/beta", "p/alpha", "Alpha")])
        self.assertNotIn("unrelated label", result)

    def test_single_anchor_component_does_not_redirect(self) -> None:
        agent = self._build_agent("1: 2")
        anchor_ids = {"Alpha": "p/alpha"}

        agent._merge_with_llm(
            "Parent", ["Alpha"], ["alpha thing"], anchor_ids=anchor_ids
        )

        agent._aliases.redirect_canonical.assert_not_called()


class TestBucketStateFollowsRedirect(unittest.TestCase):
    """After an anchor redirect, _resolve_bucket's in-memory state must follow.

    Scenario: anchors E1="Alpha" (p/alpha) and E2="Beta" (p/beta). A cache hit
    already resolved onto E2. Chunk 1 merges E1+E2 (E1 wins). A chunk 2 label
    whose text equals E2's label must resolve to E1's canonical id, not mint a
    fresh alias under the orphaned p/beta, and the cached entry must be
    rewritten onto the winner.
    """

    def test_later_chunk_and_cached_entries_use_winner(self) -> None:
        llm_router = MagicMock()
        # Chunk 1 anchors sorted: 1=Alpha [E], 2=Beta [E], 3="alpha thing" [N]
        # -> component {1,2,3}, winner Alpha. Chunk 2: nothing merges.
        llm_router.call.side_effect = ["1: 2, 3", "NO_MERGES"]
        agent = TopicMergeAgent(MagicMock(), llm_router, "u")
        aliases = MagicMock()

        def fake_get_alias(
            _owner: str, _level: int, _parent: str, raw_label: str
        ) -> Optional[Dict[str, str]]:
            if raw_label == "beta cached":
                return {"canonical_id": "p/beta", "canonical_label": "Beta"}
            return None

        aliases.get_alias.side_effect = fake_get_alias
        aliases.get_existing_canonicals.return_value = [
            {"canonical_id": "p/alpha", "canonical_label": "Alpha"},
            {"canonical_id": "p/beta", "canonical_label": "Beta"},
        ]
        aliases.make_canonical_id.side_effect = (
            RssTagTopicAliases.make_canonical_id
        )
        aliases.redirect_canonical.return_value = 1
        agent._aliases = aliases

        # Chunk size 1 forces "alpha thing" and "Beta" into separate chunks.
        with patch("rsstag.topic_merge._MAX_NEW_LABELS_PER_CALL", 1):
            resolved = agent._resolve_bucket(
                0, "p", "Parent", ["beta cached", "alpha thing", "Beta"], False
            )

        aliases.redirect_canonical.assert_called_once_with(
            "u", "p/beta", "p/alpha", "Alpha"
        )
        # Cached entry that pointed at the loser is rewritten to the winner.
        self.assertEqual(
            resolved["beta cached"],
            {"canonical_id": "p/alpha", "canonical_label": "Alpha"},
        )
        # Chunk 1 merged label lands on the winner.
        self.assertEqual(resolved["alpha thing"]["canonical_id"], "p/alpha")
        # Chunk 2 label matching the loser's label resolves to the winner id
        # instead of minting a fresh alias under the orphaned p/beta.
        self.assertEqual(
            resolved["Beta"],
            {"canonical_id": "p/alpha", "canonical_label": "Alpha"},
        )
        # No alias was ever written pointing at the losing canonical id.
        for call in aliases.upsert_alias.call_args_list:
            self.assertNotEqual(call.args[4], "p/beta")
        # Chunk 2 must not re-offer the loser as an [E] anchor.
        second_prompt: str = llm_router.call.call_args_list[1].args[1][0]
        self.assertNotIn("[E] Beta", second_prompt)


class MongoBackedTestCase(unittest.TestCase):
    db_helper: DBHelper

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        try:
            with socket.create_connection(("127.0.0.1", 8765), timeout=1):
                pass
        except OSError as exc:
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for topic merge fix tests: {exc}"
            )

    def setUp(self) -> None:
        self.db_helper = DBHelper(port=8765)
        try:
            self.db_helper.client.admin.command("ping")
        except Exception as exc:
            self.db_helper.close()
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for topic merge fix tests: {exc}"
            )
        self.db = self.db_helper.create_test_db()

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()


class TestReleaseStaleTasks(MongoBackedTestCase):
    def test_reclaims_only_old_positive_locks(self) -> None:
        tasks = RssTagTasks(self.db)
        now = time.time()
        stale_id = self.db.tasks.insert_one(
            {"user": "u", "type": TASK_TOPIC_MERGE, "processing": now - 10000}
        ).inserted_id
        fresh_id = self.db.tasks.insert_one(
            {"user": "u", "type": TASK_TOPIC_MERGE, "processing": now - 5}
        ).inserted_id
        frozen_id = self.db.tasks.insert_one(
            {"user": "u", "type": TASK_TOPIC_MERGE, "processing": TASK_FREEZED}
        ).inserted_id
        idle_id = self.db.tasks.insert_one(
            {"user": "u", "type": TASK_TOPIC_MERGE, "processing": TASK_NOT_IN_PROCESSING}
        ).inserted_id

        reclaimed = tasks.release_stale_tasks(3600)

        self.assertEqual(reclaimed, 1)
        self.assertEqual(
            self.db.tasks.find_one({"_id": stale_id})["processing"],
            TASK_NOT_IN_PROCESSING,
        )
        self.assertGreater(
            self.db.tasks.find_one({"_id": fresh_id})["processing"], 0
        )
        self.assertEqual(
            self.db.tasks.find_one({"_id": frozen_id})["processing"], TASK_FREEZED
        )
        self.assertEqual(
            self.db.tasks.find_one({"_id": idle_id})["processing"],
            TASK_NOT_IN_PROCESSING,
        )


class TestFinishTaskResetsCounters(MongoBackedTestCase):
    def test_kept_task_clears_failure_counters(self) -> None:
        tasks = RssTagTasks(self.db)
        task_id = self.db.tasks.insert_one(
            {
                "user": "u",
                "type": TASK_TOPIC_MERGE,
                "processing": time.time(),
                "failed_attempts": 2,
                "last_error": "boom",
            }
        ).inserted_id
        # A pending doc keeps the task alive after finish.
        self.db.post_grouping.insert_one(
            {"owner": "u", "post_ids": ["p1"], "groups": {"A > B": ["s"]}}
        )

        finished = tasks.finish_task(
            {"_id": task_id, "type": TASK_TOPIC_MERGE, "user": {"sid": "u"}}
        )

        self.assertTrue(finished)
        stored = self.db.tasks.find_one({"_id": task_id})
        self.assertIsNotNone(stored)
        self.assertEqual(stored["processing"], TASK_NOT_IN_PROCESSING)
        self.assertNotIn("failed_attempts", stored)
        self.assertNotIn("last_error", stored)

    def test_finish_exception_unlocks_topic_merge_claim(self) -> None:
        """A boom inside finish_task must not leave the long-lived claim stuck."""
        tasks = RssTagTasks(self.db)
        task_id = self.db.tasks.insert_one(
            {
                "user": "u",
                "type": TASK_TOPIC_MERGE,
                "processing": time.time(),
            }
        ).inserted_id

        with patch.object(
            tasks,
            "_count_pending_topic_merge_docs",
            side_effect=RuntimeError("count failed"),
        ):
            finished = tasks.finish_task(
                {"_id": task_id, "type": TASK_TOPIC_MERGE, "user": {"sid": "u"}}
            )

        self.assertFalse(finished)
        stored = self.db.tasks.find_one({"_id": task_id})
        self.assertIsNotNone(stored)
        self.assertEqual(stored["processing"], TASK_NOT_IN_PROCESSING)

    def test_finish_removes_task_when_no_pending_docs(self) -> None:
        tasks = RssTagTasks(self.db)
        task_id = self.db.tasks.insert_one(
            {
                "user": "u",
                "type": TASK_TOPIC_MERGE,
                "processing": time.time(),
                "manual": True,
            }
        ).inserted_id
        self.db.post_grouping.insert_one(
            {
                "owner": "u",
                "post_ids": ["p1"],
                "groups": {"A > B": ["s"]},
                "topic_merged": TOPIC_MERGE_VERSION,
            }
        )

        finished = tasks.finish_task(
            {"_id": task_id, "type": TASK_TOPIC_MERGE, "user": {"sid": "u"}}
        )

        self.assertTrue(finished)
        self.assertIsNone(self.db.tasks.find_one({"_id": task_id}))


class TestTopicMergeStatusCount(MongoBackedTestCase):
    def test_status_reports_pending_topic_merge_count(self) -> None:
        tasks = RssTagTasks(self.db)
        self.db.tasks.insert_one(
            {"user": "u", "type": TASK_TOPIC_MERGE, "processing": 0}
        )
        self.db.post_grouping.insert_one(
            {"owner": "u", "post_ids": ["p1"], "groups": {"A > B": ["s"]}}
        )

        status = tasks.get_tasks_status("u")

        merge_status = next(s for s in status if s["type"] == TASK_TOPIC_MERGE)
        self.assertEqual(merge_status["count"], 1)
        self.assertNotIn("(frozen)", merge_status["title"])
        self.assertNotIn("(processing)", merge_status["title"])

    def test_status_marks_frozen_and_processing_titles(self) -> None:
        tasks = RssTagTasks(self.db)
        self.db.tasks.insert_one(
            {
                "user": "u",
                "type": TASK_TOPIC_MERGE,
                "processing": TASK_FREEZED,
                "failed": True,
            }
        )

        status = tasks.get_tasks_status("u")
        merge_status = next(s for s in status if s["type"] == TASK_TOPIC_MERGE)
        self.assertIn("(frozen)", merge_status["title"])


class TestMarkDocsMergedRace(MongoBackedTestCase):
    def _agent(self) -> TopicMergeAgent:
        return TopicMergeAgent(self.db, MagicMock(), "u")

    def test_doc_rewritten_after_collection_is_not_stamped(self) -> None:
        agent = self._agent()
        agent._run_start = time.time()
        legacy_id = self.db.post_grouping.insert_one(
            {"owner": "u", "post_ids": ["p1"], "groups": {}}
        ).inserted_id
        untouched_id = self.db.post_grouping.insert_one(
            {
                "owner": "u",
                "post_ids": ["p2"],
                "groups": {},
                "updated_at": agent._run_start - 5,
            }
        ).inserted_id
        rewritten_id = self.db.post_grouping.insert_one(
            {
                "owner": "u",
                "post_ids": ["p3"],
                "groups": {},
                "updated_at": agent._run_start + 5,
            }
        ).inserted_id
        agent._collected_doc_ids = [legacy_id, untouched_id, rewritten_id]

        marked = agent._mark_docs_merged()

        self.assertTrue(marked)
        self.assertEqual(
            self.db.post_grouping.find_one({"_id": legacy_id}).get("topic_merged"),
            TOPIC_MERGE_VERSION,
        )
        self.assertEqual(
            self.db.post_grouping.find_one({"_id": untouched_id}).get("topic_merged"),
            TOPIC_MERGE_VERSION,
        )
        self.assertIsNone(
            self.db.post_grouping.find_one({"_id": rewritten_id}).get("topic_merged")
        )

    def test_mark_docs_merged_db_error_returns_false(self) -> None:
        agent = self._agent()
        agent._run_start = time.time()
        agent._collected_doc_ids = ["fake-id"]
        agent._db = MagicMock()
        agent._db.post_grouping.update_many.side_effect = RuntimeError("db down")

        self.assertFalse(agent._mark_docs_merged())
        self.assertEqual(agent._collected_doc_ids, [])

    def test_run_returns_false_when_mark_fails(self) -> None:
        agent = self._agent()
        self.db.post_grouping.insert_one(
            {"owner": "u", "post_ids": ["p1"], "groups": {}}
        )
        with patch.object(agent, "_mark_docs_merged", return_value=False):
            self.assertFalse(agent.run())


class TestRedirectCanonical(MongoBackedTestCase):
    def _alias(
        self,
        level: int,
        parent_id: str,
        raw_label: str,
        canonical_id: str,
        canonical_label: str,
    ) -> None:
        self.db.topic_aliases.insert_one(
            {
                "owner": "u",
                "level": level,
                "parent_canonical_id": parent_id,
                "raw_label": raw_label,
                "canonical_id": canonical_id,
                "canonical_label": canonical_label,
            }
        )

    def test_redirect_moves_exact_and_descendant_aliases(self) -> None:
        aliases = RssTagTopicAliases(self.db)
        # Losing anchor "tech" and its descendant "tech/ai".
        self._alias(0, "", "Technology", "tech", "Technology")
        self._alias(1, "tech", "AI", "tech/ai", "AI")
        # Winning anchor "science".
        self._alias(0, "", "Science", "science", "Science")

        moved = aliases.redirect_canonical("u", "tech", "science", "Science")

        self.assertEqual(moved, 2)
        exact = self.db.topic_aliases.find_one({"raw_label": "Technology"})
        self.assertEqual(exact["canonical_id"], "science")
        self.assertEqual(exact["canonical_label"], "Science")
        descendant = self.db.topic_aliases.find_one({"raw_label": "AI"})
        self.assertEqual(descendant["canonical_id"], "science/ai")
        self.assertEqual(descendant["parent_canonical_id"], "science")

    def test_redirect_is_noop_when_ids_equal(self) -> None:
        aliases = RssTagTopicAliases(self.db)
        self._alias(0, "", "Technology", "tech", "Technology")

        self.assertEqual(aliases.redirect_canonical("u", "tech", "tech", "Tech"), 0)


if __name__ == "__main__":
    unittest.main()
