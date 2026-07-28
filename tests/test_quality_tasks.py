import sys
import types
import unittest
from unittest.mock import MagicMock

# rsstag.tasks imports modules with runtime type issues in this environment.
sys.modules.setdefault(
    "rsstag.post_grouping", types.SimpleNamespace(RssTagPostGrouping=object)
)
sys.modules.setdefault("rsstag.tags", types.SimpleNamespace(RssTagTags=object))

from typing import Any, Dict

from rsstag.quality import build_scope_key
from rsstag.tasks import (
    RssTagTasks,
    SCOPE_CAPABILITY_SCOPED_SUPPORTED,
    SCOPE_MODE_CATEGORIES,
    SCOPE_MODE_FEEDS,
    TASK_POST_QUALITY,
    TASK_SOURCE_QUALITY,
    get_task_scope_capability,
)


class TestQualityTaskRegistration(unittest.TestCase):
    """Registry entries whose absence would fail silently at runtime."""

    def setUp(self):
        self.db = MagicMock()
        self.storage = RssTagTasks(self.db)

    def test_both_quality_tasks_support_scope(self):
        for task_type in (TASK_POST_QUALITY, TASK_SOURCE_QUALITY):
            with self.subTest(task_type=task_type):
                self.assertEqual(
                    get_task_scope_capability(task_type),
                    SCOPE_CAPABILITY_SCOPED_SUPPORTED,
                )

    def test_category_scope_is_accepted(self):
        ok, error = self.storage.validate_task_scope(
            TASK_POST_QUALITY,
            {"mode": SCOPE_MODE_CATEGORIES, "category_ids": ["tech"]},
        )

        self.assertTrue(ok, error)

    def test_both_quality_tasks_have_titles(self):
        for task_type in (TASK_POST_QUALITY, TASK_SOURCE_QUALITY):
            with self.subTest(task_type=task_type):
                self.assertTrue(self.storage.get_task_title(task_type))


