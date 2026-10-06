import gzip
import json
import unittest
from typing import Any

from rsstag.web.tag_context_stats import (
    WordCounts,
    branching,
    contrast,
    split_sentences,
)
from tests.web_test_utils import MongoWebTestCase


class TestTagContextStats(unittest.TestCase):
    def test_branching_fixed_and_open(self) -> None:
        self.assertEqual(branching([5])["fixedness"], 1.0)
        open_slot: dict[str, float] = branching([2, 2, 2, 2])
        self.assertEqual((open_slot["fixedness"], open_slot["entropy"]), (0.0, 2.0))
        skewed: dict[str, float] = branching([9, 1])
        self.assertGreater(skewed["fixedness"], 0.5)
        self.assertEqual(skewed["top_share"], 0.9)
        self.assertEqual(branching([])["distinct"], 0)

    def test_contrast_shrinks_rare_words(self) -> None:
        focus: WordCounts = WordCounts()
        reference: WordCounts = WordCounts()
        for index in range(100):
            focus.add(["common"] + (["rare"] if index < 2 else []) + ["filler"])
            reference.add(["filler"] + (["common"] if index < 20 else []))
        reference.add(["filler"])
        rare = contrast("rare", focus, reference)
        common = contrast("common", focus, reference)
        self.assertGreater(rare.lift, common.lift)
        self.assertGreater(common.z, rare.z)
        self.assertLess(common.lift_low, common.lift)
        self.assertLess(common.lift, common.lift_high)
        self.assertLess(contrast("filler", focus, reference).z, 1.96)

    def test_split_sentences(self) -> None:
        self.assertEqual(
            split_sentences("One codex. Two!\nThree"), ["One codex.", "Two!", "Three"]
        )


class TestWebTagNgramChart(MongoWebTestCase):
    def setUp(self) -> None:
        for collection in ("users", "feeds", "posts", "post_grouping", "tags"):
            self.test_db[collection].delete_many({})

    def _post(self, sid: str, pid: str, feed: str, text: bytes, tags: list[str]) -> dict[str, Any]:
        return {
            "owner": sid, "pid": pid, "feed_id": feed, "category_id": "cat",
            "tags": tags, "read": False, "processing": 0, "unix_date": 100,
            "url": f"https://example.com/{pid}",
            "content": {"title": pid.upper(), "content": gzip.compress(text)},
        }

    def _seed(self) -> str:
        user: dict[str, Any]
        sid: str
        user, sid = self.seed_test_user("ngram-chart")
        feeds: list[dict[str, Any]] = [
            {"owner": sid, "feed_id": feed, "title": feed.title(),
             "category_id": "cat", "category_title": "Category"}
            for feed in ("one", "two")
        ]
        posts: list[dict[str, Any]] = [
            self._post(sid, "p1", "one", b"<p>the codex cli tool. Weather is nice.</p>", ["codex"]),
            self._post(sid, "p2", "one", b"new codex cli app", ["codex"]),
            self._post(sid, "p3", "one", b"codex cli tool", ["codex"]),
            self._post(sid, "p4", "two", b"codex pricing plan. codex pricing tier. codex pricing", ["codex"]),
            self._post(sid, "p5", "two", b"Weather is cold. The app is nice.", ["weather"]),
            {"owner": "another-owner", "pid": "x", "tags": ["codex"], "read": False,
             "processing": 0, "content": {"title": "X", "content": gzip.compress(b"codex cli secret")}},
        ]
        self.db_helper.init_db_from_dict(self.test_db, {"feeds": feeds, "posts": posts})
        return sid

    def _data(self, sid: str, query: str) -> dict[str, Any]:
        response: Any = self.get_authenticated_client(sid).get("/tag-ngram-chart" + query)
        self.assertEqual(response.status_code, 200)
        body: str = response.data.decode()
        data: str = body.split("window.tagNgramData = ", 1)[1].split(";</script>", 1)[0]
        return json.loads(data)

    def test_phrases_with_fixedness(self) -> None:
        sid: str = self._seed()
        data: dict[str, Any] = self._data(sid, "?tag=codex")
        self.assertEqual(data["view"], "phrases")
        self.assertEqual(data["summary"]["articles"], 4)
        rows: dict[str, dict[str, Any]] = {row["bigram"]: row for row in data["rows"]}
        cli: dict[str, Any] = rows["codex cli"]
        self.assertEqual((cli["count"], cli["posts_count"], cli["distinct"]), (3, 3, 2))
        self.assertEqual(cli["words"][0]["post_ids"], ["p1", "p3"])
        self.assertEqual(rows["codex pricing"]["distinct"], 2)
        self.assertEqual(rows["codex pricing"]["fixedness"], 0.0)
        self.assertNotIn("secret", json.dumps(data))

    def test_sentences_do_not_cross_boundaries(self) -> None:
        sid: str = self._seed()
        rows: list[dict[str, Any]] = self._data(sid, "?tag=codex")["rows"]
        words: list[str] = [w["word"] for row in rows for w in row["words"]]
        self.assertNotIn("weather", words)

    def test_distinctive_words_against_scope(self) -> None:
        sid: str = self._seed()
        data: dict[str, Any] = self._data(sid, "?tag=codex&view=words")
        words: dict[str, dict[str, Any]] = {item["word"]: item for item in data["words"]}
        self.assertNotIn("codex", words)
        self.assertNotIn("weather", words)
        self.assertGreater(data["reference_sentences"], 0)
        cli: dict[str, Any] = words["cli"]
        self.assertEqual((cli["sentences"], cli["reference_sentences"], cli["articles"]), (3, 0, 3))
        self.assertGreater(cli["z"], words["app"]["z"])
        self.assertLessEqual(cli["lift_low"], cli["lift"])
        self.assertEqual(cli["examples"][0]["url"], "https://example.com/p1")
        self.assertEqual(cli["feeds"][0]["title"], "One")

    def test_feed_framing(self) -> None:
        sid: str = self._seed()
        data: dict[str, Any] = self._data(sid, "?tag=codex&view=feeds")
        rows: dict[str, dict[str, Any]] = {row["title"]: row for row in data["rows"]}
        self.assertEqual(set(rows), {"One", "Two"})
        self.assertEqual(rows["Two"]["words"][0]["word"], "pricing")
        self.assertIn("cli", [word["word"] for word in rows["One"]["words"]])
        single: dict[str, Any] = self._data(sid, "?tag=codex&view=feeds&feed=one")
        self.assertEqual(single["rows"], [])

    def test_errors(self) -> None:
        sid: str = self._seed()
        client: Any = self.get_authenticated_client(sid)
        self.assertEqual(client.get("/tag-ngram-chart").status_code, 400)
        self.assertEqual(client.get("/tag-ngram-chart?tag=codex&view=nope").status_code, 400)
        self.assertEqual(client.get("/tag-ngram-chart?tag=codex&feed=missing").status_code, 404)
