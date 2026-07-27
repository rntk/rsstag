"""Tests for the topic tags endpoint (/api/topic-tags).

The endpoint backs the "Tags" item of the per-topic context menu on the canvas
(/canvas) and hierarchy (/hierarchy) pages.
"""

import json
import unittest
from typing import Any

from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from rsstag.web.posts import (
    _collect_topic_tag_counts,
    _normalize_topic_path,
    _topic_scope_numbers,
    on_topic_tags_post,
)
from rsstag.web.routes import RSSTagRoutes
from tests.web_test_utils import MongoWebTestCase


class TestTopicPathHelpers(unittest.TestCase):
    """Pure helpers, no storage involved."""

    def test_normalize_topic_path_unifies_separators(self) -> None:
        self.assertEqual(_normalize_topic_path("A>B>C"), "A > B > C")
        self.assertEqual(_normalize_topic_path("A > B > C"), "A > B > C")
        self.assertEqual(_normalize_topic_path("  A >  B "), "A > B")

    def test_normalize_topic_path_drops_empty_parts(self) -> None:
        self.assertEqual(_normalize_topic_path(">A>>B>"), "A > B")
        self.assertEqual(_normalize_topic_path(""), "")
        self.assertEqual(_normalize_topic_path(None), "")

    def test_topic_scope_numbers_includes_nested_topics(self) -> None:
        groups: dict[str, Any] = {
            "Business > Finance": [1, 2],
            "Business > Finance > Banks": [3],
            "Business > Advertising": [4],
            "Business": [5],
        }
        self.assertEqual(
            _topic_scope_numbers(groups, "Business > Finance"), {1, 2, 3}
        )
        self.assertEqual(_topic_scope_numbers(groups, "Business"), {1, 2, 3, 4, 5})

    def test_topic_scope_numbers_ignores_sibling_prefixes(self) -> None:
        groups: dict[str, Any] = {
            "Sport": [1],
            "Sportswear": [2],
            "Sport > Football": [3],
        }
        self.assertEqual(_topic_scope_numbers(groups, "Sport"), {1, 3})

    def test_topic_scope_numbers_accepts_both_separators(self) -> None:
        self.assertEqual(
            _topic_scope_numbers({"Business>Finance": [7]}, "Business > Finance"), {7}
        )

    def test_topic_scope_numbers_skips_malformed_entries(self) -> None:
        groups: dict[str, Any] = {"Sport": [1, "two", None], "Music": "nope"}
        self.assertEqual(_topic_scope_numbers(groups, "Sport"), {1})


class StubPostGrouping:
    def __init__(self, docs: dict[str, dict[str, Any]]) -> None:
        self._docs: dict[str, dict[str, Any]] = docs

    def get_grouped_posts(self, owner: str, post_ids: list[Any]) -> Any:
        if len(post_ids) != 1:
            return None
        return self._docs.get(str(post_ids[0]))


class StubPosts:
    def __init__(self, posts: dict[str, list[str]]) -> None:
        self._posts: dict[str, list[str]] = posts

    def get_by_pids(self, owner: str, pids: list[str], projection: Any = None) -> Any:
        return [
            {"pid": pid, "tags": self._posts[pid]} for pid in pids if pid in self._posts
        ]


class StubTags:
    def __init__(self, words: dict[str, list[str]]) -> None:
        self._words: dict[str, list[str]] = words

    def get_by_tags(self, owner: str, tags: list[str], projection: Any = None) -> Any:
        return [
            {"tag": tag, "words": self._words[tag]} for tag in tags if tag in self._words
        ]


class StubApp:
    def __init__(
        self,
        groupings: dict[str, dict[str, Any]],
        posts: dict[str, list[str]],
        tag_words: dict[str, list[str]],
    ) -> None:
        self.post_grouping: StubPostGrouping = StubPostGrouping(groupings)
        self.posts: StubPosts = StubPosts(posts)
        self.tags: StubTags = StubTags(tag_words)
        # The real route map needs no database, and the handler builds tag
        # links through it.
        self.routes: RSSTagRoutes = RSSTagRoutes("localhost")


