import gzip
import json
from typing import Any

from tests.web_test_utils import MongoWebTestCase


class TestWebTagNgramChart(MongoWebTestCase):
    def setUp(self) -> None:
        for collection in ("users", "feeds", "posts", "post_grouping", "tags"):
            self.test_db[collection].delete_many({})

    def _seed(self) -> str:
        user: dict[str, Any]
        sid: str
        user, sid = self.seed_test_user("ngram-chart")
        post: dict[str, Any] = {
            "owner": sid,
            "feed_id": "one",
            "category_id": "cat",
            "tags": ["codex"],
            "read": False,
            "processing": 0,
        }
        self.db_helper.init_db_from_dict(
            self.test_db,
            {
                "feeds": [
                    {"owner": sid, "feed_id": "one", "title": "One",
                     "category_id": "cat", "category_title": "Category"},
                ],
                "posts": [
                    {**post, "pid": "p1", "unix_date": 100,
                     "content": {"title": "A", "content": gzip.compress(b"<p>the codex cli tool</p>")}},
                    {**post, "pid": "p2", "unix_date": 300,
                     "content": {"title": "B", "content": gzip.compress(b"new codex cli app")}},
                    {**post, "pid": "p3", "unix_date": 200,
                     "content": {"title": "C", "content": gzip.compress(b"codex cli tool")}},
                    {"owner": "another-owner", "pid": "x", "tags": ["codex"], "read": False,
                     "processing": 0, "content": {"title": "X", "content": gzip.compress(b"codex cli secret")}},
                ],
            },
        )
        return sid

    def _rows(self, sid: str, query: str) -> list[dict[str, Any]]:
        response: Any = self.get_authenticated_client(sid).get("/tag-ngram-chart" + query)
        self.assertEqual(response.status_code, 200)
        body: str = response.data.decode()
        data: str = body.split("window.tagNgramRows = ", 1)[1].split(";</script>", 1)[0]
        return json.loads(data)

    def test_bigram_rows_with_trigram_words(self) -> None:
        sid: str = self._seed()
        rows: list[dict[str, Any]] = self._rows(sid, "?tag=codex")
        self.assertEqual(rows[0]["bigram"], "codex cli")
        self.assertEqual(rows[0]["count"], 3)
        tool: dict[str, Any] = rows[0]["words"][0]
        self.assertEqual(
            (tool["word"], tool["trigram"], tool["count"], tool["post_ids"]),
            ("tool", "codex cli tool", 2, ["p1", "p3"]),
        )
        self.assertNotIn("secret", json.dumps(rows))

    def test_backward_trigrams_and_feed_scope(self) -> None:
        sid: str = self._seed()
        rows: list[dict[str, Any]] = self._rows(sid, "?tag=codex&feed=one")
        bigrams: list[str] = [row["bigram"] for row in rows]
        self.assertEqual(bigrams, ["codex cli"])
        self.test_db.posts.update_one(
            {"owner": sid, "pid": "p2"},
            {"$set": {"content.content": gzip.compress(b"a brand new codex")}},
        )
        rows = self._rows(sid, "?tag=codex")
        backward: dict[str, Any] = next(row for row in rows if row["bigram"] == "new codex")
        self.assertEqual(backward["words"][0]["trigram"], "brand new codex")

    def test_errors(self) -> None:
        sid: str = self._seed()
        client: Any = self.get_authenticated_client(sid)
        self.assertEqual(client.get("/tag-ngram-chart").status_code, 400)
        self.assertEqual(client.get("/tag-ngram-chart?tag=codex&feed=missing").status_code, 404)
