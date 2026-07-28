"""Tests for ProviderWorker.handle_feeds_list (the "refresh sources list"
task) and its shared _store_feeds dedup helper.

Sources can arrive from three different code paths: a sources-list refresh
(no posts), a posts download, and a raw-to-posts conversion. The single most
important property of this feature is that none of those paths ever produces
a second ``feeds`` row for a source that is already stored. These tests use a
real (disposable) MongoDB database via ``DBHelper`` for the ``feeds``/
``posts`` collections -- exactly the kind of state-across-calls dedup check
that a mocked collection cannot verify -- while providers/users/tasks stay
mocked, matching the rest of the ProviderWorker test suite.
"""

import socket
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock

from pymongo.database import Database

from rsstag.providers.feed_docs import build_feed_doc
from rsstag.web.browse import _build_available_sources
from rsstag.web.routes import RSSTagRoutes
from rsstag.workers.provider_worker import ProviderWorker
from tests.db_utils import DBHelper


def _require_test_mongo() -> None:
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=1):
            pass
    except OSError as exc:
        raise unittest.SkipTest(
            f"MongoDB on port 8765 is required for provider worker feeds-list "
            f"tests: {exc}"
        )


class TestHandleFeedsListDeduplication(unittest.TestCase):
    """DB-backed: covers the actual dedup contract of _store_feeds."""

    db_helper: DBHelper
    test_db: Database

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _require_test_mongo()
        cls.db_helper = DBHelper(port=8765)
        try:
            cls.db_helper.client.admin.command("ping")
        except Exception as exc:
            cls.db_helper.close()
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for provider worker "
                f"feeds-list tests: {exc}"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db_helper.close()
        super().tearDownClass()

    def setUp(self) -> None:
        self.db: Database = self.db_helper.create_test_db()
        self.mock_users: MagicMock = MagicMock()
        self.mock_tasks: MagicMock = MagicMock()
        self.mock_provider: MagicMock = MagicMock()
        self.providers: Dict[str, Any] = {"test_provider": self.mock_provider}
        self.record_bulk_write: MagicMock = MagicMock()
        self.worker: ProviderWorker = ProviderWorker(
            db=self.db,
            config={},
            providers=self.providers,
            users=self.mock_users,
            tasks=self.mock_tasks,
            record_bulk_write=self.record_bulk_write,
        )
        self.owner: str = "alice"
        self.mock_users.get_provider_user.return_value = {"token": "abc"}

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)

    def _task(self) -> Dict[str, Any]:
        return {
            "_id": "task-1",
            "user": {"sid": self.owner},
            "data": {"provider": "test_provider"},
        }

    def _feed(self, feed_id: Any, title: str) -> Dict[str, Any]:
        return {
            "feed_id": str(feed_id),
            "title": title,
            "owner": self.owner,
            "category_id": "NotCategorized",
            "provider": "test_provider",
        }

    def test_two_refreshes_with_same_output_leave_one_doc_per_feed(self) -> None:
        feeds: List[Dict[str, Any]] = [
            self._feed("1", "Feed One"),
            self._feed("2", "Feed Two"),
        ]
        self.mock_provider.list_feeds.return_value = feeds

        self.assertTrue(self.worker.handle_feeds_list(self._task()))
        self.assertTrue(self.worker.handle_feeds_list(self._task()))

        stored: List[Dict[str, Any]] = list(self.db.feeds.find({"owner": self.owner}))
        self.assertEqual(len(stored), 2)
        self.assertEqual({f["feed_id"] for f in stored}, {"1", "2"})

    def test_refresh_then_download_leaves_one_doc_per_feed(self) -> None:
        self.mock_provider.list_feeds.return_value = [self._feed("1", "Feed One")]
        self.assertTrue(self.worker.handle_feeds_list(self._task()))

        # A posts download for the same provider offers the same feed again,
        # this time alongside a post.
        self.mock_provider.download.return_value = [
            (
                [{"id": 1, "pid": "test_provider:1:1"}],
                [self._feed("1", "Feed One")],
            )
        ]
        download_task: Dict[str, Any] = {
            "user": {"sid": self.owner},
            "data": {"provider": "test_provider"},
        }
        self.assertTrue(self.worker.handle_download(download_task))

        stored: List[Dict[str, Any]] = list(self.db.feeds.find({"owner": self.owner}))
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["feed_id"], "1")

    def test_duplicates_inside_a_single_batch_collapse(self) -> None:
        self.mock_provider.list_feeds.return_value = [
            self._feed("1", "Feed One (first copy)"),
            self._feed("1", "Feed One (second copy)"),
            self._feed("2", "Feed Two"),
        ]

        self.assertTrue(self.worker.handle_feeds_list(self._task()))

        stored: List[Dict[str, Any]] = list(self.db.feeds.find({"owner": self.owner}))
        self.assertEqual(len(stored), 2)
        by_id = {f["feed_id"]: f for f in stored}
        self.assertEqual(by_id["1"]["title"], "Feed One (first copy)")

    def test_renamed_source_updates_title_instead_of_inserting_second_doc(
        self,
    ) -> None:
        self.mock_provider.list_feeds.return_value = [self._feed("1", "Old Name")]
        self.assertTrue(self.worker.handle_feeds_list(self._task()))

        self.mock_provider.list_feeds.return_value = [self._feed("1", "New Name")]
        self.assertTrue(self.worker.handle_feeds_list(self._task()))

        stored: List[Dict[str, Any]] = list(self.db.feeds.find({"owner": self.owner}))
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["title"], "New Name")

    def test_download_does_not_overwrite_title_refreshed_by_sources_list(
        self,
    ) -> None:
        """handle_download stores feeds with refresh_titles=False: a rename
        picked up by a later sources-list refresh must not be clobbered back
        by a download that still offers the old title from a stale batch."""
        self.mock_provider.list_feeds.return_value = [self._feed("1", "Renamed")]
        self.assertTrue(self.worker.handle_feeds_list(self._task()))

        self.mock_provider.download.return_value = [
            (
                [{"id": 1, "pid": "test_provider:1:1"}],
                [self._feed("1", "Stale Old Name")],
            )
        ]
        download_task: Dict[str, Any] = {
            "user": {"sid": self.owner},
            "data": {"provider": "test_provider"},
        }
        self.assertTrue(self.worker.handle_download(download_task))

        stored: List[Dict[str, Any]] = list(self.db.feeds.find({"owner": self.owner}))
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["title"], "Renamed")


