"""Post splitting and LLM interaction logic"""

import logging
import re
from typing import Optional, List, Dict, Any, Tuple


class PostSplitterError(Exception):
    """Base exception for PostSplitter errors"""

    pass


class LLMGenerationError(PostSplitterError):
    """Raised when LLM call fails or returns empty/invalid response"""

    pass


class ParsingError(PostSplitterError):
    """Raised when LLM response cannot be parsed correctly"""

    pass


class PostSplitter:
    """Handles text splitting using LLM calls and parsing responses"""

    def __init__(self, llm_handler: Optional[Any] = None) -> None:
        self._log = logging.getLogger("post_splitter")
        self._llm_handler = llm_handler

    def generate_grouped_data(
        self, content: str, title: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Generate grouped data from raw content and title

        Raises:
            PostSplitterError: If splitting or grouping fails
        """
        # Prepare content with title
        if title:
            full_content_html = title + ". " + content
        else:
            full_content_html = content

        full_content_plain, _ = self._build_html_mapping(full_content_html)

        # Generate chapters using LLM
        chapters = self._llm_split_chapters(full_content_plain, full_content_html)
        # _llm_split_chapters now raises exceptions, so no need to check for None returns causing exits
        # However, it might still return None if max_marker is 0 (empty/short text), which is not necessarily an error.
        # But looking at implementation below, let's see.
        if chapters is None:
            # This happens if text is too short/empty/no markers.
            # In that case, we probably shouldn't return a partial result, or maybe we should?
            # The original code returned None. Let's stick to None for "nothing to do" or "invalid input" cases not related to LLM failure?
            # Or better, if it returns None because no markers, we return None.
            return None

        # Split into sentences and create groups
        sentences, groups = self._create_sentences_and_groups(
            full_content_plain, chapters
        )

        return {
            "sentences": sentences,
            "groups": groups,
        }

    def add_markers_to_text(self, text_plain: str) -> Dict[str, Any]:
        """Create sentence-based mapping for the text.

        Returns:
            dict containing:
            - "tagged_text": Numbered sentences with {N} markers
            - "max_marker": Total number of words (linear index max)
            - "marker_positions": Dict mapping linear_index -> char_offset_end
            - "coord_map": Dict mapping (y, x) -> linear_index
            - "text_plain": Original plain text
        """
        # 1. Split into lines (sentences)
        sentences = self._split_sentences(text_plain)

        rows: List[Dict[str, int | str]] = []
        for s in sentences:
            rows.append(
                {
                    "text": text_plain[s["start"] : s["end"]],
                    "start": s["start"],
                    "end": s["end"],
                }
            )

        if not rows and text_plain.strip():
            rows.append({"text": text_plain, "start": 0, "end": len(text_plain)})

        # 2. Build Grid and Mappings
        marker_positions: Dict[int, int] = {0: 0}
        coord_to_linear: Dict[Tuple[int, int], int] = {}
        linear_idx: int = 0

        formatted_rows: List[str] = []

        for y, row in enumerate(rows):
            line_text: str = str(row["text"])
            line_start_offset: int = int(row["start"])

            # Split line into words
            words: List[re.Match[str]] = list(re.finditer(r"\S+", line_text))

            for x, match in enumerate(words):
                word_end_local = match.end()

                linear_idx += 1
                abs_end = line_start_offset + word_end_local

                marker_positions[linear_idx] = abs_end
                coord_to_linear[(y, x)] = linear_idx

            # Row format: "{SentenceNumber} Full sentence text"
            formatted_rows.append(f"{{{y}}} {line_text}")

        # 3. Build Final Text (Y axis only)
        grid_text = "\n".join(formatted_rows)

        return {
            "tagged_text": grid_text,
            "max_marker": linear_idx,
            "marker_positions": marker_positions,
            "coord_map": coord_to_linear,
            "text_plain": text_plain,
        }

    def _get_llm_topic_ranges(
        self, tagged_text: str, coord_map: Optional[Dict[Tuple[int, int], int]] = None
    ) -> List[Tuple[str, int, int]]:
        """Ask LLM to identify topics and coordinate ranges in the text

        Raises:
            LLMGenerationError
            ParsingError
        """
        prompt: str = self.build_topic_ranges_prompt(tagged_text)
        self._log.info("LLM topic ranges prompt sent (Sentence method)")
        response: str = self._call_llm(prompt, temperature=0.0).strip()
        self._log.info("LLM topic ranges response: %s", response)
        _, topic_ranges = self.parse_topic_ranges_response(response, coord_map)

        return topic_ranges

    def _get_llm_ranges(
        self, tagged_text: str, coord_map: Optional[Dict[Tuple[int, int], int]] = None
    ) -> List[Tuple[str, int, int]]:
        """Backward-compatible alias for _get_llm_topic_ranges."""
        return self._get_llm_topic_ranges(tagged_text, coord_map)

    def build_topic_ranges_prompt(self, tagged_text: str, suggested_topics: Optional[List[str]] = None) -> str:
        vocabulary_hint = ""
        if suggested_topics:
            vocabulary_hint = f"""
PREFERRED TOPICS (use these EXACT names when applicable):
{', '.join(suggested_topics)}

Use these exact topic names when they match the content. Only introduce new topics when the content doesn't fit any preferred topic.
"""

        return f"""You are analyzing a text presented as numbered sentences.
Sentence numbers are 0-indexed.

Your task: Extract specific, searchable topic keywords for each distinct section of the text.

AGGREGATION REQUIREMENTS (CRITICAL):
These keywords will be grouped across multiple articles. Use CONSISTENT, CANONICAL naming:

Common entities - use these EXACT forms:
- Languages: Python, JavaScript, TypeScript, Go, Rust, Java, C++, C#
- Databases: PostgreSQL, MongoDB, Redis, MySQL, SQLite
- Cloud: AWS, Google Cloud, Azure, Kubernetes, Docker, Terraform
- AI/ML: GPT-4, Claude, Gemini, LLaMA, ChatGPT, AI, ML, Large Language Models
- Frameworks: React, Vue, Angular, Django, FastAPI, Spring Boot, Next.js, NestJS
- Companies: OpenAI, Anthropic, Google, Microsoft, Meta, Apple, Amazon, NVIDIA

Version format: "Name X.Y" (drop patch version)
- ✓ "Python 3.12" (not "Python 3.12.1", "Python version 3.12", "Python v3.12")
- ✓ "React 19" (not "React v19.0", "React 19.0")

When in doubt: use the official product/company name with official capitalization.
{vocabulary_hint}
KEYWORD SELECTION HIERARCHY (prefer in order):
1. Named entities: specific products, companies, people, technologies
   Examples: "GPT-4", "Kubernetes", "PostgreSQL", "Linus Torvalds"
2. Specific concepts/events: concrete actions, announcements, or occurrences
   Examples: "Series B funding", "CVE-2024-1234 vulnerability", "React 19 release"
3. Technical terms: domain-specific terminology
   Examples: "vector embeddings", "JWT authentication", "HTTP/3 protocol"

HIERARCHICAL TOPIC GRAPH (REQUIRED):
Express each topic as a hierarchical path using ">" separator:
- Use 2-4 levels (avoid too shallow or too deep)
- Top level: General category (Technology, Sport, Politics, Science, Business, Health)
- Middle levels: Sub-categories (AI, Football, Database, Cloud, Security)
- Bottom level: Specific entity or aspect (GPT-4, England, PostgreSQL, AWS)

Examples:
✓ Technology>AI>GPT-4: 0-5
✓ Technology>Database>PostgreSQL: 6-9, 15-17
✓ Sport>Football>England: 10-14
✓ Science>Climate>IPCC Report: 18-20

Invalid formats:
✗ PostgreSQL: 1-5 (too flat - missing category hierarchy)
✗ Tech>Software>DB>SQL>PostgreSQL>Version15: 1-5 (too deep - max 4 levels)

For digest posts with multiple unrelated topics, create separate hierarchies:
Technology>AI>OpenAI: 0-5
Sport>Football>England: 6-10
Politics>Elections>France: 11-15

WHAT MAKES A GOOD KEYWORD:
✓ Helps readers decide if this section is relevant to their interests
✓ Specific enough to distinguish this section from others in the article
✓ Consistent with canonical naming (enables aggregation across articles)
✓ Something a user might search for
✓ 1-5 words (noun phrases preferred)

BAD KEYWORDS (too generic or inconsistent):
✗ "Tech News", "Update", "Information", "Technology", "Discussion", "News"
✗ "Postgres" (use "PostgreSQL"), "JS" (use "JavaScript"), "K8s" (use "Kubernetes")

GOOD KEYWORDS (specific, searchable, and canonical):
✓ "PostgreSQL: indexing" (not "Database Tips", "Postgres indexing")
✓ "Python: asyncio" (not "Programming", "Python async patterns")
✓ "React: hooks" (not "Frontend", "React.js hooks")
✓ "GPT-4" (not "OpenAI GPT-4", "GPT-4 model")

SEMANTIC DISTINCTIVENESS:
If multiple sections share a theme, differentiate them:
- ✓ "AI: medical imaging" and "AI: drug discovery" (not just "AI" for both)
- ✓ "PostgreSQL: indexing" and "PostgreSQL: replication" (not just "PostgreSQL")

SPECIFICITY BALANCE:
- General topic → use canonical name: "PostgreSQL", "Python", "React"
- Specific aspect → use qualified form: "PostgreSQL: indexing", "Python: asyncio"
- Don't over-specify: "React: hooks" not "React hooks useState optimization patterns"

OUTPUT FORMAT (exactly one hierarchy per line):
CategoryLevel1>CategoryLevel2>...>SpecificTopic: SentenceRanges

SentenceRanges can be:
- Single range: 0-5
- Multiple ranges: 0-5, 10-15, 20-22
- Individual sentences: 0, 2, 5
- Mixed: 0-3, 7, 10-15

Examples:
Technology>Database>PostgreSQL: 0-5, 10-15
Sport>Football>England: 2, 4, 6-9

SENTENCE RULES:
- Sentence numbers are 0-indexed
- Every sentence must belong to exactly one keyword group
- Be granular: separate distinct stories/topics into their own keyword groups

<grid>
{tagged_text}
</grid>

Output:"""

    def build_ranges_prompt(self, tagged_text: str) -> str:
        """Backward-compatible alias for topic+range prompt."""
        return self.build_topic_ranges_prompt(tagged_text)

    def build_topics_prompt(self, tagged_text: str) -> str:
        """Keep topics+ranges in a single prompt for batch flows."""
        return self.build_topic_ranges_prompt(tagged_text)

    def build_topic_mapping_prompt(self, topics: List[str], tagged_text: str) -> str:
        """Keep topics+ranges in a single prompt for batch flows."""
        _ = topics
        return self.build_topic_ranges_prompt(tagged_text)

    def parse_topic_ranges_response(
        self, response: str, coord_map: Optional[Dict[Tuple[int, int], int]] = None
    ) -> Tuple[List[str], List[Tuple[str, int, int]]]:
        """Parse response into topics list and topic ranges list."""
        topic_ranges: List[Tuple[str, int, int]] = self._parse_llm_ranges(
            response, coord_map
        )
        topics: List[str] = []
        seen: set[str] = set()
        for topic, _, _ in topic_ranges:
            if topic not in seen:
                topics.append(topic)
                seen.add(topic)
        return topics, topic_ranges

    def parse_topics_response(self, response: str) -> List[str]:
        """Extract topic names from a topic+range response."""
        topics: List[str] = []
        seen: set[str] = set()
        for line in response.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                topic_raw = line.split(":", 1)[0].strip().strip('"').strip("'")
            else:
                # Fallback: if no colon, check if the line looks like it contains ranges
                # If it doesn't, assume the whole line is a topic name
                if re.search(r"\d+\s*-\s*\d+", line) or re.search(r"\(\d+,\s*\d+\)", line):
                    continue
                topic_raw = line.strip().strip('"').strip("'")

            if not topic_raw:
                topic_raw = "no_topic"
            if topic_raw not in seen:
                topics.append(topic_raw)
                seen.add(topic_raw)
        return topics

    def parse_topic_mapping_response(
        self,
        response: str,
        topics: List[str],
        coord_map: Optional[Dict[Tuple[int, int], int]] = None,
    ) -> List[Tuple[str, int, int]]:
        """Extract ranges for known topics from a topic+range response."""
        topic_set: set[str] = set(topics)
        _, topic_ranges = self.parse_topic_ranges_response(response, coord_map)
        if not topic_set:
            return topic_ranges
        return [r for r in topic_ranges if r[0] in topic_set]

    def _build_sentence_bounds(
        self, coord_map: Dict[Tuple[int, int], int]
    ) -> Dict[int, Tuple[int, int]]:
        """Build sentence start/end word-index bounds from a coordinate map."""
        sentence_bounds: Dict[int, Tuple[int, int]] = {}
        for (y, _), linear_idx in coord_map.items():
            if y not in sentence_bounds:
                sentence_bounds[y] = (linear_idx, linear_idx)
            else:
                start_idx, end_idx = sentence_bounds[y]
                sentence_bounds[y] = (
                    min(start_idx, linear_idx),
                    max(end_idx, linear_idx),
                )
        return sentence_bounds

    def _parse_llm_ranges(
        self, response: str, coord_map: Optional[Dict[Tuple[int, int], int]] = None
    ) -> List[Tuple[str, int, int]]:
        """Parse hierarchical topic paths and ranges from LLM response.

        Expected format: Technology>Database>PostgreSQL: 0-5, 10-15

        Returns:
            List of (topic_path, start_index, end_index) tuples
        """
        sentence_bounds: Dict[int, Tuple[int, int]] = {}
        if coord_map:
            sentence_bounds = self._build_sentence_bounds(coord_map)

        lines: List[str] = [ln.strip() for ln in response.strip().split("\n") if ln.strip()]
        ranges: List[Tuple[str, int, int]] = []

        for ln in lines:
            # Split on first colon
            if ":" not in ln:
                continue

            topic_path, ranges_str = ln.split(":", 1)
            topic_path = topic_path.strip()
            ranges_str = ranges_str.strip()

            # Validate hierarchical format (should contain ">")
            if ">" not in topic_path:
                self._log.warning(f"Non-hierarchical topic (accepting anyway): {topic_path}")

            # Parse ranges: "0-5, 10-15, 20" -> list of (start, end) tuples
            parsed_ranges = self._parse_range_string(ranges_str, sentence_bounds)

            for start_idx, end_idx in parsed_ranges:
                ranges.append((topic_path, start_idx, end_idx))

        return ranges

    def _parse_range_string(
        self, ranges_str: str, sentence_bounds: Dict[int, Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """Parse range string like '0-5, 10-15, 20' into list of (start, end) tuples.

        Args:
            ranges_str: Comma-separated ranges or sentence numbers
            sentence_bounds: Mapping from sentence number to (start_word_idx, end_word_idx)

        Returns:
            List of (start_idx, end_idx) tuples (word indices if sentence_bounds provided)
        """
        results = []

        # Split by comma
        parts = [p.strip() for p in ranges_str.split(",")]

        for part in parts:
            # Try range format: "0-5"
            if "-" in part and not part.startswith("-"):
                match = re.match(r"(\d+)\s*-\s*(\d+)", part)
                if match:
                    start_sent = int(match.group(1))
                    end_sent = int(match.group(2))

                    # Convert sentence numbers to word indices if mapping available
                    if sentence_bounds:
                        for sent_num in range(start_sent, end_sent + 1):
                            bounds = sentence_bounds.get(sent_num)
                            if bounds:
                                results.append(bounds)
                            else:
                                self._log.warning(f"Sentence {sent_num} out of bounds")
                    else:
                        results.append((start_sent, end_sent))
                    continue

            # Try single sentence number: "5"
            match = re.match(r"(\d+)", part)
            if match:
                sent_num = int(match.group(1))
                if sentence_bounds:
                    bounds = sentence_bounds.get(sent_num)
                    if bounds:
                        results.append(bounds)
                    else:
                        self._log.warning(f"Sentence {sent_num} out of bounds")
                else:
                    results.append((sent_num, sent_num))

        return results

    def _normalize_topic_ranges(
        self, topic_ranges: List[Tuple[str, int, int]], max_marker: int
    ) -> List[Tuple[str, int, int]]:
        """Clamp, order, and fill gaps to ensure continuous coverage."""
        if not topic_ranges:
            return []

        cleaned: List[Tuple[str, int, int]] = []
        for topic, start, end in topic_ranges:
            start = max(1, min(start, max_marker))
            end = max(1, min(end, max_marker))
            if start > end:
                start, end = end, start
            cleaned.append((topic, start, end))

        cleaned.sort(key=lambda x: (x[1], x[2]))
        normalized: List[Tuple[str, int, int]] = []
        current: int = 1

        for topic, start, end in cleaned:
            if end < current:
                continue
            if start > current:
                normalized.append(("no_topic", current, start - 1))
            start = max(start, current)
            normalized.append((topic, start, end))
            current = end + 1
            if current > max_marker:
                break

        if current <= max_marker:
            normalized.append(("no_topic", current, max_marker))

        return normalized

    def _validate_boundaries(
        self, boundaries: List[tuple], max_marker: int
    ) -> List[tuple]:
        """Validate, clamp, and fill gaps in boundaries to ensure continuous coverage"""
        if not boundaries:
            return []

        # Sort by start marker to handle them in order
        sorted_boundaries = sorted(boundaries, key=lambda x: x[1])

        validated = []
        for i, (title, start, end) in enumerate(sorted_boundaries):
            # 1. Clamp to valid range [1, max_marker]
            start = max(1, min(start, max_marker))
            end = max(1, min(end, max_marker))
            if start > end:
                start, end = end, start

            # 2. Handle continuity and fill gaps
            if not validated:
                # First chapter MUST start at 1 to avoid a gap at the beginning
                start = 1
            else:
                prev_title, prev_start, prev_end = validated[-1]
                # Start this chapter exactly after the previous one
                start = prev_end + 1

            # 3. Ensure end is at least start
            if start > end:
                end = start

            # 4. If this is the last chapter, it MUST end at max_marker
            if i == len(sorted_boundaries) - 1:
                end = max_marker

            # Only add if start is still within bounds
            if start <= max_marker:
                validated.append((title, start, end))

        return validated

    def _build_html_mapping(self, html_text: str) -> tuple:
        """Builds a mapping between normalized plain text indices and original HTML indices.

        Adds synthetic newlines for block-level tags to ensure correct sentence splitting.
        """
        from html import unescape
        import re

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

        mapping = []
        plain_accum = []

        n = len(html_text)
        i = 0
        last_was_space = True  # Start with True to trim leading spaces

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
                    # Not a valid tag match, treat as text
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

            # Text content
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

        # Trim trailing space/newline
        while plain_accum and plain_accum[-1] in (" ", "\n"):
            plain_accum.pop()
            mapping.pop()

        final_plain = "".join(plain_accum)
        final_mapping = mapping

        if final_mapping:
            final_mapping.append(n)
        else:
            final_mapping = [0]

        return final_plain, final_mapping

    def _map_chapters_to_html(
        self,
        text_plain: str,
        text_html: str,
        chapter_boundaries: List[tuple],
        marker_positions: Dict[int, int],
        max_marker: int,
    ) -> List[Dict[str, Any]]:
        """Split text into chapters and map to HTML content using optimized linear mapping"""
        mapped_plain, mapping = self._build_html_mapping(text_html)

        chapters = []
        for title, start_marker, end_marker in chapter_boundaries:
            chapters.append(
                {"title": title, "start_tag": start_marker, "end_tag": end_marker}
            )

        last_tag = chapters[-1]["end_tag"] if chapters else 0
        last_pos = marker_positions.get(last_tag, 0) if last_tag else 0
        if last_pos < len(text_plain):
            next_start = min(last_tag + 1, max_marker)
            chapters.append(
                {
                    "title": "Remaining Content",
                    "start_tag": next_start,
                    "end_tag": max_marker,
                }
            )

        result = []
        last_map_idx = 0

        for ch in chapters:
            start_tag = ch["start_tag"]
            end_tag = ch["end_tag"]
            p_start = marker_positions.get(start_tag - 1, 0)
            p_end = marker_positions.get(end_tag, len(text_plain))
            target_snippet = text_plain[p_start:p_end].strip()

            if not target_snippet:
                result.append(
                    {
                        "title": ch["title"],
                        "text": "",
                        "plain_start": p_start,
                        "plain_end": p_end,
                    }
                )
                continue

            search_start_idx = last_map_idx
            if search_start_idx >= len(mapped_plain):
                search_start_idx = 0

            snippet_idx = mapped_plain.find(target_snippet, search_start_idx)
            if snippet_idx == -1:
                snippet_idx = mapped_plain.find(target_snippet)

            html_content = ""
            if snippet_idx != -1:
                snippet_end_idx = snippet_idx + len(target_snippet)
                last_map_idx = snippet_end_idx
                if snippet_idx < len(mapping) and snippet_end_idx < len(mapping):
                    h_start = mapping[snippet_idx]
                    h_end = mapping[snippet_end_idx]
                    html_content = text_html[h_start:h_end]
                else:
                    self._log.warning(
                        f"Map index out of bounds for chapter '{ch['title']}'"
                    )
            else:
                self._log.warning(
                    f"Could not align chapter '{ch['title']}' to HTML using fast map"
                )
                html_content = target_snippet

            result.append(
                {
                    "title": ch["title"],
                    "text": html_content.strip(),
                    "plain_start": p_start,
                    "plain_end": p_end,
                }
            )

        return result

    def _llm_split_chapters(
        self, text_plain: str, text_html: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Split content into chapters using LLM with word splitters

        Raises:
            PostSplitterError
        """
        if not self._llm_handler:
            raise LLMGenerationError("LLM handler not configured")

        marker_data = self.add_markers_to_text(text_plain)
        tagged_text = marker_data["tagged_text"]
        max_marker = marker_data["max_marker"]
        marker_positions = marker_data["marker_positions"]

        if max_marker == 0:
            if not text_plain.strip():
                return None
            self._log.info(
                "No markers generated (short text), falling back to single chapter"
            )
            return [
                {
                    "title": "Main Content",
                    "text": text_html,
                    "plain_start": 0,
                    "plain_end": len(text_plain),
                }
            ]

        # Try structured splitting
        try:
            # Pass coord_map to helper
            coord_map = marker_data.get("coord_map")
            topic_ranges = self._get_llm_topic_ranges(tagged_text, coord_map)
            if not topic_ranges:
                raise ParsingError("LLM returned no topic ranges")

            normalized_ranges: List[Tuple[str, int, int]] = self._normalize_topic_ranges(
                topic_ranges, max_marker
            )
            if not normalized_ranges:
                raise ParsingError("LLM generated no usable topic ranges")

            chapter_boundaries: List[Tuple[str, int, int]] = [
                (topic, start, end) for topic, start, end in normalized_ranges
            ]

            return self._map_chapters_to_html(
                text_plain,
                text_html,
                chapter_boundaries,
                marker_positions,
                max_marker,
            )
        except (LLMGenerationError, ParsingError) as e:
            self._log.warning(
                "LLM splitting failed (%s), falling back to single chapter",
                e,
            )
            return [
                {
                    "title": "Main Content",
                    "text": text_html,
                    "plain_start": 0,
                    "plain_end": len(text_plain),
                }
            ]

    def _call_llm(self, prompt: str, temperature: float = 0.0) -> str:
        """Calls the LLM handler.

        Raises:
            LLMGenerationError: If call fails or returns empty.
        """
        if not self._llm_handler:
            self._log.error("LLM handler not configured")
            raise LLMGenerationError("LLM handler not configured")

        try:
            response = self._llm_handler.call([prompt], temperature=temperature)
        except Exception as e:
            self._log.error("LLM call failed: %s", e)
            raise LLMGenerationError(f"LLM call failed: {e}") from e

        if not response:
            self._log.error("Empty LLM response")
            raise LLMGenerationError("Empty LLM response")

        return response

    def _create_sentences_and_groups(
        self, full_content_plain: str, chapters: List[Dict[str, Any]]
    ) -> tuple:
        """Create sentences and groups from chapters"""
        sentences = self._split_sentences(full_content_plain)
        groups = {}

        if len(chapters) == 1:
            title = chapters[0]["title"]
            groups[title] = list(range(1, len(sentences) + 1))
        else:
            sentence_info = [
                {
                    "id": sentence["number"],
                    "start": sentence["start"],
                    "end": sentence["end"],
                }
                for sentence in sentences
                if "start" in sentence and "end" in sentence
            ]

            for chapter in chapters:
                title = chapter["title"]
                plain_start = chapter.get("plain_start", 0)
                plain_end = chapter.get("plain_end", len(full_content_plain))

                chapter_sentence_numbers = []
                for s_info in sentence_info:
                    s_id = s_info["id"]
                    s_start = s_info["start"]
                    s_end = s_info["end"]

                    if (
                        (s_start >= plain_start - 2 and s_start < plain_end)
                        or (s_end > plain_start + 2 and s_end <= plain_end + 2)
                        or (s_start < plain_start and s_end > plain_end)
                    ):
                        chapter_sentence_numbers.append(s_id)

                if chapter_sentence_numbers:
                    if title not in groups:
                        groups[title] = []
                    groups[title].extend(chapter_sentence_numbers)

            for title in groups:
                groups[title] = sorted(list(set(groups[title])))

        return sentences, groups

    def _split_sentences(self, text: str) -> List[Dict[str, Any]]:
        """Split text into sentences"""
        if not text or not text.strip():
            return []
        # Split on:
        # 1. Punctuation ([.!?]) followed by whitespace and an uppercase letter
        # 2. One or more newlines (representing block boundaries)
        boundaries = list(re.finditer(r"((?<=[.!?])\s+(?=[A-ZА-Я]))|(\n+)", text))

        result = []
        start = 0
        sentence_number = 1
        for match in boundaries:
            end = match.start()
            sentence_start = start
            sentence_end = end
            while sentence_start < sentence_end and text[sentence_start].isspace():
                sentence_start += 1
            while sentence_end > sentence_start and text[sentence_end - 1].isspace():
                sentence_end -= 1
            if sentence_start < sentence_end:
                result.append(
                    {
                        "number": sentence_number,
                        "start": sentence_start,
                        "end": sentence_end,
                        "read": False,
                    }
                )
                sentence_number += 1
            start = match.end()

        sentence_start = start
        sentence_end = len(text)
        while sentence_start < sentence_end and text[sentence_start].isspace():
            sentence_start += 1
        while sentence_end > sentence_start and text[sentence_end - 1].isspace():
            sentence_end -= 1
        if sentence_start < sentence_end:
            result.append(
                {
                    "number": sentence_number,
                    "start": sentence_start,
                    "end": sentence_end,
                    "read": False,
                }
            )

        return result
