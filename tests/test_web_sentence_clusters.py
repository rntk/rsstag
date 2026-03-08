import gzip
from typing import Tuple

from tests.web_test_utils import MongoWebTestCase


class TestWebSentenceClusters(MongoWebTestCase):
    def _seed_sentence_cluster_fixture(self) -> Tuple[dict, str]:
        user, sid = self.seed_test_user("snippetweb")
        self.test_db.feeds.insert_one(
            {
                "owner": user["sid"],
                "feed_id": "feed-1",
                "category_id": "cat-1",
                "category_title": "Category",
                "category_local_url": "/category/cat-1",
                "local_url": "/feed/feed-1",
                "title": "Feed One",
                "url": "http://example.com/feed-1",
                "favicon": "",
                "processing": 0,
            }
        )
        self.test_db.posts.insert_one(
            {
                "owner": user["sid"],
                "pid": "p1",
                "feed_id": "feed-1",
                "processing": 0,
                "read": False,
                "tags": ["alpha", "gemini"],
                "content": {
                    "title": "Alpha Post",
                    "content": gzip.compress(
                        b"Sentence one. Sentence two. Sentence three."
                    ),
                },
                "url": "http://example.com/p1",
            }
        )
        self.test_db.posts.insert_one(
            {
                "owner": user["sid"],
                "pid": "p2",
                "feed_id": "feed-1",
                "processing": 0,
                "read": False,
                "tags": ["alpha", "other"],
                "content": {
                    "title": "Beta Post",
                    "content": gzip.compress(
                        b"Another sentence. Another follow up."
                    ),
                },
                "url": "http://example.com/p2",
            }
        )

        self.app.post_grouping.save_grouped_posts(
            user["sid"],
            ["p1"],
            [
                {"number": 1, "text": "Sentence one", "read": False},
                {"number": 2, "text": "Sentence two", "read": False},
                {"number": 3, "text": "Sentence three", "read": True},
            ],
            {"Topic A": [1, 2], "Topic B": [3]},
        )
        self.app.post_grouping.save_grouped_posts(
            user["sid"],
            ["p2"],
            [
                {"number": 1, "text": "Another sentence", "read": False},
                {"number": 2, "text": "Another follow up", "read": False},
            ],
            {"Topic C": [1, 2]},
        )
        self.app.snippet_clusters.replace_clusters(
            user["sid"],
            [
                {
                    "cluster_id": 5,
                    "title": "alpha, another",
                    "item_count": 2,
                    "post_ids": ["p1", "p2"],
                    "snippet_refs": [
                        {"post_id": "p1", "topic": "Topic A", "indices": [1, 2]},
                        {"post_id": "p2", "topic": "Topic C", "indices": [1, 2]},
                    ],
                }
            ],
        )

        return user, sid

    def test_sentence_clusters_pages_render_persisted_clusters(self) -> None:
        user, sid = self._seed_sentence_cluster_fixture()
        client = self.get_authenticated_client(sid)

        list_response = client.get("/sentence-clusters")
        detail_response = client.get("/sentence-clusters/5")

        self.assertEqual(list_response.status_code, 200)
        self.assertIn("Sentence Clusters", list_response.get_data(as_text=True))
        self.assertIn("alpha, another", list_response.get_data(as_text=True))

        detail_html = detail_response.get_data(as_text=True)
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn("Sentence Cluster: alpha, another", detail_html)
        self.assertIn("Sentence one Sentence two", detail_html)
        self.assertIn("Another sentence Another follow up", detail_html)
        self.assertIn("Topic A", detail_html)
        self.assertIn("Topic C", detail_html)
        self.assertIn("Groups Mind Map", detail_html)
        self.assertIn('"name": "Topics"', detail_html)
        self.assertNotIn("Topic B", detail_html)

    def test_sentence_cluster_topic_snippets_api_is_cluster_scoped(self) -> None:
        _, sid = self._seed_sentence_cluster_fixture()
        client = self.get_authenticated_client(sid)

        response = client.get(
            "/api/sentence-clusters/5/topic-snippets?topic=Topic%20A"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        assert payload is not None

        snippets = payload["snippets"]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["post_id"], "p1")
        self.assertEqual(snippets[0]["text"], "Sentence one Sentence two")

        all_topics_response = client.get("/api/sentence-clusters/5/topic-snippets")
        self.assertEqual(all_topics_response.status_code, 200)
        all_payload = all_topics_response.get_json()
        assert all_payload is not None

        all_texts = [snippet["text"] for snippet in all_payload["snippets"]]
        self.assertIn("Sentence one Sentence two", all_texts)
        self.assertIn("Another sentence Another follow up", all_texts)
        self.assertNotIn("Sentence three", all_texts)

    def test_mindmap_node_data_returns_scope_aware_cluster_actions(self) -> None:
        _, sid = self._seed_sentence_cluster_fixture()
        client = self.get_authenticated_client(sid)

        tags_response = client.post(
            "/api/mindmap-node-data",
            json={
                "action": "tags",
                "scope": {
                    "cluster_id": 5,
                    "post_ids": ["p1", "p2"],
                    "topic_path": "Topic A",
                    "node_kind": "topic",
                },
            },
        )
        self.assertEqual(tags_response.status_code, 200)
        tags_payload = tags_response.get_json()
        assert tags_payload is not None

        tag_items = tags_payload["items"]
        self.assertEqual([item["name"] for item in tag_items], ["alpha", "gemini"])
        self.assertEqual(tags_payload["result_type"], "nodes")

        sentences_response = client.post(
            "/api/mindmap-node-data",
            json={
                "action": "sentences",
                "scope": {
                    "cluster_id": 5,
                    "post_ids": ["p1", "p2"],
                    "topic_path": "Topic A",
                    "node_kind": "topic",
                    "tag": "gemini",
                },
            },
        )
        self.assertEqual(sentences_response.status_code, 200)
        sentences_payload = sentences_response.get_json()
        assert sentences_payload is not None

        self.assertEqual(sentences_payload["result_type"], "snippets")
        sentence_items = sentences_payload["items"]
        self.assertEqual(len(sentence_items), 1)
        self.assertEqual(sentence_items[0]["node_kind"], "snippet_panel")
        self.assertEqual(len(sentence_items[0]["snippets"]), 1)
        self.assertEqual(
            sentence_items[0]["snippets"][0]["text"], "Sentence one Sentence two"
        )

    def test_mindmap_node_data_returns_sources_categories_and_subtopics(self) -> None:
        user, sid = self.seed_test_user("mindmapscope")
        self.test_db.feeds.insert_many(
            [
                {
                    "owner": user["sid"],
                    "feed_id": "feed-1",
                    "category_id": "cat-1",
                    "category_title": "Category One",
                    "category_local_url": "/category/cat-1",
                    "local_url": "/feed/feed-1",
                    "title": "Feed One",
                    "url": "http://example.com/feed-1",
                    "favicon": "",
                    "processing": 0,
                },
                {
                    "owner": user["sid"],
                    "feed_id": "feed-2",
                    "category_id": "cat-2",
                    "category_title": "Category Two",
                    "category_local_url": "/category/cat-2",
                    "local_url": "/feed/feed-2",
                    "title": "Feed Two",
                    "url": "http://example.com/feed-2",
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
                        "title": "Google Gemini",
                        "content": gzip.compress(b"Sentence one. Sentence two."),
                    },
                    "url": "http://example.com/p1",
                },
                {
                    "owner": user["sid"],
                    "pid": "p2",
                    "feed_id": "feed-2",
                    "processing": 0,
                    "read": False,
                    "tags": ["cloud"],
                    "content": {
                        "title": "Google Cloud",
                        "content": gzip.compress(b"Sentence three. Sentence four."),
                    },
                    "url": "http://example.com/p2",
                },
            ]
        )
        self.app.post_grouping.save_grouped_posts(
            user["sid"],
            ["p1"],
            [
                {"number": 1, "text": "Sentence one", "read": False},
                {"number": 2, "text": "Sentence two", "read": False},
            ],
            {"Technology > Google > Gemini": [1, 2]},
        )
        self.app.post_grouping.save_grouped_posts(
            user["sid"],
            ["p2"],
            [
                {"number": 1, "text": "Sentence three", "read": False},
                {"number": 2, "text": "Sentence four", "read": False},
            ],
            {"Technology > Google > Cloud": [1, 2]},
        )

        client = self.get_authenticated_client(sid)
        scope = {
            "post_ids": ["p1", "p2"],
            "topic_path": "Technology > Google",
            "node_kind": "topic",
        }

        subtopics_response = client.post(
            "/api/mindmap-node-data",
            json={"action": "subtopics", "scope": scope},
        )
        self.assertEqual(subtopics_response.status_code, 200)
        subtopics_payload = subtopics_response.get_json()
        assert subtopics_payload is not None
        self.assertEqual(
            [item["name"] for item in subtopics_payload["items"]],
            ["Cloud", "Gemini"],
        )

        sources_response = client.post(
            "/api/mindmap-node-data",
            json={
                "action": "sources",
                "scope": {**scope, "tag": "gemini"},
            },
        )
        self.assertEqual(sources_response.status_code, 200)
        sources_payload = sources_response.get_json()
        assert sources_payload is not None
        self.assertEqual([item["name"] for item in sources_payload["items"]], ["Feed One"])

        categories_response = client.post(
            "/api/mindmap-node-data",
            json={"action": "categories", "scope": scope},
        )
        self.assertEqual(categories_response.status_code, 200)
        categories_payload = categories_response.get_json()
        assert categories_payload is not None
        self.assertEqual(
            [item["name"] for item in categories_payload["items"]],
            ["Category One", "Category Two"],
        )

    def test_sentence_cluster_detail_and_api_respect_only_unread(self) -> None:
        user, sid = self._seed_sentence_cluster_fixture()
        self.test_db.users.update_one(
            {"sid": user["sid"]},
            {"$set": {"settings.only_unread": True}},
        )
        client = self.get_authenticated_client(sid)

        detail_response = client.get("/sentence-clusters/5")
        api_response = client.get("/api/sentence-clusters/5/topic-snippets")

        detail_html = detail_response.get_data(as_text=True)
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn("Sentence one Sentence two", detail_html)
        self.assertIn("Another sentence Another follow up", detail_html)
        self.assertNotIn("Sentence three", detail_html)

        self.assertEqual(api_response.status_code, 200)
        payload = api_response.get_json()
        assert payload is not None
        texts = [snippet["text"] for snippet in payload["snippets"]]
        self.assertIn("Sentence one Sentence two", texts)
        self.assertIn("Another sentence Another follow up", texts)
        self.assertNotIn("Sentence three", texts)

    def test_snippet_pages_render_sanitized_html(self) -> None:
        user, sid = self.seed_test_user("snippethtml")
        self.test_db.feeds.insert_one(
            {
                "owner": user["sid"],
                "feed_id": "feed-html",
                "category_id": "cat-html",
                "category_title": "Category",
                "category_local_url": "/category/cat-html",
                "local_url": "/feed/feed-html",
                "title": "Feed Html",
                "url": "http://example.com/feed-html",
                "favicon": "",
                "processing": 0,
            }
        )
        self.test_db.posts.insert_one(
            {
                "owner": user["sid"],
                "pid": "p-html",
                "feed_id": "feed-html",
                "processing": 0,
                "read": False,
                "content": {
                    "title": "HTML Post",
                    "content": gzip.compress(
                        b"<p>Visit <a href=\"https://example.com/story\">story</a>.</p>"
                    ),
                },
                "url": "http://example.com/p-html",
            }
        )

        self.app.post_grouping.save_grouped_posts(
            user["sid"],
            ["p-html"],
            [
                {
                    "number": 1,
                    "text": (
                        '<p>Visit <a href="https://example.com/story" '
                        'onclick="alert(1)">story</a>.</p>'
                        '<script>alert(1)</script>'
                    ),
                    "read": False,
                }
            ],
            {"Topic Html": [1]},
        )
        self.app.snippet_clusters.replace_clusters(
            user["sid"],
            [
                {
                    "cluster_id": 9,
                    "title": "html cluster",
                    "item_count": 1,
                    "post_ids": ["p-html"],
                    "snippet_refs": [
                        {"post_id": "p-html", "topic": "Topic Html", "indices": [1]}
                    ],
                }
            ],
        )

        client = self.get_authenticated_client(sid)
        grouped_response = client.get("/post-grouped-snippets/p-html")
        cluster_response = client.get("/sentence-clusters/9")

        grouped_html = grouped_response.get_data(as_text=True)
        cluster_html = cluster_response.get_data(as_text=True)

        self.assertEqual(grouped_response.status_code, 200)
        self.assertEqual(cluster_response.status_code, 200)
        self.assertIn('href="https://example.com/story"', grouped_html)
        self.assertIn('href="https://example.com/story"', cluster_html)
        self.assertIn("target=\"_blank\"", grouped_html)
        self.assertNotIn("onclick=", grouped_html)
        self.assertNotIn("<script>", grouped_html)
        self.assertNotIn("onclick=", cluster_html)
        self.assertNotIn("<script>", cluster_html)
