"""Shared grouped-snippet extraction helpers."""

import html
import re
from html.parser import HTMLParser
from typing import Any, Dict, List
from urllib.parse import urlparse

ALLOWED_SNIPPET_TAGS: set[str] = {
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "em",
    "i",
    "li",
    "mark",
    "ol",
    "p",
    "strong",
    "u",
    "ul",
}
SELF_CLOSING_SNIPPET_TAGS: set[str] = {"br"}
SKIP_CONTENT_TAGS: set[str] = {"script", "style"}


def _is_safe_snippet_href(value: str) -> bool:
    """Allow only safe link targets for rendered snippets."""
    stripped: str = value.strip()
    if not stripped:
        return False
    if stripped.startswith(("/", "#")):
        return True

    parsed = urlparse(stripped)
    return parsed.scheme in {"http", "https", "mailto"}


class _SafeSnippetHTMLParser(HTMLParser):
    """Minimal sanitizer for snippet HTML fragments."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_stack: list[str] = []
        self._open_tags: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        normalized_tag: str = tag.lower()
        if normalized_tag in SKIP_CONTENT_TAGS:
            self._skip_stack.append(normalized_tag)
            return
        if self._skip_stack or normalized_tag not in ALLOWED_SNIPPET_TAGS:
            return

        if normalized_tag == "a":
            sanitized_attrs: list[str] = []
            href_value: str | None = None
            title_value: str | None = None
            for attr_name, attr_value in attrs:
                if attr_value is None:
                    continue
                lower_name: str = attr_name.lower()
                if lower_name == "href" and _is_safe_snippet_href(attr_value):
                    href_value = attr_value.strip()
                elif lower_name == "title":
                    title_value = attr_value.strip()

            if not href_value:
                return

            sanitized_attrs.append(f'href="{html.escape(href_value, quote=True)}"')
            sanitized_attrs.append('target="_blank"')
            sanitized_attrs.append('rel="noopener noreferrer nofollow"')
            if title_value:
                sanitized_attrs.append(
                    f'title="{html.escape(title_value, quote=True)}"'
                )
            self._parts.append(f"<a {' '.join(sanitized_attrs)}>")
            self._open_tags.append(normalized_tag)
            return

        self._parts.append(f"<{normalized_tag}>")
        if normalized_tag not in SELF_CLOSING_SNIPPET_TAGS:
            self._open_tags.append(normalized_tag)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag: str = tag.lower()
        if normalized_tag in SKIP_CONTENT_TAGS:
            if self._skip_stack and self._skip_stack[-1] == normalized_tag:
                self._skip_stack.pop()
            return
        if self._skip_stack:
            return
        if (
            normalized_tag in ALLOWED_SNIPPET_TAGS
            and normalized_tag not in SELF_CLOSING_SNIPPET_TAGS
            and self._open_tags
            and self._open_tags[-1] == normalized_tag
        ):
            self._open_tags.pop()
            self._parts.append(f"</{normalized_tag}>")

    def handle_data(self, data: str) -> None:
        if self._skip_stack or not data:
            return
        self._parts.append(html.escape(data))

    def handle_entityref(self, name: str) -> None:
        if self._skip_stack:
            return
        self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._skip_stack:
            return
        self._parts.append(f"&#{name};")

    def get_html(self) -> str:
        """Return sanitized fragment HTML."""
        return "".join(self._parts)


def sanitize_snippet_html(value: str) -> str:
    """Sanitize snippet HTML while preserving a small safe subset."""
    parser = _SafeSnippetHTMLParser()
    parser.feed(value)
    parser.close()
    return parser.get_html()


def strip_html_markup(value: str) -> str:
    """Convert HTML-ish text to plain text."""
    without_tags: str = re.sub(r"<[^>]+>", " ", value)
    unescaped: str = html.unescape(without_tags)
    return re.sub(r"\s+", " ", unescaped).strip()


def snippet_text_from_sentence(raw_content: str, sentence: Dict[str, Any]) -> str:
    """Get display-ready snippet text from sentence data."""
    sentence_text: Any = sentence.get("text")
    if sentence_text:
        return strip_html_markup(str(sentence_text))

    start_idx: Any = sentence.get("start")
    end_idx: Any = sentence.get("end")
    if (
        isinstance(start_idx, int)
        and isinstance(end_idx, int)
        and 0 <= start_idx < end_idx <= len(raw_content)
    ):
        return strip_html_markup(raw_content[start_idx:end_idx])
    return ""


def snippet_html_from_sentence(raw_content: str, sentence: Dict[str, Any]) -> str:
    """Get sanitized HTML fragment for sentence data."""
    sentence_text: Any = sentence.get("text")
    if sentence_text:
        return sanitize_snippet_html(str(sentence_text))

    start_idx: Any = sentence.get("start")
    end_idx: Any = sentence.get("end")
    if (
        isinstance(start_idx, int)
        and isinstance(end_idx, int)
        and 0 <= start_idx < end_idx <= len(raw_content)
    ):
        return sanitize_snippet_html(raw_content[start_idx:end_idx])
    return ""


def merge_grouped_snippets(
    raw_content: str,
    sentences: List[Dict[str, Any]],
    groups: Dict[str, List[int]],
    post_meta: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """Build merged snippets grouped by topic for one post."""
    topics_data: Dict[str, List[Dict[str, Any]]] = {}
    sentences_map: Dict[int, Dict[str, Any]] = {
        int(sentence["number"]): sentence
        for sentence in sentences
        if "number" in sentence
    }

    for topic, indices in groups.items():
        sorted_indices: List[int] = sorted(int(index) for index in indices)
        if not sorted_indices:
            continue

        snippets: List[Dict[str, Any]] = []
        current_snippet: Dict[str, Any] | None = None
        for idx in sorted_indices:
            sentence: Dict[str, Any] | None = sentences_map.get(idx)
            if not sentence:
                continue

            text: str = snippet_text_from_sentence(raw_content, sentence)
            snippet_html: str = snippet_html_from_sentence(raw_content, sentence)
            if not text:
                continue

            if current_snippet and idx == int(current_snippet["index"]) + 1:
                current_snippet["text"] += " " + text
                if snippet_html:
                    current_snippet["html"] += " " + snippet_html
                current_snippet["index"] = idx
                current_snippet["indices"].append(idx)
                if not sentence.get("read", False):
                    current_snippet["read"] = False
            else:
                if current_snippet:
                    snippets.append(current_snippet)
                current_snippet = {
                    "topic": topic,
                    "text": text,
                    "html": snippet_html or html.escape(text),
                    "post_id": post_meta["post_id"],
                    "post_title": post_meta["post_title"],
                    "index": idx,
                    "indices": [idx],
                    "url": post_meta.get("url"),
                    "read": bool(sentence.get("read", False)),
                    "feed_id": post_meta.get("feed_id", ""),
                    "feed_title": post_meta.get("feed_title", ""),
                    "category_id": post_meta.get("category_id", ""),
                    "category_title": post_meta.get("category_title", ""),
                    "post_tags": list(post_meta.get("post_tags", [])),
                }

        if current_snippet:
            snippets.append(current_snippet)

        if snippets:
            topics_data[topic] = snippets

    return topics_data
