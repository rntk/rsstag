import gzip
import unittest

from rsstag.web.posts import _serialize_canvas_posts
from tests.web_test_utils import MongoWebTestCase


class TestCanvasSerialization(unittest.TestCase):
    def test_script_markup_is_escaped(self) -> None:
        posts: list[dict[str, str]] = [{"title": "</script><script>alert(1)</script>"}]

        serialized: str = _serialize_canvas_posts(posts)

        self.assertNotIn("</script>", serialized)
        self.assertIn("\\u003c/script\\u003e", serialized)


class TestWebCanvas(MongoWebTestCase):
    def setUp(self) -> None:
        self.test_db.posts.delete_many({})
        self.test_db.feeds.delete_many({})
        self.test_db.post_grouping.delete_many({})

    def _seed_canvas(self) -> tuple[str, str]:
        user, sid = self.seed_test_user("canvas-user")
        feed_id: str = "canvas-feed"
        self.db_helper.init_db_from_dict(
            self.test_db,
            {
                "feeds": [
                    {
                        "owner": user["sid"],
                        "feed_id": feed_id,
                        "category_id": "canvas-category",
                        "category_title": "Canvas category",
                        "local_url": f"/feed/{feed_id}",
                        "title": "Canvas Feed",
                        "url": "https://example.com/feed",
                        "favicon": "",
                        "processing": 0,
                    },
                    {
                        "owner": user["sid"],
                        "feed_id": "other-feed",
                        "category_id": "other-category",
                        "category_title": "Other category",
                        "local_url": "/feed/other-feed",
                        "title": "Other Feed",
                        "url": "https://example.com/other-feed",
                        "favicon": "",
                        "processing": 0,
                    },
                ],
                "posts": [
                    {
                        "owner": user["sid"],
                        "pid": "canvas-post-1",
                        "feed_id": feed_id,
                        "processing": 0,
                        "read": False,
                        "tags": ["canvas"],
                        "unix_date": 2,
                        "url": "https://example.com/canvas-post-1",
                        "content": {
                            "title": "Aligned post",
                            "content": gzip.compress(b"First sentence. Second sentence."),
                        },
                    },
                    {
                        "owner": user["sid"],
                        "pid": "other-post",
                        "feed_id": "other-feed",
                        "processing": 0,
                        "read": False,
                        "tags": ["other"],
                        "unix_date": 1,
                        "url": "https://example.com/other-post",
                        "content": {
                            "title": "Excluded post",
                            "content": gzip.compress(b"Not in the canvas."),
                        },
                    },
                ],
            },
        )
        self.app.post_grouping.save_grouped_posts(
            user["sid"],
            ["canvas-post-1"],
            [
                {"number": 1, "text": "First sentence.", "read": False},
                {"number": 2, "text": "Second sentence.", "read": False},
            ],
            {"Technology > Canvas": [1, 2]},
        )
        return sid, feed_id

    def test_canvas_without_filters_is_allowed(self) -> None:
        _, sid = self.seed_test_user("canvas-missing-feed")
        client = self.get_authenticated_client(sid)

        response = client.get("/canvas")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"All posts", response.data)

    def test_canvas_renders_only_selected_feed_with_grouped_topics(self) -> None:
        sid, feed_id = self._seed_canvas()
        client = self.get_authenticated_client(sid)

        response = client.get(f"/canvas?feed={feed_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Aligned post", response.data)
        self.assertIn(b"First sentence.", response.data)
        self.assertIn(b"Technology \\u003e Canvas", response.data)
        self.assertIn(b"feed-canvas.js", response.data)
        self.assertIn(b'data-post-read-toggle', response.data)
        self.assertIn(b'data-canvas-read-all="true"', response.data)
        self.assertIn(b'"read": false', response.data)
        self.assertNotIn(b"Excluded post", response.data)

    def test_canvas_filters_by_tag_without_feed(self) -> None:
        sid, _ = self._seed_canvas()
        client = self.get_authenticated_client(sid)

        response = client.get("/canvas?tag=canvas")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Aligned post", response.data)
        self.assertNotIn(b"Excluded post", response.data)

    def test_canvas_combines_feed_and_tag_filters(self) -> None:
        sid, feed_id = self._seed_canvas()
        client = self.get_authenticated_client(sid)

        response = client.get(f"/canvas?feed={feed_id}&tag=other")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Aligned post", response.data)
        self.assertNotIn(b"Excluded post", response.data)

    def test_canvas_topic_filter_keeps_whole_matching_topic(self) -> None:
        sid, feed_id = self._seed_canvas()
        client = self.get_authenticated_client(sid)

        response = client.get(f"/canvas?feed={feed_id}&tag=Canvas&topic=1")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"First sentence.", response.data)
        self.assertIn(b"Second sentence.", response.data)

    def test_canvas_sentences_filter_keeps_whole_matching_topic(self) -> None:
        sid, feed_id = self._seed_canvas()
        client = self.get_authenticated_client(sid)

        response = client.get(f"/canvas?feed={feed_id}&tag=First&sentences=1")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"First sentence.", response.data)
        self.assertIn(b"Second sentence.", response.data)

    def test_canvas_topic_and_sentences_filter_drops_non_matching_topic(self) -> None:
        sid, feed_id = self._seed_canvas()
        client = self.get_authenticated_client(sid)

        response = client.get(f"/canvas?feed={feed_id}&tag=nomatch&topic=1&sentences=1")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"First sentence.", response.data)
        self.assertNotIn(b"Second sentence.", response.data)

    def test_hierarchy_includes_topic_sentences_for_summaries(self) -> None:
        sid, feed_id = self._seed_canvas()
        client = self.get_authenticated_client(sid)

        response = client.get(f"/hierarchy?feed={feed_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Technology \\u003e Canvas", response.data)
        self.assertIn(b"First sentence.", response.data)
        self.assertIn(b"Second sentence.", response.data)
        self.assertIn(b"feed-hierarchy.js", response.data)


if __name__ == "__main__":
    unittest.main()
