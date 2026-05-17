import unittest
from rsstag.html_utils import build_html_mapping


class TestBuildHtmlMapping(unittest.TestCase):
    def test_plain_text_no_html(self):
        text = "hello world"
        plain, mapping = build_html_mapping(text)
        self.assertEqual(plain, "hello world")
        # Mapping includes an extra trailing index
        self.assertEqual(mapping, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])

    def test_simple_tag(self):
        html = "<p>hello</p>"
        plain, mapping = build_html_mapping(html)
        self.assertEqual(plain, "hello")

    def test_block_tag_adds_newline(self):
        html = "<p>hello</p><p>world</p>"
        plain, mapping = build_html_mapping(html)
        self.assertEqual(plain, "hello\nworld")

    def test_inline_tag_ignored(self):
        html = "<span>hello</span>"
        plain, mapping = build_html_mapping(html)
        self.assertEqual(plain, "hello")

    def test_html_entities(self):
        html = "hello&nbsp;world"
        plain, mapping = build_html_mapping(html)
        self.assertEqual(plain, "hello world")

    def test_multiple_spaces_collapsed(self):
        html = "hello   world"
        plain, mapping = build_html_mapping(html)
        self.assertEqual(plain, "hello world")

    def test_empty_string(self):
        plain, mapping = build_html_mapping("")
        self.assertEqual(plain, "")
        self.assertEqual(mapping, [0])

    def test_only_tags(self):
        html = "<div></div>"
        plain, mapping = build_html_mapping(html)
        self.assertEqual(plain, "")

    def test_mixed_content(self):
        html = "<div><p>first</p><span>second</span></div>"
        plain, mapping = build_html_mapping(html)
        self.assertEqual(plain, "first\nsecond")

    def test_trailing_whitespace_removed(self):
        html = "hello  "
        plain, mapping = build_html_mapping(html)
        self.assertEqual(plain, "hello")

    def test_br_tag(self):
        html = "hello<br>world"
        plain, mapping = build_html_mapping(html)
        self.assertEqual(plain, "hello\nworld")

    def test_complex_entities(self):
        html = "a &lt; b &gt; c"
        plain, mapping = build_html_mapping(html)
        self.assertEqual(plain, "a < b > c")


if __name__ == "__main__":
    unittest.main()
