"""Deterministic coloring tests with no database or external model dependency."""

import json
import math
import re
from html import unescape
from pathlib import Path
from urllib.parse import quote_plus

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader
import unittest
from typing import Any
from unittest.mock import patch

from rsstag.web.tag_concordance import _position_words
from rsstag.web.word_coloring import (
    COLORING_STRATEGIES, ColoringContext, ColoringStrategy, Highlight, Resolver,
    apply_coloring, tfidf_scores,
)


class TestWordColoring(unittest.TestCase):
    def test_tfidf_formula_and_maximum_normalization(self) -> None:
        scores: dict[str, dict[str, float]] = tfidf_scores({
            "a": "Root common rare rare", "b": "Root common other",
        }, "root")
        maximum: float = (1 + math.log(2)) * (1 + math.log(3 / 2))
        self.assertAlmostEqual(scores["a"]["rare"], 1.0)
        self.assertAlmostEqual(scores["a"]["common"], 1 / maximum)
        self.assertAlmostEqual(scores["b"]["common"], 1 / (1 + math.log(3 / 2)))
        self.assertTrue(all(0 < value <= 1 for document in scores.values() for value in document.values()))

    def test_stopwords_numbers_tag_and_inflections(self) -> None:
        scores: dict[str, dict[str, float]] = tfidf_scores({
            "a": "THE and 123 markets MARKET recalls recall машины машина и в",
        }, "market")
        self.assertEqual(set(scores["a"]), {"recal", "машин"})
        self.assertEqual(scores["a"]["recal"], 1.0)
        self.assertEqual(scores["a"]["машин"], 1.0)

    def test_empty_and_single_document_corpora(self) -> None:
        self.assertEqual(tfidf_scores({}, "root"), {})
        self.assertEqual(tfidf_scores({"a": "Root the 42", "b": ""}, "root"), {"a": {}, "b": {}})
        self.assertEqual(tfidf_scores({"a": "Root rare"}, "root"), {"a": {"rare": 1.0}})

    def test_pipeline_preserves_default_and_attaches_per_article_scores(self) -> None:
        rows: list[dict[str, Any]] = [
            {"pid": pid, "before_words": _position_words("RECALLS! ordinary", True),
             "after_words": _position_words("rare", False)} for pid in ("a", "a", "b")
        ]
        context: ColoringContext = ColoringContext("root", {
            "a": "Root recall recalls ordinary rare", "b": "Root ordinary ordinary rare recall",
        }, {"left": [{"lemma": "recal", "words": ["recalls"]}]})
        options: list[dict[str, Any]] = apply_coloring(rows, context)
        self.assertEqual([option["key"] for option in options], ["important", "tfidf", "none"])
        self.assertEqual(options[1]["threshold"], 0.8)
        word: dict[str, Any] = rows[0]["before_words"][-2]
        self.assertEqual(word["text"], "RECALLS!")
        self.assertEqual(word["color"], "before")
        self.assertEqual(word["colorings"]["important"], {"color": "before", "score": 1.0})
        self.assertIsNone(word["colorings"]["none"])
        self.assertEqual(word["colorings"]["tfidf"]["score"], 1.0)
        self.assertEqual(word["colorings"], rows[1]["before_words"][-2]["colorings"])
        self.assertLess(rows[2]["before_words"][-2]["colorings"]["tfidf"]["score"], 0.8)
        self.assertTrue(all(result is None for result in rows[0]["before_words"][0]["colorings"].values()))

    def test_tfidf_works_without_insights(self) -> None:
        rows: list[dict[str, Any]] = [{"pid": "a", "before_words": _position_words("Rare!", True), "after_words": []}]
        apply_coloring(rows, ColoringContext("root", {"a": "Root rare"}, None))
        self.assertIsNone(rows[0]["before_words"][-1]["color"])
        self.assertEqual(rows[0]["before_words"][-1]["colorings"]["tfidf"], {"color": "tfidf", "score": 1.0})

    def test_template_renders_registry_options_and_safe_word_data(self) -> None:
        directory: Path = Path(__file__).resolve().parents[1] / "rsstag/web/templates/default"
        environment: Environment = Environment(loader=ChoiceLoader([
            DictLoader({"head-data.html": "", "site-header.html": "{% macro site_header(active, show_context_filter) %}{% endmacro %}"}),
            FileSystemLoader(str(directory)),
        ]))
        environment.filters["url_encode"] = quote_plus
        row: dict[str, Any] = {"pid": "a", "before_words": _position_words("Rare", True),
                               "after_words": _position_words("", False), "match": "Root", "duplicate_of": None}
        options: list[dict[str, Any]] = apply_coloring([row], ColoringContext("root", {"a": "Root rare"}, None))
        # JSON contains characters that could otherwise break an HTML attribute.
        row["before_words"][-1]["colorings"]["experiment"] = {"color": "' ><script>", "score": 1.0}
        html: str = environment.get_template("tag-context-wall.html").render(
            tag="root", rows=[row], article_count=1, user_settings={}, page_number=1, has_more=False,
            coloring_options=options,
        )
        self.assertIn('id="wall-coloring-mode"', html)
        self.assertIn('value="tfidf"', html)
        self.assertIn('data-threshold="0.8"', html)
        self.assertIn('aria-describedby="wall-coloring-description"', html)
        self.assertNotIn("<script>", html)
        results: list[dict[str, Any]] = [json.loads(unescape(value)) for value in re.findall(r"data-colorings='([^']*)'", html)]
        self.assertEqual(len(results), 40)
        self.assertEqual(results[19]["tfidf"], {"color": "tfidf", "score": 1.0})

    def test_registry_extension_needs_no_template_changes(self) -> None:
        def prepare(context: ColoringContext) -> Resolver:
            def resolve(row: dict[str, Any], side: str, text: str) -> Highlight | None:
                return {"color": "after", "score": 0.9} if text else None
            return resolve

        custom: ColoringStrategy = ColoringStrategy("custom", "Custom", "Experimental", prepare, 0.85)
        rows: list[dict[str, Any]] = [{"before_words": [{"text": "hello"}], "after_words": []}]
        with patch("rsstag.web.word_coloring.COLORING_STRATEGIES", (custom,)):
            options: list[dict[str, Any]] = apply_coloring(rows, ColoringContext("root", {}, None))
        self.assertEqual(options[0]["key"], "custom")
        self.assertEqual(rows[0]["before_words"][0]["colorings"]["custom"]["score"], 0.9)

    def test_strategy_failure_does_not_break_other_modes(self) -> None:
        def fail(context: ColoringContext) -> Resolver:
            raise RuntimeError("unavailable")

        broken: ColoringStrategy = ColoringStrategy("broken", "Broken", "Unavailable", fail)
        with patch("rsstag.web.word_coloring.COLORING_STRATEGIES", (broken, *COLORING_STRATEGIES)), \
                self.assertLogs("rsstag.web.word_coloring", level="ERROR"):
            options: list[dict[str, Any]] = apply_coloring([], ColoringContext("root", {}, None))
        self.assertEqual([option["key"] for option in options], ["important", "tfidf", "none"])


if __name__ == "__main__":
    unittest.main()
