import json

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

        feeds = client.post("/api/context-filter/suggestions", data={"type": "feed", "req": "feed-"})
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
            ["feed-1", "feed-2"],
        )
        self.assertEqual(
            [item["value"] for item in categories.get_json()["data"]],
            ["cat-1", "cat-2"],
        )
        self.assertIn("Technology", [item["value"] for item in topics.get_json()["data"]])
        self.assertIn(
            "Technology > AI",
            [item["value"] for item in subtopics.get_json()["data"]],
        )

    def test_context_filter_suggestions_rejects_unknown_type(self):
        sid = self._seed_filter_fixture()
        client = self.get_authenticated_client(sid)
        response = client.post("/api/context-filter/suggestions", data={"type": "unknown", "req": "x"})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    import unittest

    unittest.main()
