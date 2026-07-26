"""Unit tests for read-state filtering inside `_build_topics_index`.

These run without MongoDB: the storage layers `_build_topics_index` touches are
replaced by small in-memory stubs.
"""

import unittest
from typing import Any, Iterator, Optional

from rsstag.web.posts import _all_posts_read, _build_topics_index, _build_topics_tree


class StubTopicAliases:
    """Identity alias resolver: every raw topic path is already canonical."""

    def load_owner_map(self, owner: str) -> dict[str, Any]:
        return {}

    def resolve_path(
        self, raw_topic: str, alias_map: Optional[dict[str, Any]] = None
    ) -> dict[str, str]:
        return {"canonical_path": raw_topic}


class StubPosts:
    def __init__(self, posts: list[dict[str, Any]]) -> None:
        self._posts: list[dict[str, Any]] = posts
        self._db: Any = None

    def get_by_pids(
        self, owner: str, pids: list[Any], projection: Optional[dict] = None
    ) -> Iterator[dict[str, Any]]:
        wanted: set[Any] = set(pids)
        return iter([post for post in self._posts if post["pid"] in wanted])


class StubFeeds:
    def get_by_feed_ids(
        self, owner: str, feed_ids: list[Any], projection: Optional[dict] = None
    ) -> Iterator[dict[str, Any]]:
        return iter([{"feed_id": fid, "title": f"Feed {fid}"} for fid in feed_ids])


class StubPostGrouping:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs: list[dict[str, Any]] = docs

    def get_all_by_owner(
        self, owner: str, projection: Optional[dict] = None
    ) -> Iterator[dict[str, Any]]:
        return iter(list(self._docs))


class StubApp:
    def __init__(self, posts: list[dict[str, Any]], docs: list[dict[str, Any]]) -> None:
        self.posts: StubPosts = StubPosts(posts)
        self.feeds: StubFeeds = StubFeeds()
        self.post_grouping: StubPostGrouping = StubPostGrouping(docs)
        self.topic_aliases: StubTopicAliases = StubTopicAliases()
        self.db: Any = None


POSTS: list[dict[str, Any]] = [
    {"pid": "unread-post", "feed_id": "feed-1", "read": False},
    {"pid": "read-post", "feed_id": "feed-1", "read": True},
    {"pid": "partial-post", "feed_id": "feed-1", "read": False},
    {"pid": "flagless-post", "feed_id": "feed-1"},
]

GROUPINGS: list[dict[str, Any]] = [
    {
        "post_ids": ["unread-post"],
        "sentences": [{"number": 1, "text": "Unread.", "read": False}],
        "groups": {"Alpha > Unread": [1]},
    },
    {
        # Marked read as a whole while the sentence flags stayed stale.
        "post_ids": ["read-post"],
        "sentences": [{"number": 1, "text": "Read.", "read": False}],
        "groups": {"Beta > WholePostRead": [1]},
    },
    {
        "post_ids": ["partial-post"],
        "sentences": [
            {"number": 1, "text": "Unread.", "read": False},
            {"number": 2, "text": "Read.", "read": True},
        ],
        "groups": {"Gamma > StillUnread": [1], "Gamma > SentencesRead": [2]},
    },
    {
        "post_ids": ["flagless-post"],
        "sentences": [{"number": 1, "text": "No read field.", "read": False}],
        "groups": {"Delta > NoReadField": [1]},
    },
    {
        "post_ids": ["read-post", "unread-post"],
        "sentences": [{"number": 1, "text": "Mixed.", "read": False}],
        "groups": {"Epsilon > Mixed": [1]},
    },
    {
        "post_ids": ["deleted-post"],
        "sentences": [{"number": 1, "text": "Orphan.", "read": False}],
        "groups": {"Zeta > MissingPost": [1]},
    },
]

USER: dict[str, Any] = {"sid": "topics-sid", "settings": {}}


def build_paths(only_unread: bool) -> set[str]:
    """Return every topic path present in the tree for the given setting."""
    app: Any = StubApp(POSTS, GROUPINGS)
    topic_counts, _ = _build_topics_index(app, USER, None, only_unread=only_unread)
    tree: list[dict[str, Any]] = _build_topics_tree(topic_counts)

    paths: set[str] = set()

    def walk(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            paths.add(str(node["path"]))
            walk(node.get("children", []))

    walk(tree)
    return paths


class TestAllPostsRead(unittest.TestCase):
    def test_empty_grouping_is_not_read(self) -> None:
        self.assertFalse(_all_posts_read([], {"a"}))

    def test_all_known_read(self) -> None:
        self.assertTrue(_all_posts_read(["a", "b"], {"a", "b"}))

    def test_unknown_pid_counts_as_unread(self) -> None:
        self.assertFalse(_all_posts_read(["a", "missing"], {"a"}))


class TestTopicsIndexOnlyUnread(unittest.TestCase):
    def test_fully_read_post_topics_are_hidden(self) -> None:
        paths: set[str] = build_paths(only_unread=True)

        self.assertIn("Alpha > Unread", paths)
        self.assertNotIn("Beta > WholePostRead", paths)
        # A hidden leaf takes its parent branch with it.
        self.assertNotIn("Beta", paths)

    def test_topics_with_only_read_sentences_are_hidden(self) -> None:
        paths: set[str] = build_paths(only_unread=True)

        self.assertIn("Gamma > StillUnread", paths)
        self.assertNotIn("Gamma > SentencesRead", paths)
        self.assertIn("Gamma", paths)

    def test_unknown_read_state_stays_visible(self) -> None:
        paths: set[str] = build_paths(only_unread=True)

        # Post without a "read" field and grouping for a deleted post: fail open.
        self.assertIn("Delta > NoReadField", paths)
        self.assertIn("Zeta > MissingPost", paths)
        # Grouping mixing a read and an unread post is still relevant.
        self.assertIn("Epsilon > Mixed", paths)

    def test_read_topics_visible_when_setting_disabled(self) -> None:
        paths: set[str] = build_paths(only_unread=False)

        self.assertIn("Alpha > Unread", paths)
        self.assertIn("Beta > WholePostRead", paths)
        self.assertIn("Gamma > SentencesRead", paths)


if __name__ == "__main__":
    unittest.main()
