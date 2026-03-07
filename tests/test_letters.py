import unittest
from unittest.mock import Mock
from rsstag.letters import RssTagLetters
from tests.db_utils import DBHelper


class TestRssTagLetters(unittest.TestCase):
    def setUp(self) -> None:
        self.db_helper = DBHelper(port=8765)
        self.db = self.db_helper.create_test_db()
        self.letters = RssTagLetters(self.db)
        self.owner = "test_user"

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()

    def test_prepare(self) -> None:
        """Test that prepare creates the required indexes"""
        self.letters.prepare()
        indices = self.db.letters.index_information()
        for index in self.letters.indexes:
            self.assertIn(f"{index}_1", indices)

    def test_get_empty_result(self) -> None:
        """Test get returns empty dict when owner doesn't exist"""
        result = self.letters.get(self.owner)
        self.assertEqual(result, {})

    def test_get_with_data(self) -> None:
        """Test get returns letters data for an owner"""
        data = {
            "letters": {
                "a": {
                    "letter": "a",
                    "unread_count": 5,
                    "local_url": "/group/tag/startwith/a/1",
                },
                "b": {
                    "letter": "b",
                    "unread_count": 3,
                    "local_url": "/group/tag/startwith/b/1",
                },
            }
        }
        self.db.letters.insert_one({"owner": self.owner, **data})

        result = self.letters.get(self.owner)
        self.assertIn("letters", result)
        self.assertEqual(len(result["letters"]), 2)
        self.assertIn("a", result["letters"])
        self.assertIn("b", result["letters"])

    def test_get_with_sort(self) -> None:
        """Test get with make_sort=True returns sorted letters"""
        data = {
            "letters": {
                "c": {"letter": "c", "unread_count": 1},
                "a": {"letter": "a", "unread_count": 2},
                "b": {"letter": "b", "unread_count": 3},
            }
        }
        self.db.letters.insert_one({"owner": self.owner, **data})

        result = self.letters.get(self.owner, make_sort=True)
        letters_keys = list(result["letters"].keys())
        self.assertEqual(letters_keys, ["a", "b", "c"])

    def test_to_list_all_letters(self) -> None:
        """Test to_list returns all letters when only_unread is None"""
        letters_data = {
            "letters": {
                "a": {"letter": "a", "unread_count": 0},
                "b": {"letter": "b", "unread_count": 5},
                "c": {"letter": "c", "unread_count": 3},
            }
        }

        result = self.letters.to_list(letters_data)
        self.assertEqual(len(result), 3)

    def test_to_list_only_unread(self) -> None:
        """Test to_list filters unread letters when only_unread=True"""
        letters_data = {
            "letters": {
                "a": {"letter": "a", "unread_count": 0},
                "b": {"letter": "b", "unread_count": 5},
                "c": {"letter": "c", "unread_count": 0},
                "d": {"letter": "d", "unread_count": 3},
            }
        }

        result = self.letters.to_list(letters_data, only_unread=True)
        self.assertEqual(len(result), 2)
        unread_letters = [item["letter"] for item in result]
        self.assertIn("b", unread_letters)
        self.assertIn("d", unread_letters)
        self.assertNotIn("a", unread_letters)
        self.assertNotIn("c", unread_letters)

    def test_to_list_empty_letters(self) -> None:
        """Test to_list returns empty list when letters is empty"""
        letters_data = {"letters": {}}

        result = self.letters.to_list(letters_data)
        self.assertEqual(result, [])

    def test_change_unread_mark_as_read(self) -> None:
        """Test change_unread decrements unread count when marking as read"""
        initial_data = {
            "owner": self.owner,
            "letters": {
                "a": {"letter": "a", "unread_count": 10},
                "b": {"letter": "b", "unread_count": 5},
            },
        }
        self.db.letters.insert_one(initial_data)

        letters_to_update = {"a": 3, "b": 2}
        self.letters.change_unread(self.owner, letters_to_update, readed=True)

        result = self.db.letters.find_one({"owner": self.owner})
        self.assertEqual(result["letters"]["a"]["unread_count"], 7)
        self.assertEqual(result["letters"]["b"]["unread_count"], 3)

    def test_change_unread_mark_as_unread(self) -> None:
        """Test change_unread increments unread count when marking as unread"""
        initial_data = {
            "owner": self.owner,
            "letters": {
                "a": {"letter": "a", "unread_count": 5},
                "b": {"letter": "b", "unread_count": 3},
            },
        }
        self.db.letters.insert_one(initial_data)

        letters_to_update = {"a": 2, "b": 1}
        self.letters.change_unread(self.owner, letters_to_update, readed=False)

        result = self.db.letters.find_one({"owner": self.owner})
        self.assertEqual(result["letters"]["a"]["unread_count"], 7)
        self.assertEqual(result["letters"]["b"]["unread_count"], 4)

    def test_change_unread_empty_update(self) -> None:
        """Test change_unread with empty update dict does nothing"""
        initial_data = {
            "owner": self.owner,
            "letters": {
                "a": {"letter": "a", "unread_count": 10},
            },
        }
        self.db.letters.insert_one(initial_data)

        self.letters.change_unread(self.owner, {}, readed=True)

        result = self.db.letters.find_one({"owner": self.owner})
        self.assertEqual(result["letters"]["a"]["unread_count"], 10)

    def test_sync_with_tags_new_letters(self) -> None:
        """Test sync_with_tags creates new letters from tags"""
        router = Mock()
        router.get_url_by_endpoint = Mock(
            side_effect=lambda endpoint, params: f"/group/tag/startwith/{params['letter']}/{params['page_number']}"
        )

        tags = [
            {"tag": "apple", "unread_count": 5},
            {"tag": "banana", "unread_count": 3},
            {"tag": "apricot", "unread_count": 2},
        ]

        self.letters.sync_with_tags(self.owner, tags, router)

        result = self.db.letters.find_one({"owner": self.owner})
        self.assertIsNotNone(result)
        self.assertEqual(len(result["letters"]), 2)  # 'a' and 'b'
        self.assertEqual(result["letters"]["a"]["letter"], "a")
        self.assertEqual(result["letters"]["a"]["unread_count"], 7)  # 5 + 2
        self.assertEqual(result["letters"]["b"]["letter"], "b")
        self.assertEqual(result["letters"]["b"]["unread_count"], 3)

    def test_sync_with_tags_empty_tags(self) -> None:
        """Test sync_with_tags with empty tags list"""
        router = Mock()

        self.letters.sync_with_tags(self.owner, [], router)

        result = self.db.letters.find_one({"owner": self.owner})
        self.assertIsNotNone(result)
        self.assertEqual(result["owner"], self.owner)
        self.assertEqual(len(result["letters"]), 0)

    def test_sync_with_tags_updates_existing(self) -> None:
        """Test sync_with_tags updates existing letters"""
        initial_data = {
            "owner": self.owner,
            "letters": {
                "a": {
                    "letter": "a",
                    "unread_count": 2,
                    "local_url": "/group/tag/startwith/a/1",
                }
            },
        }
        self.db.letters.insert_one(initial_data)

        router = Mock()
        router.get_url_by_endpoint = Mock(
            return_value="/group/tag/startwith/a/1"
        )

        tags = [
            {"tag": "apple", "unread_count": 5},
            {"tag": "apricot", "unread_count": 3},
        ]

        self.letters.sync_with_tags(self.owner, tags, router)

        result = self.db.letters.find_one({"owner": self.owner})
        self.assertEqual(result["letters"]["a"]["unread_count"], 8)  # 2 + 5 + 3

    def test_sync_with_tags_router_url_generation(self) -> None:
        """Test sync_with_tags calls router with correct parameters"""
        router = Mock()
        router.get_url_by_endpoint = Mock(return_value="/test/url")

        tags = [
            {"tag": "test", "unread_count": 1},
        ]

        self.letters.sync_with_tags(self.owner, tags, router)

        router.get_url_by_endpoint.assert_called_once()
        call_kwargs = router.get_url_by_endpoint.call_args[1]
        self.assertEqual(call_kwargs["endpoint"], "on_group_by_tags_startwith_get")
        self.assertEqual(call_kwargs["params"]["letter"], "t")
        self.assertEqual(call_kwargs["params"]["page_number"], 1)

    def test_sync_with_tags_special_characters(self) -> None:
        """Test sync_with_tags handles tags with special first characters"""
        router = Mock()
        router.get_url_by_endpoint = Mock(return_value="/test/url")

        tags = [
            {"tag": "123numbers", "unread_count": 2},
            {"tag": "@special", "unread_count": 1},
        ]

        self.letters.sync_with_tags(self.owner, tags, router)

        result = self.db.letters.find_one({"owner": self.owner})
        # Should have letters for '1' and '@'
        self.assertIn("1", result["letters"])
        self.assertIn("@", result["letters"])


if __name__ == "__main__":
    unittest.main()
