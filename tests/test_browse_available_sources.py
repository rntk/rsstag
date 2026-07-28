"""Unit tests for rsstag.web.browse._build_available_sources.

A sources-list refresh can store feeds before any post is downloaded, so the
unread-grouping category view alone would never show them. This helper is
what surfaces those "available but not yet shown" feeds to the categories
page (rendered as ``sources`` / ``feeds_list_providers`` by
on_group_by_category_get).
"""

import unittest
from typing import Any, Dict, List

from rsstag.web.browse import _build_available_sources


class TestBuildAvailableSources(unittest.TestCase):
    def test_excludes_feeds_already_shown_in_unread_grouping(self) -> None:
        db_feeds: List[Dict[str, Any]] = [
            {"feed_id": "1", "title": "Shown feed"},
            {"feed_id": "2", "title": "Not shown feed"},
        ]

        result = _build_available_sources(db_feeds, shown_feed_ids={"1"}, feeds_quality={})

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["feed_id"], "2")

    def test_includes_feeds_stored_by_a_sources_list_refresh_with_no_posts(self) -> None:
        db_feeds: List[Dict[str, Any]] = [
            {
                "feed_id": "3",
                "title": "Fresh from refresh, no posts yet",
                "local_url": "/feed/3",
                "provider": "telegram",
                "category_title": "NotCategorized",
            },
        ]

        result = _build_available_sources(db_feeds, shown_feed_ids=set(), feeds_quality={})

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0],
            {
                "feed_id": "3",
                "title": "Fresh from refresh, no posts yet",
                "url": "/feed/3",
                "provider": "telegram",
                "category_title": "NotCategorized",
                "quality": None,
            },
        )

    def test_sorts_case_insensitively_by_title(self) -> None:
        db_feeds: List[Dict[str, Any]] = [
            {"feed_id": "1", "title": "zebra"},
            {"feed_id": "2", "title": "Apple"},
            {"feed_id": "3", "title": "banana"},
        ]

        result = _build_available_sources(db_feeds, shown_feed_ids=set(), feeds_quality={})

        self.assertEqual([f["title"] for f in result], ["Apple", "banana", "zebra"])

    def test_falls_back_to_feed_id_when_title_missing(self) -> None:
        db_feeds: List[Dict[str, Any]] = [{"feed_id": "no-title-feed"}]

        result = _build_available_sources(db_feeds, shown_feed_ids=set(), feeds_quality={})

        self.assertEqual(result[0]["title"], "no-title-feed")

    def test_attaches_quality_when_present(self) -> None:
        db_feeds: List[Dict[str, Any]] = [{"feed_id": "1", "title": "Feed"}]

        result = _build_available_sources(
            db_feeds, shown_feed_ids=set(), feeds_quality={"1": 0.75}
        )

        self.assertEqual(result[0]["quality"], 0.75)

    def test_empty_input_returns_empty_list(self) -> None:
        self.assertEqual(
            _build_available_sources([], shown_feed_ids=set(), feeds_quality={}), []
        )


if __name__ == "__main__":
    unittest.main()
