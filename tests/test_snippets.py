from typing import Any
import unittest

from rsstag.snippets import merge_grouped_snippets, sanitize_snippet_html


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


if __name__ == "__main__":
    unittest.main()
