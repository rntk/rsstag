"""Deterministic coloring tests with no database or external model dependency."""

import json
import math
import re
import unittest
from html import unescape
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import quote_plus

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from rsstag.surprise import LeaveOneOutSurprise
from rsstag.web.keywords import _extract_rake_keywords, _extract_yake_keywords
from rsstag.web.tag_concordance import _position_words
from rsstag.web.tag_insights import STOPWORDS
from rsstag.web.word_coloring import (
    COLORING_STRATEGIES,
    ColoringContext,
    ColoringStrategy,
    Highlight,
    Resolver,
    apply_coloring,
    keyword_scores,
    pmi_scores,
    surprise_scores,
    tfidf_scores,
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

    def test_pmi_formula_support_and_article_boundaries(self) -> None:
        scores: dict[str, dict[str, float]] = pmi_scores({
            "a": "alpha beta alpha beta", "b": "gamma delta gamma delta",
            "c": "alpha gamma", "empty": "Root the 42",
        }, "root")
        # Each repeated pair has four events per direction. Marginals for
        # alpha/gamma are five; beta/delta are four, out of eighteen events.
        self.assertEqual(scores["a"], {"alpha": 1.0, "beta": 1.0})
        self.assertEqual(scores["b"], {"gamma": 1.0, "delta": 1.0})
        self.assertEqual(scores["c"], {})
        self.assertEqual(scores["empty"], {})
        self.assertEqual(pmi_scores({"a": "alpha", "b": "beta"}, "root"), {"a": {}, "b": {}})
        self.assertEqual(pmi_scores({}, "root"), {})

    def test_pmi_uses_joint_and_marginal_event_probabilities(self) -> None:
        scores: dict[str, dict[str, float]] = pmi_scores({
            "a": "alpha beta alpha beta", "b": "gamma delta gamma delta",
            "c": "alpha gamma alpha gamma",
        }, "root")
        # 24 directed events: alpha/gamma have eight, beta/delta four.
        strongest: float = math.log2(4 * 24 / (8 * 4))
        bridge: float = math.log2(4 * 24 / (8 * 8))
        self.assertAlmostEqual(scores["c"]["alpha"], bridge / strongest)
        self.assertAlmostEqual(scores["c"]["gamma"], bridge / strongest)
        self.assertEqual(scores["a"]["beta"], 1.0)

    def test_keywords_reuse_endpoint_phrase_scores(self) -> None:
        for extractor in (_extract_rake_keywords, _extract_yake_keywords):
            with self.subTest(extractor=extractor.__name__):
                scores: dict[str, dict[str, float]] = keyword_scores(
                    {"a": "Root alpha beta and gamma", "b": "THE 42 Root"}, "root", extractor,
                )
                expected: dict[str, float] = {}
                for item in extractor(["root alpha beta and gamma"], set(STOPWORDS) | {"root"}, 15):
                    for word in item.phrase.split():
                        expected[word] = max(expected.get(word, 0.0), item.score)
                maximum: float = max(expected.values())
                self.assertEqual(scores["a"], {word: score / maximum for word, score in expected.items()})
                self.assertEqual(scores["b"], {})
                self.assertEqual(keyword_scores({}, "root", extractor), {})

    def test_surprise_matches_endpoint_calculation_and_ignores_article_order(self) -> None:
        documents: dict[str, str] = {
            "a": "Root alpha beta", "b": "Root alpha beta", "c": "Root alpha gamma",
        }
        raw: dict[str, float] = LeaveOneOutSurprise().compute([
            ["alpha", "beta"], ["alpha", "beta"], ["alpha", "gamma"],
        ])
        maximum: float = max(raw.values())
        scores: dict[str, dict[str, float]] = surprise_scores(documents, "root")
        self.assertEqual(scores["a"], {word: raw[word] / maximum for word in ("alpha", "beta") if raw[word] > 0})
        self.assertNotIn("gamma", scores["c"])
        self.assertEqual(scores, surprise_scores(dict(reversed(list(documents.items()))), "root"))
        self.assertEqual(surprise_scores({"a": "alpha beta"}, "root"), {"a": {}})
        self.assertEqual(surprise_scores({}, "root"), {})

    def test_keyword_phrases_stop_at_punctuation_and_short_stopwords(self) -> None:
        for boundary in (".", ",", ";", "!", "?", "\n", " a ", " и ", " 42 "):
            with self.subTest(boundary=boundary):
                scores: dict[str, dict[str, float]] = keyword_scores(
                    {"a": f"alpha beta{boundary}gamma"}, "root", _extract_rake_keywords,
                )
                # A two-word phrase scores 4; the separate singleton scores 1.
                self.assertEqual(scores["a"], {"alpha": 1.0, "beta": 1.0, "gamma": 0.25})

    def test_keyword_extractors_never_receive_cross_sentence_phrases(self) -> None:
        for extractor in (_extract_rake_keywords, _extract_yake_keywords):
            with self.subTest(extractor=extractor.__name__):
                with patch("rsstag.web.word_coloring._normalize", side_effect=lambda scores: scores):
                    separated: dict[str, dict[str, float]] = keyword_scores(
                        {"a": "alpha beta. gamma delta"}, "root", extractor,
                    )
                    stopped: dict[str, dict[str, float]] = keyword_scores(
                        {"a": "alpha beta and gamma delta"}, "root", extractor,
                    )
                # A punctuation marker is treated just like a retained stopword,
                # without turning sentences into separate YAKE-style documents.
                self.assertEqual(separated, stopped)

    def test_log_odds_coloring_carries_support_and_ignores_duplicate_rows(self) -> None:
        rows: list[dict[str, Any]] = [
            {"pid": "a", "before_words": _position_words("RECALLS!", True), "after_words": []}
            for _ in range(3)
        ]
        context: ColoringContext = ColoringContext("root", {
            "a": "Root recalls and the and the and ordinary ordinary ordinary",
            "b": "Root recall and the and the and ordinary ordinary ordinary",
        }, None)
        options: list[dict[str, Any]] = apply_coloring(rows, context)
        expected: dict[str, Any] = rows[0]["before_words"][-1]["colorings"]["log_odds"]
        self.assertEqual(expected["color"], "log_odds")
        self.assertEqual(expected["support"], 2)
        self.assertEqual(expected["score"], 1.0)
        self.assertGreater(expected["z_score"], 0.0)
        for row in rows:
            self.assertEqual(row["before_words"][-1]["colorings"]["log_odds"], expected)
        self.assertIn("YAKE-style", [option["label"] for option in options])

    def test_new_modes_handle_inflections_and_missing_insights(self) -> None:
        rows: list[dict[str, Any]] = [{
            "pid": "a", "before_words": _position_words("RECALLS! and 123 Root", True),
            "after_words": [],
        }]
        options: list[dict[str, Any]] = apply_coloring(rows, ColoringContext("root", {
            "a": "Root recall recalls alpha alpha", "b": "Root recall alpha", "c": "Root recall beta",
        }, None))
        self.assertEqual(len(options), 8)
        word: dict[str, Any] = rows[0]["before_words"][-4]
        for key in ("pmi", "rake", "yake", "surprise"):
            with self.subTest(mode=key):
                self.assertIsNotNone(word["colorings"][key])
                self.assertGreater(word["colorings"][key]["score"], 0)
                self.assertLessEqual(word["colorings"][key]["score"], 1)
                self.assertEqual(word["colorings"][key]["color"], key)
                for excluded in rows[0]["before_words"][-3:]:
                    self.assertIsNone(excluded["colorings"][key])

    def test_pipeline_preserves_default_and_attaches_per_article_scores(self) -> None:
        rows: list[dict[str, Any]] = [
            {"pid": pid, "before_words": _position_words("RECALLS! ordinary", True),
             "after_words": _position_words("rare", False)} for pid in ("a", "a", "b")
        ]
        context: ColoringContext = ColoringContext("root", {
            "a": "Root recall recalls ordinary rare", "b": "Root ordinary ordinary rare recall",
        }, {"left": [{"lemma": "recal", "words": ["recalls"]}]})
        options: list[dict[str, Any]] = apply_coloring(rows, context)
        self.assertEqual([option["key"] for option in options], ["important", "tfidf", "pmi", "rake", "yake", "surprise", "log_odds", "none"])
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
        for mode in ("tfidf", "pmi", "rake", "yake", "surprise", "log_odds"):
            self.assertIn(f'value="{mode}"', html)
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
        self.assertEqual([option["key"] for option in options], ["important", "tfidf", "pmi", "rake", "yake", "surprise", "log_odds", "none"])


if __name__ == "__main__":
    unittest.main()
