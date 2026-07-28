"""Unit tests for the shared feed-doc builder used by every provider.

``build_feed_doc``/``dedup_feed_docs`` are what keep a posts download, a
raw-to-posts conversion, and a sources-list refresh from ever inserting two
``feeds`` documents for the same source: they all have to agree on the same
string ``feed_id`` for the same source. These tests pin that contract down,
including parity with the Telegram provider's own feed-doc builder.
"""

import unittest
from typing import Any, Dict

from rsstag.providers.feed_docs import build_feed_doc, dedup_feed_docs
from rsstag.providers.providers import TELEGRAM
from rsstag.providers.telegram import TelegramProvider
from rsstag.web.routes import RSSTagRoutes


class TestBuildFeedDoc(unittest.TestCase):
    def setUp(self) -> None:
        self.routes: RSSTagRoutes = RSSTagRoutes("rsstag.test")

    def test_feed_id_is_a_string_even_for_integer_input(self) -> None:
        doc: Dict[str, Any] = build_feed_doc(
            owner="alice",
            feed_id=-100123456,
            title="Test channel",
            provider=TELEGRAM,
            routes=self.routes,
            category_id="NotCategorized",
        )

        self.assertIsInstance(doc["feed_id"], str)
        self.assertEqual(doc["feed_id"], "-100123456")

    def test_title_falls_back_to_stream_id_when_blank(self) -> None:
        doc: Dict[str, Any] = build_feed_doc(
            owner="alice",
            feed_id=42,
            title="",
            provider=TELEGRAM,
            routes=self.routes,
            category_id="NotCategorized",
        )

        self.assertEqual(doc["title"], "42")

    def test_category_title_defaults_to_category_id(self) -> None:
        doc: Dict[str, Any] = build_feed_doc(
            owner="alice",
            feed_id=42,
            title="Chan",
            provider=TELEGRAM,
            routes=self.routes,
            category_id="tech",
        )

        self.assertEqual(doc["category_title"], "tech")

    def test_origin_feed_id_defaults_to_feed_id(self) -> None:
        doc: Dict[str, Any] = build_feed_doc(
            owner="alice",
            feed_id=42,
            title="Chan",
            provider=TELEGRAM,
            routes=self.routes,
            category_id="tech",
        )

        self.assertEqual(doc["origin_feed_id"], 42)

    def test_origin_feed_id_can_be_overridden(self) -> None:
        doc: Dict[str, Any] = build_feed_doc(
            owner="alice",
            feed_id="42",
            title="Chan",
            provider=TELEGRAM,
            routes=self.routes,
            category_id="tech",
            origin_feed_id=99,
        )

        self.assertEqual(doc["origin_feed_id"], 99)

    def test_matches_telegram_providers_own_feed_doc_builder(self) -> None:
        """The list_feeds path and the download/raw path must build byte-identical docs.

        ``TelegramProvider._build_feed_doc`` is the private helper both
        ``download``/``raw_messages_to_posts`` and ``list_feeds`` funnel
        through; it forwards straight into ``build_feed_doc``. Calling both
        with the same chat id must yield the same ``feed_id``, otherwise a
        sources-list refresh and a later posts download would create two rows
        for the same chat.
        """
        config: Dict[str, Any] = {"settings": {"no_category_name": "NotCategorized"}}
        provider: TelegramProvider = TelegramProvider(config, db=None)
        chat_id = -1009988776655

        via_provider: Dict[str, Any] = provider._build_feed_doc(
            "alice", chat_id, "My Channel", self.routes
        )
        via_shared_builder: Dict[str, Any] = build_feed_doc(
            owner="alice",
            feed_id=chat_id,
            title="My Channel",
            provider=TELEGRAM,
            routes=self.routes,
            category_id=provider.no_category_name,
        )

        self.assertEqual(via_provider["feed_id"], via_shared_builder["feed_id"])
        self.assertEqual(via_provider["feed_id"], str(chat_id))
        self.assertIsInstance(via_provider["feed_id"], str)


class TestDedupFeedDocs(unittest.TestCase):
    def test_collapses_repeated_feed_id_keeping_first(self) -> None:
        feeds = [
            {"feed_id": "1", "title": "First"},
            {"feed_id": "1", "title": "Second (should be dropped)"},
            {"feed_id": "2", "title": "Other"},
        ]

        result = dedup_feed_docs(feeds)

        self.assertEqual(len(result), 2)
        by_id = {feed["feed_id"]: feed for feed in result}
        self.assertEqual(by_id["1"]["title"], "First")
        self.assertEqual(by_id["2"]["title"], "Other")

    def test_treats_int_and_str_feed_id_as_the_same_identity(self) -> None:
        feeds = [
            {"feed_id": 1, "title": "Int form"},
            {"feed_id": "1", "title": "String form (should be dropped)"},
        ]

        result = dedup_feed_docs(feeds)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Int form")

    def test_skips_docs_without_feed_id(self) -> None:
        feeds = [
            {"title": "No feed_id"},
            {"feed_id": "", "title": "Blank feed_id"},
            {"feed_id": "1", "title": "Valid"},
        ]

        result = dedup_feed_docs(feeds)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Valid")

    def test_empty_input_returns_empty_list(self) -> None:
        self.assertEqual(dedup_feed_docs([]), [])


if __name__ == "__main__":
    unittest.main()
