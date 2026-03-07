import gzip

from tests.web_test_utils import MongoWebTestCase


class TestWebSentenceClusters(MongoWebTestCase):
    def test_sentence_clusters_pages_render_persisted_clusters(self) -> None:
        user, sid = self.seed_test_user("snippetweb")
        client = self.get_authenticated_client(sid)

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
