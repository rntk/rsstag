import unittest
from unittest.mock import MagicMock, call

from rsstag.letters import RssTagLetters


class TestRssTagLettersStorage(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.storage = RssTagLetters(self.db)

    def test_prepare_creates_all_indexes(self):
        self.storage.prepare()

        self.assertEqual(self.db.letters.create_index.call_count, len(self.storage.indexes))
        self.db.letters.create_index.assert_has_calls(
            [call(index) for index in self.storage.indexes], any_order=True
        )

    def test_get_returns_empty_dict_when_nothing_found(self):
        self.db.letters.find_one.return_value = None

        result = self.storage.get(owner="alice")

        self.assertEqual({}, result)
        self.db.letters.find_one.assert_called_once_with({"owner": "alice"})

    def test_get_sorts_letters_when_requested(self):
        self.db.letters.find_one.return_value = {
            "owner": "alice",
            "letters": {
                "z": {"letter": "z", "unread_count": 1},
                "a": {"letter": "a", "unread_count": 2},
            },
        }

        result = self.storage.get(owner="alice", make_sort=True)

        self.assertEqual(["a", "z"], list(result["letters"].keys()))

    def test_to_list_can_filter_only_unread(self):
        letters = {
            "letters": {
                "a": {"letter": "a", "unread_count": 0},
                "b": {"letter": "b", "unread_count": 3},
            }
        }

        result = self.storage.to_list(letters, only_unread=True)

        self.assertEqual([{"letter": "b", "unread_count": 3}], result)

    def test_change_unread_updates_counts_for_each_letter(self):
        self.storage.change_unread(
            owner="alice", letters={"a": 2, "b": 1}, readed=True
        )

        self.db.letters.update_one.assert_called_once_with(
            {"owner": "alice"},
            {"$inc": {"letters.a.unread_count": -2, "letters.b.unread_count": -1}},
        )

    def test_sync_with_tags_aggregates_counts_and_sets_local_urls(self):
        router = MagicMock()
        router.get_url_by_endpoint.side_effect = lambda endpoint, params: (
            f"/group/{params['letter']}/{params['page_number']}"
        )

        tags = [
            {"tag": "alpha", "unread_count": 2},
            {"tag": "atom", "unread_count": 1},
            {"tag": "beta", "unread_count": 5},
        ]

        self.storage.sync_with_tags(owner="alice", tags=tags, router=router)

        self.db.letters.update_one.assert_called_once()
        query, update = self.db.letters.update_one.call_args.args[:2]
        kwargs = self.db.letters.update_one.call_args.kwargs

        self.assertEqual({"owner": "alice"}, query)
        letters = update["$set"]["letters"]
        self.assertEqual(3, letters["a"]["unread_count"])
        self.assertEqual(5, letters["b"]["unread_count"])
        self.assertEqual("/group/a/1", letters["a"]["local_url"])
        self.assertEqual("/group/b/1", letters["b"]["local_url"])
        self.assertTrue(kwargs.get("upsert"))


if __name__ == "__main__":
    unittest.main()
