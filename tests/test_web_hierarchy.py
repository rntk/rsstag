import gzip
import unittest

from tests.web_test_utils import MongoWebTestCase


class TestWebHierarchy(MongoWebTestCase):
    def setUp(self) -> None:
        self.test_db.posts.delete_many({})
        self.test_db.feeds.delete_many({})
        self.test_db.post_grouping.delete_many({})
        self.test_db.tags.delete_many({})

    def _seed_hierarchy(self) -> tuple[str, str]:
        user, sid = self.seed_test_user("hierarchy-user")
        feed_id: str = "hierarchy-feed"
        self.db_helper.init_db_from_dict(
            self.test_db,
            {
                "feeds": [
                    {
                        "owner": user["sid"],
                        "feed_id": feed_id,
                        "category_id": "hierarchy-category",
                        "category_title": "Hierarchy category",
                        "local_url": f"/feed/{feed_id}",
                        "title": "Hierarchy Feed",
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
                        "pid": "hierarchy-post-1",
                        "feed_id": feed_id,
                        "processing": 0,
                        "read": False,
                        "tags": ["hierarchy"],
                        "unix_date": 2,
                        "url": "https://example.com/hierarchy-post-1",
                        "content": {
                            "title": "First post",
                            "content": gzip.compress(b"First sentence. Second sentence."),
                        },
                    },
                    {
                        "owner": user["sid"],
                        "pid": "hierarchy-post-2",
                        "feed_id": feed_id,
                        "processing": 0,
                        "read": False,
                        "tags": ["hierarchy"],
                        "unix_date": 3,
                        "url": "https://example.com/hierarchy-post-2",
                        "content": {
                            "title": "Second post",
                            "content": gzip.compress(b"Third sentence. Fourth sentence."),
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
                            "content": gzip.compress(b"Not in the hierarchy."),
                        },
                    },
                ],
            },
        )
        self.app.post_grouping.save_grouped_posts(
            user["sid"],
            ["hierarchy-post-1"],
            [
                {"number": 1, "text": "First sentence.", "read": False},
                {"number": 2, "text": "Second sentence.", "read": False},
            ],
            {"Technology > Shared": [1, 2], "Technology > Only First": [1]},
        )
        self.app.post_grouping.save_grouped_posts(
            user["sid"],
            ["hierarchy-post-2"],
            [
                {"number": 1, "text": "Third sentence.", "read": False},
                {"number": 2, "text": "Fourth sentence.", "read": False},
            ],
            {"Technology > Shared": [1]},
        )
        return sid, feed_id

    def test_hierarchy_without_filters_is_allowed(self) -> None:
        _, sid = self.seed_test_user("hierarchy-missing-feed")
        client = self.get_authenticated_client(sid)

        response = client.get("/hierarchy")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"All posts", response.data)

    def test_hierarchy_unknown_feed_returns_404(self) -> None:
        _, sid = self.seed_test_user("hierarchy-unknown-feed")
        client = self.get_authenticated_client(sid)

        response = client.get("/hierarchy?feed=does-not-exist")

        self.assertEqual(response.status_code, 404)

    def test_hierarchy_aggregates_topics_across_posts(self) -> None:
        sid, feed_id = self._seed_hierarchy()
        client = self.get_authenticated_client(sid)

        response = client.get(f"/hierarchy?feed={feed_id}")
        body: str = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("window.hierarchyTopics", body)
        self.assertIn(b"feed-hierarchy.js", response.data)
        self.assertIn("Technology \\u003e Shared", body)
        self.assertIn("Technology \\u003e Only First", body)
        self.assertNotIn("Excluded post", body)

        shared_index: int = body.index("Technology \\u003e Shared")
        # posts_count should be 2 for the shared topic since both posts contain it.
        shared_segment: str = body[shared_index : shared_index + 200]
        self.assertIn('"posts_count": 2', shared_segment)
        self.assertIn('"sentences_count": 3', shared_segment)
        self.assertIn('"title": "First post"', body)
        self.assertIn('"title": "Second post"', body)
        self.assertIn(
            '"sentences": [{"number": 1, "text": "First sentence.", "read": false}, '
            '{"number": 2, "text": "Second sentence.", "read": false}]',
            body,
        )
        self.assertIn(
            '"sentences": [{"number": 1, "text": "Third sentence.", "read": false}]',
            body,
        )

        only_first_index: int = body.index("Technology \\u003e Only First")
        only_first_segment: str = body[only_first_index : only_first_index + 200]
        self.assertIn('"posts_count": 1', only_first_segment)
        self.assertIn('"sentences_count": 1', only_first_segment)

    def test_hierarchy_filters_by_tag_without_feed(self) -> None:
        sid, _ = self._seed_hierarchy()
        client = self.get_authenticated_client(sid)

        response = client.get("/hierarchy?tag=hierarchy")
        body: str = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Technology \\u003e Shared", body)
        self.assertIn('"posts_count": 2', body)
        self.assertNotIn("Excluded post", body)
        # Lemma itself is always available for highlight when no tag metadata exists.
        self.assertIn("window.TAG_WORDS", body)
        self.assertIn('"hierarchy"', body)

    def test_hierarchy_tag_words_include_surface_forms(self) -> None:
        sid, _ = self._seed_hierarchy()
        self.db_helper.init_db_from_dict(
            self.test_db,
            {
                "tags": [
                    {
                        "owner": sid,
                        "tag": "run",
                        "words": ["run", "running", "ran"],
                        "posts_count": 1,
                        "unread_count": 1,
                    }
                ],
            },
        )
        client = self.get_authenticated_client(sid)

        response = client.get("/hierarchy?tag=run")
        body: str = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("window.TAG_WORDS", body)
        self.assertIn('"running"', body)
        self.assertIn('"ran"', body)

    def test_hierarchy_combines_feed_and_tag_filters(self) -> None:
        sid, feed_id = self._seed_hierarchy()
        client = self.get_authenticated_client(sid)

        response = client.get(f"/hierarchy?feed={feed_id}&tag=other")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Technology \\u003e Shared", response.data)

    def test_hierarchy_topic_filter_broadens_selection_beyond_post_tags(self) -> None:
        sid, feed_id = self._seed_hierarchy()
        client = self.get_authenticated_client(sid)

        # "Shared" is not a literal post tag, only part of the topic name.
        response = client.get(f"/hierarchy?feed={feed_id}&tag=Shared&topic=1")
        body: str = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Technology \\u003e Shared", body)
        self.assertNotIn("Technology \\u003e Only First", body)

    def test_hierarchy_sentences_filter_broadens_selection_beyond_post_tags(self) -> None:
        sid, feed_id = self._seed_hierarchy()
        client = self.get_authenticated_client(sid)

        # "Third" is not a literal post tag, only appears within a sentence.
        response = client.get(f"/hierarchy?feed={feed_id}&tag=Third&sentences=1")
        body: str = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Technology \\u003e Shared", body)
        self.assertNotIn("Technology \\u003e Only First", body)

    def test_hierarchy_text_filter_excludes_non_matching_topics(self) -> None:
        sid, feed_id = self._seed_hierarchy()
        client = self.get_authenticated_client(sid)

        response = client.get(f"/hierarchy?feed={feed_id}&tag=nomatch&topic=1&sentences=1")
        body: str = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Technology \\u003e Shared", body)
        self.assertNotIn("Technology \\u003e Only First", body)

    def test_hierarchy_text_filter_does_not_bypass_tagged_posts(self) -> None:
        sid, feed_id = self._seed_hierarchy()
        client = self.get_authenticated_client(sid)

        # Both posts are tagged "hierarchy", but none of their topic names or
        # grouped sentences contains it. Text filters must still exclude them.
        response = client.get(
            f"/hierarchy?feed={feed_id}&tag=hierarchy&topic=1&sentences=1"
        )
        body: str = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Technology \\u003e Shared", body)
        self.assertNotIn("Technology \\u003e Only First", body)

    def test_hierarchy_topic_name_is_script_safe(self) -> None:
        sid, _ = self.seed_test_user("hierarchy-script-user")
        feed_id: str = "hierarchy-script-feed"
        self.db_helper.init_db_from_dict(
            self.test_db,
            {
                "feeds": [
                    {
                        "owner": sid,
                        "feed_id": feed_id,
                        "category_id": "hierarchy-script-category",
                        "category_title": "Hierarchy script category",
                        "local_url": f"/feed/{feed_id}",
                        "title": "Hierarchy Script Feed",
                        "url": "https://example.com/feed",
                        "favicon": "",
                        "processing": 0,
                    }
                ],
                "posts": [
                    {
                        "owner": sid,
                        "pid": "hierarchy-script-post",
                        "feed_id": feed_id,
                        "processing": 0,
                        "read": False,
                        "tags": ["hierarchy"],
                        "unix_date": 1,
                        "url": "https://example.com/hierarchy-script-post",
                        "content": {
                            "title": "Script post",
                            "content": gzip.compress(b"Some sentence."),
                        },
                    }
                ],
            },
        )
        self.app.post_grouping.save_grouped_posts(
            sid,
            ["hierarchy-script-post"],
            [{"number": 1, "text": "Some sentence.", "read": False}],
            {"</script><script>alert(1)</script>": [1]},
        )
        client = self.get_authenticated_client(sid)

        response = client.get(f"/hierarchy?feed={feed_id}")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"</script><script>alert(1)</script>", response.data)
        self.assertIn(b"\\u003c/script\\u003e", response.data)


if __name__ == "__main__":
    unittest.main()
