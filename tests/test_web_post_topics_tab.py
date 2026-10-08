import json
import unittest
from typing import Any
from unittest.mock import MagicMock
from urllib.parse import quote_plus

from jinja2 import Environment, PackageLoader
from werkzeug.wrappers import Request, Response

from rsstag.web.posts import (
    _filter_topics_by_tag,
    on_category_get,
    on_entity_get,
    on_posts_topics_post,
    on_tag_get,
)
from rsstag.web.routes import RSSTagRoutes


def _source(post_id: str, *texts: str) -> dict[str, Any]:
    return {
        "post_id": post_id,
        "title": f"Post {post_id}",
        "url": "",
        "feed_title": "",
        "feed_url": "",
        "sentences": [
            {"number": i, "text": text, "read": False} for i, text in enumerate(texts)
        ],
    }


def _grouped(pids: list[str]) -> dict[str, Any]:
    data: dict[str, dict[str, Any]] = {
        "1": {"groups": {"Pets>Cats": [0], "Weather": [1]},
              "sentences": [{"number": 0, "text": "Cats purr."},
                            {"number": 1, "text": "Rain today."}]},
        "2": {"groups": {"Pets>Dogs": [0]},
              "sentences": [{"number": 0, "text": "Dogs bark."}]},
    }
    return data.get(pids[0])


class TestPostTopicsTab(unittest.TestCase):
    def setUp(self) -> None:
        self.app: MagicMock = MagicMock()
        self.app.routes = RSSTagRoutes("localhost")
        self.app.template_env = Environment(loader=PackageLoader("rsstag.web", "templates/default"))
        self.app.template_env.filters.update({"json": json.dumps, "url_encode": quote_plus})
        self.app.posts.get_by_tags.return_value = []
        self.app.tags.get_by_tags.return_value = []
        self.app.feeds.get_by_feed_ids.return_value = []
        self.app.post_grouping.get_grouped_posts.side_effect = lambda owner, pids: _grouped(pids)
        self.user: dict[str, Any] = {
            "sid": "owner", "settings": {"only_unread": False, "similar_posts": False},
        }

    def _post(self, body: Any) -> Response:
        request: Request = Request.from_values(
            method="POST", data=json.dumps(body), content_type="application/json"
        )
        return on_posts_topics_post(self.app, self.user, request)

    def test_tag_page_exposes_topics_tag(self) -> None:
        self.app.tags.get_by_tag.return_value = {"words": ["cats"]}
        response: Response = on_tag_get(self.app, self.user, Request.from_values(), "cat")
        self.assertIn('window.topics_tag = "cat";', response.get_data(as_text=True))

    def test_entity_page_exposes_topics_tag(self) -> None:
        response: Response = on_entity_get(self.app, self.user, "red fox", window=3)
        self.assertIn('window.topics_tag = "red fox";', response.get_data(as_text=True))

    def test_category_page_has_unfiltered_topics(self) -> None:
        self.app.feeds.get_by_category.return_value = [{"feed_id": "one"}]
        self.app.posts.get_by_category.return_value = []
        response: Response = on_category_get(self.app, self.user, Request.from_values(), "News")
        self.assertIn("window.topics_tag = null;", response.get_data(as_text=True))

    def test_returns_all_topics_of_listed_posts(self) -> None:
        self.app.posts.get_by_pids.return_value = [{"pid": 1}, {"pid": 2}]
        response: Response = self._post({"post_ids": [1, 2]})
        self.assertEqual(response.status_code, 200)
        names: list[str] = [t["name"] for t in response.get_json()["data"]["topics"]]
        self.assertEqual(names, ["Pets>Cats", "Pets>Dogs", "Weather"])
        self.assertEqual(self.app.posts.get_by_pids.call_args.args[:2], ("owner", [1, 2]))

    def test_tag_filters_topics_by_surface_forms(self) -> None:
        self.app.posts.get_by_pids.return_value = [{"pid": 1}, {"pid": 2}]
        self.app.tags.get_by_tag.return_value = {"words": ["cats"]}
        data: dict[str, Any] = self._post({"post_ids": [1, 2], "tag": "cat"}).get_json()["data"]
        self.assertEqual([t["name"] for t in data["topics"]], ["Pets>Cats"])
        self.assertIn("cats", data["tag_words"])

    def test_rejects_bad_body(self) -> None:
        self.assertEqual(self._post({"post_ids": "1"}).status_code, 400)

    def test_empty_post_ids_skip_db(self) -> None:
        response: Response = self._post({"post_ids": []})
        self.assertEqual(response.get_json()["data"]["topics"], [])
        self.app.posts.get_by_pids.assert_not_called()

    def test_build_failure_returns_500(self) -> None:
        self.app.posts.get_by_pids.side_effect = RuntimeError("db down")
        self.assertEqual(self._post({"post_ids": [1]}).status_code, 500)


class TestFilterTopicsByTag(unittest.TestCase):
    def test_keeps_only_mentioning_posts_and_recounts(self) -> None:
        import re

        topics: list[dict[str, Any]] = [{
            "name": "Mixed", "posts_count": 2, "sentences_count": 2,
            "sentences": ["Red fox ran.", "Blue bird."],
            "sources": [_source("1", "Red fox ran."), _source("2", "Blue bird.")],
        }]
        patterns = [re.compile(r"(?<!\w)red(?!\w)", re.I), re.compile(r"(?<!\w)fox(?!\w)", re.I)]
        result: list[dict[str, Any]] = _filter_topics_by_tag(topics, patterns)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["posts_count"], 1)
        self.assertEqual(result[0]["sentences"], ["Red fox ran."])

    def test_word_boundaries(self) -> None:
        import re

        topics: list[dict[str, Any]] = [{
            "name": "Taxonomy", "posts_count": 1, "sentences_count": 1,
            "sentences": ["Category theory."], "sources": [_source("1", "Category theory.")],
        }]
        self.assertEqual(_filter_topics_by_tag(topics, [re.compile(r"(?<!\w)cat(?!\w)", re.I)]), [])


if __name__ == "__main__":
    unittest.main()
