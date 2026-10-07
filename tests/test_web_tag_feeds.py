import json
import unittest
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import quote_plus, urlencode

from jinja2 import Environment, PackageLoader
from werkzeug.wrappers import Request, Response

from rsstag.web.posts import on_tag_feeds_get, on_tag_get
from rsstag.web.routes import RSSTagRoutes
from rsstag.web.tags import on_get_tag_page
from tests.web_test_utils import MongoWebTestCase


class TestTagFeedCloudRendering(unittest.TestCase):
    """Verify real templates and handler behavior without a database service."""

    def setUp(self) -> None:
        self.app: MagicMock = MagicMock()
        self.app.routes = RSSTagRoutes("localhost")
        self.app.template_env = Environment(loader=PackageLoader("rsstag.web", "templates/default"))
        self.app.template_env.filters.update({"json": json.dumps, "tojson": json.dumps, "url_encode": quote_plus})
        self.app.on_error.side_effect = lambda user, request, error: Response(status=error.code)
        self.user: dict[str, Any] = {
            "sid": "owner", "settings": {"only_unread": True, "similar_posts": True, "context_filter": {"tags": ["focused"]}},
        }
        self.app.tags.get_by_tag.return_value = {"tag": "c++", "words": ["c++"]}
        self.app.posts.get_tag_feed_counts.return_value = [
            {"_id": "one", "count": 5}, {"_id": "two+three", "count": 1}, {"_id": "missing", "count": 2},
        ]
        self.app.feeds.get_by_feed_ids.return_value = [
            {"feed_id": "two+three", "title": "Other <source>"}, {"feed_id": "one", "title": "Main source"},
        ]

    def test_cloud_renders_weighted_sources_and_encoded_links(self) -> None:
        response: Response = on_tag_feeds_get(self.app, self.user, Request.from_values(), "c++")
        self.assertEqual(response.status_code, 200)
        body: str = response.get_data(as_text=True)
        self.assertIn("2 feeds / sources · 6 matching posts", body)
        self.assertIn("Other &lt;source&gt;", body)
        self.assertIn('href="/tag/c++?feed=two%2Bthree"', body)
        self.assertLess(body.index("Main source"), body.index("Other &lt;source&gt;"))
        self.assertIn("tag-feed-cloud-size-5", body)
        self.assertIn("tag-feed-cloud-size-1", body)
        self.app.posts.get_tag_feed_counts.assert_called_once_with("owner", "c++", True, context_tags=["focused"])

    def test_empty_and_missing_tag(self) -> None:
        self.app.posts.get_tag_feed_counts.return_value = []
        self.app.feeds.get_by_feed_ids.return_value = []
        response: Response = on_tag_feeds_get(self.app, self.user, Request.from_values(), "c++")
        self.assertIn("No feeds / sources mention this tag", response.get_data(as_text=True))
        self.app.tags.get_by_tag.return_value = None
        self.assertEqual(on_tag_feeds_get(self.app, self.user, Request.from_values(), "missing").status_code, 404)

    def test_section_returns_only_cloud_content(self) -> None:
        response: Response = on_tag_feeds_get(
            self.app, self.user, Request.from_values(query_string="view=section"), "c++"
        )
        body: str = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('class="tag-feed-cloud"', body)
        self.assertIn("Other &lt;source&gt;", body)
        self.assertIn("2 feeds / sources · 6 matching posts", body)
        self.assertNotIn("<html", body)
        self.assertNotIn("<script", body)

    def test_tag_info_starts_with_unloaded_feed_section(self) -> None:
        self.app.tags.get_by_tag.return_value.update({
            "_id": "tag", "local_url": "/tag/c++", "unread_count": 6, "posts_count": 6,
        })
        response: Response = on_get_tag_page(self.app, self.user, Request.from_values(), "c++")
        self.assertEqual(response.status_code, 200)
        body: str = response.get_data(as_text=True)
        self.assertIn('data-url="/tag/c++/feeds?view=section"', body)
        self.assertIn('aria-controls="tag_feeds_cloud" aria-expanded="false"', body)
        self.assertIn('<div id="tag_feeds_cloud" class="tag_info_block space-y-6"></div>', body)
        self.app.posts.get_tag_feed_counts.assert_not_called()

    def test_database_error_is_handled(self) -> None:
        self.app.posts.get_tag_feed_counts.side_effect = RuntimeError("Unavailable")
        self.assertEqual(on_tag_feeds_get(self.app, self.user, Request.from_values(), "c++").status_code, 500)

    def test_selected_source_keeps_tag_context_and_excludes_similar_posts(self) -> None:
        self.app.feeds.get_by_feed_id.return_value = {"title": "Other <source>", "category_title": "Category", "favicon": ""}
        self.app.posts.get_by_tags.return_value = [{"feed_id": "two+three", "pid": "p1"}]
        response: Response = on_tag_get(self.app, self.user, Request.from_values(query_string="feed=two%2Bthree"), "c++")
        self.assertEqual(response.status_code, 200)
        self.app.posts.get_by_tags.assert_called_once_with(
            "owner", ["c++"], True, {"_id": False, "content.content": False}, context_tags=["focused"], feed_id="two+three",
        )
        self.app.posts.get_clusters.assert_not_called()
        self.assertIn("Other &lt;source&gt;", response.get_data(as_text=True))


