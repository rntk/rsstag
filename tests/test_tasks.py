import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# rsstag.tasks imports modules with runtime type issues in this environment.
sys.modules.setdefault("rsstag.post_grouping", types.SimpleNamespace(RssTagPostGrouping=object))
sys.modules.setdefault("rsstag.tags", types.SimpleNamespace(RssTagTags=object))

from typing import Any, Dict, List

from rsstag.task_state import TASK_STATUS_PENDING
from rsstag.tasks import (
    RssTagTasks,
    TASK_ANTHOLOGY,
    TASK_MARK,
    TASK_MARK_TELEGRAM,
    TASK_NOT_IN_PROCESSING,
    TASK_POST_GROUPING,
    TASK_W2V,
    SCOPE_MODE_ALL,
    SCOPE_MODE_POSTS,
    SCOPE_MODE_FEEDS,
    SCOPE_MODE_CATEGORIES,
    SCOPE_MODE_PROVIDER,
)


class TestRssTagTasksScope(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.storage = RssTagTasks(self.db)

    def test_validate_task_scope_rejects_scoped_mode_for_global_task(self):
        ok, error = self.storage.validate_task_scope(
            TASK_W2V,
            {"mode": SCOPE_MODE_POSTS, "post_ids": ["p1"]},
        )

        self.assertFalse(ok)
        self.assertIn("global-only", error)

    def test_validate_task_scope_requires_ids_for_scope_modes(self):
        cases = [
            (SCOPE_MODE_POSTS, {}, "post id"),
            (SCOPE_MODE_FEEDS, {}, "feed id"),
            (SCOPE_MODE_CATEGORIES, {}, "category id"),
            (SCOPE_MODE_PROVIDER, {}, "provider value"),
        ]

        for mode, extra, expected_msg in cases:
            with self.subTest(mode=mode):
                ok, error = self.storage.validate_task_scope(
                    TASK_POST_GROUPING,
                    {"mode": mode, **extra},
                )
                self.assertFalse(ok)
                self.assertIn(expected_msg, error)

    def test_validate_task_scope_accepts_valid_scoped_input(self):
        ok, error = self.storage.validate_task_scope(
            TASK_POST_GROUPING,
            {"mode": SCOPE_MODE_POSTS, "post_ids": ["pid-1"]},
        )

        self.assertTrue(ok)
        self.assertEqual("", error)

    def test_validate_task_scope_accepts_anthology_scope(self):
        ok, error = self.storage.validate_task_scope(
            TASK_ANTHOLOGY,
            {"mode": SCOPE_MODE_FEEDS, "feed_ids": ["feed-1"]},
        )

        self.assertTrue(ok)
        self.assertEqual("", error)

    def test_get_task_title_includes_anthology(self):
        self.assertIn("Anthology", self.storage.get_task_title(TASK_ANTHOLOGY))

    def test_build_post_scope_predicate_all_mode(self):
        task = {"scope": {"mode": SCOPE_MODE_ALL}}

        query = self.storage._build_post_scope_predicate("alice", task)

        self.assertEqual({"owner": "alice"}, query)

    def test_build_post_scope_predicate_posts_mode(self):
        task = {"scope": {"mode": SCOPE_MODE_POSTS, "post_ids": ["1", "2"]}}

        query = self.storage._build_post_scope_predicate("alice", task)

        self.assertEqual({"owner": "alice", "pid": {"$in": ["1", "2"]}}, query)

    def test_build_post_scope_predicate_feeds_mode(self):
        task = {"scope": {"mode": SCOPE_MODE_FEEDS, "feed_ids": ["f1", "f2"]}}

        query = self.storage._build_post_scope_predicate("alice", task)

        self.assertEqual({"owner": "alice", "feed_id": {"$in": ["f1", "f2"]}}, query)

    def test_build_post_scope_predicate_categories_mode_uses_feed_resolution(self):
        task = {"scope": {"mode": SCOPE_MODE_CATEGORIES, "category_ids": ["c1"]}}

        with patch.object(self.storage, "_resolve_scope_feed_ids", return_value=["f9"]):
            query = self.storage._build_post_scope_predicate("alice", task)

        self.assertEqual({"owner": "alice", "feed_id": {"$in": ["f9"]}}, query)

    def test_build_post_scope_predicate_provider_mode(self):
        task = {"scope": {"mode": SCOPE_MODE_PROVIDER, "provider": " telegram "}}

        query = self.storage._build_post_scope_predicate("alice", task)

        self.assertEqual({"owner": "alice", "provider": "telegram"}, query)

    def test_build_post_scope_predicate_provider_mode_empty_provider_falls_back_to_owner_only(self):
        # If a stored task has mode=provider but empty provider, the predicate
        # must not silently match all posts — this documents the current behaviour
        # so any change is explicit.
        task = {"scope": {"mode": SCOPE_MODE_PROVIDER, "provider": ""}}

        query = self.storage._build_post_scope_predicate("alice", task)

        self.assertEqual({"owner": "alice"}, query)

    def test_validate_task_scope_none_scope_defaults_to_all_and_succeeds(self):
        # None scope should normalise to ALL mode, which is valid for any task.
        ok, error = self.storage.validate_task_scope(TASK_POST_GROUPING, None)

        self.assertTrue(ok)
        self.assertEqual("", error)

    def test_validate_task_scope_all_mode_accepted_for_global_only_task(self):
        # A global-only task with ALL scope (the default) must be accepted.
        ok, error = self.storage.validate_task_scope(TASK_W2V, {"mode": SCOPE_MODE_ALL})

        self.assertTrue(ok)
        self.assertEqual("", error)

    def test_validate_task_scope_unknown_mode_treated_as_all(self):
        # An unrecognised mode is normalised to ALL, so validation should pass.
        ok, error = self.storage.validate_task_scope(
            TASK_POST_GROUPING, {"mode": "nonexistent_mode"}
        )

        self.assertTrue(ok)
        self.assertEqual("", error)


def _is_claimable(doc: Dict[str, Any], now: float = 1000.0) -> bool:
    """Plain-Python mirror of TaskStateMachine.claimable_filter.

    The real filter is a Mongo query and there is no Mongo (or mongomock) in
    this environment, so the three branches are re-expressed here to pin the
    doc shapes that can and cannot be claimed. Kept deliberately literal so a
    change to the filter shows up as a diff against this function.
    """
    if doc.get("status") == "pending" and not doc.get("backoff_until", 0) > now:
        return True
    if doc.get("status") == "running" and doc.get("lease_until", now) < now:
        return True
    return "status" not in doc and doc.get("processing") == TASK_NOT_IN_PROCESSING


class TestRssTagTasksMarkStatus(unittest.TestCase):
    """A mark payload's boolean read flag must not shadow the task status."""

    def setUp(self) -> None:
        self.db = MagicMock()
        self.storage = RssTagTasks(self.db)

    def _add_mark_task(self, task_type: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.storage.add_task({"type": task_type, "user": "user-1", "data": [payload]})
        inserted: List[Dict[str, Any]] = self.db.tasks.insert_many.call_args.args[0]
        self.assertEqual(len(inserted), 1)
        return inserted[0]

    def _mark_payload(self, readed: bool) -> Dict[str, Any]:
        """The payload shape built by read_state.py / on_read_posts_post."""
        return {
            "user": "user-1",
            "id": "provider-id-1",
            "status": readed,
            "processing": TASK_NOT_IN_PROCESSING,
            "type": TASK_MARK,
            "provider": "bazqux",
        }

    def test_legacy_boolean_status_doc_is_unclaimable(self) -> None:
        """Regression: the exact shape that left mark tasks stuck in the queue."""
        self.assertFalse(_is_claimable(self._mark_payload(True)))

    def test_enqueued_mark_task_is_claimable(self) -> None:
        doc = self._add_mark_task(TASK_MARK, self._mark_payload(True))

        self.assertEqual(doc["status"], TASK_STATUS_PENDING)
        self.assertTrue(_is_claimable(doc))

    def test_enqueued_mark_task_keeps_read_flag(self) -> None:
        doc = self._add_mark_task(TASK_MARK, self._mark_payload(True))
        self.assertIs(doc["mark_status"], True)

    def test_enqueued_unread_mark_task_keeps_read_flag(self) -> None:
        doc = self._add_mark_task(TASK_MARK, self._mark_payload(False))

        self.assertIs(doc["mark_status"], False)
        self.assertEqual(doc["status"], TASK_STATUS_PENDING)
        self.assertTrue(_is_claimable(doc))

    def test_telegram_mark_task_has_no_read_flag(self) -> None:
        """The telegram payload never carried a boolean, so it stayed claimable."""
        doc = self._add_mark_task(
            TASK_MARK_TELEGRAM,
            {
                "user": "user-1",
                "id": "",
                "processing": TASK_NOT_IN_PROCESSING,
                "type": TASK_MARK_TELEGRAM,
                "provider": "telegram",
            },
        )

        self.assertEqual(doc["status"], TASK_STATUS_PENDING)
        self.assertNotIn("mark_status", doc)
        self.assertTrue(_is_claimable(doc))

    def test_provider_payload_exposes_read_flag_as_status(self) -> None:
        """Providers read data["status"]; it must stay the boolean, not "pending"."""
        doc = self._add_mark_task(TASK_MARK, self._mark_payload(False))

        data = self.storage._mark_task_data(doc)

        self.assertIs(data["status"], False)

    def test_provider_payload_never_passes_lifecycle_string(self) -> None:
        data = self.storage._mark_task_data(
            {"type": TASK_MARK, "status": TASK_STATUS_PENDING}
        )
        self.assertIsInstance(data["status"], bool)


if __name__ == "__main__":
    unittest.main()
