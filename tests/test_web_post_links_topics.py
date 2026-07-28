"""Tests for the topic links exposed by the post links block ("Show links")."""

import gzip
import json
import re
import unittest
from typing import Any
from urllib.parse import parse_qs, urlparse

from rsstag.web.posts import _post_topic_sentence_counts, _topic_prefix_paths
from tests.web_test_utils import MongoWebTestCase


class TestTopicPrefixPaths(unittest.TestCase):
    def test_expands_every_ancestor_path(self) -> None:
        self.assertEqual(
            _topic_prefix_paths("AI > LLMs > Training"),
            ["AI", "AI > LLMs", "AI > LLMs > Training"],
        )

    def test_normalizes_separator_spacing(self) -> None:
        self.assertEqual(_topic_prefix_paths("AI>LLMs"), ["AI", "AI > LLMs"])

    def test_empty_topic_has_no_paths(self) -> None:
        self.assertEqual(_topic_prefix_paths("  >  "), [])


class TestPostTopicSentenceCounts(unittest.TestCase):
    def test_parent_accumulates_child_sentences_without_double_count(self) -> None:
        docs: list[dict[str, Any]] = [
            {
                "groups": {
                    "AI > LLMs": [1, 2],
                    "AI > Hardware": [2, 3],
                }
            }
        ]

        counts: dict[str, int] = _post_topic_sentence_counts(docs)

        self.assertEqual(counts["AI"], 3)
        self.assertEqual(counts["AI > LLMs"], 2)
        self.assertEqual(counts["AI > Hardware"], 2)

    def test_sentence_numbers_of_different_docs_are_not_merged(self) -> None:
        docs: list[dict[str, Any]] = [
            {"groups": {"AI": [1]}},
            {"groups": {"AI": [1]}},
        ]

        self.assertEqual(_post_topic_sentence_counts(docs)["AI"], 2)

    def test_ignores_broken_groups(self) -> None:
        docs: list[dict[str, Any]] = [
            {"groups": None},
            {"groups": {"AI": "not-a-list", "ML": [], "OK": [1, "x"]}},
            {},
        ]

        self.assertEqual(_post_topic_sentence_counts(docs), {"OK": 1})


