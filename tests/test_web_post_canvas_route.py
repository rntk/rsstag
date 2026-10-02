"""Focused tests for post canvas route behavior without database access."""

import json
import re
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from jinja2 import Environment, FileSystemLoader, select_autoescape
from werkzeug.exceptions import NotFound
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

import rsstag.web.posts as posts
from rsstag.snippets import snippet_text_from_sentence


def _request() -> Request:
    return Request(EnvironBuilder(path="/post-canvas").get_environ())


class PostCanvasRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app: MagicMock = MagicMock()
        self.template: MagicMock = MagicMock()
        self.template.render.return_value = "<html>canvas</html>"
        self.app.template_env.get_template.return_value = self.template
        self.user: dict[str, Any] = {"settings": {"theme": "dark"}}

    def test_route_renders_article_sheets_and_payload(self) -> None:
        hostile_text: str = "</script><script>alert('x')</script> & 'quoted'"
        context: dict[str, Any] = {
            "post_id": "p1",
            "posts": [
                {
                    "post_id": "p1",
                    "content": f"<p>Canvas <b>post</b>. {hostile_text}</p>",
                    "feed_title": "Canvas feed",
                    "url": "https://example.com/p1",
                    "read": False,
                }
            ],
            "sentences": [
                {
                    "number": 1,
                    "post_sentence_number": 1,
                    "post_id": "p1",
                    "text": hostile_text,
                    "read": False,
                    "start": 0,
                    "end": len(hostile_text),
                }
            ],
            "groups": {"Topic": [1]},
            "has_grouped_data": True,
            "feed_title": "Canvas feed",
            "current_topic": None,
            "current_topic_label": "",
            "current_topic_query": "",
            "topic_only_view": False,
            "group_colors": {"Topic": "#123456"},
            "hierarchical_segments": [],
            "post_to_index_map": {"p1": 0},
        }
        template_dir: Path = (
            Path(__file__).parents[1] / "rsstag" / "web" / "templates" / "default"
        )
        self.app.template_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html"]),
        )
        with patch.object(
            posts, "_build_grouped_posts_page_context", return_value=context
        ) as build:
            response = posts.on_post_canvas_get(self.app, self.user, _request(), "p1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/html")
        rendered: str = response.get_data(as_text=True)
        # Article HTML is rendered into the sheet, not into the JSON payload.
        self.assertIn('<div class="post-canvas__article-html"><p>Canvas <b>post</b>.', rendered)
        self.assertIn('href="https://example.com/p1"', rendered)
        build.assert_called_once_with(
            self.app, self.user, unittest.mock.ANY, "p1", plain_sentences=True
        )
        match: re.Match[str] | None = re.search(
            r'<script id="post-canvas-data" type="application/json">(.*?)</script>',
            rendered,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        self.assertNotIn("</script><script>", match.group(1))
        payload: dict[str, Any] = json.loads(match.group(1))
        self.assertEqual(payload["sentences"][0]["text"], hostile_text)
        self.assertEqual(
            payload["posts"],
            [
                {
                    "post_id": "p1",
                    "feed_title": "Canvas feed",
                    "url": "https://example.com/p1",
                }
            ],
        )
        self.assertEqual(payload["groups"], {"Topic": [1]})

    def test_route_returns_not_found_for_missing_or_empty_posts(self) -> None:
        for context in (None, {"posts": []}):
            with self.subTest(context=context):
                self.app.on_error.return_value = MagicMock(status_code=404)
                with patch.object(
                    posts, "_build_grouped_posts_page_context", return_value=context
                ):
                    response = posts.on_post_canvas_get(self.app, self.user, _request())

                self.assertEqual(response.status_code, 404)
                self.app.on_error.assert_called_with(
                    self.user, unittest.mock.ANY, unittest.mock.ANY
                )
                self.assertIsInstance(self.app.on_error.call_args.args[2], NotFound)

    def test_route_returns_informative_server_error_on_failure(self) -> None:
        with patch.object(
            posts,
            "_build_grouped_posts_page_context",
            side_effect=RuntimeError("failure"),
        ):
            response = posts.on_post_canvas_get(self.app, self.user, _request())

        self.assertEqual(response.status_code, 500)
        self.assertIn("could not be loaded", response.get_data(as_text=True))

    def test_missing_sentence_text_is_extracted_from_raw_content_offsets(self) -> None:
        raw_content: str = "Before. <b>Recovered sentence.</b> After."
        start: int = raw_content.index("<b>")
        end: int = raw_content.index(" After.")

        extracted: str = snippet_text_from_sentence(
            raw_content, {"start": start, "end": end}
        )

        self.assertEqual(extracted, "Recovered sentence.")


if __name__ == "__main__":
    unittest.main()