class TestHandleFeedsListErrorPaths(unittest.TestCase):
    """Mock-only: matches the style of test_provider_worker.py."""

    def setUp(self) -> None:
        self.mock_db: MagicMock = MagicMock()
        self.mock_users: MagicMock = MagicMock()
        self.mock_tasks: MagicMock = MagicMock()
        self.record_bulk_write: MagicMock = MagicMock()

    def _worker(self, providers: Dict[str, Any]) -> ProviderWorker:
        return ProviderWorker(
            db=self.mock_db,
            config={},
            providers=providers,
            users=self.mock_users,
            tasks=self.mock_tasks,
            record_bulk_write=self.record_bulk_write,
        )

    def test_provider_without_list_feeds_fails_cleanly(self) -> None:
        provider_without_list_feeds: MagicMock = MagicMock(spec=["download"])
        worker: ProviderWorker = self._worker(
            {"test_provider": provider_without_list_feeds}
        )
        self.mock_users.get_provider_user.return_value = {"token": "abc"}
        task: Dict[str, Any] = {
            "_id": "task-1",
            "user": {"sid": "alice"},
            "data": {"provider": "test_provider"},
        }

        result = worker.handle_feeds_list(task)

        self.assertFalse(result)
        self.mock_tasks.mark_task_failed.assert_called_once()
        self.assertEqual(self.mock_tasks.mark_task_failed.call_args[0][0], "task-1")
        self.mock_db.feeds.insert_many.assert_not_called()

    def test_unknown_provider_fails_cleanly(self) -> None:
        worker: ProviderWorker = self._worker({})
        self.mock_users.get_provider_user.return_value = {"token": "abc"}
        task: Dict[str, Any] = {
            "_id": "task-1",
            "user": {"sid": "alice"},
            "data": {"provider": "missing_provider"},
        }

        result = worker.handle_feeds_list(task)

        self.assertFalse(result)
        self.mock_tasks.mark_task_failed.assert_called_once_with(
            "task-1", "Unknown provider missing_provider"
        )
        self.mock_db.feeds.insert_many.assert_not_called()

    def test_user_without_provider_credentials_returns_true_without_writing(
        self,
    ) -> None:
        worker: ProviderWorker = self._worker({"test_provider": MagicMock()})
        self.mock_users.get_provider_user.return_value = None
        task: Dict[str, Any] = {
            "_id": "task-1",
            "user": {"sid": "alice"},
            "data": {"provider": "test_provider"},
        }

        result = worker.handle_feeds_list(task)

        self.assertTrue(result)
        self.mock_db.feeds.insert_many.assert_not_called()
        self.mock_tasks.mark_task_failed.assert_not_called()

    def test_provider_error_marks_task_failed_and_clears_in_queue(self) -> None:
        provider: MagicMock = MagicMock()
        provider.list_feeds.side_effect = Exception("boom")
        worker: ProviderWorker = self._worker({"test_provider": provider})
        self.mock_users.get_provider_user.return_value = {"token": "abc"}
        task: Dict[str, Any] = {
            "_id": "task-1",
            "user": {"sid": "alice"},
            "data": {"provider": "test_provider"},
        }

        result = worker.handle_feeds_list(task)

        self.assertFalse(result)
        self.mock_tasks.mark_task_failed.assert_called_once()
        self.mock_users.update_by_sid.assert_any_call(
            "alice", {"in_queue.test_provider": False}
        )


