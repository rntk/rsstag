import gzip
import json
import re
import unittest
from types import SimpleNamespace
from unittest import mock
from werkzeug.wrappers import Request

from rsstag.web.tag_list_view import TagListView
from rsstag.web.tags import (
    _filter_and_sort_scoped,
    _tag_list_item,
    on_tags_canvas_data_get,
    on_tags_user_rank_post,
)
from tests.web_test_utils import MongoWebTestCase


class TestTagsCanvasData(unittest.TestCase):
    def test_canvas_data_paginates_and_includes_both_metrics(self) -> None:
        documents: list[dict[str, object]] = [
            {"tag": "alpha", "local_url": "/entity/alpha", "posts_count": 12,
             "unread_count": 3, "temperature": 0.5, "words": ["alpha", "alias"]},
            {"tag": "beta", "local_url": "/entity/beta", "posts_count": 7,
             "unread_count": 1, "temperature": 2.0},
        ]
        tags = mock.Mock()
        tags.count.return_value = len(documents)
        tags.get_all.side_effect = lambda *args, **kwargs: documents[
            kwargs["opts"]["offset"]:kwargs["opts"]["offset"] + kwargs["opts"]["limit"]
        ]
        app = SimpleNamespace(tags=tags)
        user: dict[str, object] = {"sid": "owner", "settings": {"only_unread": False}}
        request = Request.from_values(query_string="offset=1&limit=1")

        with mock.patch("rsstag.web.tags._get_scoped_tag_counts", return_value=(False, {})):
            response = on_tags_canvas_data_get(app, user, request)

        data: dict = json.loads(response.get_data(as_text=True))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["next_offset"], 2)
        self.assertEqual(data["tags"], [{"tag": "beta", "url": "/entity/beta",
                                         "count": 7, "temperature": 2.0, "words": []}])
        self.assertIn("words", tags.get_all.call_args.kwargs["projection"])
        with mock.patch("rsstag.web.tags._get_scoped_tag_counts", return_value=(False, {})):
            first = on_tags_canvas_data_get(
                app, user, Request.from_values(query_string="offset=0&limit=1")
            )
        self.assertEqual(json.loads(first.get_data(as_text=True))["tags"][0]["words"],
                         ["alpha", "alias"])

    def test_canvas_data_rejects_invalid_offset(self) -> None:
        response = on_tags_canvas_data_get(
            SimpleNamespace(), {}, Request.from_values(query_string="offset=invalid")
        )
        self.assertEqual(response.status_code, 400)


class TestTagsUserRankHandler(unittest.TestCase):
    def setUp(self) -> None:
        self.tags = mock.Mock()
        self.tags.get_by_tag.return_value = {"tag": "python"}
        self.tags.set_user_rank.return_value = True
        self.app = SimpleNamespace(tags=self.tags)
        self.user: dict[str, object] = {"sid": "owner"}

    def _post(self, body: object) -> tuple[int, dict]:
        request = Request.from_values(
            method="POST", data=json.dumps(body), content_type="application/json"
        )
        response = on_tags_user_rank_post(self.app, self.user, request)
        return response.status_code, json.loads(response.get_data(as_text=True))

    def test_sets_each_valid_value(self) -> None:
        for value in ("hidden", "pinned", None):
            with self.subTest(value=value):
                status, data = self._post({"tag": "python", "value": value})
                self.assertEqual((200, {"ok": True}), (status, data))
                self.tags.set_user_rank.assert_called_with("owner", "python", value)

    def test_rejects_bad_input(self) -> None:
        bodies: list[object] = [
            {"value": "hidden"},
            {"tag": "  ", "value": "hidden"},
            {"tag": 5, "value": "hidden"},
            {"tag": "python", "value": "bogus"},
            {"tag": "python", "value": 1},
            ["python"],
        ]
        for body in bodies:
            with self.subTest(body=body):
                status, data = self._post(body)
                self.assertEqual(400, status)
                self.assertIn("error", data)
        self.tags.set_user_rank.assert_not_called()

    def test_rejects_non_json_body(self) -> None:
        request = Request.from_values(method="POST", data="not json")
        response = on_tags_user_rank_post(self.app, self.user, request)
        self.assertEqual(400, response.status_code)

    def test_unknown_tag_is_404(self) -> None:
        self.tags.get_by_tag.return_value = None
        status, _ = self._post({"tag": "ghost", "value": "hidden"})
        self.assertEqual(404, status)
        self.tags.set_user_rank.assert_not_called()

    def test_storage_failure_is_500(self) -> None:
        self.tags.set_user_rank.return_value = False
        status, data = self._post({"tag": "python", "value": "hidden"})
        self.assertEqual(500, status)
        self.assertIn("error", data)
        self.tags.get_by_tag.side_effect = RuntimeError("db down")
        self.assertEqual(500, self._post({"tag": "python", "value": None})[0])


