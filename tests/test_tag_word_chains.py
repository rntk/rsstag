"""Word window extraction does not require a database."""

import unittest

from rsstag.web.posts import _tag_chain_windows


class TestTagWordChains(unittest.TestCase):
    def test_shared_parent_from_words_on_either_side(self) -> None:
        first: list[tuple[str, str]] = _tag_chain_windows(
            "codex CLI tool", "codex", ["codex"]
        )
        second: list[tuple[str, str]] = _tag_chain_windows(
            "CLI codex app", "codex", ["codex"]
        )
        self.assertEqual(first, [("codex > cli > tool", "codex CLI tool")])
        self.assertEqual(second, [("codex > cli > app", "CLI codex app")])

    def test_window_is_six_words_on_each_side(self) -> None:
        text: str = (
            "zero one two three four five six CODEX seven eight nine ten eleven twelve thirteen"
        )
        windows: list[tuple[str, str]] = _tag_chain_windows(text, "codex", ["codex"])
        self.assertEqual(
            windows[0][0],
            "codex > one > two > three > four > five > six > seven > eight > nine > ten > eleven > twelve",
        )
        self.assertEqual(
            windows[0][1],
            "…one two three four five six CODEX seven eight nine ten eleven twelve…",
        )

    def test_word_boundaries_variants_and_repeated_occurrences(self) -> None:
        windows: list[tuple[str, str]] = _tag_chain_windows(
            "codexish is unrelated", "codex", ["codex"]
        )
        self.assertEqual(windows, [])
        self.assertEqual(
            _tag_chain_windows("Running quickly", "run", ["run", "running"])[0][0],
            "run > quickly",
        )
        self.assertEqual(
            len(_tag_chain_windows("codex first codex second", "codex", ["codex"])), 2
        )

    def test_ngram_and_unicode(self) -> None:
        windows: list[tuple[str, str]] = _tag_chain_windows(
            "Use Machine Learning today", "machine learning", ["machine learning"]
        )
        self.assertEqual(windows[0][0], "machine learning > use > today")
        self.assertEqual(
            _tag_chain_windows("Привет кодекс мир", "кодекс", ["кодекс"])[0][0],
            "кодекс > привет > мир",
        )

    def test_snippet_is_bounded_for_long_tokens(self) -> None:
        text: str = "codex " + "a" * 1000
        self.assertLessEqual(
            len(_tag_chain_windows(text, "codex", ["codex"])[0][1]), 242
        )

    def test_bounded_preview_keeps_tag_visible_after_long_words(self) -> None:
        text: str = "a" * 1000 + " codex tool"
        self.assertIn("codex", _tag_chain_windows(text, "codex", ["codex"])[0][1])
