import unittest

from tests.web_test_utils import MongoWebTestCase


class TestWebProcessing(MongoWebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.owner = "testuser"
        self.user_data, self.sid = self.seed_test_user(self.owner, "password")
        self.minimal_data = self.seed_minimal_data(self.owner)
        self.client = self.get_authenticated_client(self.sid)

    def test_on_processing_get_empty(self) -> None:
        response = self.client.get("/processing")
        self.assertEqual(response.status_code, 200)

    def test_on_processing_get_lists_posts_and_tags(self) -> None:
        post_pid = self.minimal_data["post_pids"][0]
        tag = self.minimal_data["tag"]

        self.test_db.posts.update_one(
            {"owner": self.owner, "pid": post_pid},
            {"$set": {"processing": 1}},
        )
        self.test_db.tags.update_one(
            {"owner": self.owner, "tag": tag},
            {"$set": {"processing": 2}},
        )

        response = self.client.get("/processing")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn(post_pid, body)
        self.assertIn(tag, body)

    def test_on_processing_reset_post_redirects(self) -> None:
        post_pid = self.minimal_data["post_pids"][0]
        self.test_db.posts.update_one(
            {"owner": self.owner, "pid": post_pid},
            {"$set": {"processing": 1}},
        )

        response = self.client.post(
            "/processing/reset",
            data={"type": "post", "id": post_pid},
        )
        self.assertIn(response.status_code, [301, 302, 307, 308])
        self.assertIn("/processing", response.headers.get("Location", ""))

        doc = self.test_db.posts.find_one({"owner": self.owner, "pid": post_pid})
        self.assertIsNotNone(doc)
        self.assertEqual(doc.get("processing"), 0)

    def test_on_processing_reset_tag_redirects(self) -> None:
        tag = self.minimal_data["tag"]
        self.test_db.tags.update_one(
            {"owner": self.owner, "tag": tag},
            {"$set": {"processing": 1}},
        )

        response = self.client.post(
            "/processing/reset",
            data={"type": "tag", "id": tag},
        )
        self.assertIn(response.status_code, [301, 302, 307, 308])
        self.assertIn("/processing", response.headers.get("Location", ""))

        doc = self.test_db.tags.find_one({"owner": self.owner, "tag": tag})
        self.assertIsNotNone(doc)
        self.assertEqual(doc.get("processing"), 0)

    def test_on_processing_reset_post_unknown_type_ignores(self) -> None:
        response = self.client.post(
            "/processing/reset",
            data={"type": "unknown", "id": "whatever"},
        )
        self.assertIn(response.status_code, [301, 302, 307, 308])
        self.assertIn("/processing", response.headers.get("Location", ""))


if __name__ == "__main__":
    unittest.main()
