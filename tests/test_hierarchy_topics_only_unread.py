"""Unit tests for read filtering in `_build_hierarchy_topics` (the /hierarchy page).

No MongoDB needed: the only storage call the helper makes is stubbed.
"""

import unittest
from typing import Any, Optional

from rsstag.web.posts import _build_hierarchy_topics


class StubPostGrouping:
    def __init__(self, docs: dict[str, dict[str, Any]]) -> None:
        self._docs: dict[str, dict[str, Any]] = docs

    def get_grouped_posts(
        self, owner: str, post_ids: list[Any]
    ) -> Optional[dict[str, Any]]:
        if len(post_ids) != 1:
            return None
        return self._docs.get(str(post_ids[0]))


class StubApp:
    def __init__(self, docs: dict[str, dict[str, Any]]) -> None:
        self.post_grouping: StubPostGrouping = StubPostGrouping(docs)


USER: dict[str, Any] = {"sid": "hierarchy-sid"}

POSTS: list[dict[str, Any]] = [
    {
        "pid": "post-1",
        "url": "https://example.com/post-1",
        "content": {"title": "First post"},
    },
    {
        "pid": "post-2",
        "url": "https://example.com/post-2",
        "content": {"title": "Second post"},
    },
]

GROUPINGS: dict[str, dict[str, Any]] = {
    "post-1": {
        "sentences": [
            {"number": 1, "text": "Ad one.", "read": True},
            {"number": 2, "text": "Ad two.", "read": True},
            {"number": 3, "text": "Money one.", "read": True},
            {"number": 4, "text": "Money two.", "read": False},
        ],
        "groups": {
            "Business > Advertising": [1, 2],
            "Business > Finance": [3, 4],
        },
    },
    "post-2": {
        "sentences": [
            {"number": 1, "text": "Shared ad.", "read": False},
            # No "read" field: unknown state must stay visible.
            {"number": 2, "text": "Match report."},
        ],
        "groups": {
            "Business > Advertising": [1],
            "Sport": [2],
        },
    },
}


def build(only_unread: bool) -> dict[str, dict[str, Any]]:
    app: Any = StubApp(GROUPINGS)
    topics: list[dict[str, Any]] = _build_hierarchy_topics(
        app, USER, POSTS, only_unread=only_unread
    )
    return {topic["name"]: topic for topic in topics}


class TestHierarchyTopicsOnlyUnread(unittest.TestCase):
    def test_topic_with_only_read_sentences_is_hidden(self) -> None:
        topics: dict[str, dict[str, Any]] = build(only_unread=True)

        self.assertIn("Business > Advertising", topics)
        # Post 1 has both of its advertising sentences read, post 2 does not:
        # only post 2 remains a source.
        advertising: dict[str, Any] = topics["Business > Advertising"]
        self.assertEqual(advertising["posts_count"], 1)
        self.assertEqual(advertising["sentences_count"], 1)
        self.assertEqual(
            [source["post_id"] for source in advertising["sources"]], ["post-2"]
        )

    def test_read_sentences_are_dropped_from_the_payload(self) -> None:
        topics: dict[str, dict[str, Any]] = build(only_unread=True)

        finance: dict[str, Any] = topics["Business > Finance"]
        self.assertEqual(finance["sentences_count"], 1)
        self.assertEqual(
            [sentence["number"] for sentence in finance["sources"][0]["sentences"]], [4]
        )
        self.assertEqual(finance["sentences"], ["Money two."])

    def test_topic_disappears_when_every_source_is_read(self) -> None:
        docs: dict[str, dict[str, Any]] = {
            "post-1": {
                "sentences": [{"number": 1, "text": "Ad one.", "read": True}],
                "groups": {"Business > Advertising": [1]},
            }
        }
        app: Any = StubApp(docs)
        topics: list[dict[str, Any]] = _build_hierarchy_topics(
            app, USER, [POSTS[0]], only_unread=True
        )

        self.assertEqual(topics, [])

    def test_sentence_without_read_field_stays_visible(self) -> None:
        topics: dict[str, dict[str, Any]] = build(only_unread=True)

        self.assertIn("Sport", topics)
        self.assertEqual(topics["Sport"]["sentences_count"], 1)

    def test_read_topics_are_kept_when_setting_disabled(self) -> None:
        topics: dict[str, dict[str, Any]] = build(only_unread=False)

        advertising: dict[str, Any] = topics["Business > Advertising"]
        self.assertEqual(advertising["posts_count"], 2)
        self.assertEqual(advertising["sentences_count"], 3)
        self.assertEqual(topics["Business > Finance"]["sentences_count"], 2)

    def test_sentences_count_ignores_indices_without_text(self) -> None:
        docs: dict[str, dict[str, Any]] = {
            "post-1": {
                "sentences": [{"number": 1, "text": "Only real sentence.", "read": False}],
                # Index 2 has no matching sentence document.
                "groups": {"Sport": [1, 2]},
            }
        }
        app: Any = StubApp(docs)
        topics: list[dict[str, Any]] = _build_hierarchy_topics(
            app, USER, [POSTS[0]], only_unread=False
        )

        self.assertEqual(topics[0]["sentences_count"], 1)


if __name__ == "__main__":
    unittest.main()