class TestCollectTopicTagCounts(unittest.TestCase):
    """Tag counting itself, with storage stubbed out (no MongoDB needed)."""

    def setUp(self) -> None:
        self.app: Any = StubApp(
            groupings={
                "post-1": {
                    "sentences": [
                        {"number": 1, "text": "The banks raised rates.", "read": False},
                        {"number": 2, "text": "Another bank followed.", "read": True},
                        {"number": 3, "text": "Football is unrelated.", "read": False},
                    ],
                    "groups": {
                        "Business > Finance": [1, 2],
                        "Sport > Football": [3],
                    },
                },
                "post-2": {
                    "sentences": [
                        {"number": 1, "text": "A bank opened a branch.", "read": True}
                    ],
                    "groups": {"Business > Finance > Banks": [1]},
                },
            },
            posts={
                "post-1": ["bank", "football", "rate"],
                "post-2": ["bank"],
            },
            tag_words={
                "bank": ["bank", "banks"],
                "football": ["football"],
                "rate": ["rate", "rates"],
            },
        )

    def test_every_sentence_counts_when_only_unread_is_off(self) -> None:
        counters, sentences_count = _collect_topic_tag_counts(
            self.app, "sid", ["post-1", "post-2"], "Business > Finance", False
        )
        self.assertEqual(sentences_count, 3)
        self.assertEqual(counters["bank"]["count"], 3)
        self.assertEqual(counters["bank"]["posts"], {"post-1", "post-2"})

    def test_read_sentences_drop_out_when_only_unread_is_on(self) -> None:
        counters, sentences_count = _collect_topic_tag_counts(
            self.app, "sid", ["post-1", "post-2"], "Business > Finance", True
        )
        self.assertEqual(sentences_count, 1)
        self.assertEqual(counters["bank"]["count"], 1)
        self.assertEqual(counters["bank"]["posts"], {"post-1"})

    def test_surface_forms_of_the_lemma_are_matched(self) -> None:
        counters, _ = _collect_topic_tag_counts(
            self.app, "sid", ["post-1"], "Business > Finance", False
        )
        # "rates" is a surface form of the "rate" lemma.
        self.assertEqual(counters["rate"]["count"], 1)

    def test_sibling_topics_do_not_leak_in(self) -> None:
        counters, sentences_count = _collect_topic_tag_counts(
            self.app, "sid", ["post-1", "post-2"], "Business > Finance", False
        )
        self.assertNotIn("football", counters)
        self.assertEqual(sentences_count, 3)

    def test_tags_are_matched_on_word_boundaries(self) -> None:
        app: Any = StubApp(
            groupings={
                "p": {
                    "sentences": [{"number": 1, "text": "Ranking bands.", "read": False}],
                    "groups": {"T": [1]},
                }
            },
            posts={"p": ["rank", "band"]},
            tag_words={"rank": ["rank"], "band": ["band", "bands"]},
        )
        counters, _ = _collect_topic_tag_counts(app, "sid", ["p"], "T", False)
        # "rank" is only a substring of "Ranking" and must not match.
        self.assertNotIn("rank", counters)
        self.assertEqual(counters["band"]["count"], 1)

    def test_multi_word_surface_forms_are_matched(self) -> None:
        app: Any = StubApp(
            groupings={
                "p": {
                    "sentences": [
                        {"number": 1, "text": "The central bank met.", "read": False}
                    ],
                    "groups": {"T": [1]},
                }
            },
            posts={"p": ["centralbank"]},
            tag_words={"centralbank": ["central bank"]},
        )
        counters, _ = _collect_topic_tag_counts(app, "sid", ["p"], "T", False)
        self.assertEqual(counters["centralbank"]["count"], 1)

    def test_short_tags_are_skipped(self) -> None:
        app: Any = StubApp(
            groupings={
                "p": {
                    "sentences": [{"number": 1, "text": "EU and banks.", "read": False}],
                    "groups": {"T": [1]},
                }
            },
            posts={"p": ["eu", "bank"]},
            tag_words={"eu": ["eu"], "bank": ["banks"]},
        )
        counters, _ = _collect_topic_tag_counts(app, "sid", ["p"], "T", False)
        self.assertNotIn("eu", counters)
        self.assertIn("bank", counters)

    def test_a_post_without_grouping_is_skipped(self) -> None:
        counters, sentences_count = _collect_topic_tag_counts(
            self.app, "sid", ["missing"], "Business > Finance", False
        )
        self.assertEqual(counters, {})
        self.assertEqual(sentences_count, 0)

    def test_a_tag_without_a_tag_document_falls_back_to_the_lemma(self) -> None:
        app: Any = StubApp(
            groupings={
                "p": {
                    "sentences": [{"number": 1, "text": "About crypto.", "read": False}],
                    "groups": {"T": [1]},
                }
            },
            posts={"p": ["crypto"]},
            tag_words={},
        )
        counters, _ = _collect_topic_tag_counts(app, "sid", ["p"], "T", False)
        self.assertEqual(counters["crypto"]["count"], 1)


