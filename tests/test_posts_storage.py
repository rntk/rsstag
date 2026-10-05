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


    def test_prepare(self):
        from unittest.mock import call
        self.storage.prepare()
        self.assertEqual(self.db.posts.create_index.call_count, len(self.storage.indexes))
        calls = [call(idx) for idx in self.storage.indexes]
        self.db.posts.create_index.assert_has_calls(calls, any_order=True)

    def test_prepare_exception(self):
        self.db.posts.create_index.side_effect = Exception("test error")
        self.storage.prepare()
        self.assertEqual(self.db.posts.create_index.call_count, len(self.storage.indexes))

    def test_get_by_category(self):
        cursor = MagicMock()
        cursor.allow_disk_use.return_value = cursor
        cursor.sort.return_value = cursor
        self.db.posts.find.return_value = cursor

        result = self.storage.get_by_category(
            owner="alice",
            only_unread=True,
            category="tech",
            projection={"title": 1},
            context_tags=["ai"]
        )

        self.assertIs(result, cursor)
        self.db.posts.find.assert_called_once_with(
            {
                "owner": "alice",
                "category_id": "tech",
                "read": False,
                "tags": {"$all": ["ai"]}
            },
            projection={"title": 1}
        )
        cursor.allow_disk_use.assert_called_once_with(True)
        cursor.sort.assert_called_once_with([("feed_id", -1), ("unix_date", -1)])

    def test_get_all(self):
        cursor = MagicMock()
        self.db.posts.find.return_value = cursor

        result = self.storage.get_all(
            owner="alice",
            only_unread=False,
            projection={"title": 1}
        )

        self.assertIs(result, cursor)
        self.db.posts.find.assert_called_once_with(
            {
                "owner": "alice",
                "read": True
            },
            projection={"title": 1}
        )

    def test_get_grouped_stat(self):
        cursor = MagicMock()
        self.db.posts.aggregate.return_value = cursor

        result = self.storage.get_grouped_stat("alice", only_unread=True)

        self.assertIs(result, cursor)
        self.db.posts.aggregate.assert_called_once_with(
            [
                {"$match": {"owner": "alice", "read": False}},
                {
                    "$group": {
                        "_id": "$feed_id",
                        "category_id": {"$first": "$category_id"},
                        "count": {"$sum": 1},
                    }
                },
            ]
        )

    def test_get_by_feed_id(self):
        cursor = MagicMock()
        cursor.allow_disk_use.return_value = cursor
        cursor.sort.return_value = cursor
        self.db.posts.find.return_value = cursor

        result = self.storage.get_by_feed_id(
            owner="alice",
            feed_id="feed123",
            only_unread=True,
            projection={"title": 1},
            context_tags=["tag1"]
        )

        self.assertIs(result, cursor)
        self.db.posts.find.assert_called_once_with(
            {
                "owner": "alice",
                "feed_id": "feed123",
                "read": False,
                "tags": {"$all": ["tag1"]}
            },
            projection={"title": 1}
        )
        cursor.allow_disk_use.assert_called_once_with(True)
        cursor.sort.assert_called_once_with([("feed_id", -1), ("unix_date", -1)])

    def test_get_by_pid(self):
        self.db.posts.find_one.return_value = {"title": "test"}
        result = self.storage.get_by_pid("alice", "pid1", projection={"title": 1})
        self.assertEqual(result, {"title": "test"})
        self.db.posts.find_one.assert_called_once_with({"owner": "alice", "pid": "pid1"}, projection={"title": 1})

    def test_get_by_id(self):
        self.db.posts.find_one.return_value = {"title": "test"}
        result = self.storage.get_by_id("alice", "id1", projection={"title": 1})
        self.assertEqual(result, {"title": "test"})
        self.db.posts.find_one.assert_called_once_with({"owner": "alice", "id": "id1"}, projection={"title": 1})

    def test_get_by_pids(self):
        cursor = MagicMock()
        self.db.posts.find.return_value = cursor
        result = self.storage.get_by_pids("alice", ["pid1", "pid2"], projection={"title": 1})
        self.assertIs(result, cursor)
        self.db.posts.find.assert_called_once_with({"owner": "alice", "pid": {"$in": ["pid1", "pid2"]}}, projection={"title": 1})

    def test_get_by_tags_list(self):
        cursor = MagicMock()
        self.db.posts.find.return_value = cursor
        result = self.storage.get_by_tags_list("alice", ["tag1", "tag2"], only_unread=True, projection={"title": 1})
        self.assertIs(result, cursor)
        self.db.posts.find.assert_called_once_with({"owner": "alice", "tags": {"$in": ["tag1", "tag2"]}, "read": False}, projection={"title": 1})

    def test_get_by_query(self):
        cursor = MagicMock()
        self.db.posts.find.return_value = cursor
        result = self.storage.get_by_query({"query": "val"}, projection={"title": 1})
        self.assertIs(result, cursor)
        self.db.posts.find.assert_called_once_with({"query": "val"}, projection={"title": 1})

    def test_get_processing(self):
        cursor = MagicMock()
        self.db.posts.find.return_value = cursor
        result = self.storage.get_processing("alice")
        self.assertIs(result, cursor)
        self.db.posts.find.assert_called_once_with(
            {"owner": "alice", "processing": {"$ne": 0, "$exists": True}},
            projection={"pid": True, "title": True, "processing": True}
        )

    def test_reset_processing(self):
        self.storage.reset_processing("alice", "pid1")
        self.db.posts.update_one.assert_called_once_with(
            {"owner": "alice", "pid": "pid1"},
            {"$set": {"processing": 0}}
        )

    def test_change_status(self):
        result = self.storage.change_status("alice", ["pid1", "pid2"], True)
        self.assertTrue(result)
        self.db.posts.update_many.assert_called_once_with(
            {"owner": "alice", "pid": {"$in": ["pid1", "pid2"]}},
            {"$set": {"read": True}}
        )

    def test_get_by_clusters(self):
        cursor = MagicMock()
        cursor.allow_disk_use.return_value = cursor
        cursor.sort.return_value = cursor
        self.db.posts.find.return_value = cursor

        result = self.storage.get_by_clusters(
            owner="alice",
            clusters=["c1", "c2"],
            only_unread=True,
            projection={"title": 1},
            context_tags=["tag1"]
        )

        self.assertIs(result, cursor)
        self.db.posts.find.assert_called_once_with(
            {
                "owner": "alice",
                "clusters": {"$exists": True, "$elemMatch": {"$in": ["c1", "c2"]}},
                "read": False,
                "tags": {"$all": ["tag1"]}
            },
            projection={"title": 1}
        )
        cursor.allow_disk_use.assert_called_once_with(True)
        cursor.sort.assert_called_once_with([("feed_id", -1), ("unix_date", -1)])

    def test_get_clusters(self):
        posts = [
            {"clusters": ["c1", "c2"]},
            {"clusters": ["c2", "c3"]},
            {"other": "val"},
            {"clusters": []}
        ]
        result = self.storage.get_clusters(posts)
        self.assertEqual(result, {"c1", "c2", "c3"})

    def test_count(self):
        self.db.posts.count_documents.return_value = 42
        result = self.storage.count("alice")
        self.assertEqual(result, 42)
        self.db.posts.count_documents.assert_called_once_with({"owner": "alice"})

