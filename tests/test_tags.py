import unittest
from unittest.mock import MagicMock

from rsstag.tags import RssTagTags


class TestRssTagTagsStorage(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.storage = RssTagTags(self.db)

    def test_change_unread_creates_bulk_updates(self):
        self.storage.change_unread("alice", {"python": 2, "ai": 5}, readed=True)

        self.db.tags.bulk_write.assert_called_once()
        updates = self.db.tags.bulk_write.call_args.args[0]
        self.assertEqual(2, len(updates))
        self.assertEqual({"owner": "alice", "tag": "python"}, updates[0]._filter)
        self.assertEqual({"$inc": {"unread_count": -2}}, updates[0]._doc)
        self.assertEqual({"owner": "alice", "tag": "ai"}, updates[1]._filter)
        self.assertEqual({"$inc": {"unread_count": -5}}, updates[1]._doc)

    def test_get_all_builds_query_sort_and_options(self):
        cursor = MagicMock()
        cursor.allow_disk_use.return_value = cursor
        cursor.sort.return_value = cursor
        self.db.tags.find.return_value = cursor

        opts = {"regexp": "py", "offset": 3, "limit": 5}
        projection = {"tag": True}

        result = self.storage.get_all(
            "alice",
            only_unread=True,
            hot_tags=True,
            opts=opts,
            projection=projection,
        )

        self.assertIs(result, cursor)
        self.db.tags.find.assert_called_once_with(
            {
                "owner": "alice",
                "tag": {"$regex": "py", "$options": "i"},
                "unread_count": {"$gt": 0},
            },
            skip=3,
            limit=5,
            projection=projection,
        )
        cursor.allow_disk_use.assert_called_once_with(True)
        cursor.sort.assert_called_once_with(
            [("temperature", -1), ("unread_count", -1)]
        )

    def test_get_groups_accumulates_values_from_aggregation(self):
        self.db.tags.aggregate.return_value = [
            {"_id": ["tech", "python"], "counter": 2},
            {"_id": ["tech"], "counter": 1},
        ]

        groups = self.storage.get_groups("alice", only_unread=True)

        self.assertEqual({"tech": 2, "python": 1}, dict(groups))
        self.db.tags.aggregate.assert_called_once_with(
            [
                {
                    "$match": {
                        "owner": "alice",
                        "groups": {"$exists": True},
                        "unread_count": {"$gt": 0},
                    }
                },
                {"$group": {"_id": "$groups", "counter": {"$sum": 1}}},
            ]
        )


if __name__ == "__main__":
    unittest.main()