class TestTopicTagsHandler(unittest.TestCase):
    """The request/response contract of the handler, with storage stubbed."""

    def setUp(self) -> None:
        self.app: Any = StubApp(
            groupings={
                "post-1": {
                    "sentences": [
                        {"number": 1, "text": "The banks raised rates.", "read": False},
                        {"number": 2, "text": "Another bank followed.", "read": True},
                        {"number": 3, "text": "Football is unrelated.", "read": False},
                    ],
                    "groups": {
                        "Business > Finance": [1, 2],
                        "Sport > Football": [3],
                    },
                },
                "post-2": {
                    "sentences": [
                        {"number": 1, "text": "A bank opened a branch.", "read": True}
                    ],
                    "groups": {"Business > Finance > Banks": [1]},
                },
            },
            posts={"post-1": ["bank", "football", "rate"], "post-2": ["bank"]},
            tag_words={
                "bank": ["bank", "banks"],
                "football": ["football"],
                "rate": ["rate", "rates"],
            },
        )
        self.user: dict[str, Any] = {
            "sid": "topic-tags-sid",
            "settings": {"only_unread": False},
        }

    @staticmethod
    def _request(body: str) -> Request:
        return Request(
            EnvironBuilder(
                method="POST", data=body, content_type="application/json"
            ).get_environ()
        )

    def _call(self, **body: Any) -> tuple[int, dict[str, Any]]:
        response = on_topic_tags_post(
            self.app, self.user, self._request(json.dumps(body))
        )
        return response.status_code, json.loads(response.get_data(as_text=True))

    def test_every_sentence_is_reported_when_only_unread_is_off(self) -> None:
        status, payload = self._call(
            topic="Business > Finance", post_ids=["post-1", "post-2"]
        )
        self.assertEqual(status, 200)
        data = payload["data"]
        self.assertEqual(data["topic"], "Business > Finance")
        self.assertEqual(data["sentences_count"], 3)
        tags = {tag["tag"]: tag for tag in data["tags"]}
        self.assertEqual(tags["bank"]["count"], 3)
        # The two read matches and the unread one span both posts.
        self.assertEqual(tags["bank"]["posts_count"], 2)
        self.assertNotIn("football", tags)

    def test_the_only_unread_setting_narrows_counts_and_posts(self) -> None:
        self.user["settings"]["only_unread"] = True
        _, payload = self._call(
            topic="Business > Finance", post_ids=["post-1", "post-2"]
        )
        data = payload["data"]
        self.assertEqual(data["sentences_count"], 1)
        tags = {tag["tag"]: tag for tag in data["tags"]}
        self.assertEqual(tags["bank"]["count"], 1)
        self.assertEqual(tags["bank"]["posts_count"], 1)

    def test_a_tag_of_read_sentences_only_drops_out_for_only_unread(self) -> None:
        self.user["settings"]["only_unread"] = True
        _, payload = self._call(topic="Business > Finance > Banks", post_ids=["post-2"])
        data = payload["data"]
        self.assertEqual(data["sentences_count"], 0)
        self.assertEqual(data["tags"], [])

    def test_tags_are_sorted_by_count_then_name(self) -> None:
        _, payload = self._call(
            topic="Business > Finance", post_ids=["post-1", "post-2"]
        )
        counts = [(tag["count"], tag["tag"]) for tag in payload["data"]["tags"]]
        self.assertEqual(counts, sorted(counts, key=lambda item: (-item[0], item[1])))

    def test_tag_links_point_to_the_tag_info_page(self) -> None:
        _, payload = self._call(topic="Business > Finance", post_ids=["post-1"])
        tags = {tag["tag"]: tag for tag in payload["data"]["tags"]}
        self.assertEqual(tags["bank"]["url"], "/tag-info/bank")

    def test_topic_separator_is_normalized_in_the_response(self) -> None:
        _, payload = self._call(topic="Business>Finance", post_ids=["post-1"])
        self.assertEqual(payload["data"]["topic"], "Business > Finance")

    def test_empty_post_ids_return_an_empty_result(self) -> None:
        status, payload = self._call(topic="Business > Finance", post_ids=[])
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["tags"], [])
        self.assertEqual(payload["data"]["sentences_count"], 0)

    def test_missing_topic_is_rejected(self) -> None:
        status, payload = self._call(topic="  ", post_ids=["post-1"])
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_malformed_json_is_rejected(self) -> None:
        response = on_topic_tags_post(
            self.app, self.user, self._request("{not json")
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", json.loads(response.get_data(as_text=True)))

    def test_storage_failure_returns_500(self) -> None:
        def boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("storage down")

        self.app.post_grouping.get_grouped_posts = boom
        status, payload = self._call(
            topic="Business > Finance", post_ids=["post-1"]
        )
        self.assertEqual(status, 500)
        self.assertIn("error", payload)


class TestWebTopicTags(MongoWebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.owner = "topictagsuser"
        _, self.sid = self.seed_test_user(self.owner, "password")
        self.client = self.get_authenticated_client(self.sid)
        # Seeded users get only_unread on; most cases here check the full scope.
        self._set_only_unread(False)

        self.test_db.posts.insert_one(
            {
                "owner": self.sid,
                "pid": "post-1",
                "feed_id": "feed-1",
                "read": False,
                "processing": 0,
                "tags": ["bank", "football", "advert"],
                "content": {"title": "First post"},
            }
        )
        self.test_db.posts.insert_one(
            {
                "owner": self.sid,
                "pid": "post-2",
                "feed_id": "feed-1",
                "read": False,
                "processing": 0,
                "tags": ["bank"],
                "content": {"title": "Second post"},
            }
        )
        for tag, words in (
            ("bank", ["bank", "banks"]),
            ("football", ["football"]),
            ("advert", ["advert"]),
        ):
            self.test_db.tags.insert_one(
                {
                    "owner": self.sid,
                    "tag": tag,
                    "words": words,
                    "posts_count": 1,
                    "unread_count": 1,
                    "local_url": f"/entity/{tag}",
                    "processing": 0,
                    "temperature": 1,
                    "freq": 1.0,
                    "sentiment": [],
                }
            )

        self.app.post_grouping.save_grouped_posts(
            self.sid,
            ["post-1"],
            [
                {"number": 1, "text": "The banks raised rates.", "read": False},
                {"number": 2, "text": "Another bank followed.", "read": True},
                {"number": 3, "text": "Football is unrelated here.", "read": False},
            ],
            {"Business > Finance": [1, 2], "Sport > Football": [3]},
        )
        self.app.post_grouping.save_grouped_posts(
            self.sid,
            ["post-2"],
            [{"number": 1, "text": "A bank opened a branch.", "read": True}],
            {"Business > Finance > Banks": [1]},
        )

    def _set_only_unread(self, only_unread: bool) -> None:
        self.test_db.users.update_one(
            {"sid": self.sid}, {"$set": {"settings.only_unread": only_unread}}
        )

    def _request(
        self, topic: str, post_ids: list[str]
    ) -> tuple[int, dict[str, Any]]:
        response = self.client.post(
            "/api/topic-tags",
            data=json.dumps({"topic": topic, "post_ids": post_ids}),
            content_type="application/json",
        )
        return response.status_code, json.loads(response.get_data(as_text=True))

    def test_returns_tags_of_the_topic_scope(self) -> None:
        status, payload = self._request("Business > Finance", ["post-1", "post-2"])
        self.assertEqual(status, 200)
        tags = {tag["tag"]: tag for tag in payload["data"]["tags"]}
        self.assertIn("bank", tags)
        # "football" belongs to a sibling topic, so it must not appear here.
        self.assertNotIn("football", tags)
        self.assertEqual(tags["bank"]["count"], 3)
        self.assertEqual(tags["bank"]["posts_count"], 2)
        self.assertEqual(payload["data"]["sentences_count"], 3)

    def test_matches_surface_forms_of_the_tag_lemma(self) -> None:
        _, payload = self._request("Business > Finance", ["post-1"])
        tags = {tag["tag"]: tag for tag in payload["data"]["tags"]}
        # "banks" is a surface form of the "bank" lemma: both sentences count.
        self.assertEqual(tags["bank"]["count"], 2)

    def test_the_only_unread_setting_keeps_unread_sentences_only(self) -> None:
        self._set_only_unread(True)
        _, payload = self._request("Business > Finance", ["post-1", "post-2"])
        tags = {tag["tag"]: tag for tag in payload["data"]["tags"]}
        self.assertEqual(tags["bank"]["count"], 1)
        self.assertEqual(tags["bank"]["posts_count"], 1)
        self.assertEqual(payload["data"]["sentences_count"], 1)

    def test_nested_topics_are_included(self) -> None:
        _, payload = self._request("Business", ["post-1", "post-2"])
        self.assertEqual(payload["data"]["sentences_count"], 3)
        _, only_leaf = self._request("Business > Finance > Banks", ["post-2"])
        self.assertEqual(only_leaf["data"]["sentences_count"], 1)

    def test_tag_url_points_to_the_tag_info_page(self) -> None:
        _, payload = self._request("Business > Finance", ["post-1"])
        tags = {tag["tag"]: tag for tag in payload["data"]["tags"]}
        self.assertEqual(tags["bank"]["url"], "/tag-info/bank")

    def test_topic_path_separator_is_normalized(self) -> None:
        _, with_spaces = self._request("Business > Finance", ["post-1"])
        _, without_spaces = self._request("Business>Finance", ["post-1"])
        self.assertEqual(with_spaces["data"], without_spaces["data"])

    def test_unknown_topic_returns_empty_tags(self) -> None:
        status, payload = self._request("Nothing > Here", ["post-1"])
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["tags"], [])
        self.assertEqual(payload["data"]["sentences_count"], 0)

    def test_missing_topic_is_rejected(self) -> None:
        status, payload = self._request("", ["post-1"])
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_invalid_json_is_rejected(self) -> None:
        response = self.client.post(
            "/api/topic-tags", data="{not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_requires_authentication(self) -> None:
        response = self.build_client().post(
            "/api/topic-tags",
            data=json.dumps({"topic": "Business", "post_ids": ["post-1"]}),
            content_type="application/json",
        )
        self.assertIn(response.status_code, [301, 302])


if __name__ == "__main__":
    unittest.main()
