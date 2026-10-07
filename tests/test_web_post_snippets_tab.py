import json
import unittest
from typing import Any
from unittest.mock import MagicMock
from urllib.parse import quote_plus

from jinja2 import Environment, PackageLoader
from werkzeug.wrappers import Request, Response

from rsstag.web.posts import on_category_get, on_entity_get, on_tag_get, on_tag_grouped_snippets_get
from rsstag.web.routes import RSSTagRoutes


class TestPostSnippetsTab(unittest.TestCase):
    def setUp(self) -> None:
        self.app: MagicMock = MagicMock()
        self.app.routes = RSSTagRoutes("localhost")
        self.app.template_env = Environment(loader=PackageLoader("rsstag.web", "templates/default"))
        self.app.template_env.filters.update({"json": json.dumps, "url_encode": quote_plus})
        self.app.posts.get_by_tags.return_value = []
        self.app.tags.get_by_tags.return_value = []
        self.app.on_error.side_effect = lambda user, request, error: Response(status=error.code)
        self.user: dict[str, Any] = {
            "sid": "owner", "settings": {"only_unread": True, "similar_posts": False},
        }

    def test_tag_tab_preserves_source_filter(self) -> None:
        self.app.tags.get_by_tag.return_value = {"words": ["cats"]}
        response: Response = on_tag_get(
            self.app, self.user, Request.from_values(query_string="feed=one%2Btwo"), "cat"
        )
        body: str = response.get_data(as_text=True)
        self.assertIn('window.snippets_url = "/tag-grouped-snippets/cat?feed=one%2Btwo"', body)
        self.assertIn('src="/static/js/post-grouped-snippets.js"', body)

    def test_entity_tab_preserves_window(self) -> None:
        response: Response = on_entity_get(self.app, self.user, "red fox", window=3)
        self.assertIn(
            'window.snippets_url = "/entity-grouped-snippets/red%20fox?window=3"',
            response.get_data(as_text=True),
        )

    def test_category_has_no_sentence_filter_tab(self) -> None:
        self.app.feeds.get_by_category.return_value = [{"feed_id": "one"}]
        self.app.posts.get_by_category.return_value = []
        response: Response = on_category_get(self.app, self.user, Request.from_values(), "News")
        body: str = response.get_data(as_text=True)
        self.assertIn("window.snippets_url = null;", body)
        self.assertNotIn('src="/static/js/post-grouped-snippets.js"', body)

    def test_tag_snippets_query_preserves_feed_and_context(self) -> None:
        self.user["settings"]["context_filter"] = {"tags": ["focus"]}
        self.app.tags.get_by_tag.return_value = {"words": ["cats"]}
        on_tag_grouped_snippets_get(
            self.app, self.user, Request.from_values(query_string="feed=one%2Btwo"), "cat"
        )
        self.app.posts.get_by_tags.assert_called_once_with(
            "owner", ["cat"], only_unread=True, projection={"pid": True},
            context_tags=["focus"], feed_id="one+two",
        )
