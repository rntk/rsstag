import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

from rsstag.tokens import RssTagTokens


class TestRssTagTokens(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.tokens = RssTagTokens(self.db)

    def test_prepare_creates_all_indexes(self):
        self.tokens.prepare()

        self.assertEqual(self.db.tokens.create_index.call_count, len(self.tokens.indexes))
        self.db.tokens.create_index.assert_has_calls(
            [call(index) for index in self.tokens.indexes], any_order=True
        )

    def test_prepare_ignores_index_creation_errors(self):
        self.db.tokens.create_index.side_effect = Exception("already exists")

        self.tokens.prepare()

        self.assertEqual(self.db.tokens.create_index.call_count, len(self.tokens.indexes))

    @patch("rsstag.tokens.randint", return_value=100)
    @patch("rsstag.tokens.os.urandom", return_value=b"random_bytes")
    @patch("rsstag.tokens.sha256")
    def test_create_generates_token_and_inserts_document(
        self, mock_sha256, mock_urandom, mock_randint
    ):
        mock_sha256.return_value.hexdigest.return_value = "a" * 64

        result = self.tokens.create(owner="alice", expires_days=30)

        self.assertEqual(result, "a" * 64)
        mock_randint.assert_called_once_with(80, 200)
        mock_urandom.assert_called_once_with(100)
        mock_sha256.assert_called_once_with(b"random_bytes")

        self.db.tokens.insert_one.assert_called_once()
        inserted = self.db.tokens.insert_one.call_args[0][0]
        self.assertEqual(inserted["token"], "a" * 64)
        self.assertEqual(inserted["owner"], "alice")
        self.assertIsInstance(inserted["created"], datetime)
        self.assertIsInstance(inserted["expires"], datetime)
        self.assertEqual(inserted["expires"], inserted["created"] + timedelta(days=30))

    def test_get_all_finds_and_sorts_by_created_descending(self):
        cursor = MagicMock()
        sorted_cursor = MagicMock()
        cursor.sort.return_value = sorted_cursor
        self.db.tokens.find.return_value = cursor

        result = self.tokens.get_all(owner="alice")

        self.assertIs(result, sorted_cursor)
        self.db.tokens.find.assert_called_once_with({"owner": "alice"})
        cursor.sort.assert_called_once_with("created", -1)

    def test_delete_returns_true_when_deleted(self):
        self.db.tokens.delete_one.return_value = MagicMock(deleted_count=1)

        result = self.tokens.delete(owner="alice", token="t1")

        self.assertTrue(result)
        self.db.tokens.delete_one.assert_called_once_with(
            {"owner": "alice", "token": "t1"}
        )

    def test_delete_returns_false_when_not_deleted(self):
        self.db.tokens.delete_one.return_value = MagicMock(deleted_count=0)

        result = self.tokens.delete(owner="alice", token="t1")

        self.assertFalse(result)
        self.db.tokens.delete_one.assert_called_once_with(
            {"owner": "alice", "token": "t1"}
        )

    @patch("rsstag.tokens.datetime")
    def test_validate_returns_doc_when_found_and_not_expired(self, mock_datetime):
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now

        doc = {
            "token": "t1",
            "owner": "alice",
            "expires": datetime(2025, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
        }
        self.db.tokens.find_one.return_value = doc

        result = self.tokens.validate(token="t1")

        self.assertEqual(result, doc)
        self.db.tokens.find_one.assert_called_once_with({"token": "t1"})
        mock_datetime.now.assert_called_once_with(timezone.utc)

    def test_validate_returns_none_when_not_found(self):
        self.db.tokens.find_one.return_value = None

        result = self.tokens.validate(token="t1")

        self.assertIsNone(result)
        self.db.tokens.find_one.assert_called_once_with({"token": "t1"})

    @patch("rsstag.tokens.datetime")
    def test_validate_returns_none_when_expired(self, mock_datetime):
        now = datetime(2025, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now

        doc = {
            "token": "t1",
            "owner": "alice",
            "expires": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        }
        self.db.tokens.find_one.return_value = doc

        result = self.tokens.validate(token="t1")

        self.assertIsNone(result)
        self.db.tokens.find_one.assert_called_once_with({"token": "t1"})
        mock_datetime.now.assert_called_once_with(timezone.utc)


if __name__ == "__main__":
    unittest.main()
