"""Tests for the "only unread" setting on the topic hierarchy/list/mindmap pages."""

import gzip
import json
import re
from typing import Any, Optional

from tests.web_test_utils import MongoWebTestCase


class TestWebTopicsOnlyUnread(MongoWebTestCase):
    def setUp(self) -> None:
        self.test_db.posts.delete_many({})
        self.test_db.feeds.delete_many({})
        self.test_db.post_grouping.delete_many({})

    def _seed_topics(self, login: str, only_unread: bool) -> str:
        """Seed one unread post, one fully read post and one partially read post."""
        user, sid = self.seed_test_user(login)
        owner: str = user["sid"]
        feed_id: str = "topics-feed"
        self.test_db.users.update_one(
            {"sid": sid}, {"$set": {"settings.only_unread": only_unread}}
        )
        self.db_helper.init_db_from_dict(
            self.test_db,
            {
                "feeds": [
                    {
                        "owner": owner,
                        "feed_id": feed_id,
                        "category_id": "topics-category",
                        "category_title": "Topics category",
                        "local_url": f"/feed/{feed_id}",
                        "title": "Topics Feed",
                        "url": "https://example.com/feed",
                        "favicon": "",
                        "processing": 0,
                    }
                ],
                "posts": [
                    {
                        "owner": owner,
                        "pid": "unread-post",
                        "feed_id": feed_id,
                        "category_id": "topics-category",
                        "processing": 0,
                        "read": False,
                        "tags": ["topics"],
                        "unix_date": 3,
                        "url": "https://example.com/unread-post",
                        "content": {
                            "title": "Unread post",
                            "content": gzip.compress(b"Unread sentence."),
                        },
                    },
                    {
                        "owner": owner,
                        "pid": "read-post",
                        "feed_id": feed_id,
                        "category_id": "topics-category",
                        "processing": 0,
                        "read": True,
                        "tags": ["topics"],
                        "unix_date": 2,
                        "url": "https://example.com/read-post",
                        "content": {
                            "title": "Read post",
                            "content": gzip.compress(b"Read sentence."),
                        },
                    },
                    {
                        "owner": owner,
                        "pid": "partial-post",
                        "feed_id": feed_id,
                        "category_id": "topics-category",
                        "processing": 0,
                        "read": False,
                        "tags": ["topics"],
                        "unix_date": 1,
                        "url": "https://example.com/partial-post",
                        "content": {
                            "title": "Partially read post",
                            "content": gzip.compress(b"Mixed sentences."),
                        },
                    },
                ],
            },
        )
        self.app.post_grouping.save_grouped_posts(
            owner,
            ["unread-post"],
            [{"number": 1, "text": "Unread sentence.", "read": False}],
            {"Alpha > Unread": [1]},
        )
        # The post is read as a whole while its sentence flags stayed stale:
        # this is what happens for groupings rebuilt after a post was marked read.
        self.app.post_grouping.save_grouped_posts(
            owner,
            ["read-post"],
            [{"number": 1, "text": "Read sentence.", "read": False}],
            {"Beta > WholePostRead": [1]},
        )
        self.app.post_grouping.save_grouped_posts(
            owner,
            ["partial-post"],
            [
                {"number": 1, "text": "Still unread sentence.", "read": False},
                {"number": 2, "text": "Already read sentence.", "read": True},
            ],
            {"Gamma > StillUnread": [1], "Gamma > SentencesRead": [2]},
        )
        return sid

    def _get_hierarchy_data(self, sid: str) -> dict[str, Any]:
        client = self.get_authenticated_client(sid)
        response = client.get("/topic-hierarchy")
        self.assertEqual(response.status_code, 200)
        body: str = response.data.decode("utf-8")
        match: Optional[re.Match[str]] = re.search(
            r"window\.topic_hierarchy_data = (.+);", body
        )
        self.assertIsNotNone(match, "topic_hierarchy_data not found in page")
        return json.loads(match.group(1))

    @staticmethod
    def _collect_paths(nodes: list[dict[str, Any]]) -> set[str]:
        paths: set[str] = set()
        for node in nodes:
            paths.add(str(node.get("_topicPath", "")))
            paths |= TestWebTopicsOnlyUnread._collect_paths(node.get("children", []))
        return paths

    def test_hierarchy_hides_topics_of_fully_read_posts(self) -> None:
        sid: str = self._seed_topics("topics-only-unread", only_unread=True)

        data: dict[str, Any] = self._get_hierarchy_data(sid)
        paths: set[str] = self._collect_paths(data.get("children", []))

        self.assertIn("Alpha > Unread", paths)
        self.assertNotIn("Beta > WholePostRead", paths)
        # A hidden leaf must take its parent branch with it.
        self.assertNotIn("Beta", paths)

    def test_hierarchy_hides_topics_with_only_read_sentences(self) -> None:
        sid: str = self._seed_topics("topics-only-unread-sentences", only_unread=True)

        data: dict[str, Any] = self._get_hierarchy_data(sid)
        paths: set[str] = self._collect_paths(data.get("children", []))

        self.assertIn("Gamma > StillUnread", paths)
        self.assertNotIn("Gamma > SentencesRead", paths)
        self.assertIn("Gamma", paths)

    def test_hierarchy_shows_read_topics_when_setting_disabled(self) -> None:
        sid: str = self._seed_topics("topics-all-posts", only_unread=False)

        data: dict[str, Any] = self._get_hierarchy_data(sid)
        paths: set[str] = self._collect_paths(data.get("children", []))

        self.assertIn("Alpha > Unread", paths)
        self.assertIn("Beta > WholePostRead", paths)
        self.assertIn("Gamma > SentencesRead", paths)

    def test_topics_list_and_mindmap_hide_fully_read_posts(self) -> None:
        sid: str = self._seed_topics("topics-list-only-unread", only_unread=True)
        client = self.get_authenticated_client(sid)

        for url in ("/topics-list", "/topics-mindmap"):
            with self.subTest(url=url):
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                body: str = response.data.decode("utf-8")
                self.assertIn("StillUnread", body)
                self.assertNotIn("WholePostRead", body)

    def test_topic_snippets_page_resolves_branch_posts_server_side(self) -> None:
        sid: str = self._seed_topics("topic-snippets", only_unread=False)
        client = self.get_authenticated_client(sid)

        response = client.get("/topic-grouped-snippets?topic=Gamma")

        self.assertEqual(response.status_code, 200)
        body: str = response.data.decode("utf-8")
        self.assertIn("Still unread sentence.", body)
        self.assertIn("Already read sentence.", body)
        self.assertNotIn("/post-grouped/partial-post", body)
        self.assertNotIn("/post-grouped-snippets/partial-post", body)

    def test_topic_only_grouped_page_resolves_more_than_one_hundred_posts(self) -> None:
        """The topic URL must not grow with the number of matching posts."""
        user, sid = self.seed_test_user("topic-only-grouped", "topic-only-grouped")
        owner: str = user["sid"]
        feed_id: str = "topic-only-feed"
        topic: str = "Large topic"
        post_count: int = 101
        posts: list[dict[str, Any]] = []
        grouped_posts: list[tuple[str, dict[str, Any]]] = []

        for index in range(post_count):
            post_id: str = f"topic-only-post-{index:03d}"
            posts.append(
                {
                    "owner": owner,
                    "pid": post_id,
                    "feed_id": feed_id,
                    "processing": 0,
                    "read": False,
                    "tags": ["topics"],
                    "url": f"https://example.com/{post_id}",
                    "content": {
                        "title": f"Topic-only post {index}",
                        "content": gzip.compress(f"Sentence {index}.".encode("utf-8")),
                    },
                }
            )
            grouped_posts.append(
                (
                    post_id,
                    {"number": 0, "text": f"Sentence {index}.", "read": False},
                )
            )

        self.db_helper.init_db_from_dict(
            self.test_db,
            {
                "feeds": [
                    {
                        "owner": owner,
                        "feed_id": feed_id,
                        "category_id": "topic-only-category",
                        "category_title": "Topic-only category",
                        "local_url": f"/feed/{feed_id}",
                        "title": "Topic-only feed",
                        "url": "https://example.com/feed",
                        "favicon": "",
                        "processing": 0,
                    }
                ],
                "posts": posts,
            },
        )
        for post_id, sentence in grouped_posts:
            self.app.post_grouping.save_grouped_posts(
                owner, [post_id], [sentence], {topic: [0]}
            )

        client = self.get_authenticated_client(sid)
        response = client.get("/post-grouped?topic=Large%20topic")

        self.assertEqual(response.status_code, 200)
        body: str = response.data.decode("utf-8")
        self.assertEqual(body.count('id="post_topic-only-post-'), post_count)
        self.assertIn('window.post_id = "";', body)
