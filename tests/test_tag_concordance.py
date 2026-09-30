"""Concordance behavior checks without a database service."""

import gzip
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch
from urllib.parse import quote_plus

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader
from werkzeug.wrappers import Request, Response

from rsstag.web.routes import RSSTagRoutes
from rsstag.web.tag_concordance import _contexts, _detail_data, _position_words, _rows, _sentence_documents, on_tag_concordance_get, on_tag_context_wall_get


class TestTagConcordance(unittest.TestCase):
    def setUp(self) -> None:
        self.user: dict[str, Any] = {"sid": "owner", "settings": {"only_unread": False, "posts_on_page": 2}}

    def test_late_occurrence_has_twenty_words_on_each_side(self) -> None:
        text: str = " ".join([f"before{i}" for i in range(90)] + ["Root,"] + [f"after{i}" for i in range(30)])
        rows: list[dict[str, str]] = list(_contexts(text, "root"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["match"], "Root")
        self.assertEqual(re.findall(r"\w+", rows[0]["before"]), [f"before{i}" for i in range(70, 90)])
        self.assertEqual(re.findall(r"\w+", rows[0]["after"]), [f"after{i}" for i in range(20)])
        self.assertTrue(rows[0]["before"].startswith("… "))
        self.assertTrue(rows[0]["after"].startswith(","))
        self.assertTrue(rows[0]["after"].endswith(" …"))

    def test_wall_positions_count_outward_and_preserve_punctuation(self) -> None:
        before: list[dict[str, Any]] = _position_words("… Hello, nearby", before=True)
        after: list[dict[str, Any]] = _position_words(", next word! …", before=False)
        self.assertEqual(len(before), 20)
        self.assertEqual(before[-2:], [{"text": "… Hello,", "position": 2}, {"text": "nearby", "position": 1}])
        self.assertEqual(after[:2], [{"text": ", next", "position": 1}, {"text": "word! …", "position": 2}])
        self.assertTrue(all(not word["text"] for word in before[:-2] + after[2:]))
        self.assertEqual(_position_words("!", before=False)[0]["text"], "!")

    def test_original_spelling_punctuation_stems_and_whole_phrases(self) -> None:
        cases: list[tuple[str, str, list[str]]] = [
            ("A PARTY won.", "parti", ["PARTY"]),
            ("Running quickly.", "run", ["Running"]),
            ("Новости о машинах.", "машин", ["машинах"]),
            ("Earth and cartoons.", "art", []),
            ("<a href='/root'>Other</a> <b>Root</b> news.", "root", ["Root"]),
            ("Artificial intelligence; artificial other intelligence.", "artifici intellig", ["Artificial intelligence"]),
            ("Root, root! ROOT?", "root", ["Root", "root", "ROOT"]),
            ("Nothing here.", "", []),
        ]
        for text, tag, expected in cases:
            with self.subTest(text=text, tag=tag):
                self.assertEqual([row["match"] for row in _contexts(text, tag)], expected)

    def test_topics_and_metadata_belong_to_each_sentence_and_article(self) -> None:
        posts: list[dict[str, Any]] = [
            {"pid": pid, "content": {"title": pid}, "metadata": {"source": f"Source {pid}"}}
            for pid in ("first", "second")
        ]
        documents: dict[str, dict[str, Any]] = {
            "first": {"sentences": [{"number": 1, "text": "Root one."}, {"number": 2, "text": "Root two."}],
                      "groups": {"Tech > AI": [1], "News": [2]}},
            "second": {"sentences": [{"number": 1, "text": "Root three."}], "groups": {"Other": [1]}},
        }
        rows: list[dict[str, Any]] = list(_rows(posts, documents, "root", None))
        self.assertEqual([row["topics"] for row in rows], [["Tech > AI"], ["News"], ["Other"]])
        self.assertEqual([row["metadata"]["source"] for row in rows], ["Source first", "Source first", "Source second"])
        self.assertEqual([row["url"] for row in rows], ["/posts/first", "/posts/first", "/posts/second"])

    def test_ambiguous_multi_article_grouping_is_not_attributed(self) -> None:
        grouping: Mock = Mock()
        grouping.get_by_post_ids.return_value = [
            {"post_ids": ["one", "two"], "groups": {"Wrong": [1]}},
            {"post_ids": ["outside"], "groups": {"Wrong": [1]}},
            {"post_ids": ["one"], "groups": {"Right": [1]}},
        ]
        result: dict[str, dict[str, Any]] = _sentence_documents(
            SimpleNamespace(post_grouping=grouping), self.user, [{"pid": "one"}, {"pid": "two"}],
        )
        self.assertEqual(result, {"one": {"post_ids": ["one"], "groups": {"Right": [1]}}})
        self.assertEqual(grouping.get_by_post_ids.call_args.args, ("owner", ["one", "two"]))

    def test_details_include_all_topic_sentences_even_read_nonmatches(self) -> None:
        posts: list[dict[str, Any]] = [{"pid": "one"}, {"pid": "two"}]
        documents: dict[str, dict[str, Any]] = {
            "one": {"sentences": [
                {"number": 1, "text": "Root root."},
                {"number": 2, "text": "<b>Full context.</b>", "read": True},
                {"number": 3, "text": "Unrelated."},
            ], "groups": {"Topic": [1, 2], "Second topic": [1, 3]}},
            "two": {"sentences": [{"number": 2, "text": "Other article."}], "groups": {"Topic": [2]}},
        }
        rows: list[dict[str, Any]] = list(_rows(posts, documents, "root", True))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["detail_key"], rows[1]["detail_key"])
        details: dict[str, Any] = _detail_data(posts, documents, rows)
        self.assertEqual(set(details["posts"]), {"one"})
        self.assertEqual(details["posts"]["one"]["sentences"][:2], [
            {"number": 1, "text": "Root root.", "read": False},
            {"number": 2, "text": "Full context.", "read": True},
        ])
        self.assertEqual(details["posts"]["one"]["groups"]["Second topic"], [1, 3])
        self.assertEqual(details["entries"][rows[0]["detail_key"]]["topics"], ["Second topic", "Topic"])
        self.assertNotIn("sections", rows[0])

    def test_shared_topic_text_is_serialized_once_per_post(self) -> None:
        posts: list[dict[str, Any]] = [{"pid": "one"}]
        sentences: list[dict[str, Any]] = [
            {"number": index, "text": f"Root sentence unique_{index}."} for index in range(300)
        ]
        documents: dict[str, dict[str, Any]] = {"one": {
            "sentences": sentences, "groups": {"Large topic": list(range(300))},
        }}
        rows: list[dict[str, Any]] = list(_rows(posts, documents, "root", None))
        details: dict[str, Any] = _detail_data(posts, documents, rows)
        serialized: str = json.dumps(details)
        self.assertEqual(len(details["entries"]), 300)
        self.assertEqual(serialized.count('"text":'), 300)
        self.assertEqual(serialized.count('"groups":'), 1)
        self.assertTrue(all("sections" not in row for row in rows))

    def test_detail_indices_preserve_read_sentences_and_fallback_text(self) -> None:
        posts: list[dict[str, Any]] = [
            {"pid": "grouped"},
            {"pid": "fallback", "content": {"content": gzip.compress(b"Opening. Root full fallback.")}},
        ]
        documents: dict[str, dict[str, Any]] = {"grouped": {"sentences": [
            {"number": 5, "text": "Read first.", "read": True},
            {"number": 7, "text": "Root without topic."},
        ]}}
        rows: list[dict[str, Any]] = list(_rows(posts, documents, "root", True))
        details: dict[str, Any] = _detail_data(posts, documents, rows)
        for row in rows:
            entry: dict[str, Any] = details["entries"][row["detail_key"]]
            sentence: dict[str, Any] = details["posts"][row["pid"]]["sentences"][entry["sentence_index"]]
            self.assertEqual(sentence["number"], row["number"])
            self.assertIn("Root", sentence["text"])
            self.assertEqual(entry["topics"], [])

    def test_unread_filter_never_falls_back_to_read_sentences(self) -> None:
        posts: list[dict[str, Any]] = [{"pid": "one", "content": {"content": gzip.compress(b"Root read.")}}]
        documents: dict[str, dict[str, Any]] = {"one": {"sentences": [
            {"number": 1, "text": "Root read.", "read": True},
            {"number": 2, "text": "Root unread.", "read": False},
        ]}}
        self.assertEqual([row["number"] for row in _rows(posts, documents, "root", True)], [2])
        documents["one"]["sentences"][1]["read"] = True
        self.assertEqual(list(_rows(posts, documents, "root", True)), [])
        self.assertEqual(len(list(_rows(posts, documents, "root", None))), 2)

    def test_ungrouped_text_fallback_has_no_invented_topics(self) -> None:
        posts: list[dict[str, Any]] = [{"pid": "one", "content": {"content": gzip.compress(b"Opening. <b>Root</b> news. Closing.")}}]
        rows: list[dict[str, Any]] = list(_rows(posts, {"one": {"groups": {"Other": [1]}}}, "root", None))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["match"], "Root")
        self.assertEqual(rows[0]["after"], "news.")
        self.assertIsNone(rows[0]["number"])
        self.assertEqual(rows[0]["topics"], [])

    def test_handler_paginates_article_bodies_and_scopes_queries(self) -> None:
        posts: Mock = Mock()
        posts.get_by_tags.return_value = iter({"pid": index} for index in range(6))
        posts.get_by_pids.return_value = [
            {"pid": index, "feed_id": "feed", "content": {"content": gzip.compress(b"Root news.")}}
            for index in (2, 3)
        ]
        feeds: Mock = Mock()
        feeds.get_by_feed_ids.return_value = [{"feed_id": "feed", "title": "Source", "provider": "rss"}]
        grouping: Mock = Mock()
        grouping.get_by_post_ids.return_value = []
        environment: Mock = Mock()
        environment.get_template.return_value.render.return_value = "page"
        app: Any = SimpleNamespace(posts=posts, feeds=feeds, post_grouping=grouping, template_env=environment)
        self.user["settings"]["only_unread"] = True
        with patch("rsstag.web.tag_concordance._get_context_tags", return_value=["context"]):
            response: Response = on_tag_concordance_get(app, self.user, Request.from_values("/tag-concordance/root?page=2"), "root")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(posts.get_by_tags.call_args.args[:3], ("owner", ["root"], True))
        self.assertEqual(posts.get_by_tags.call_args.kwargs["context_tags"], ["context"])
        self.assertEqual(posts.get_by_pids.call_args.args, ("owner", [2, 3]))
        self.assertEqual(grouping.get_by_post_ids.call_args.args, ("owner", ["2", "3"]))
        self.assertEqual(feeds.get_by_feed_ids.call_args.args, ("owner", ["feed"]))
        rendered: dict[str, Any] = environment.get_template.return_value.render.call_args.kwargs
        self.assertEqual(rendered["page_number"], 2)
        self.assertEqual(rendered["article_count"], 2)
        self.assertTrue(rendered["has_more"])
        self.assertEqual([row["metadata"]["source"] for row in rendered["rows"]], ["Source", "Source"])
        posts.get_by_tags.return_value = iter([{"pid": 2}, {"pid": 3}])
        response = on_tag_context_wall_get(app, self.user, Request.from_values(), "root")
        self.assertEqual(response.status_code, 200)
        environment.get_template.assert_called_with("tag-context-wall.html")
        rendered = environment.get_template.return_value.render.call_args.kwargs
        self.assertEqual(len(rendered["rows"][0]["before_words"]), 20)
        self.assertEqual(rendered["rows"][0]["after_words"][0]["text"], "news.")
        self.assertEqual(rendered["details"]["posts"]["2"]["metadata"]["source"], "Source")

    def test_handler_rejects_invalid_pages_and_handles_storage_failure(self) -> None:
        for page in ("0", "-1", "abc", "10001"):
            with self.subTest(page=page):
                response: Response = on_tag_concordance_get(SimpleNamespace(), self.user, Request.from_values(query_string={"page": page}), "root")
                self.assertEqual(response.status_code, 400)
        posts: Mock = Mock()
        posts.get_by_tags.side_effect = RuntimeError("private database details")
        with self.assertLogs("rsstag.web.tag_concordance", level="ERROR"):
            response = on_tag_concordance_get(SimpleNamespace(posts=posts), self.user, Request.from_values(), "root")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private", response.get_data(as_text=True))

    def test_route_resolves_phrase_tag(self) -> None:
        routes: RSSTagRoutes = RSSTagRoutes("localhost")
        request: Request = Request.from_values("/tag-concordance/artificial%20intelligence")
        endpoint: str
        values: dict[str, str]
        endpoint, values = routes.bind_to_environ(request.environ).match()
        self.assertEqual(endpoint, "on_tag_concordance_get")
        self.assertEqual(values, {"tag": "artificial intelligence"})
        endpoint, values = routes.bind_to_environ(Request.from_values(
            "/tag-context-wall/artificial%20intelligence").environ).match()
        self.assertEqual(endpoint, "on_tag_context_wall_get")
        self.assertEqual(values, {"tag": "artificial intelligence"})

    def test_template_escapes_article_and_topic_text(self) -> None:
        directory: Path = Path(__file__).resolve().parents[1] / "rsstag/web/templates/default"
        environment: Environment = Environment(loader=ChoiceLoader([
            DictLoader({"head-data.html": "", "site-header.html": "{% macro site_header(active, show_context_filter) %}{% endmacro %}"}),
            FileSystemLoader(str(directory)),
        ]))
        environment.filters["url_encode"] = quote_plus
        payload: str = '<img src=x onerror="alert(1)">'
        row: dict[str, Any] = {"before": payload, "after": payload, "match": payload, "title": payload,
                               "url": "/posts/one", "number": 1, "topics": [payload],
                               "metadata": {"source": payload, "provider": payload, "category": payload}}
        html: str = environment.get_template("tag-concordance.html").render(
            tag=payload, rows=[row], article_count=1, user_settings={}, page_number=1, has_more=False,
        )
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)
        self.assertNotIn("?page=2", html)
        buttons: list[str] = re.findall(r'<button[^>]*class="tag-concordance__context[^>]*>', html)
        self.assertEqual(len(buttons), 2)
        self.assertTrue(all('aria-label=' not in button for button in buttons))
        phrase_html: str = environment.get_template("tag-concordance.html").render(
            tag="artificial intelligence", rows=[], article_count=0, user_settings={}, page_number=1, has_more=False,
        )
        self.assertIn('/tag-explorer/artificial%20intelligence', phrase_html)
        row["before_words"] = _position_words(payload, before=True)
        row["after_words"] = _position_words(payload, before=False)
        wall_html: str = environment.get_template("tag-context-wall.html").render(
            tag=payload, rows=[row], article_count=1, user_settings={}, page_number=2, has_more=True,
        )
        self.assertNotIn("<img", wall_html)
        self.assertEqual(wall_html.count('class="tag-context-wall__word '), 40)
        self.assertIn('aria-haspopup="dialog"', wall_html)
        self.assertIn('?page=3', wall_html)
        row["before_words"] = _position_words("Hello nearby", before=True)
        row["after_words"] = _position_words("next words here.", before=False)
        wall_html = environment.get_template("tag-context-wall.html").render(
            tag="root", rows=[row], article_count=1, user_settings={}, page_number=1, has_more=False,
        )
        contexts: list[str] = re.findall(
            r'<span class="tag-context-wall__context[^\"]*">(.*?)</span>\s*(?:<strong|</button>)',
            wall_html, flags=re.DOTALL,
        )
        self.assertEqual([re.sub(r"<[^>]+>", "", context).strip() for context in contexts],
                         ["Hello nearby", "next words here."])


if __name__ == "__main__":
    unittest.main()
