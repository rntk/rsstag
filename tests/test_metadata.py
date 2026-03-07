import unittest
from types import SimpleNamespace
from urllib.parse import quote_plus
import json
import os
import time

from jinja2 import Environment, PackageLoader

from rsstag.web.metadata import _render_page


class _FakeFeeds:
    def get_all(self, owner: str, projection: dict | None = None) -> list[dict]:
        del owner, projection
        return [
            {"feed_id": "feed-1", "title": "Feed One", "category_id": "cat-1"},
            {"feed_id": "feed-2", "title": "Feed Two", "category_id": "cat-2"},
        ]


class TestMetadataPage(unittest.TestCase):
    def setUp(self) -> None:
        template_env: Environment = Environment(
            loader=PackageLoader("rsstag.web", os.path.join("templates", "default"))
        )
        template_env.filters["json"] = lambda d: json.dumps(d, default=str)
        template_env.filters["tojson"] = lambda d: json.dumps(d, default=str)
        template_env.filters["url_encode"] = quote_plus
        template_env.filters["timestamp_to_datetime"] = (
            lambda ts: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
            if ts
            else "N/A"
        )
        template_env.filters["hex_to_rgba"] = (
            lambda hex_color, alpha=0.15: f"rgba({hex_color},{alpha})"
        )
        template_env.filters["find_group"] = lambda sentence, groups: None

        self.app: SimpleNamespace = SimpleNamespace(
            template_env=template_env,
            feeds=_FakeFeeds(),
            config={
                "settings": {
                    "support": "support@example.com",
                    "version": "test-version",
                    "providers": "telegram,gmail",
                }
            },
        )
        self.user: dict = {
            "sid": "user-1",
            "provider": "telegram",
            "settings": {},
        }

    def test_scope_blocks_match_scope_values(self) -> None:
        response = _render_page(self.app, self.user)
        html: str = response.get_data(as_text=True)

        self.assertIn('option value="posts"', html)
        self.assertIn('option value="feeds"', html)
        self.assertIn('option value="categories"', html)
        self.assertIn('option value="provider"', html)

        self.assertIn('id="scope-posts"', html)
        self.assertIn('id="scope-feeds"', html)
        self.assertIn('id="scope-categories"', html)
        self.assertIn('id="scope-provider"', html)

    def test_post_ids_textarea_is_rendered(self) -> None:
        response = _render_page(
            self.app,
            self.user,
            form_data={"scope_type": "posts", "post_ids": "p1,p2"},
        )
        html: str = response.get_data(as_text=True)

        self.assertIn('<textarea name="post_ids"', html)
        self.assertIn(">p1,p2</textarea>", html)


if __name__ == "__main__":
    unittest.main()
