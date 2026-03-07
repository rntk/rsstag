"""Shared grouped-snippet extraction helpers."""

import html
import re
from typing import Any, Dict, List


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
            if not text:
                continue

            if current_snippet and idx == int(current_snippet["index"]) + 1:
                current_snippet["text"] += " " + text
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
                    "post_id": post_meta["post_id"],
                    "post_title": post_meta["post_title"],
                    "index": idx,
                    "indices": [idx],
                    "url": post_meta.get("url"),
                    "read": bool(sentence.get("read", False)),
                    "feed_id": post_meta.get("feed_id", ""),
                    "feed_title": post_meta.get("feed_title", ""),
                }

        if current_snippet:
            snippets.append(current_snippet)

        if snippets:
            topics_data[topic] = snippets

    return topics_data