class TestDiscoveredSourcesReachTheCategoriesPage(unittest.TestCase):
    """End to end: refreshed sources are stored and land in the page data.

    The refresh only pays off if a source discovered without any post shows
    up under "available sources" on the categories page with a usable link,
    so this drives the real documents a provider builds all the way to
    ``_build_available_sources``.
    """

    db_helper: DBHelper
    test_db: Database

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _require_test_mongo()
        cls.db_helper = DBHelper(port=8765)
        try:
            cls.db_helper.client.admin.command("ping")
        except Exception as exc:
            cls.db_helper.close()
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for the sources page test: {exc}"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db_helper.close()
        super().tearDownClass()

    def setUp(self) -> None:
        self.db: Database = self.db_helper.create_test_db()
        self.owner: str = "alice"
        self.mock_users: MagicMock = MagicMock()
        self.mock_users.get_provider_user.return_value = {"sid": self.owner}
        self.mock_provider: MagicMock = MagicMock()
        self.worker: ProviderWorker = ProviderWorker(
            db=self.db,
            config={},
            providers={"telegram": self.mock_provider},
            users=self.mock_users,
            tasks=MagicMock(),
            record_bulk_write=MagicMock(),
        )

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)

    def test_refreshed_source_appears_as_an_available_source(self) -> None:
        routes: RSSTagRoutes = RSSTagRoutes("localhost")
        # A real telegram chat id is a large negative number.
        self.mock_provider.list_feeds.return_value = [
            build_feed_doc(
                owner=self.owner,
                feed_id=-1001234567890,
                title="Some channel",
                provider="telegram",
                routes=routes,
                category_id="NotCategorized",
            )
        ]

        self.assertTrue(
            self.worker.handle_feeds_list(
                {
                    "_id": "task-1",
                    "user": {"sid": self.owner},
                    "data": {"provider": "telegram"},
                }
            )
        )

        stored: List[Dict[str, Any]] = list(self.db.feeds.find({"owner": self.owner}))
        # Nothing was downloaded, so the unread listing shows no feed at all.
        sources: List[Dict[str, Any]] = _build_available_sources(
            stored, set(), {}
        )

        self.assertEqual(len(sources), 1)
        source: Dict[str, Any] = sources[0]
        self.assertEqual(source["feed_id"], "-1001234567890")
        self.assertEqual(source["title"], "Some channel")
        self.assertEqual(source["provider"], "telegram")
        self.assertEqual(source["url"], "/feed/-1001234567890")
        self.assertEqual(source["category_title"], "NotCategorized")

    def test_source_with_unread_posts_is_not_repeated_as_available(self) -> None:
        routes: RSSTagRoutes = RSSTagRoutes("localhost")
        self.mock_provider.list_feeds.return_value = [
            build_feed_doc(
                owner=self.owner,
                feed_id=-100,
                title="Read me",
                provider="telegram",
                routes=routes,
                category_id="NotCategorized",
            )
        ]
        self.assertTrue(
            self.worker.handle_feeds_list(
                {
                    "_id": "task-1",
                    "user": {"sid": self.owner},
                    "data": {"provider": "telegram"},
                }
            )
        )

        stored: List[Dict[str, Any]] = list(self.db.feeds.find({"owner": self.owner}))
        sources: List[Dict[str, Any]] = _build_available_sources(
            stored, {"-100"}, {}
        )

        self.assertEqual(sources, [])


if __name__ == "__main__":
    unittest.main()
