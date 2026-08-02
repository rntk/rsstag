"""Tests for the post grouping cache management handlers."""

import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

import rsstag.web.grouping_cache as handlers


def _request(path: str = "/post-grouping-cache", **kwargs: Any) -> Request:
    return Request(EnvironBuilder(path=path, **kwargs).get_environ())


class _FakeApp:
    def __init__(self) -> None:
        self.post_grouping_cache = MagicMock()
        self.post_grouping_cache.count_entries.return_value = 3
        self.post_grouping_cache.find_entries.return_value = []
        self.post_grouping_cache.summary.return_value = {"entries": 0}
        self.post_grouping_cache.delete_keys.return_value = 1
        self.post_grouping_cache.purge.return_value = 2
        self.template_env = MagicMock()
        self.template_env.get_template.return_value.render.return_value = "<html></html>"

    def get_page_count(self, items_count: int, on_page: int) -> int:
        return 1


class PostGroupingCacheHandlersTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _FakeApp()
        self.user: Dict[str, Any] = {"sid": "owner", "settings": {}, "provider": "rss"}

    def test_get_passes_filters_to_the_cache(self) -> None:
        request = _request(query_string="kind=chunk&sort=hits_per_day&order=desc&page=2")

        response = handlers.on_post_grouping_cache_get(self.app, self.user, request)

        self.assertEqual(response.status_code, 200)
        self.app.post_grouping_cache.find_entries.assert_called_once_with(
            "owner",
            kind="chunk",
            sort_by="hits_per_day",
            descending=True,
            skip=handlers.ENTRIES_ON_PAGE,
            limit=handlers.ENTRIES_ON_PAGE,
        )

    def test_get_falls_back_to_safe_defaults(self) -> None:
        request = _request(query_string="kind=evil&sort=$where&order=&page=-3")

        handlers.on_post_grouping_cache_get(self.app, self.user, request)

        self.app.post_grouping_cache.find_entries.assert_called_once_with(
            "owner",
            kind="",
            sort_by="hits",
            descending=False,
            skip=0,
            limit=handlers.ENTRIES_ON_PAGE,
        )

    def test_delete_removes_checked_keys(self) -> None:
        request = _request(
            path="/post-grouping-cache/delete",
            method="POST",
            data={"keys": ["aaa", "bbb"], "sort": "hits", "order": "asc"},
        )

        response = handlers.on_post_grouping_cache_delete_post(
            self.app, self.user, request
        )

        self.app.post_grouping_cache.delete_keys.assert_called_once_with(
            "owner", ["aaa", "bbb"]
        )
        self.assertEqual(response.status_code, 302)

    def test_purge_parses_thresholds(self) -> None:
        request = _request(
            path="/post-grouping-cache/purge",
            method="POST",
            data={"max_hits": "1", "older_than_days": "14", "kind": "document"},
        )

        handlers.on_post_grouping_cache_purge_post(self.app, self.user, request)

        self.app.post_grouping_cache.purge.assert_called_once_with(
            "owner", max_hits=1, older_than_days=14.0, kind="document"
        )

    def test_purge_ignores_broken_thresholds(self) -> None:
        request = _request(
            path="/post-grouping-cache/purge",
            method="POST",
            data={"max_hits": "abc", "older_than_days": "-5", "kind": "junk"},
        )

        handlers.on_post_grouping_cache_purge_post(self.app, self.user, request)

        self.app.post_grouping_cache.purge.assert_called_once_with(
            "owner", max_hits=0, older_than_days=0.0, kind=""
        )

    def test_cache_errors_do_not_break_the_page(self) -> None:
        self.app.post_grouping_cache.delete_keys.side_effect = RuntimeError("db down")
        request = _request(
            path="/post-grouping-cache/delete", method="POST", data={"keys": ["aaa"]}
        )

        response = handlers.on_post_grouping_cache_delete_post(
            self.app, self.user, request
        )

        self.assertEqual(response.status_code, 302)


class PostGroupingCacheTemplateTestCase(unittest.TestCase):
    """Render the real template so syntax errors surface in tests."""

    def test_template_renders_entries(self) -> None:
        import json
        import time

        from jinja2 import Environment, PackageLoader

        env = Environment(loader=PackageLoader("rsstag.web", "templates/default"))
        env.filters["json"] = lambda d: json.dumps(d, default=str)
        env.filters["timestamp_to_datetime"] = lambda ts: (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "N/A"
        )

        html: str = env.get_template("post-grouping-cache.html").render(
            entries=[
                {
                    "key": "a" * 64,
                    "kind": "document",
                    "model": "openai:gpt-5-mini",
                    "hits": 4,
                    "hits_per_day": 1.5,
                    "age_days": 2.5,
                    "last_hit_at": time.time(),
                    "value_size": 2048,
                }
            ],
            summary={
                "entries": 1,
                "hits": 4,
                "size": 2048,
                "document_entries": 1,
                "document_hits": 4,
                "chunk_entries": 0,
                "chunk_hits": 0,
                "unused_entries": 0,
            },
            total=1,
            page_number=1,
            pages_count=1,
            kind="",
            sort_by="hits",
            order="asc",
            sortable_fields=["hits", "hits_per_day"],
            user_settings={},
            provider="rss",
        )

        self.assertIn("openai:gpt-5-mini", html)
        self.assertIn("aaaaaaaaaaaaaaaa", html)
        self.assertIn("/post-grouping-cache/purge", html)


if __name__ == "__main__":
    unittest.main()
