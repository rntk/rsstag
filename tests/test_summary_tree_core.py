"""Pure summary-tree logic: filters, response decoding and excerpts."""

import gzip
import unittest
from typing import Any, Dict, List, Optional

from rsstag.summary_tree import filters as doc_filters
from rsstag.summary_tree.parsers import extract_object
from rsstag.summary_tree.model import evidence_rows
from rsstag.summary_tree.sources import SourcePost


class TestFilters(unittest.TestCase):
    def test_normalize_drops_unknown_and_empty(self) -> None:
        self.assertEqual(
            doc_filters.normalize_filters(
                {"entity": "  new   york ", "tags": ["b", "", "a", "b"], "feed_ids": [],
                 "only_unread": "0", "topic": "x"}
            ),
            {"entity": "new york", "tags": ["a", "b"]},
        )

    def test_hash_is_order_insensitive(self) -> None:
        options: Dict[str, Any] = doc_filters.normalize_options({})
        first = doc_filters.normalize_filters({"entity": "x", "tags": ["a", "b"]})
        second = doc_filters.normalize_filters({"tags": ["b", "a"], "entity": "x"})
        self.assertEqual(doc_filters.filters_hash(first, options), doc_filters.filters_hash(second, options))

    def test_options_are_bounded(self) -> None:
        self.assertEqual(doc_filters.normalize_options({"limit": "9999", "window": "x"}),
                         {"window": doc_filters.DEFAULT_WINDOW, "limit": doc_filters.MAX_LIMIT})

    def test_build_query_ands_fragments(self) -> None:
        query = doc_filters.build_query(None, "u", {"entity": "new york", "feed_ids": ["f1"], "only_unread": True})  # type: ignore[arg-type]
        self.assertEqual(query["owner"], "u")
        self.assertIn({"tags": {"$all": ["new", "york"]}}, query["$and"])
        self.assertIn({"feed_id": {"$in": ["f1"]}}, query["$and"])
        self.assertIn({"read": False}, query["$and"])

    def test_window_predicate(self) -> None:
        lemmas: bytes = gzip.compress("new a b c york".encode("utf-8"))
        post: Dict[str, Any] = {"lemmas": lemmas}
        self.assertTrue(doc_filters.matches_predicates(post, {"entity": "new york"}, {"window": 4}))
        self.assertFalse(doc_filters.matches_predicates(post, {"entity": "new york"}, {"window": 3}))
        self.assertTrue(doc_filters.matches_predicates({}, {"entity": "single"}, {"window": 1}))

    def test_words_within_window_uses_closest_occurrences(self) -> None:
        self.assertTrue(doc_filters.words_within_window("a x x x x b a".split(), ["a", "b"], 1))


class TestParsers(unittest.TestCase):
    def test_braces_inside_strings(self) -> None:
        self.assertEqual(extract_object('```json\n{"text":"a } and { b"}\n```'), {"text": "a } and { b"})


class TestEvidenceRows(unittest.TestCase):
    def test_numbered_title_and_complete_text(self) -> None:
        post: SourcePost = SourcePost("p", "Title", "First fact. Last fact.", "f", "", 0)
        self.assertEqual(evidence_rows(post), ["Title", "First fact.", "Last fact."])

    def test_overlong_title_and_unbroken_text_are_bounded(self) -> None:
        post: SourcePost = SourcePost("p", "T" * 9000, "X" * 10000, "f", "", 0)
        rows: List[str] = evidence_rows(post)
        self.assertTrue(all(len(row) <= 800 for row in rows))
        self.assertEqual("".join(rows), post.title + post.text)


if __name__ == "__main__":
    unittest.main()