class TestPostLemmaSentence(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()

    def test_iter_no_split(self):
        import gzip
        from rsstag.posts import PostLemmaSentence
        sentence = PostLemmaSentence(self.db, "alice", split=False)
        self.db.posts.find.return_value = [
            {"lemmas": gzip.compress(b"word1 word2")},
            {"lemmas": gzip.compress(b"word3 word4")}
        ]

        result = list(sentence)
        self.assertEqual(result, ["word1 word2", "word3 word4"])
        self.db.posts.find.assert_called_once_with({"owner": "alice"}, projection={"lemmas": True})

    def test_iter_split(self):
        import gzip
        from rsstag.posts import PostLemmaSentence
        sentence = PostLemmaSentence(self.db, "alice", split=True)
        self.db.posts.find.return_value = [
            {"lemmas": gzip.compress(b"word1 word2")},
            {"lemmas": gzip.compress(b"word3 word4")}
        ]

        result = list(sentence)
        self.assertEqual(result, [["word1", "word2"], ["word3", "word4"]])
        self.db.posts.find.assert_called_once_with({"owner": "alice"}, projection={"lemmas": True})

    def test_count(self):
        from rsstag.posts import PostLemmaSentence
        sentence = PostLemmaSentence(self.db, "alice")
        self.db.posts.count_documents.return_value = 42
        result = sentence.count()
        self.assertEqual(result, 42)
        self.db.posts.count_documents.assert_called_once_with({"owner": "alice"})

if __name__ == "__main__":
    unittest.main()