class TestScopedUserRank(unittest.TestCase):
    def test_context_filter_branch_uses_user_rank(self) -> None:
        names: list[str] = ["generic", "hidden", "plain", "pinned"]
        counts: dict[str, int] = {name: 5 for name in names}
        docs: dict[str, dict] = {
            "generic": {"rank": {"noise": True, "score": 0.0}},
            "hidden": {"user_rank": "hidden", "rank": {"noise": False, "score": 9.0}},
            "plain": {"rank": {"noise": False, "score": 1.0}},
            "pinned": {"user_rank": "pinned", "rank": {"noise": True, "score": 1000.0}},
        }
        view = TagListView(sort="informative", hide_noise=True)
        self.assertEqual(["pinned", "plain"], _filter_and_sort_scoped(names, counts, docs, view))
        shown = TagListView(sort="informative", hide_noise=False)
        self.assertEqual(
            ["pinned", "hidden", "plain", "generic"],
            _filter_and_sort_scoped(names, counts, docs, shown),
        )

    def test_tag_list_item_exposes_user_rank(self) -> None:
        self.assertIsNone(_tag_list_item({}, "a", 1)["user_rank"])
        self.assertEqual("pinned", _tag_list_item({"user_rank": "pinned"}, "a", 1)["user_rank"])


