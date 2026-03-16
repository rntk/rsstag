import gzip
import unittest

from tests.web_test_utils import MongoWebTestCase


class TestWebPathRecommendations(MongoWebTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _, cls.sid = cls.seed_test_user("paths-user", "paths-user")
        cls.auth_client = cls.get_authenticated_client(cls.sid)

        compressed = gzip.compress("Path recommendation fixture.".encode("utf-8"))
        cls.test_db.feeds.insert_one({
            "owner": cls.sid,
            "feed_id": "paths-feed",
            "category_id": "paths-category",
            "category_title": "Paths Category",
            "category_local_url": "/category/paths-category",
            "local_url": "/feed/paths-feed",
            "title": "Paths Feed",
            "url": "http://example.com/paths",
            "favicon": "",
            "processing": 0,
        })

        for index, pid in enumerate(("paths-post-1", "paths-post-2", "paths-post-3"), start=1):
            cls.test_db.posts.insert_one({
                "owner": cls.sid,
                "pid": pid,
                "feed_id": "paths-feed",
                "processing": 0,
                "tags": ["google"],
                "content": {
                    "title": f"Paths Post {index}",
                    "content": compressed,
                },
                "date": 1700000000 + index,
            })

        for tag, posts_count in (("google", 5), ("googl", 4), ("googgle", 3), ("gamma", 2)):
            cls.test_db.tags.insert_one({
                "owner": cls.sid,
                "tag": tag,
                "posts_count": posts_count,
                "unread_count": posts_count,
                "words": [tag],
                "local_url": f"/tag/{tag}",
                "processing": 0,
                "temperature": 1,
                "freq": 1.0,
                "sentiment": [],
            })

        cls.app.post_grouping.save_grouped_posts(
            cls.sid,
            ["paths-post-1"],
            sentences=[
                {"number": 0, "text": "Gemini update", "read": False},
                {"number": 1, "text": "Search update", "read": False},
            ],
            groups={
                "Google > Gemini": [0],
                "Google > Search": [1],
            },
        )
        cls.app.post_grouping.save_grouped_posts(
            cls.sid,
            ["paths-post-2"],
            sentences=[
                {"number": 0, "text": "Gemma update", "read": False},
                {"number": 1, "text": "Gmail update", "read": False},
            ],
            groups={
                "Google > Gemma": [0],
                "Google > Gmail": [1],
            },
        )
        cls.app.post_grouping.save_grouped_posts(
            cls.sid,
            ["paths-post-3"],
            sentences=[
                {"number": 0, "text": "Deep Gemini note", "read": False},
            ],
            groups={
                "Google > Gemini Advanced": [0],
            },
        )

    def test_recommendations_endpoint_returns_tag_and_topic_groups(self) -> None:
        path = self.app.paths.create_or_get(
            self.sid,
            "sentences",
            {
                "tags": {"values": ["google"], "logic": "and"},
                "topics": {"values": ["Google > Gemini"], "logic": "and"},
            },
            {"tags": {"values": ["spam"], "logic": "and"}},
            "",
        )
        self.assertIsNotNone(path)

        response = self.auth_client.get(
            f"/api/paths/{path['path_id']}/recommendations"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["data"]

        groups = {group["id"]: group for group in payload["groups"]}
        self.assertIn("tags_replace", groups)
        self.assertIn("topics_replace", groups)
        self.assertIn("topics_add", groups)

        tag_item = groups["tags_replace"]["items"][0]
        self.assertEqual(tag_item["provider"], "similar_tags")
        self.assertEqual(tag_item["exclude"], {"tags": {"values": ["spam"], "logic": "and"}})
        self.assertNotIn("google", tag_item["filterset"]["tags"]["values"])
        self.assertEqual(tag_item["filterset"]["topics"]["values"], ["Google > Gemini"])
        self.assertGreater(tag_item["posts_count"], 0)
        self.assertGreater(tag_item["sentences_count"], 0)
        self.assertTrue(tag_item["suggestion_id"])
        self.assertTrue(tag_item["title"])

        topic_item = groups["topics_replace"]["items"][0]
        self.assertEqual(topic_item["provider"], "similar_topics")
        self.assertEqual(topic_item["source_value"], "Google > Gemini")
        self.assertNotEqual(topic_item["suggested_value"], "Google > Gemini")
        self.assertEqual(topic_item["filterset"]["tags"]["values"], ["google"])

    def test_recommendations_endpoint_preserves_level_topic_shape(self) -> None:
        path = self.app.paths.create_or_get(
            self.sid,
            "posts",
            {
                "topics": {
                    "values": [{"mode": "level", "level": 2, "value": "Gemini"}],
                    "logic": "and",
                }
            },
            {},
            "",
        )
        self.assertIsNotNone(path)

        response = self.auth_client.get(
            f"/api/paths/{path['path_id']}/recommendations"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["data"]

        groups = {group["id"]: group for group in payload["groups"]}
        self.assertIn("topics_replace", groups)

        item = groups["topics_replace"]["items"][0]
        self.assertEqual(item["source_value"]["mode"], "level")
        self.assertEqual(item["source_value"]["level"], 2)
        self.assertEqual(item["suggested_value"]["mode"], "level")
        self.assertEqual(item["suggested_value"]["level"], 2)
        self.assertNotEqual(item["suggested_value"]["value"], "Gemini")
        self.assertGreater(item["posts_count"], 0)
        self.assertEqual(item["filterset"]["topics"]["values"][0]["mode"], "level")

    def test_recommendations_endpoint_returns_404_for_missing_path(self) -> None:
        response = self.auth_client.get("/api/paths/missing-path/recommendations")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
