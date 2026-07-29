"""Regression tests for Telegram source download filtering."""

import unittest
from queue import Queue
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock, patch

from rsstag.providers.telegram import TelegramProvider


class TestTelegramFetch(unittest.TestCase):
    """Bulk downloads must preserve the channel-only Telegram contract."""

    def setUp(self) -> None:
        config: Dict[str, Any] = {
            "settings": {"no_category_name": "NotCategorized"}
        }
        self.provider: TelegramProvider = TelegramProvider(config, db=None)

    def test_bulk_download_drops_non_channel_chats(self) -> None:
        tasks_q: Queue[Tuple[bool, int, Dict[str, Any]]] = Queue()
        results_q: Queue[Tuple[int, Dict[str, List[Dict[str, int]]], List[str]]] = Queue()
        channel: Dict[str, Any] = {
            "id": -100123,
            "title": "A group source",
            "type": {
                "@type": "chatTypeSupergroup",
                "is_channel": False,
            },
            "unread_count": 1,
        }
        response: MagicMock = MagicMock()
        response.update = {"messages": [{"chat_id": -100123, "id": 1}]}
        response.error = None
        self.provider._TelegramProvider__requests_repeater = MagicMock(
            return_value=response
        )
        tasks_q.put((True, 1, channel))

        with patch("rsstag.providers.telegram.time.sleep"):
            self.provider._fetch(tasks_q, results_q)

        self.assertTrue(results_q.empty())
        self.assertTrue(tasks_q.empty())

    def test_bulk_download_accepts_broadcast_channels(self) -> None:
        tasks_q: Queue[Tuple[bool, int, Dict[str, Any]]] = Queue()
        results_q: Queue[Tuple[int, Dict[str, List[Dict[str, int]]], List[str]]] = Queue()
        channel: Dict[str, Any] = {
            "id": -10042,
            "title": "A broadcast channel",
            "type": {
                "@type": "chatTypeSupergroup",
                "is_channel": True,
            },
            "unread_count": 1,
        }
        response: MagicMock = MagicMock()
        response.update = {"messages": [{"chat_id": -10042, "id": 1}]}
        response.error = None
        self.provider._TelegramProvider__requests_repeater = MagicMock(
            return_value=response
        )
        tasks_q.put((True, 1, channel))

        with patch("rsstag.providers.telegram.time.sleep"):
            self.provider._fetch(tasks_q, results_q)

        self.assertEqual(results_q.get_nowait()[0], -10042)

    def test_bulk_download_drops_chat_without_channel_type(self) -> None:
        tasks_q: Queue[Tuple[bool, int, Dict[str, Any]]] = Queue()
        results_q: Queue[Tuple[int, Dict[str, List[Dict[str, int]]], List[str]]] = Queue()
        tasks_q.put((True, 1, {"id": 42, "title": "A private chat", "unread_count": 1}))

        with patch("rsstag.providers.telegram.time.sleep"):
            self.provider._fetch(tasks_q, results_q)

        self.assertTrue(results_q.empty())


if __name__ == "__main__":
    unittest.main()
