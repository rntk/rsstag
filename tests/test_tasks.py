import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# rsstag.tasks imports modules with runtime type issues in this environment.
sys.modules.setdefault("rsstag.post_grouping", types.SimpleNamespace(RssTagPostGrouping=object))
sys.modules.setdefault("rsstag.tags", types.SimpleNamespace(RssTagTags=object))

from rsstag.tasks import (
    RssTagTasks,
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


if __name__ == "__main__":
    unittest.main()