class TestWebTags(MongoWebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.owner = "testuser"
        user_data, self.sid = self.seed_test_user(self.owner, "password")
        # Use sid as owner so DB queries by user["sid"] actually find the fixtures.
        self.minimal_data = self.seed_minimal_data(self.sid)
        # Remove the malformed letters doc inserted by seed_minimal_data;
        # endpoints work fine with an empty letters list.
        self.test_db.letters.delete_one({"owner": self.sid})
        self.client = self.get_authenticated_client(self.sid)

    def _seed_post_with_lemmas(
        self,
        pid: str,
        tags: list[str],
        lemmas_text: str,
        content_text: str | None = None,
    ) -> None:
        doc: dict = {
            "owner": self.sid,
            "pid": pid,
            "feed_id": self.minimal_data["feed_id"],
            "processing": 0,
            "tags": tags,
            "lemmas": gzip.compress(lemmas_text.encode("utf-8")),
            "date": 1700000000,
        }
        if content_text is not None:
            doc["content"] = {
                "title": f"Post {pid}",
                "content": gzip.compress(content_text.encode("utf-8")),
            }
        self.test_db.posts.insert_one(doc)

    def _seed_tag(
        self,
        tag: str,
        count: int = 1,
        classifications: list[dict] | None = None,
    ) -> None:
        doc: dict = {
            "owner": self.sid,
            "tag": tag,
            "posts_count": count,
            "unread_count": count,
            "words": [tag],
            "local_url": f"/entity/{tag}",
            "processing": 0,
            "temperature": 1,
            "freq": 1.0,
            "sentiment": [],
        }
        if classifications:
            doc["classifications"] = classifications
        self.test_db.tags.insert_one(doc)

    def _seed_post_grouping(
        self,
        pid: str,
        sentences: list[dict],
        groups: dict[str, list[int]],
    ) -> None:
        self.app.post_grouping.save_grouped_posts(self.sid, [pid], sentences, groups)

    # ------------------------------------------------------------------
    # on_group_by_tags_get
    # ------------------------------------------------------------------
    def test_on_group_by_tags_get_returns_200(self) -> None:
        response = self.client.get("/group/tag/1")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("testtag", body)

    def test_user_rank_api_hides_and_pins_tags_on_group_page(self) -> None:
        self._seed_tag("pinme", 5)
        self._seed_tag("hideme", 5)
        for tag, value in (("pinme", "pinned"), ("hideme", "hidden")):
            response = self.client.post("/api/tags/user-rank", json={"tag": tag, "value": value})
            self.assertEqual(200, response.status_code)
            self.assertEqual({"ok": True}, response.get_json())
        stored: dict = self.test_db.tags.find_one({"owner": self.sid, "tag": "hideme"})
        self.assertEqual("hidden", stored["user_rank"])
        self.assertTrue(stored["rank"]["noise"])
        page = self.client.get("/group/tag/1?sort=informative&hide_noise=1").get_data(as_text=True)
        self.assertIn("pinme", page)
        self.assertNotIn("hideme", page)
        self.assertLess(page.index("pinme"), page.index("testtag"))
        shown = self.client.get("/group/tag/1").get_data(as_text=True)
        self.assertIn("hideme", shown)
        self.assertRegex(shown, r"user_rank\W+hidden")
        cleared = self.client.post("/api/tags/user-rank", json={"tag": "hideme", "value": None})
        self.assertEqual(200, cleared.status_code)
        self.assertNotIn(
            "user_rank", self.test_db.tags.find_one({"owner": self.sid, "tag": "hideme"})
        )

    def test_user_rank_api_validates_input(self) -> None:
        bad = self.client.post("/api/tags/user-rank", json={"tag": "testtag", "value": "x"})
        self.assertEqual(400, bad.status_code)
        missing = self.client.post("/api/tags/user-rank", json={"tag": "ghost", "value": "hidden"})
        self.assertEqual(404, missing.status_code)

    def test_tags_canvas_page_and_chunked_data(self) -> None:
        self._seed_tag("canvas-second", count=2)
        page = self.client.get("/tags/canvas")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Tag canvas", page.get_data(as_text=True))

        first = self.client.get("/api/tags/canvas?offset=0&limit=1")
        second = self.client.get("/api/tags/canvas?offset=1&limit=1")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        first_data: dict = json.loads(first.get_data(as_text=True))
        second_data: dict = json.loads(second.get_data(as_text=True))
        self.assertEqual(first_data["total"], second_data["total"])
        self.assertEqual(first_data["next_offset"], 1)
        self.assertNotEqual(first_data["tags"][0]["tag"], second_data["tags"][0]["tag"])
        self.assertIn("temperature", first_data["tags"][0])

        invalid = self.client.get("/api/tags/canvas?offset=invalid")
        self.assertEqual(invalid.status_code, 400)

    def test_on_group_by_tags_get_respects_context_filters(self) -> None:
        user, sid = self.seed_test_user("ctx-tags-user", "password")
        self.test_db.feeds.insert_one(
            {
                "owner": sid,
                "feed_id": "ctx-feed",
                "category_id": "ctx-cat",
                "category_title": "Ctx Cat",
                "category_local_url": "/category/ctx-cat",
                "local_url": "/feed/ctx-feed",
                "title": "Ctx Feed",
                "url": "http://example.com/ctx-feed",
                "favicon": "",
                "processing": 0,
            }
        )
        self.test_db.posts.insert_one(
            {
                "owner": sid,
                "pid": "ctx-post-1",
                "feed_id": "ctx-feed",
                "tags": ["ctxtag"],
                "read": False,
                "processing": 0,
            }
        )
        self.test_db.tags.insert_one(
            {
                "owner": sid,
                "tag": "ctxtag",
                "posts_count": 1,
                "unread_count": 1,
                "words": ["ctxtag"],
                "local_url": "/entity/ctxtag",
                "processing": 0,
                "temperature": 1,
                "freq": 1.0,
                "sentiment": [],
            }
        )
        self.app.users.update_settings(
            sid,
            {
                "context_filter": {
                    "feeds": ["ctx-feed"],
                }
            },
        )
        client = self.get_authenticated_client(sid)
        response = client.get("/group/tag/1")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("ctxtag", body)
        self.assertNotIn("testtag", body)

    def _seed_ranked_tags(self, sid: str) -> None:
        ranked: list[tuple[str, int, dict]] = [
            ("rank_common", 9, {"score": 0.1, "noise": True}),
            ("rank_topical", 3, {"score": 4.0, "noise": False, "hot": 0.5}),
            ("rank_trend", 2, {"score": 1.0, "noise": False, "hot": 5.0}),
        ]
        for tag, count, rank in ranked:
            self.test_db.tags.insert_one(
                {
                    "owner": sid,
                    "tag": tag,
                    "posts_count": count,
                    "unread_count": count,
                    "words": [tag],
                    "local_url": f"/entity/{tag}",
                    "processing": 0,
                    "temperature": 1,
                    "freq": 1.0,
                    "rank": rank,
                }
            )

    @staticmethod
    def _page_tag_names(body: str) -> list[str]:
        match = re.search(r"var initial_tags_list = (.*?);", body, re.DOTALL)
        assert match is not None
        return [item["tag"] for item in json.loads(match.group(1))]

    def test_on_group_by_tags_get_sort_switcher(self) -> None:
        _, sid = self.seed_test_user("rank-sort-user", "password")
        self._seed_ranked_tags(sid)
        client = self.get_authenticated_client(sid)

        body = client.get("/group/tag/1").get_data(as_text=True)
        self.assertEqual(
            ["rank_common", "rank_topical", "rank_trend"], self._page_tag_names(body)
        )
        self.assertIn("tag-sort-switcher", body)
        self.assertIn('href="/group/tag/1?sort=informative"', body)
        self.assertIn('initial_tag_sort = "count";', body)

        body = client.get("/group/tag/1?sort=informative&hide_noise=1").get_data(
            as_text=True
        )
        self.assertEqual(["rank_topical", "rank_trend"], self._page_tag_names(body))
        self.assertIn('initial_tag_sort = "informative";', body)
        self.assertIn("/group/tag/1?sort=hot&hide_noise=1", body)

        body = client.get("/group/tag/1?sort=hot").get_data(as_text=True)
        self.assertEqual(
            ["rank_trend", "rank_topical", "rank_common"], self._page_tag_names(body)
        )
        self.assertIn('initial_tag_sort = "hot";', body)

    def test_on_group_by_tags_get_sorts_context_filtered_tags(self) -> None:
        _, sid = self.seed_test_user("rank-ctx-user", "password")
        self._seed_ranked_tags(sid)
        self.test_db.posts.insert_one(
            {
                "owner": sid,
                "pid": "rank-ctx-post",
                "feed_id": "rank-ctx-feed",
                "tags": ["rank_common", "rank_topical", "rank_trend"],
                "read": False,
                "processing": 0,
            }
        )
        self.app.users.update_settings(
            sid, {"context_filter": {"feeds": ["rank-ctx-feed"]}}
        )
        client = self.get_authenticated_client(sid)

        body = client.get("/group/tag/1?sort=informative&hide_noise=1").get_data(
            as_text=True
        )
        self.assertEqual(["rank_topical", "rank_trend"], self._page_tag_names(body))

    def test_on_group_by_tags_get_pagination(self) -> None:
        user, sid = self.seed_test_user("pagination-user", "password")
        self.app.users.update_settings(sid, {"tags_on_page": 2})
        feed_id = "pag-feed"
        self.test_db.feeds.insert_one(
            {
                "owner": sid,
                "feed_id": feed_id,
                "category_id": "pag-cat",
                "category_title": "Pag Cat",
                "category_local_url": "/category/pag-cat",
                "local_url": f"/feed/{feed_id}",
                "title": "Pag Feed",
                "url": "http://example.com/pag-feed",
                "favicon": "",
                "processing": 0,
            }
        )
        for i, tag in enumerate(["pag_a", "pag_b", "pag_c"]):
            self.test_db.posts.insert_one(
                {
                    "owner": sid,
                    "pid": f"pag-post-{i}",
                    "feed_id": feed_id,
                    "tags": [tag],
                    "read": False,
                    "processing": 0,
                }
            )
            self.test_db.tags.insert_one(
                {
                    "owner": sid,
                    "tag": tag,
                    "posts_count": 1,
                    "unread_count": 1,
                    "words": [tag],
                    "local_url": f"/entity/{tag}",
                    "processing": 0,
                    "temperature": 1,
                    "freq": 1.0,
                    "sentiment": [],
                }
            )
        client = self.get_authenticated_client(sid)
        page1 = client.get("/group/tag/1")
        self.assertEqual(page1.status_code, 200)
        body1 = page1.get_data(as_text=True)

        page2 = client.get("/group/tag/2")
        self.assertEqual(page2.status_code, 200)
        body2 = page2.get_data(as_text=True)

        # Both pages should render successfully and contain different tag subsets.
        self.assertNotEqual(body1, body2)

    def test_on_group_by_tags_get_can_filter_to_tags_in_post_topics(self) -> None:
        user, sid = self.seed_test_user("topic-tag-filter-user", "password")
        feed_id = "topic-tag-filter-feed"
        self.test_db.feeds.insert_one(
            {
                "owner": sid,
                "feed_id": feed_id,
                "category_id": "topic-tag-filter-category",
                "category_title": "Topic Tag Filter",
                "category_local_url": "/category/topic-tag-filter-category",
                "local_url": f"/feed/{feed_id}",
                "title": "Topic Tag Filter",
                "url": "http://example.com/topic-tag-filter-feed",
                "favicon": "",
                "processing": 0,
            }
        )
        self.test_db.posts.insert_many(
            [
                {
                    "owner": sid,
                    "pid": "topic-tag-filter-post-1",
                    "feed_id": feed_id,
                    "tags": ["helpful", "noise"],
                    "read": False,
                    "processing": 0,
                },
                {
                    "owner": sid,
                    "pid": "topic-tag-filter-post-2",
                    "feed_id": feed_id,
                    "tags": ["other"],
                    "read": False,
                    "processing": 0,
                },
            ]
        )
        for tag in ("helpful", "noise", "other"):
            self.test_db.tags.insert_one(
                {
                    "owner": sid,
                    "tag": tag,
                    "posts_count": 1,
                    "unread_count": 1,
                    "words": [tag],
                    "local_url": f"/entity/{tag}",
                    "processing": 0,
                    "temperature": 1,
                    "freq": 1.0,
                    "sentiment": [],
                    "topic_backed": tag != "noise",
                }
            )

        client = self.get_authenticated_client(sid)
        response = client.get("/group/tag/1?topics=1")
        self.assertEqual(response.status_code, 200)
        match = re.search(
            r"var initial_tags_list = (.*?);",
            response.get_data(as_text=True),
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        tags = {item["tag"] for item in json.loads(match.group(1))}
        self.assertEqual(tags, {"helpful", "other"})
        self.assertNotIn("noise", tags)
        self.assertIn('/group/tag/1?topics=1', response.get_data(as_text=True))

    # ------------------------------------------------------------------
    # on_group_by_tags_categories_get / on_group_by_tags_by_category_get
    # ------------------------------------------------------------------
    def test_on_group_by_tags_categories_get_returns_200(self) -> None:
        self._seed_tag(
            "cattag", count=1, classifications=[{"category": "Tech", "count": 1}]
        )
        response = self.client.get("/group/tags-categories/1")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Tech", body)

    def test_on_group_by_tags_by_category_get_returns_200(self) -> None:
        self._seed_tag(
            "cattag", count=1, classifications=[{"category": "Tech", "count": 1}]
        )
        response = self.client.get("/tags/category/Tech/1")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("cattag", body)

    # ------------------------------------------------------------------
    # on_s_tree_get
    # ------------------------------------------------------------------
    def test_on_s_tree_get_returns_200_with_sentences(self) -> None:
        content = "This is a sentence with testtag in it. Another sentence here."
        self._seed_post_with_lemmas(
            "post-s-tree", ["testtag"], "testtag sentence another", content
        )
        response = self.client.get("/s-tree/testtag")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("testtag", body)

    # ------------------------------------------------------------------
    # on_tag_grouped_topics_get / on_tag_llm_topics_get
    # ------------------------------------------------------------------
    def test_on_tag_grouped_topics_get_with_grouping_data(self) -> None:
        pid = self.minimal_data["post_pids"][0]
        self._seed_post_grouping(
            pid,
            sentences=[
                {"number": 1, "text": "Hello testtag world", "read": False},
                {"number": 2, "text": "Another sentence", "read": False},
            ],
            groups={
                "Topic A": [1],
                "Topic B": [2],
            },
        )
        response = self.client.get("/tag-grouped-topics/testtag")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("data", data)
        tags = [item["tag"] for item in data["data"]]
        self.assertIn("Topic A", tags)

    def test_on_tag_llm_topics_get_with_grouping_data(self) -> None:
        pid = self.minimal_data["post_pids"][0]
        self._seed_post_grouping(
            pid,
            sentences=[
                {"number": 1, "text": "Hello testtag world", "read": False},
                {"number": 2, "text": "Another sentence", "read": False},
            ],
            groups={
                "Topic A > Subtopic": [1],
                "Topic B": [2],
            },
        )
        response = self.client.get("/tag-llm-topics/testtag")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("data", data)
        tags = [item["tag"] for item in data["data"]]
        self.assertIn("Topic A", tags)
        self.assertIn("Subtopic", tags)

    def test_on_entity_grouped_snippets_get_returns_matching_topic_ranges(self) -> None:
        self._seed_post_with_lemmas(
            "entity-snippet-post",
            ["testtag"],
            "hello testtag world",
            "Testtag appears in grouped range. Another sentence without it.",
        )
        self._seed_post_grouping(
            "entity-snippet-post",
            sentences=[
                {
                    "number": 1,
                    "text": "Testtag appears in grouped range",
                    "read": False,
                },
                {
                    "number": 2,
                    "text": "Another sentence without it",
                    "read": False,
                },
            ],
            groups={
                "Topic A": [1],
                "Topic B": [2],
            },
        )

        response = self.client.get("/entity-grouped-snippets/testtag")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Entity Snippets: testtag", body)
        self.assertIn("Topic A", body)
        self.assertIn("<mark>Testtag</mark> appears in grouped range", body)
        self.assertNotIn("Topic B", body)

    # ------------------------------------------------------------------
    # on_tag_context_tree_get
    # ------------------------------------------------------------------
    def test_on_tag_context_tree_get_returns_200(self) -> None:
        self._seed_post_with_lemmas(
            "post-ctx", ["testtag"], "hello testtag world foo bar"
        )
        response = self.client.get("/tag-context-tree/testtag")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("testtag", body)
        self.assertIn("mindmap_data", body)

    def test_tag_explorer_page_and_json_selections(self) -> None:
        self._seed_post_with_lemmas(
            "explorer-context", ["testtag", "related"],
            "before testtag right after", "Before testtag right after. Extra sentence.",
        )
        self._seed_post_with_lemmas(
            "explorer-other", ["testtag", "other"],
            "before testtag elsewhere", "Before testtag elsewhere.",
        )

        self._seed_post_grouping(
            "explorer-context",
            [{"number": 1, "text": "Before testtag right after.", "read": False},
             {"number": 2, "text": "Extra sentence.", "read": False}],
            {"Examples > Context": [1], "Examples > Other": [2]},
        )

        page_response = self.client.get("/tag-explorer/testtag")
        self.assertEqual(page_response.status_code, 200)
        page_body = page_response.get_data(as_text=True)
        self.assertIn("tag-explorer-tree", page_body)
        self.assertIn("right", page_body)

        context_response = self.client.get(
            "/tag-explorer/testtag",
            query_string={
                "format": "json",
                "selection": json.dumps(
                    {"kind": "context", "chain": ["right"]}
                ),
            },
        )
        self.assertEqual(context_response.status_code, 200)
        context_result = context_response.get_json()
        self.assertEqual(context_result["total"], 1)
        self.assertEqual(context_result["posts"][0]["pid"], "explorer-context")

        self.assertIn('"topics"', page_body)
        for chain in (["Examples"], ["Examples", "Context"]):
            topic_response = self.client.get(
                "/tag-explorer/testtag",
                query_string={
                    "format": "json",
                    "selection": json.dumps({"kind": "topic", "chain": chain}),
                },
            )
            self.assertEqual(topic_response.status_code, 200)
            topic_result = topic_response.get_json()
            self.assertEqual(topic_result["total"], 1)
            self.assertEqual(topic_result["posts"][0]["pid"], "explorer-context")
            self.assertEqual(
                [sentence["number"] for sentence in topic_result["sentences"]],
                [1, 2] if len(chain) == 1 else [1],
            )

    # ------------------------------------------------------------------
    # on_ba_surprise_get
    # ------------------------------------------------------------------
    def test_on_ba_surprise_get_returns_200(self) -> None:
        # Posts need >=2 unique tags for LeaveOneOutSurprise.
        for i in range(3):
            self.test_db.posts.insert_one(
                {
                    "owner": self.sid,
                    "pid": f"surprise-post-{i}",
                    "feed_id": self.minimal_data["feed_id"],
                    "tags": ["testtag", f"extratag{i}"],
                    "read": False,
                    "processing": 0,
                }
            )
            self.test_db.tags.insert_one(
                {
                    "owner": self.sid,
                    "tag": f"extratag{i}",
                    "posts_count": 1,
                    "unread_count": 1,
                    "words": [f"extratag{i}"],
                    "local_url": f"/entity/extratag{i}",
                    "processing": 0,
                    "temperature": 1,
                    "freq": 1.0,
                    "sentiment": [],
                }
            )
        response = self.client.get("/ba-surprise")
        self.assertEqual(response.status_code, 200)

    def test_on_ba_surprise_get_with_tag_filter(self) -> None:
        response = self.client.get("/ba-surprise?tag=testtag")
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # tag-scoped: on_tag_ba_surprise_get / rake / yake
    # ------------------------------------------------------------------
    ITEM_KEYS = {"tag", "url", "words", "count", "sentiment", "temp", "freq"}

    def _seed_scoped_data(self) -> None:
        for i in range(3):
            self._seed_post_with_lemmas(
                f"scoped-{i}",
                ["scopedtag", f"cotag{i}", "shared"],
                f"scopedtag machine learning model{i} shared insight",
            )
            self.test_db.posts.update_one(
                {"owner": self.sid, "pid": f"scoped-{i}"}, {"$set": {"read": False}}
            )
            self._seed_tag(f"cotag{i}", count=5)
        self._seed_tag("shared", count=5)
        self._seed_tag("scopedtag", count=5)
        # Post without the scoped tag must not influence results.
        self._seed_post_with_lemmas(
            "unscoped", ["other", "othertwo"], "unrelated banana content"
        )
        self.test_db.posts.update_one(
            {"owner": self.sid, "pid": "unscoped"}, {"$set": {"read": False}}
        )
        self._seed_tag("other", count=5)
        self._seed_tag("othertwo", count=5)

    def test_on_tag_ba_surprise_get_returns_scoped_data(self) -> None:
        self._seed_scoped_data()
        response = self.client.get("/tag-ba-surprise/scopedtag")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        data = response.get_json()["data"]
        self.assertIsInstance(data, list)
        names = {item["tag"] for item in data}
        self.assertIn("shared", names)
        self.assertNotIn("scopedtag", names)
        self.assertNotIn("other", names)
        for item in data:
            self.assertEqual(set(item.keys()), self.ITEM_KEYS)

    def test_on_tag_ba_surprise_get_unknown_tag_returns_empty(self) -> None:
        response = self.client.get("/tag-ba-surprise/nosuchtag")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"data": []})

    def test_on_tag_ba_surprise_get_blank_tag_returns_400(self) -> None:
        response = self.client.get("/tag-ba-surprise/%20")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_on_tag_ba_surprise_get_error_returns_500(self) -> None:
        with mock.patch.object(
            self.app.posts, "get_by_tags", side_effect=RuntimeError("boom")
        ):
            response = self.client.get("/tag-ba-surprise/scopedtag")
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.get_json())

    def test_on_tag_keywords_dyn_get_return_scoped_data(self) -> None:
        self._seed_scoped_data()
        for endpoint in ("tag-rake-dyn", "tag-yake-dyn"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(f"/{endpoint}/scopedtag")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "application/json")
                data = response.get_json()["data"]
                self.assertIsInstance(data, list)
                self.assertTrue(data)
                phrases = {item["tag"] for item in data}
                self.assertNotIn("scopedtag", phrases)
                self.assertFalse(any("banana" in p for p in phrases))
                self.assertTrue(any("machine" in p for p in phrases))
                for item in data:
                    self.assertEqual(set(item.keys()), self.ITEM_KEYS)

    def test_on_tag_keywords_dyn_get_unknown_tag_returns_empty(self) -> None:
        for endpoint in ("tag-rake-dyn", "tag-yake-dyn"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(f"/{endpoint}/nosuchtag")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json(), {"data": []})

    def test_on_tag_keywords_dyn_get_blank_tag_returns_400(self) -> None:
        for endpoint in ("tag-rake-dyn", "tag-yake-dyn"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(f"/{endpoint}/%20")
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

    def test_on_tag_keywords_dyn_get_error_returns_500(self) -> None:
        with mock.patch.object(
            self.app.posts, "get_by_tags", side_effect=RuntimeError("boom")
        ):
            for endpoint in ("tag-rake-dyn", "tag-yake-dyn"):
                with self.subTest(endpoint=endpoint):
                    response = self.client.get(f"/{endpoint}/scopedtag")
                    self.assertEqual(response.status_code, 500)
                    self.assertIn("error", response.get_json())

    # ------------------------------------------------------------------
    # on_get_chain / on_get_sunburst
    # ------------------------------------------------------------------
    def test_on_get_chain_returns_200(self) -> None:
        self._seed_post_with_lemmas("post-chain", ["testtag"], "hello testtag world")
        response = self.client.get("/chain/testtag")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("testtag", body)

    def test_on_get_sunburst_returns_200(self) -> None:
        self._seed_post_with_lemmas("post-sun", ["testtag"], "hello testtag world")
        response = self.client.get("/sunburst/testtag")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("testtag", body)

    def test_on_get_tree_returns_200(self) -> None:
        response = self.client.get("/tree/testtag")
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # on_tfidf_tags_get
    # ------------------------------------------------------------------
    def test_on_tfidf_tags_get_returns_200(self) -> None:
        response = self.client.get("/tfidf-tags")
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # Existing endpoint coverage
    # ------------------------------------------------------------------
    def test_on_group_by_tags_group(self) -> None:
        response = self.client.get("/tags/group/test/1")
        self.assertEqual(response.status_code, 200)

    def test_on_group_by_tags_sentiment(self) -> None:
        response = self.client.get("/tags/sentiment/positive/1")
        self.assertEqual(response.status_code, 200)

    def test_on_get_context_tags(self) -> None:
        response = self.client.get("/context-tags/testtag")
        self.assertIn(response.status_code, [200, 404])

    def test_on_post_tags_search(self) -> None:
        response = self.client.post("/tags-search", data={"req": "testtag"})
        self.assertIn(response.status_code, [200, 301, 302])

    def test_on_get_tag_similar_tags(self) -> None:
        response = self.client.get("/tag-similar-tags/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_get_sentences_with_tags(self) -> None:
        response = self.client.get("/sentences/with/tags/testtag")
        self.assertEqual(response.status_code, 200)

    def test_on_get_posts_with_tags(self) -> None:
        response = self.client.get("/posts/with/tags/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_get_tag_page(self) -> None:
        response = self.client.get("/tag-info/testtag")
        self.assertEqual(response.status_code, 200)

    def test_on_tag_tfidf_get(self) -> None:
        response = self.client.get("/tag-tfidf/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_tag_topics_get(self) -> None:
        response = self.client.get("/tag-topics/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_tag_clusters_get(self) -> None:
        response = self.client.get("/tag-clusters/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_tag_entities_get(self) -> None:
        response = self.client.get("/tag-entities/testtag")
        self.assertEqual(response.status_code, 200)

    def test_on_tag_specific_get(self) -> None:
        response = self.client.get("/tag-specific/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_tag_specific1_get(self) -> None:
        response = self.client.get("/tag-specific1/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_get_tag_siblings(self) -> None:
        self._seed_post_with_lemmas("post-sib", ["testtag"], "hello testtag world")
        response = self.client.get("/tag-siblings/testtag")
        self.assertEqual(response.status_code, 200)

    def test_on_get_tag_pmi(self) -> None:
        self._seed_post_with_lemmas("post-pmi", ["testtag"], "hello testtag world")
        response = self.client.get("/tag-pmi/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_tag_contexts_classification_get(self) -> None:
        self.test_db.tags.update_one(
            {"owner": self.sid, "tag": "testtag"},
            {
                "$set": {
                    "classifications": [
                        {"category": "Cat", "count": 1, "pids": ["p1"]}
                    ]
                }
            },
        )
        response = self.client.get("/tag-contexts-classification/testtag")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)

    def test_on_tag_dates_get(self) -> None:
        response = self.client.get("/tag-dates/testtag")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("data", data)

    def test_on_group_by_tags_startwith_get(self) -> None:
        response = self.client.get("/group/tag/startwith/t/1")
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # ML model endpoints (mocked)
    # ------------------------------------------------------------------
    def test_on_get_tag_similar_with_mocked_w2v(self) -> None:
        with mock.patch("os.path.exists", return_value=True):
            with mock.patch("gensim.models.word2vec.Word2Vec.load") as mock_load:
                mock_model = mock.MagicMock()
                mock_model.wv.most_similar.return_value = [("similar1", 0.9)]
                mock_load.return_value = mock_model
                self.test_db.users.update_one(
                    {"sid": self.sid}, {"$set": {"w2v": "test_model.bin"}}
                )
                response = self.client.get("/tag-similar/w2v/testtag")
                self.assertEqual(response.status_code, 200)
                data = response.get_json()
                self.assertIn("data", data)

    def test_on_get_tag_similar_with_mocked_fasttext(self) -> None:
        with mock.patch("os.path.exists", return_value=True):
            with mock.patch("gensim.models.fasttext.FastText.load") as mock_load:
                mock_model = mock.MagicMock()
                mock_model.wv.similar_by_word.return_value = [("similar1", 0.9)]
                mock_load.return_value = mock_model
                self.test_db.users.update_one(
                    {"sid": self.sid}, {"$set": {"fasttext": "test_model.bin"}}
                )
                response = self.client.get("/tag-similar/fasttext/testtag")
                self.assertEqual(response.status_code, 200)
                data = response.get_json()
                self.assertIn("data", data)


if __name__ == "__main__":
    unittest.main()
