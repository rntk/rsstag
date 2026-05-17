import unittest
from unittest.mock import MagicMock, call

from pymongo import DESCENDING, UpdateOne

from rsstag.bi_grams import RssTagBiGrams


class TestRssTagBiGramsStorage(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.storage = RssTagBiGrams(self.db)
        self.storage.log = MagicMock()

    # ------------------------------------------------------------------
    # prepare
    # ------------------------------------------------------------------
    def test_prepare_creates_all_indexes(self):
        self.storage.prepare()

        self.assertEqual(
            self.db.bi_grams.create_index.call_count, len(self.storage.indexes)
        )
        self.db.bi_grams.create_index.assert_has_calls(
            [call(index) for index in self.storage.indexes], any_order=True
        )

    def test_prepare_swallows_index_creation_errors(self):
        self.db.bi_grams.create_index.side_effect = Exception("already exists")

        self.storage.prepare()

        self.assertEqual(
            self.db.bi_grams.create_index.call_count, len(self.storage.indexes)
        )

    # ------------------------------------------------------------------
    # get_by_bi_gram
    # ------------------------------------------------------------------
    def test_get_by_bi_gram(self):
        self.db.bi_grams.find_one.return_value = {"owner": "alice", "tag": "foo bar"}

        result = self.storage.get_by_bi_gram("alice", "foo bar")

        self.assertEqual(result, {"owner": "alice", "tag": "foo bar"})
        self.db.bi_grams.find_one.assert_called_once_with(
            {"owner": "alice", "tag": "foo bar"}
        )

    # ------------------------------------------------------------------
    # get_by_tags
    # ------------------------------------------------------------------
    def _mock_find_chain(self):
        cursor = MagicMock()
        self.db.bi_grams.find.return_value = cursor
        cursor.allow_disk_use.return_value = cursor
        cursor.sort.return_value = cursor
        return cursor

    def test_get_by_tags_basic(self):
        cursor = self._mock_find_chain()

        result = self.storage.get_by_tags("alice", ["foo", "bar"])

        self.assertIs(result, cursor)
        self.db.bi_grams.find.assert_called_once_with(
            {"owner": "alice", "tags": {"$all": ["foo", "bar"]}},
            projection=None,
        )
        cursor.allow_disk_use.assert_called_once_with(True)
        cursor.sort.assert_called_once_with([("posts_count", DESCENDING)])

    def test_get_by_tags_only_unread(self):
        cursor = self._mock_find_chain()

        result = self.storage.get_by_tags("alice", ["foo", "bar"], only_unread=True)

        self.assertIs(result, cursor)
        self.db.bi_grams.find.assert_called_once_with(
            {
                "owner": "alice",
                "tags": {"$all": ["foo", "bar"]},
                "unread_count": {"$gt": 0},
            },
            projection=None,
        )
        cursor.allow_disk_use.assert_called_once_with(True)
        cursor.sort.assert_called_once_with([("unread_count", DESCENDING)])

    def test_get_by_tags_with_projection(self):
        cursor = self._mock_find_chain()

        result = self.storage.get_by_tags("alice", ["foo"], projection={"tag": 1})

        self.assertIs(result, cursor)
        self.db.bi_grams.find.assert_called_once_with(
            {"owner": "alice", "tags": {"$all": ["foo"]}},
            projection={"tag": 1},
        )

    # ------------------------------------------------------------------
    # change_unread
    # ------------------------------------------------------------------
    def test_change_unread(self):
        tags = {"foo": 3, "bar": 5}

        result = self.storage.change_unread("alice", tags, readed=True)

        self.assertTrue(result)
        self.db.bi_grams.bulk_write.assert_called_once()
        args, kwargs = self.db.bi_grams.bulk_write.call_args
        updates = args[0]
        self.assertEqual(len(updates), 2)
        for u in updates:
            self.assertIsInstance(u, UpdateOne)
        self.assertEqual(kwargs, {"ordered": False})

        # Verify the inc values are negative when readed=True
        mapping = {
            u._filter["tag"]: u._doc["$inc"]["unread_count"] for u in updates
        }
        self.assertEqual(mapping, {"foo": -3, "bar": -5})

    def test_change_unread_empty_tags(self):
        result = self.storage.change_unread("alice", {}, readed=True)

        self.assertTrue(result)
        self.db.bi_grams.bulk_write.assert_not_called()

    # ------------------------------------------------------------------
    # count
    # ------------------------------------------------------------------
    def test_count_basic(self):
        self.db.bi_grams.count_documents.return_value = 42

        result = self.storage.count("alice")

        self.assertEqual(result, 42)
        self.db.bi_grams.count_documents.assert_called_once_with({"owner": "alice"})

    def test_count_with_regexp(self):
        self.storage.count("alice", regexp="^foo")

        self.db.bi_grams.count_documents.assert_called_once_with(
            {"owner": "alice", "tag": {"$regex": "^foo", "$options": "i"}}
        )

    def test_count_only_unread(self):
        self.storage.count("alice", only_unread=True)

        self.db.bi_grams.count_documents.assert_called_once_with(
            {"owner": "alice", "unread_count": {"$gt": 0}}
        )

    def test_count_with_sentiments(self):
        self.storage.count("alice", sentiments=["positive", "neutral"])

        self.db.bi_grams.count_documents.assert_called_once_with(
            {
                "owner": "alice",
                "$and": [
                    {"sentiment": {"$exists": True}},
                    {"sentiment": {"$all": ["positive", "neutral"]}},
                ],
            }
        )

    def test_count_with_groups(self):
        self.storage.count("alice", groups=["g1", "g2"])

        self.db.bi_grams.count_documents.assert_called_once_with(
            {
                "owner": "alice",
                "$and": [
                    {"groups": {"$exists": True}},
                    {"groups": {"$all": ["g1", "g2"]}},
                ],
            }
        )

    def test_count_sentiments_and_groups_overwrite_bug(self):
        """Documents the bug where sentiments $and is overwritten by groups $and."""
        self.storage.count("alice", sentiments=["pos"], groups=["g1"])

        query = self.db.bi_grams.count_documents.call_args[0][0]
        self.assertEqual(
            query,
            {
                "owner": "alice",
                "$and": [
                    {"groups": {"$exists": True}},
                    {"groups": {"$all": ["g1"]}},
                ],
            },
        )

    def test_count_with_context_tags(self):
        self.storage.count("alice", context_tags=["foo", "bar"])

        self.db.bi_grams.count_documents.assert_called_once_with(
            {"owner": "alice", "tags": {"$all": ["foo", "bar"]}}
        )

    def test_count_combined(self):
        self.storage.count(
            "alice",
            only_unread=True,
            regexp="foo",
            context_tags=["bar"],
        )

        self.db.bi_grams.count_documents.assert_called_once_with(
            {
                "owner": "alice",
                "tag": {"$regex": "foo", "$options": "i"},
                "unread_count": {"$gt": 0},
                "tags": {"$all": ["bar"]},
            }
        )

    # ------------------------------------------------------------------
    # get_all
    # ------------------------------------------------------------------
    def test_get_all_basic(self):
        cursor = self._mock_find_chain()

        result = self.storage.get_all("alice")

        self.assertIs(result, cursor)
        self.db.bi_grams.find.assert_called_once_with({"owner": "alice"})
        cursor.allow_disk_use.assert_called_once_with(True)
        cursor.sort.assert_called_once_with([("posts_count", DESCENDING)])

    def test_get_all_with_opts(self):
        cursor = self._mock_find_chain()

        result = self.storage.get_all(
            "alice", opts={"offset": 10, "limit": 5, "regexp": "test"}
        )

        self.assertIs(result, cursor)
        self.db.bi_grams.find.assert_called_once_with(
            {"owner": "alice", "tag": {"$regex": "test", "$options": "i"}},
            skip=10,
            limit=5,
        )

    def test_get_all_hot_tags(self):
        cursor = self._mock_find_chain()

        result = self.storage.get_all("alice", hot_tags=True)

        self.assertIs(result, cursor)
        cursor.sort.assert_called_once_with(
            [("temperature", DESCENDING), ("posts_count", DESCENDING)]
        )

    def test_get_all_only_unread(self):
        cursor = self._mock_find_chain()

        result = self.storage.get_all("alice", only_unread=True)

        self.assertIs(result, cursor)
        self.db.bi_grams.find.assert_called_once_with(
            {"owner": "alice", "unread_count": {"$gt": 0}}
        )
        cursor.sort.assert_called_once_with([("unread_count", DESCENDING)])

    def test_get_all_with_context_tags_and_projection(self):
        cursor = self._mock_find_chain()

        result = self.storage.get_all(
            "alice", context_tags=["foo"], projection={"tag": 1}
        )

        self.assertIs(result, cursor)
        self.db.bi_grams.find.assert_called_once_with(
            {"owner": "alice", "tags": {"$all": ["foo"]}},
            projection={"tag": 1},
        )

    # ------------------------------------------------------------------
    # set_temperature
    # ------------------------------------------------------------------
    def test_set_temperature(self):
        result = self.storage.set_temperature("alice", "foo bar", 0.5)

        self.assertTrue(result)
        self.db.bi_grams.update_one.assert_called_once_with(
            {"owner": "alice", "tag": "foo bar"},
            {"$set": {"temperature": 0.5}},
        )

    # ------------------------------------------------------------------
    # set_temperatures
    # ------------------------------------------------------------------
    def test_set_temperatures(self):
        values = {"foo": 0.1, "bar": 0.2}

        result = self.storage.set_temperatures("alice", values)

        self.assertTrue(result)
        self.db.bi_grams.bulk_write.assert_called_once()
        args, kwargs = self.db.bi_grams.bulk_write.call_args
        updates = args[0]
        self.assertEqual(len(updates), 2)
        for u in updates:
            self.assertIsInstance(u, UpdateOne)
        self.assertEqual(kwargs, {"ordered": False})

        mapping = {u._filter["tag"]: u._doc["$set"]["temperature"] for u in updates}
        self.assertEqual(mapping, {"foo": 0.1, "bar": 0.2})

    def test_set_temperatures_empty_values(self):
        result = self.storage.set_temperatures("alice", {})

        self.assertTrue(result)
        self.db.bi_grams.bulk_write.assert_not_called()

    # ------------------------------------------------------------------
    # remove_by_count
    # ------------------------------------------------------------------
    def test_remove_by_count(self):
        result = self.storage.remove_by_count("alice", 3)

        self.assertTrue(result)
        self.db.bi_grams.delete_many.assert_called_once_with(
            {"owner": "alice", "posts_count": 3}
        )
        delete_result = self.db.bi_grams.delete_many.return_value
        self.storage.log.info.assert_called_once_with(
            "Deleted bigrams: %d for %s", delete_result.deleted_count, "alice"
        )


if __name__ == "__main__":
    unittest.main()
