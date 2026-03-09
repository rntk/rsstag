from typing import Any
import unittest

from rsstag.snippets import (
    build_expanded_snippet_context,
    merge_grouped_snippets,
    sanitize_snippet_html,
)


class TestSnippets(unittest.TestCase):
    def test_sanitize_snippet_html_preserves_safe_links(self) -> None:
        html_value: str = (
            '<p>Read <a href="https://example.com/x" onclick="evil()">more</a>.</p>'
        )

        sanitized: str = sanitize_snippet_html(html_value)

        self.assertIn('href="https://example.com/x"', sanitized)
        self.assertIn('target="_blank"', sanitized)
        self.assertIn('rel="noopener noreferrer nofollow"', sanitized)
        self.assertNotIn("onclick", sanitized)
        self.assertIn("<p>", sanitized)
        self.assertIn("</p>", sanitized)

    def test_sanitize_snippet_html_drops_script_and_unsafe_href(self) -> None:
        html_value: str = (
            '<script>alert(1)</script><a href="javascript:alert(1)">bad</a><b>ok</b>'
        )

        sanitized: str = sanitize_snippet_html(html_value)

        self.assertNotIn("script", sanitized)
        self.assertNotIn("javascript:", sanitized)
        self.assertNotIn("<a ", sanitized)
        self.assertEqual(sanitized, "bad<b>ok</b>")

    def test_merge_grouped_snippets_keeps_plain_text_and_html(self) -> None:
        raw_content: str = (
            '<p>Visit <a href="https://example.com">Example</a>.</p>'
            '<p>Next <strong>sentence</strong>.</p>'
        )
        sentences: list[dict[str, Any]] = [
            {
                "number": 1,
                "text": '<p>Visit <a href="https://example.com">Example</a>.</p>',
                "read": False,
            },
            {
                "number": 2,
                "text": '<p>Next <strong>sentence</strong>.</p>',
                "read": False,
            },
        ]
        groups: dict[str, list[int]] = {"Topic A": [1, 2]}

        merged: dict[str, list[dict[str, Any]]] = merge_grouped_snippets(
            raw_content,
            sentences,
            groups,
            {
                "post_id": "p1",
                "post_title": "Post",
                "url": "https://example.com/post",
            },
        )

        snippet: dict[str, Any] = merged["Topic A"][0]
        self.assertEqual(snippet["text"], "Visit Example . Next sentence .")
        self.assertIn('href="https://example.com"', snippet["html"])
        self.assertIn("<strong>sentence</strong>", snippet["html"])

    def test_build_expanded_snippet_context_grows_from_both_sides(self) -> None:
        raw_content: str = "One. Two. Three. Four. Five."
        sentences: list[dict[str, Any]] = [
            {"number": 1, "text": "One."},
            {"number": 2, "text": "Two."},
            {"number": 3, "text": "Three."},
            {"number": 4, "text": "Four."},
            {"number": 5, "text": "Five."},
        ]

        expanded: dict[str, Any] | None = build_expanded_snippet_context(
            raw_content,
            sentences,
            base_indices=[3],
            visible_indices=[3],
            step=1,
        )

        assert expanded is not None
        self.assertEqual(expanded["visible_indices"], [2, 3, 4])
        self.assertEqual(expanded["before"]["indices"], [2])
        self.assertEqual(expanded["base"]["indices"], [3])
        self.assertEqual(expanded["after"]["indices"], [4])
        self.assertEqual(expanded["before"]["text"], "Two.")
        self.assertEqual(expanded["base"]["text"], "Three.")
        self.assertEqual(expanded["after"]["text"], "Four.")
        self.assertTrue(expanded["can_extend_before"])
        self.assertTrue(expanded["can_extend_after"])

    def test_build_expanded_snippet_context_uses_ordered_neighbors_for_gapped_numbers(self) -> None:
        raw_content: str = "One. Three. Six."
        sentences: list[dict[str, Any]] = [
            {"number": 1, "text": "One."},
            {"number": 3, "text": "Three."},
            {"number": 6, "text": "Six."},
        ]

        expanded: dict[str, Any] | None = build_expanded_snippet_context(
            raw_content,
            sentences,
            base_indices=[3],
            visible_indices=[3],
            step=1,
        )

        assert expanded is not None
        self.assertEqual(expanded["visible_indices"], [1, 3, 6])
        self.assertEqual(expanded["before"]["indices"], [1])
        self.assertEqual(expanded["after"]["indices"], [6])
        self.assertFalse(expanded["can_extend_before"])
        self.assertFalse(expanded["can_extend_after"])


if __name__ == "__main__":
    unittest.main()