class TestWebPostLinksTopics(MongoWebTestCase):
    def setUp(self) -> None:
        self.test_db.posts.delete_many({})
        self.test_db.feeds.delete_many({})
        self.test_db.post_grouping.delete_many({})

    def _seed_post(self, login: str) -> tuple[str, str, str]:
        """Seed a user with one feed and two posts. Returns (sid, owner, pid)."""
        user, sid = self.seed_test_user(login)
        owner: str = user["sid"]
        feed_id: str = "links-feed"
        self.db_helper.init_db_from_dict(
            self.test_db,
            {
                "feeds": [
                    {
                        "owner": owner,
                        "feed_id": feed_id,
                        "category_id": "links-category",
                        "category_title": "Links category",
                        "category_local_url": "/category/links-category",
                        "local_url": f"/feed/{feed_id}",
                        "title": "Links Feed",
                        "url": "https://example.com/feed",
                        "favicon": "",
                        "processing": 0,
                    }
                ],
                "posts": [
                    {
                        "owner": owner,
                        "pid": pid,
                        "feed_id": feed_id,
                        "category_id": "links-category",
                        "processing": 0,
                        "read": False,
                        "tags": ["linkstag"],
                        "unix_date": 1,
                        "url": f"https://example.com/{pid}",
                        "content": {
                            "title": f"Post {pid}",
                            "content": gzip.compress(
                                b"Test post content for integration tests."
                            ),
                        },
                    }
                    for pid in ("links-post-1", "links-post-2")
                ],
            },
        )
        return sid, owner, "links-post-1"

    def _get_links(self, sid: str, pid: str) -> dict[str, Any]:
        client = self.get_authenticated_client(sid)
        response = client.get(f"/post-links/{pid}")
        self.assertEqual(response.status_code, 200)
        return json.loads(response.data)["data"]

    def test_topics_and_subtopics_are_linked(self) -> None:
        sid, owner, pid = self._seed_post("links-topics-user")
        self.app.post_grouping.save_grouped_posts(
            owner,
            [pid],
            [
                {"number": 1, "text": "First."},
                {"number": 2, "text": "Second."},
            ],
            {"AI > LLMs > Training": [1, 2]},
        )

        data: dict[str, Any] = self._get_links(sid, pid)

        topics: list[dict[str, Any]] = data["topics"]
        self.assertEqual(
            [topic["topic"] for topic in topics],
            ["AI", "AI > LLMs", "AI > LLMs > Training"],
        )
        self.assertEqual([topic["name"] for topic in topics], ["AI", "LLMs", "Training"])
        self.assertEqual([topic["level"] for topic in topics], [1, 2, 3])
        self.assertEqual([topic["sentences"] for topic in topics], [2, 2, 2])

    def test_topic_urls_point_to_grouped_pages_of_the_post(self) -> None:
        sid, owner, pid = self._seed_post("links-topics-urls-user")
        self.app.post_grouping.save_grouped_posts(
            owner,
            [pid],
            [{"number": 1, "text": "First."}],
            {"AI > LLMs": [1]},
        )

        topics: list[dict[str, Any]] = self._get_links(sid, pid)["topics"]

        leaf: dict[str, Any] = topics[-1]
        parsed = urlparse(leaf["url"])
        self.assertEqual(parsed.path, f"/post-grouped/{pid}")
        self.assertEqual(parse_qs(parsed.query)["topic"], ["AI > LLMs"])

        parsed_snippets = urlparse(leaf["snippets_url"])
        self.assertEqual(parsed_snippets.path, f"/post-grouped-snippets/{pid}")
        self.assertEqual(parse_qs(parsed_snippets.query)["topic"], ["AI > LLMs"])

    def test_grouped_page_keeps_only_the_requested_topic(self) -> None:
        """The link must survive the round trip: the target page filters by it."""
        sid, owner, pid = self._seed_post("links-topics-roundtrip-user")
        self.app.post_grouping.save_grouped_posts(
            owner,
            [pid],
            [{"number": 0, "text": "Test post content for integration tests."}],
            {"AI > LLMs": [0], "Cooking": [0]},
        )
        topics: list[dict[str, Any]] = self._get_links(sid, pid)["topics"]
        llms_url: str = next(
            topic["url"] for topic in topics if topic["topic"] == "AI > LLMs"
        )

        client = self.get_authenticated_client(sid)
        response = client.get(llms_url)

        self.assertEqual(response.status_code, 200)
        page: str = response.data.decode("utf-8")
        rendered_groups = re.search(r"window\.groups = (\{.*?\});", page, re.DOTALL)
        self.assertIsNotNone(rendered_groups, "grouped page must render window.groups")
        self.assertEqual(
            list(json.loads(rendered_groups.group(1)).keys()), ["AI > LLMs"]
        )

    def test_topics_of_a_legacy_multi_post_grouping_are_returned(self) -> None:
        """Every current writer groups a single post, older docs hold several.

        Such a doc is invisible to the hash lookup of `get_grouped_posts`, so
        the links block must find it by post id membership instead.
        """
        sid, owner, pid = self._seed_post("links-topics-multi-user")
        other_pid: str = "links-post-2"
        self.app.post_grouping.save_grouped_posts(
            owner,
            [pid, other_pid],
            [{"number": 1, "text": "Shared."}],
            {"Shared > Topic": [1]},
        )

        topics: list[dict[str, Any]] = self._get_links(sid, pid)["topics"]

        self.assertEqual(
            [topic["topic"] for topic in topics], ["Shared", "Shared > Topic"]
        )

    def test_ungrouped_post_has_no_topics(self) -> None:
        sid, _, pid = self._seed_post("links-topics-empty-user")

        self.assertEqual(self._get_links(sid, pid)["topics"], [])

    def test_topics_of_another_owner_are_not_exposed(self) -> None:
        sid, _, pid = self._seed_post("links-topics-owner-user")
        self.app.post_grouping.save_grouped_posts(
            "someone-else",
            [pid],
            [{"number": 1, "text": "Foreign."}],
            {"Foreign": [1]},
        )

        self.assertEqual(self._get_links(sid, pid)["topics"], [])


if __name__ == "__main__":
    unittest.main()