class TestQualityTaskEnqueue(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.storage = RssTagTasks(self.db)
        self.storage._state = MagicMock()
        self.storage._state.enqueue.return_value = True

    def _add(self, category_id: str) -> Dict[str, Any]:
        self.storage.add_task(
            {
                "user": "alice",
                "type": TASK_POST_QUALITY,
                "host": "localhost",
                "scope": {
                    "mode": SCOPE_MODE_CATEGORIES,
                    "category_ids": [category_id],
                },
            }
        )
        return self.storage._state.enqueue.call_args[0][0]

    def test_scope_reaches_the_task_doc(self):
        self.storage.add_task(
            {
                "user": "alice",
                "type": TASK_POST_QUALITY,
                "host": "localhost",
                "scope": {"mode": SCOPE_MODE_FEEDS, "feed_ids": ["f1"]},
            }
        )

        fields = self.storage._state.enqueue.call_args[0][1]
        self.assertEqual(fields["scope"]["mode"], SCOPE_MODE_FEEDS)
        self.assertEqual(fields["scope"]["feed_ids"], ["f1"])

    def test_two_categories_queue_independently(self):
        first_key = self._add("tech")
        second_key = self._add("news")

        self.assertNotEqual(first_key["scope_key"], second_key["scope_key"])

    def test_same_category_reuses_one_queue_slot(self):
        self.assertEqual(self._add("tech")["scope_key"], self._add("tech")["scope_key"])

    def test_scope_key_matches_the_normalized_scope(self):
        key = self._add("tech")

        self.assertEqual(
            key["scope_key"],
            build_scope_key(
                {
                    "mode": SCOPE_MODE_CATEGORIES,
                    "post_ids": [],
                    "feed_ids": [],
                    "category_ids": ["tech"],
                    "provider": "",
                }
            ),
        )


class TestQualityTaskClaim(unittest.TestCase):
    """The pending marker must agree across claim, count and drain check."""

    def setUp(self):
        self.db = MagicMock()
        self.storage = RssTagTasks(self.db)
        self.storage._state = MagicMock()
        self.users = MagicMock()
        self.users.get_by_sid.return_value = {"sid": "alice", "settings": {}}

        self.task_doc = {
            "_id": "task-1",
            "user": "alice",
            "type": TASK_POST_QUALITY,
            "manual": True,
            "scope": {"mode": SCOPE_MODE_FEEDS, "feed_ids": ["f1"]},
        }
        self.storage._state.claim.return_value = self.task_doc

    def _set_pending_posts(self, posts):
        cursor = MagicMock()
        cursor.limit.return_value = posts
        self.db.posts.find.return_value = cursor
        self.db.posts.count_documents.return_value = len(posts)

    def test_claims_unscored_posts_within_scope(self):
        self._set_pending_posts([{"_id": "p1", "pid": "pid1"}])

        task = self.storage.get_task(self.users)

        self.assertEqual(task["type"], TASK_POST_QUALITY)
        self.assertEqual(len(task["data"]), 1)
        query = self.db.posts.find.call_args[0][0]
        self.assertEqual(query["quality"], {"$exists": False})
        self.assertEqual(query["feed_id"], {"$in": ["f1"]})

    def test_locks_the_posts_it_claimed(self):
        self._set_pending_posts([{"_id": "p1", "pid": "pid1"}])

        self.storage.get_task(self.users)

        query, update = self.db.posts.update_many.call_args[0]
        self.assertEqual(query, {"_id": {"$in": ["p1"]}})
        self.assertGreater(update["$set"]["processing"], 0)

    def test_completes_once_every_post_in_scope_is_scored(self):
        self._set_pending_posts([])

        task = self.storage.get_task(self.users)

        self.assertEqual(task["type"], 0)
        self.storage._state.complete.assert_called_once_with("task-1")

    def test_a_drained_scan_does_not_queue_a_rollup(self) -> None:
        self._set_pending_posts([])
        self.storage.add_task = MagicMock(return_value=True)

        self.storage.get_task(self.users)

        self.storage.add_task.assert_not_called()
        self.storage._state.complete.assert_called_once_with("task-1")

    def test_no_rollup_is_queued_while_posts_remain(self):
        cursor = MagicMock()
        cursor.limit.return_value = []
        self.db.posts.find.return_value = cursor
        self.db.posts.count_documents.return_value = 5
        self.storage.add_task = MagicMock(return_value=True)

        self.storage.get_task(self.users)

        self.storage.add_task.assert_not_called()

    def test_stays_queued_while_posts_remain_but_are_locked(self):
        cursor = MagicMock()
        cursor.limit.return_value = []
        self.db.posts.find.return_value = cursor
        self.db.posts.count_documents.return_value = 7

        self.storage.get_task(self.users)

        self.storage._state.complete.assert_not_called()
        self.storage._state.release.assert_called_once_with("task-1")


class TestQualityTaskFinish(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.storage = RssTagTasks(self.db)
        self.storage._state = MagicMock()

    def test_finish_releases_locks_and_keeps_the_task_queued(self):
        task = {
            "_id": "task-1",
            "type": TASK_POST_QUALITY,
            "manual": True,
            "user": {"sid": "alice"},
            "data": [{"_id": "p1"}, {"_id": "p2"}],
        }

        self.assertTrue(self.storage.finish_task(task))

        self.storage._state.complete.assert_not_called()
        updates = self.db.posts.bulk_write.call_args[0][0]
        self.assertEqual(len(updates), 2)

    def test_finish_does_not_overwrite_the_quality_marker(self):
        task = {
            "_id": "task-1",
            "type": TASK_POST_QUALITY,
            "manual": True,
            "user": {"sid": "alice"},
            "data": [{"_id": "p1"}],
        }

        self.storage.finish_task(task)

        update = self.db.posts.bulk_write.call_args[0][0][0]._doc
        self.assertNotIn("quality", update["$set"])

    def test_pending_count_uses_the_same_marker_as_the_claim(self):
        self.db.posts.count_documents.return_value = 3

        count = self.storage._count_pending_quality_posts(
            "alice",
            {"scope": {"mode": SCOPE_MODE_FEEDS, "feed_ids": ["f1"]}},
        )

        self.assertEqual(count, 3)
        query = self.db.posts.count_documents.call_args[0][0]
        self.assertEqual(query["quality"], {"$exists": False})
        self.assertEqual(query["feed_id"], {"$in": ["f1"]})


if __name__ == "__main__":
    unittest.main()
