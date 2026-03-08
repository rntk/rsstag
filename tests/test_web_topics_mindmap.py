import gzip
import json
from typing import Any

from tests.web_test_utils import MongoWebTestCase


class TestWebTopicsMindmap(MongoWebTestCase):
    def _seed_mindmap_fixture(self) -> str:
        user, sid = self.seed_test_user("mindmap-user")

        self.test_db.feeds.insert_many(
            [
                {
                    "owner": user["sid"],
                    "feed_id": "feed-1",
                    "category_id": "cat-platform",
                    "category_title": "Platform",
                    "category_local_url": "/category/cat-platform",
                    "local_url": "/feed/feed-1",
                    "title": "Platform Feed",
                    "url": "http://example.com/feed-1",
                    "favicon": "",
                    "processing": 0,
                },
                {
                    "owner": user["sid"],
                    "feed_id": "feed-2",
                    "category_id": "cat-search",
                    "category_title": "Search",
                    "category_local_url": "/category/cat-search",
                    "local_url": "/feed/feed-2",
                    "title": "Search Feed",
                    "url": "http://example.com/feed-2",
                    "favicon": "",
                    "processing": 0,
                },
                {
                    "owner": user["sid"],
                    "feed_id": "feed-3",
                    "category_id": "cat-sports",
                    "category_title": "Sports",
                    "category_local_url": "/category/cat-sports",
                    "local_url": "/feed/feed-3",
                    "title": "Sports Feed",
                    "url": "http://example.com/feed-3",
                    "favicon": "",
                    "processing": 0,
                },
            ]
        )

        self.test_db.posts.insert_many(
            [
                {
                    "owner": user["sid"],
                    "pid": "p1",
                    "feed_id": "feed-1",
                    "processing": 0,
                    "read": False,
                    "tags": ["gemini", "ai"],
                    "content": {
                        "title": "Gemini Launch",
                        "content": gzip.compress(b"Gemini launch. AI agents."),
                    },
                    "url": "http://example.com/p1",
                },
                {
                    "owner": user["sid"],
                    "pid": "p2",
                    "feed_id": "feed-2",
                    "processing": 0,
                    "read": False,
                    "tags": ["google", "search"],
                    "content": {
                        "title": "Search Update",
                        "content": gzip.compress(b"Search update."),
                    },
                    "url": "http://example.com/p2",
                },
                {
                    "owner": user["sid"],
                    "pid": "p3",
                    "feed_id": "feed-3",
                    "processing": 0,
                    "read": False,
                    "tags": ["football"],
                    "content": {
                        "title": "Football News",
                        "content": gzip.compress(b"Football final."),
                    },
                    "url": "http://example.com/p3",
                },
            ]
        )

        self.app.post_grouping.save_grouped_posts(
            user["sid"],
            ["p1"],
            [
                {"number": 1, "text": "Gemini launch", "read": False},
                {"number": 2, "text": "AI agents", "read": False},
            ],
            {
                "Technology > Google": [1],
                "Technology > Google > Gemini": [1],
                "Technology > AI": [2],
            },
        )
        self.app.post_grouping.save_grouped_posts(
            user["sid"],
            ["p2"],
            [{"number": 1, "text": "Search update", "read": False}],
            {
                "Technology > Google": [1],
                "Technology > Google > Search": [1],
            },
        )
        self.app.post_grouping.save_grouped_posts(
            user["sid"],
            ["p3"],
            [{"number": 1, "text": "Football final", "read": False}],
            {"Sports > Football": [1]},
        )

        return sid

    def _post_node_data(self, sid: str, payload: dict[str, Any]) -> dict[str, Any]:
        client = self.get_authenticated_client(sid)
        response = client.post(
            "/api/mindmap-node-data",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        assert result is not None
        return result

    def test_mindmap_node_data_returns_subtopics_sources_categories_and_tags(self) -> None:
        sid = self._seed_mindmap_fixture()
        scope: dict[str, Any] = {
            "node_kind": "topic",
            "topic_path": "Technology",
            "post_ids": ["p1", "p2"],
        }

        subtopics = self._post_node_data(sid, {"action": "subtopics", "scope": scope})
        subtopic_names = [item["name"] for item in subtopics["items"]]
        self.assertEqual(subtopics["result_type"], "nodes")
        self.assertEqual(subtopic_names, ["Google", "AI"])
        self.assertIn("subtopics", subtopics["available_actions"])
        self.assertEqual(subtopics["items"][0]["scope"]["topic_path"], "Technology > Google")

        sources = self._post_node_data(sid, {"action": "sources", "scope": scope})
        source_names = {item["name"] for item in sources["items"]}
        self.assertEqual(source_names, {"Platform Feed", "Search Feed"})
        self.assertEqual(sources["items"][0]["node_kind"], "source")
        self.assertIn("available_actions", sources["items"][0])

        categories = self._post_node_data(sid, {"action": "categories", "scope": scope})
        category_names = {item["name"] for item in categories["items"]}
        self.assertEqual(category_names, {"Platform", "Search"})
        self.assertEqual(categories["items"][0]["node_kind"], "category")

        tags = self._post_node_data(sid, {"action": "tags", "scope": scope})
        tag_names = {item["name"] for item in tags["items"]}
        self.assertTrue({"gemini", "ai", "google", "search"}.issubset(tag_names))
        gemini_scope = next(item["scope"] for item in tags["items"] if item["name"] == "gemini")
        self.assertEqual(gemini_scope["tags"], ["gemini"])

    def test_mindmap_node_data_returns_snippets_for_scoped_sentences(self) -> None:
        sid = self._seed_mindmap_fixture()
        payload: dict[str, Any] = {
            "action": "sentences",
            "scope": {
                "node_kind": "tag",
                "topic_path": "Technology",
                "post_ids": ["p1", "p2"],
                "tags": ["gemini"],
            },
        }

        response_data = self._post_node_data(sid, payload)

        self.assertEqual(response_data["result_type"], "snippets")
        self.assertEqual(response_data["count"], 1)
        self.assertEqual(response_data["snippet_count"], 2)

        snippet_panel = response_data["items"][0]
        self.assertEqual(snippet_panel["node_kind"], "snippet_panel")
        snippet_texts = {snippet["text"] for snippet in snippet_panel["snippets"]}
        self.assertEqual(snippet_texts, {"Gemini launch", "AI agents"})
        for snippet in snippet_panel["snippets"]:
            self.assertEqual(snippet["post_id"], "p1")
            self.assertEqual(snippet["category_title"], "Platform")
            self.assertIn("gemini", snippet["post_tags"])

    def test_mindmap_node_data_rejects_invalid_payloads(self) -> None:
        sid = self._seed_mindmap_fixture()
        client = self.get_authenticated_client(sid)

        missing_scope = client.post(
            "/api/mindmap-node-data",
            data=json.dumps({"action": "tags"}),
            content_type="application/json",
        )
        bad_action = client.post(
            "/api/mindmap-node-data",
            data=json.dumps({"action": "unknown", "scope": {}}),
            content_type="application/json",
        )

        self.assertEqual(missing_scope.status_code, 400)
        self.assertEqual(bad_action.status_code, 400)
