"""HTML to plain text conversion utilities."""

import re
from html import unescape
from typing import List, Tuple

BLOCK_TAGS = {
    "p",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "ul",
    "ol",
    "blockquote",
    "pre",
    "hr",
    "br",
    "td",
    "tr",
    "table",
    "header",
    "footer",
    "section",
    "article",
    "aside",
}


def build_html_mapping(html_text: str) -> Tuple[str, List[int]]:
    """Build a mapping between normalized plain text indices and original HTML indices.

    Adds synthetic newlines for block-level tags to ensure correct sentence splitting.

    Returns:
        Tuple of (plain_text, mapping) where mapping[i] is the HTML index
        corresponding to plain_text[i].
    """
    mapping: List[int] = []
    plain_accum: List[str] = []

    n = len(html_text)
    i = 0
    last_was_space = True

    tag_pattern = re.compile(r"<(/?)([a-zA-Z0-9]+)([^>]*)>")

    while i < n:
        if html_text[i] == "<":
            match = tag_pattern.match(html_text, i)
            if match:
                tag_name = match.group(2).lower()
                is_block = tag_name in BLOCK_TAGS

                if is_block:
                    if plain_accum and plain_accum[-1] != "\n":
                        if plain_accum[-1] == " ":
                            plain_accum[-1] = "\n"
                        else:
                            plain_accum.append("\n")
                            mapping.append(i)
                    last_was_space = True

                i = match.end()
                continue
            else:
                char = html_text[i]
                if char.isspace():
                    if not last_was_space:
                        plain_accum.append(" ")
                        mapping.append(i)
                        last_was_space = True
                else:
                    plain_accum.append(char)
                    mapping.append(i)
                    last_was_space = False
                i += 1
                continue

        next_tag = html_text.find("<", i)
        chunk_end = next_tag if next_tag != -1 else n
        chunk = html_text[i:chunk_end]

        j = 0
        while j < len(chunk):
            char = chunk[j]
            if char == "&":
                ent_end = chunk.find(";", j)
                if ent_end != -1 and ent_end - j < 10:
                    entity = chunk[j : ent_end + 1]
                    decoded_char = unescape(entity)
                    if decoded_char.isspace():
                        if not last_was_space:
                            plain_accum.append(" ")
                            mapping.append(i + j)
                            last_was_space = True
                    else:
                        for dc in decoded_char:
                            plain_accum.append(dc)
                            mapping.append(i + j)
                            last_was_space = False
                    j = ent_end + 1
                    continue

            if char.isspace():
                if not last_was_space:
                    plain_accum.append(" ")
                    mapping.append(i + j)
                    last_was_space = True
            else:
                plain_accum.append(char)
                mapping.append(i + j)
                last_was_space = False
            j += 1
        i = chunk_end

    while plain_accum and plain_accum[-1] in (" ", "\n"):
        plain_accum.pop()
        mapping.pop()

    final_plain = "".join(plain_accum)

    if mapping:
        mapping.append(n)
    else:
        mapping = [0]

    return final_plain, mapping
