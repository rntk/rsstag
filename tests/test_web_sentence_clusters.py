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