class TestWebTagFeeds(MongoWebTestCase):
    def setUp(self) -> None:
        for collection in ("users", "feeds", "posts", "tags"):
            self.test_db[collection].delete_many({})
        _user: dict[str, Any]
        self.sid: str
        _user, self.sid = self.seed_test_user("tag-feeds")
        data: dict[str, Any] = self.seed_minimal_data(self.sid)
        self.feed_id: str = data["feed_id"]
        self.test_db.posts.update_many({"owner": self.sid}, {"$set": {"read": False}})
        second_feed: dict[str, Any] = dict(self.test_db.feeds.find_one({"owner": self.sid}))
        second_feed.pop("_id")
        second_feed.update({"feed_id": "https://example.com/feed?a=1&b=two+three", "title": "Other <source>"})
        self.second_feed_id: str = second_feed["feed_id"]
        base_post: dict[str, Any] = dict(self.test_db.posts.find_one({"owner": self.sid}))
        base_post.pop("_id")
        posts: list[dict[str, Any]] = [
            dict(base_post, pid="other-unread", feed_id=self.second_feed_id, tags=["testtag", "focused"]),
            dict(base_post, pid="other-read", feed_id=self.second_feed_id, read=True),
            dict(base_post, pid="unrelated", feed_id=self.second_feed_id, tags=["else"]),
            dict(base_post, pid="private", owner="another-owner"),
            dict(base_post, pid="deleted-feed", feed_id="missing"),
        ]
        self.db_helper.init_db_from_dict(self.test_db, {"feeds": [second_feed], "posts": posts})

    def _cloud(self) -> str:
        response: Any = self.get_authenticated_client(self.sid).get("/tag/testtag/feeds")
        self.assertEqual(response.status_code, 200)
        return response.data.decode()

    def test_cloud_counts_and_escaped_titles(self) -> None:
        body: str = self._cloud()
        self.assertIn("2 feeds / sources · 3 matching posts", body)
        self.assertIn("Other &lt;source&gt;", body)
        self.assertNotIn("Other <source>", body)
        self.assertIn('title="2 matching posts"', body)
        self.assertIn('title="1 matching posts"', body)
        self.assertLess(body.index("Test Feed"), body.index("Other &lt;source&gt;"))
        self.assertNotIn("missing", body)

    def test_all_posts_setting(self) -> None:
        self.app.users.update_settings(self.sid, {"only_unread": False})
        self.assertIn("2 feeds / sources · 4 matching posts", self._cloud())

    def test_context_tags_and_empty_state(self) -> None:
        self.app.users.update_settings(self.sid, {"context_filter": {"tags": ["focused"]}})
        body: str = self._cloud()
        self.assertIn("1 feeds / sources · 1 matching posts", body)
        self.assertNotIn("Test Feed", body)
        self.app.users.update_settings(self.sid, {"context_filter": {"tags": ["absent"]}})
        self.assertIn("No feeds / sources mention this tag with the current filters.", self._cloud())

    def test_source_link_only_returns_matching_posts(self) -> None:
        query: str = urlencode({"feed": self.second_feed_id})
        self.assertIn("/tag/testtag?" + query.replace("&", "&amp;"), self._cloud())
        response: Any = self.get_authenticated_client(self.sid).get("/tag/testtag?" + query)
        self.assertEqual(response.status_code, 200)
        body: str = response.data.decode()
        posts: list[dict[str, Any]] = json.loads(body.split("window.posts_list = ", 1)[1].split(";", 1)[0])
        self.assertEqual([item["post"]["pid"] for item in posts], ["other-unread"])
        self.assertIn('href="/tag/testtag/feeds"', body)
        self.assertIn("Other &lt;source&gt;", body)

    def test_source_posts_apply_context_tags(self) -> None:
        self.app.users.update_settings(self.sid, {"context_filter": {"tags": ["absent"]}})
        response: Any = self.get_authenticated_client(self.sid).get("/tag/testtag?" + urlencode({"feed": self.second_feed_id}))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"window.posts_list = [];", response.data)

    def test_missing_tag_or_foreign_feed_returns_not_found(self) -> None:
        client: Any = self.get_authenticated_client(self.sid)
        self.assertEqual(client.get("/tag/unknown/feeds").status_code, 404)
        self.assertEqual(client.get("/tag/testtag?feed=unknown").status_code, 404)
        self.db_helper.init_db_from_dict(self.test_db, {"feeds": [{"owner": "another-owner", "feed_id": "foreign", "title": "Private"}]})
        self.assertEqual(client.get("/tag/testtag?feed=foreign").status_code, 404)

    def test_database_failure_returns_server_error(self) -> None:
        with patch.object(self.app.posts, "get_tag_feed_counts", side_effect=RuntimeError("Unavailable")):
            response: Any = self.get_authenticated_client(self.sid).get("/tag/testtag/feeds")
        self.assertEqual(response.status_code, 500)
