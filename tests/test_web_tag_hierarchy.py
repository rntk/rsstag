import gzip
import json
from typing import Any

from tests.web_test_utils import MongoWebTestCase


class TestWebTagHierarchy(MongoWebTestCase):
    def setUp(self) -> None:
        for collection in ("users", "feeds", "posts", "post_grouping", "tags"):
            self.test_db[collection].delete_many({})

    def _seed(self, grouped: bool = True) -> str:
        user: dict[str, Any]
        sid: str
        user, sid = self.seed_test_user("word-hierarchy")
        self.db_helper.init_db_from_dict(
            self.test_db,
            {
                "feeds": [
                    {
                        "owner": sid,
                        "feed_id": "one",
                        "title": "One",
                        "category_id": "cat",
                        "category_title": "Category",
                        "local_url": "/feed/one",
                    },
                    {
                        "owner": sid,
                        "feed_id": "two",
                        "title": "Two",
                        "category_id": "other",
                        "category_title": "Other",
                        "local_url": "/feed/two",
                    },
                ],
                "posts": [
                    {
                        "owner": sid,
                        "pid": "p1",
                        "feed_id": "one",
                        "category_id": "cat",
                        "tags": ["codex"],
                        "read": False,
                        "processing": 0,
                        "unix_date": 2,
                        "content": {
                            "title": "First",
                            "content": gzip.compress(b"<p>codex CLI tool</p>"),
                        },
                    },
                    {
                        "owner": sid,
                        "pid": "p2",
                        "feed_id": "two",
                        "category_id": "other",
                        "tags": ["codex"],
                        "read": False,
                        "processing": 0,
                        "unix_date": 1,
                        "content": {
                            "title": "Second",
                            "content": gzip.compress(b"CLI codex app"),
                        },
                    },
                    {
                        "owner": "another-owner",
                        "pid": "private",
                        "tags": ["codex"],
                        "read": False,
                        "processing": 0,
                        "content": {
                            "title": "Private",
                            "content": gzip.compress(b"codex secret"),
                        },
                    },
                ],
            },
        )
        if grouped:
            self.app.post_grouping.save_grouped_posts(
                sid,
                ["p1"],
                [{"number": 1, "text": "codex CLI tool", "read": False}],
                {"Tools": [1]},
            )
            self.app.post_grouping.save_grouped_posts(
                sid,
                ["p2"],
                [{"number": 1, "text": "CLI codex app", "read": False}],
                {"Apps": [1]},
            )
        return sid

    def _topics(self, sid: str, query: str) -> list[dict[str, Any]]:
        response: Any = self.get_authenticated_client(sid).get("/tag-hierarchy" + query)
        self.assertEqual(response.status_code, 200)
        body: str = response.data.decode()
        data: str = body.split("window.hierarchyTopics = ", 1)[1].split(
            ";</script>", 1
        )[0]
        return json.loads(data)

    def test_chains_and_source_sentence_identities(self) -> None:
        sid: str = self._seed()
        topics: list[dict[str, Any]] = self._topics(sid, "?tag=codex")
        self.assertEqual(
            [item["name"] for item in topics],
            ["codex > cli > app", "codex > cli > tool"],
        )
        self.assertEqual(
            topics[1]["sources"][0]["sentences"][0],
            {
                "number": 1,
                "text": "codex CLI tool",
                "read": False,
                "snippet": "codex CLI tool",
            },
        )
        self.assertEqual(topics[1]["sources"][0]["feed_title"], "One")

    def test_feed_category_and_missing_scope(self) -> None:
        sid: str = self._seed()
        for query in ("?tag=codex&feed=one", "?tag=codex&category=cat"):
            topics: list[dict[str, Any]] = self._topics(sid, query)
            self.assertEqual([item["name"] for item in topics], ["codex > cli > tool"])
        client: Any = self.get_authenticated_client(sid)
        self.assertEqual(
            client.get("/tag-hierarchy?tag=codex&feed=missing").status_code, 404
        )
        self.assertEqual(client.get("/tag-hierarchy").status_code, 400)
        self.assertEqual(client.get("/tag-hierarchy/?tag=codex").status_code, 200)

    def test_read_sentences_are_excluded(self) -> None:
        sid: str = self._seed()
        self.app.post_grouping.update_snippets_read_status(sid, "p1", [1], True)
        topics: list[dict[str, Any]] = self._topics(sid, "?tag=codex")
        self.assertEqual([item["name"] for item in topics], ["codex > cli > app"])

    def test_ungrouped_post_fallback_keeps_full_text(self) -> None:
        sid: str = self._seed(grouped=False)
        topics: list[dict[str, Any]] = self._topics(sid, "?tag=codex&feed=one")
        self.assertEqual(len(topics), 1)
        sentence: dict[str, Any] = topics[0]["sources"][0]["sentences"][0]
        self.assertIn("codex CLI tool", sentence["text"])
        self.assertNotIn("<p>", sentence["text"])
        self.assertNotIn("number", sentence)

    def test_sentence_filter_can_search_beyond_post_tags(self) -> None:
        sid: str = self._seed()
        self.assertEqual(self._topics(sid, "?tag=CLI"), [])
        topics: list[dict[str, Any]] = self._topics(sid, "?tag=CLI&sentences=1")
        self.assertEqual(len(topics), 2)

    def test_ngram_scope_and_script_safe_data(self) -> None:
        sid: str = self._seed(grouped=False)
        self.test_db.posts.update_one(
            {"owner": sid, "pid": "p1"},
            {
                "$set": {
                    "tags": ["machine", "learning"],
                    "bi_grams": ["machine learning"],
                    "content.content": gzip.compress(
                        b"<p>Use machine learning today</p>"
                    ),
                    "content.title": "</script><script>alert(1)</script>",
                }
            },
        )
        topics: list[dict[str, Any]] = self._topics(
            sid, "?tag=machine+learning&feed=one"
        )
        self.assertEqual(
            [item["name"] for item in topics], ["machine learning > use > today"]
        )
        response: Any = self.get_authenticated_client(sid).get(
            "/tag-hierarchy?tag=machine+learning"
        )
        self.assertNotIn(b"</script><script>alert(1)</script>", response.data)

    def test_context_tag_scope(self) -> None:
        sid: str = self._seed()
        self.test_db.posts.update_one(
            {"owner": sid, "pid": "p1"}, {"$set": {"tags": ["codex", "focused"]}}
        )
        self.app.users.update_settings(sid, {"context_filter": {"tags": ["focused"]}})
        topics: list[dict[str, Any]] = self._topics(sid, "?tag=codex")
        self.assertEqual([item["name"] for item in topics], ["codex > cli > tool"])

    def test_all_sentences_mode_preserves_read_material(self) -> None:
        sid: str = self._seed()
        self.app.users.update_settings(sid, {"only_unread": False})
        self.app.post_grouping.update_snippets_read_status(sid, "p1", [1], True)
        topics: list[dict[str, Any]] = self._topics(sid, "?tag=codex")
        self.assertEqual(len(topics), 2)
        self.assertTrue(topics[1]["sources"][0]["sentences"][0]["read"])
