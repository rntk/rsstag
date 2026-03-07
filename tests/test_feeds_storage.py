import unittest
from unittest.mock import MagicMock, call

from rsstag.feeds import RssTagFeeds


class TestRssTagFeedsStorage(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.storage = RssTagFeeds(self.db)

    def test_prepare_creates_all_indexes(self):
        self.storage.prepare()

        self.assertEqual(self.db.feeds.create_index.call_count, len(self.storage.indexes))
        self.db.feeds.create_index.assert_has_calls(
            [call(index) for index in self.storage.indexes], any_order=True
        )

    def test_prepare_ignores_index_creation_errors(self):
        self.db.feeds.create_index.side_effect = Exception("already exists")

        self.storage.prepare()

        self.assertEqual(self.db.feeds.create_index.call_count, len(self.storage.indexes))

    def test_get_by_category_filters_by_category_when_not_all(self):
        cursor = MagicMock()
        self.db.feeds.find.return_value = cursor

        result = self.storage.get_by_category(
            owner="alice", category="tech", projection={"title": 1}
        )

        self.assertIs(result, cursor)
        self.db.feeds.find.assert_called_once_with(
            {"owner": "alice", "category_id": "tech"}, projection={"title": 1}
        )

    def test_get_by_category_skips_category_filter_for_all(self):
        cursor = MagicMock()
        self.db.feeds.find.return_value = cursor

        result = self.storage.get_by_category(
            owner="alice", category=self.storage.all_feeds, projection={"title": 1}
        )

        self.assertIs(result, cursor)
        self.db.feeds.find.assert_called_once_with(
            {"owner": "alice"}, projection={"title": 1}
        )

    def test_get_all(self):
        cursor = MagicMock()
        self.db.feeds.find.return_value = cursor

        result = self.storage.get_all(owner="alice", projection={"title": 1})

        self.assertIs(result, cursor)
        self.db.feeds.find.assert_called_once_with(
            {"owner": "alice"}, projection={"title": 1}
        )

    def test_get_by_feed_id(self):
        self.db.feeds.find_one.return_value = {"feed_id": "f-1"}

        result = self.storage.get_by_feed_id(owner="alice", feed_id="f-1")

        self.assertEqual({"feed_id": "f-1"}, result)
        self.db.feeds.find_one.assert_called_once_with({"owner": "alice", "feed_id": "f-1"})

    def test_get_by_categories(self):
        cursor = MagicMock()
        self.db.feeds.find.return_value = cursor

        result = self.storage.get_by_categories(
            owner="alice", categories=["tech", "science"], projection={"title": 1}
        )

        self.assertIs(result, cursor)
        self.db.feeds.find.assert_called_once_with(
            {"owner": "alice", "category_id": {"$in": ["tech", "science"]}},
            projection={"title": 1},
        )

    def test_get_by_feed_ids(self):
        cursor = MagicMock()
        self.db.feeds.find.return_value = cursor

        result = self.storage.get_by_feed_ids(
            owner="alice", feed_ids=["f-1", "f-2"], projection={"title": 1}
        )

        self.assertIs(result, cursor)
        self.db.feeds.find.assert_called_once_with(
            {"owner": "alice", "feed_id": {"$in": ["f-1", "f-2"]}},
            projection={"title": 1},
        )


if __name__ == "__main__":
    unittest.main()
