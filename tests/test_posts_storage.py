import unittest
from unittest.mock import MagicMock

from rsstag.posts import RssTagPosts


class TestRssTagPostsStorage(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.storage = RssTagPosts(self.db)

    def test_get_by_tags_merges_context_tags_without_duplicates(self):
        cursor = MagicMock()
        cursor.allow_disk_use.return_value = cursor
        cursor.sort.return_value = cursor
        self.db.posts.find.return_value = cursor

        result = self.storage.get_by_tags(
            owner="alice",
            tags=["python", "ai"],
            context_tags=["ai", "news"],
            only_unread=True,
        )

        self.assertIs(result, cursor)
        self.db.posts.find.assert_called_once_with(
            {
                "owner": "alice",
                "tags": {"$all": ["python", "ai", "news"]},
                "read": False,
            },
            projection=None,
        )
        cursor.allow_disk_use.assert_called_once_with(True)
        cursor.sort.assert_called_once_with([("feed_id", -1), ("unix_date", -1)])

    def test_set_clusters_creates_bulk_updates_for_each_cluster(self):
        similars = {"cluster-a": ["p1", "p2"], "cluster-b": ["p3"]}

        self.storage.set_clusters("alice", similars)

        self.db.posts.bulk_write.assert_called_once()
        operations = self.db.posts.bulk_write.call_args.args[0]
        self.assertEqual(2, len(operations))
        self.assertEqual(
            {"owner": "alice", "pid": {"$in": ["p1", "p2"]}},
            operations[0]._filter,
        )
        self.assertEqual(
            {"$addToSet": {"clusters": "cluster-a"}},
            operations[0]._doc,
        )

    def test_get_neighbors_by_unix_date_combines_before_and_after(self):
        before_cursor = MagicMock()
        before_cursor.sort.return_value.limit.return_value = [{"pid": "before"}]

        after_cursor = MagicMock()
        after_cursor.sort.return_value.limit.return_value = [{"pid": "after"}]

        self.db.posts.find.side_effect = [before_cursor, after_cursor]

        neighbors = self.storage.get_neighbors_by_unix_date(
            owner="alice", unix_date=1000, count=1, projection={"pid": True}
        )

        self.assertEqual([{"pid": "before"}, {"pid": "after"}], neighbors)
        self.assertEqual(2, self.db.posts.find.call_count)

    def test_get_stat_aggregates_read_and_unread_counts(self):
        self.db.posts.aggregate.return_value = [
            {"_id": True, "counter": 7},
            {"_id": False, "counter": 3},
        ]
        self.db.tags.count_documents.return_value = 11

        stat = self.storage.get_stat("alice")

        self.assertEqual({"read": 7, "unread": 3, "tags": 11}, stat)
        self.db.tags.count_documents.assert_called_once_with({"owner": "alice"})


if __name__ == "__main__":
    unittest.main()
