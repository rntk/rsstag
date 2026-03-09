import json
import re

from tests.web_test_utils import MongoWebTestCase


class TestWebContextFilter(MongoWebTestCase):
    def _seed_filter_fixture(self):
        user, sid = self.seed_test_user("ctx-filter")
        self.test_db.feeds.insert_many(
            [
                {
                    "owner": sid,
                    "feed_id": "feed-1",
                    "category_id": "cat-1",
                    "category_title": "Cat One",
                    "category_local_url": "/category/cat-1",
                    "local_url": "/feed/feed-1",
                    "title": "Feed One",
                    "url": "http://example.com/feed-1",
                    "favicon": "",
                    "processing": 0,
                },
                {
                    "owner": sid,
                    "feed_id": "feed-2",
                    "category_id": "cat-2",
                    "category_title": "Cat Two",
                    "category_local_url": "/category/cat-2",
                    "local_url": "/feed/feed-2",
                    "title": "Feed Two",
                    "url": "http://example.com/feed-2",
                    "favicon": "",
                    "processing": 0,
                },
            ]
        )
        self.app.post_grouping.save_grouped_posts(
            sid,
            ["p1"],
            [{"number": 1, "text": "Sentence", "read": False}],
            {
                "Technology": [1],
                "Technology > AI": [1],
                "Technology > AI > Agents": [1],
            },
        )
        return sid

    def _extract_tags_from_group_page(self, response) -> dict[str, int]:
        html = response.get_data(as_text=True)
        match = re.search(r"var initial_tags_list = (.*?);", html, re.DOTALL)
        self.assertIsNotNone(match)
        tags_payload = json.loads(match.group(1))
        return {item["tag"]: item["count"] for item in tags_payload}

    def _seed_feed_scoped_tag_fixture(self):
        _, sid = self.seed_test_user("ctx-feed-scope")
        self.test_db.feeds.insert_many(
            [
                {
                    "owner": sid,
                    "feed_id": "feed-alpha",
                    "category_id": "cat-alpha",
                    "category_title": "Cat Alpha",
                    "category_local_url": "/category/cat-alpha",
                    "local_url": "/feed/feed-alpha",
                    "title": "Feed Alpha",
                    "url": "http://example.com/feed-alpha",
                    "favicon": "",
                    "processing": 0,
                },
                {
                    "owner": sid,
                    "feed_id": "feed-beta",
                    "category_id": "cat-beta",
                    "category_title": "Cat Beta",
                    "category_local_url": "/category/cat-beta",
                    "local_url": "/feed/feed-beta",
                    "title": "Feed Beta",
                    "url": "http://example.com/feed-beta",
                    "favicon": "",
                    "processing": 0,
                },
            ]
        )

        self.test_db.posts.insert_many(
            [
                {
                    "owner": sid,
                    "pid": "alpha-1",
                    "feed_id": "feed-alpha",
                    "category_id": "cat-alpha",
                    "tags": ["alpha", "shared"],
                    "read": False,
                    "processing": 0,
                },
                {
                    "owner": sid,
                    "pid": "alpha-2",
                    "feed_id": "feed-alpha",
                    "category_id": "cat-alpha",
                    "tags": ["alpha"],
                    "read": False,
                    "processing": 0,
                },
                {
                    "owner": sid,
                    "pid": "beta-1",
                    "feed_id": "feed-beta",
                    "category_id": "cat-beta",
                    "tags": ["beta", "shared"],
                    "read": False,
                    "processing": 0,
                },
                {
                    "owner": sid,
                    "pid": "beta-2",
                    "feed_id": "feed-beta",
                    "category_id": "cat-beta",
                    "tags": ["beta"],
                    "read": False,
                    "processing": 0,
                },
            ]
        )

        self.test_db.tags.insert_many(
            [
                {
                    "owner": sid,
                    "tag": "alpha",
                    "posts_count": 2,
                    "unread_count": 2,
                    "words": ["alpha"],
                    "local_url": "/entity/alpha",
                    "classifications": [{"category": "Alpha Domain", "count": 2}],
                    "processing": 0,
                },
                {
                    "owner": sid,
                    "tag": "beta",
                    "posts_count": 2,
                    "unread_count": 2,
                    "words": ["beta"],
                    "local_url": "/entity/beta",
                    "classifications": [{"category": "Beta Domain", "count": 2}],
                    "processing": 0,
                },
                {
                    "owner": sid,
                    "tag": "shared",
                    "posts_count": 2,
                    "unread_count": 2,
                    "words": ["shared"],
                    "local_url": "/entity/shared",
                    "classifications": [{"category": "Cross Domain", "count": 2}],
                    "processing": 0,
                },
            ]
        )
        self.test_db.letters.insert_many(
            [
                {"owner": sid, "letter": "a", "unread_count": 2, "posts_count": 2},
                {"owner": sid, "letter": "b", "unread_count": 2, "posts_count": 2},
                {"owner": sid, "letter": "s", "unread_count": 2, "posts_count": 2},
            ]
        )
        return sid

    def test_context_filter_add_item_validates_topic_and_subtopic(self):
        sid = self._seed_filter_fixture()
        client = self.get_authenticated_client(sid)

        ok_topic = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "topic", "value": "Technology > AI"}),
            content_type="application/json",
        )
        self.assertEqual(ok_topic.status_code, 200)

        bad_topic = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "topic", "value": "Missing > Topic"}),
            content_type="application/json",
        )
        self.assertEqual(bad_topic.status_code, 404)

        ok_subtopic = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "subtopic", "value": "Technology > AI > Agents"}),
            content_type="application/json",
        )
        self.assertEqual(ok_subtopic.status_code, 200)

        bad_subtopic = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "subtopic", "value": "Technology"}),
            content_type="application/json",
        )
        self.assertEqual(bad_subtopic.status_code, 404)

    def test_context_filter_suggestions_supports_all_new_types(self):
        sid = self._seed_filter_fixture()
        client = self.get_authenticated_client(sid)

        feeds = client.post("/api/context-filter/suggestions", data={"type": "feed", "req": "feed one"})
        categories = client.post(
            "/api/context-filter/suggestions", data={"type": "category", "req": "cat-"}
        )
        topics = client.post(
            "/api/context-filter/suggestions", data={"type": "topic", "req": "technology"}
        )
        subtopics = client.post(
            "/api/context-filter/suggestions", data={"type": "subtopic", "req": "ai"}
        )

        self.assertEqual(feeds.status_code, 200)
        self.assertEqual(categories.status_code, 200)
        self.assertEqual(topics.status_code, 200)
        self.assertEqual(subtopics.status_code, 200)

        self.assertEqual(
            [item["value"] for item in feeds.get_json()["data"]],
            ["feed-1"],
        )
        self.assertEqual(feeds.get_json()["data"][0]["label"], "Feed One")
        self.assertEqual(feeds.get_json()["data"][0]["meta"], "feed-1")
        self.assertEqual(
            [item["value"] for item in categories.get_json()["data"]],
            ["cat-1", "cat-2"],
        )
        self.assertEqual(categories.get_json()["data"][0]["meta"], "1 feed")
        topic_items = topics.get_json()["data"]
        self.assertIn("Technology", [item["value"] for item in topic_items])
        self.assertTrue(
            any(
                item["meta"].endswith("sentence") or item["meta"].endswith("sentences")
                for item in topic_items
            )
        )
        self.assertIn(
            "Technology > AI",
            [item["value"] for item in subtopics.get_json()["data"]],
        )

    def test_context_filter_suggestions_rejects_unknown_type(self):
        sid = self._seed_filter_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post("/api/context-filter/suggestions", data={"type": "unknown", "req": "x"})
        self.assertEqual(response.status_code, 400)

    def test_context_filter_feed_scopes_group_tag_counts(self):
        sid = self._seed_feed_scoped_tag_fixture()
        client = self.get_authenticated_client(sid)

        no_filter_response = client.get("/group/tag/1")
        self.assertEqual(no_filter_response.status_code, 200)
        no_filter_counts = self._extract_tags_from_group_page(no_filter_response)
        self.assertEqual(no_filter_counts["alpha"], 2)
        self.assertEqual(no_filter_counts["beta"], 2)
        self.assertEqual(no_filter_counts["shared"], 2)

        add_filter_response = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "feed", "value": "feed-alpha"}),
            content_type="application/json",
        )
        self.assertEqual(add_filter_response.status_code, 200)

        scoped_response = client.get("/group/tag/1")
        self.assertEqual(scoped_response.status_code, 200)
        scoped_counts = self._extract_tags_from_group_page(scoped_response)

        self.assertEqual(scoped_counts.get("alpha"), 2)
        self.assertEqual(scoped_counts.get("shared"), 1)
        self.assertNotIn("beta", scoped_counts)


    def test_context_filter_active_with_no_matching_posts_returns_empty_tag_lists(self):
        sid = self._seed_feed_scoped_tag_fixture()
        client = self.get_authenticated_client(sid)

        add_filter_response = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "feed", "value": "feed-missing"}),
            content_type="application/json",
        )
        self.assertEqual(add_filter_response.status_code, 200)

        scoped_tags = self._extract_tags_from_group_page(client.get("/group/tag/1"))
        self.assertEqual(scoped_tags, {})

        scoped_categories = self._extract_tags_from_group_page(client.get("/group/tags-categories/1"))
        self.assertEqual(scoped_categories, {})

    def test_context_filter_feed_scopes_tag_categories(self):
        sid = self._seed_feed_scoped_tag_fixture()
        client = self.get_authenticated_client(sid)

        unscoped_categories = self._extract_tags_from_group_page(client.get("/group/tags-categories/1"))
        self.assertEqual(unscoped_categories["Alpha Domain"], 1)
        self.assertEqual(unscoped_categories["Beta Domain"], 1)
        self.assertEqual(unscoped_categories["Cross Domain"], 1)

        add_filter_response = client.post(
            "/api/context-filter/item",
            data=json.dumps({"type": "feed", "value": "feed-alpha"}),
            content_type="application/json",
        )
        self.assertEqual(add_filter_response.status_code, 200)

        scoped_categories = self._extract_tags_from_group_page(client.get("/group/tags-categories/1"))
        self.assertEqual(scoped_categories["Alpha Domain"], 1)
        self.assertEqual(scoped_categories["Cross Domain"], 1)
        self.assertNotIn("Beta Domain", scoped_categories)


if __name__ == "__main__":
    import unittest

    unittest.main()
