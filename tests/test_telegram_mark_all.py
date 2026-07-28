import unittest
from typing import Any
from unittest.mock import MagicMock

from rsstag.providers.providers import TELEGRAM
from rsstag.providers.telegram import TelegramProvider


class TestTelegramMarkAll(unittest.TestCase):
    def setUp(self) -> None:
        config: dict[str, Any] = {
            "settings": {"no_category_name": "NotCategorized"}
        }
        self.db: MagicMock = MagicMock()
        self.provider: TelegramProvider = TelegramProvider(config, self.db)
        self.provider._tlg_sync = MagicMock()
        self.user: dict[str, str] = {
            "sid": "alice",
            "phone": "+10000000000",
        }

    def test_only_queries_telegram_feeds(self) -> None:
        self.db.feeds.find.return_value = [
            {
                "feed_id": "-100123456",
                "title": "Telegram channel",
                "provider": TELEGRAM,
            }
        ]
        posts_cursor: MagicMock = MagicMock()
        posts_cursor.allow_disk_use.return_value = posts_cursor
        posts_cursor.sort.return_value = [
            {"id": 10, "read": True},
            {"id": 20, "read": False},
        ]
        self.db.posts.find.return_value = posts_cursor

        result: bool = self.provider.mark_all({}, self.user)

        self.assertTrue(result)
        self.db.feeds.find.assert_called_once_with(
            {"owner": "alice", "provider": TELEGRAM},
            projection={"feed_id": True, "title": True},
        )
        self.provider._tlg_sync.assert_called_once_with(
            "+10000000000",
            "alice",
            [(-100123456, 10)],
        )

    def test_invalid_telegram_feed_id_is_skipped(self) -> None:
        self.db.feeds.find.return_value = [
            {
                "feed_id": "3ab803707954118ae0c3e61d8c0cfea1",
                "title": "Invalid Telegram feed",
                "provider": TELEGRAM,
            }
        ]

        with self.assertLogs(level="WARNING") as logs:
            result: bool = self.provider.mark_all({}, self.user)

        self.assertTrue(result)
        self.provider._tlg_sync.assert_not_called()
        self.assertTrue(
            any("invalid feed id" in message for message in logs.output),
            logs.output,
        )


if __name__ == "__main__":
    unittest.main()
