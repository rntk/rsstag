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
        """Generate grouped data from raw text content and title

        Raises:
            PostSplitterError: If splitting or grouping fails
        """
        if title:
            text = title + ". " + content
        else:
            text = content

        if not text.strip():
            return None

        sentences = self._split_sentences(text)
        if not sentences:
            return None

        marker_data = self.add_markers_to_text(text)
        tagged_text = marker_data["tagged_text"]
        sentence_count = marker_data["sentence_count"]

        if sentence_count == 0:
            return None

        try:
            topic_ranges = self._get_llm_topic_ranges(tagged_text)
            if not topic_ranges:
                raise ParsingError("LLM returned no topic ranges")

            normalized = self._normalize_topic_ranges(
                topic_ranges, sentence_count - 1
            )
            if not normalized:
                raise ParsingError("No usable topic ranges")

            groups = self._build_groups(normalized, sentences)
        except (LLMGenerationError, ParsingError) as e:
            self._log.warning("LLM splitting failed (%s), using single group", e)
            groups = {"Main Content": list(range(1, len(sentences) + 1))}

        return {"sentences": sentences, "groups": groups}

    def add_markers_to_text(self, text_plain: str) -> Dict[str, Any]:
        """Create sentence-based mapping with {N} markers.

        Returns:
            dict containing:
            - "tagged_text": Numbered sentences with {N} markers
            - "sentence_count": Total number of sentences
            - "text_plain": Original plain text
        """
        sentences = self._split_sentences(text_plain)

        rows: List[str] = []
        for s in sentences:
            rows.append(text_plain[s["start"] : s["end"]])

        if not rows and text_plain.strip():
            rows.append(text_plain)

        formatted = [f"{{{i}}} {row}" for i, row in enumerate(rows)]

        return {
            "tagged_text": "\n".join(formatted),
            "sentence_count": len(rows),
            "text_plain": text_plain,
        }

    def _get_llm_topic_ranges(
        self, tagged_text: str
    ) -> List[Tuple[str, int, int]]:
        """Ask LLM to identify topics and sentence ranges in the text

        Raises:
            LLMGenerationError
            ParsingError
        """
        prompt: str = self.build_topic_ranges_prompt(tagged_text)
        self._log.info("LLM topic ranges prompt sent")
        response: str = self._call_llm(prompt, temperature=0.0).strip()
        self._log.info("LLM topic ranges response: %s", response)
        _, topic_ranges = self.parse_topic_ranges_response(response)

        return topic_ranges

    def build_topic_ranges_prompt(self, tagged_text: str) -> str:
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

    def parse_topic_ranges_response(
        self, response: str
    ) -> Tuple[List[str], List[Tuple[str, int, int]]]:
        """Parse response into topics list and topic ranges list."""
        topic_ranges: List[Tuple[str, int, int]] = self._parse_llm_ranges(response)
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
    ) -> List[Tuple[str, int, int]]:
        """Extract ranges for known topics from a topic+range response."""
        topic_set: set[str] = set(topics)
        _, topic_ranges = self.parse_topic_ranges_response(response)
        if not topic_set:
            return topic_ranges
        return [r for r in topic_ranges if r[0] in topic_set]

    def _parse_llm_ranges(
        self, response: str
    ) -> List[Tuple[str, int, int]]:
        """Parse hierarchical topic paths and sentence ranges from LLM response.

        Expected format: Technology>Database>PostgreSQL: 0-5, 10-15

        Returns:
            List of (topic_path, start_sentence, end_sentence) tuples
        """
        lines: List[str] = [ln.strip() for ln in response.strip().split("\n") if ln.strip()]
        ranges: List[Tuple[str, int, int]] = []

        for ln in lines:
            if ":" not in ln:
                continue

            topic_path, ranges_str = ln.split(":", 1)
            topic_path = topic_path.strip()
            ranges_str = ranges_str.strip()

            if ">" not in topic_path:
                self._log.warning(f"Non-hierarchical topic (accepting anyway): {topic_path}")

            parsed_ranges = self._parse_range_string(ranges_str)

            for start_idx, end_idx in parsed_ranges:
                ranges.append((topic_path, start_idx, end_idx))

        return ranges

    def _parse_range_string(self, ranges_str: str) -> List[Tuple[int, int]]:
        """Parse range string like '0-5, 10-15, 20' into list of (start, end) tuples.

        Returns:
            List of (start, end) tuples with 0-based sentence indices
        """
        results = []

        parts = [p.strip() for p in ranges_str.split(",")]

        for part in parts:
            if "-" in part and not part.startswith("-"):
                match = re.match(r"(\d+)\s*-\s*(\d+)", part)
                if match:
                    results.append((int(match.group(1)), int(match.group(2))))
                    continue

            match = re.match(r"(\d+)", part)
            if match:
                n = int(match.group(1))
                results.append((n, n))

        return results

    def _normalize_topic_ranges(
        self, topic_ranges: List[Tuple[str, int, int]], max_index: int
    ) -> List[Tuple[str, int, int]]:
        """Clamp, order, and fill gaps to ensure continuous coverage.

        Uses 0-based sentence indices.
        """
        if not topic_ranges:
            return []

        cleaned: List[Tuple[str, int, int]] = []
        for topic, start, end in topic_ranges:
            start = max(0, min(start, max_index))
            end = max(0, min(end, max_index))
            if start > end:
                start, end = end, start
            cleaned.append((topic, start, end))

        cleaned.sort(key=lambda x: (x[1], x[2]))
        normalized: List[Tuple[str, int, int]] = []
        current: int = 0

        for topic, start, end in cleaned:
            if end < current:
                continue
            if start > current:
                normalized.append(("no_topic", current, start - 1))
            start = max(start, current)
            normalized.append((topic, start, end))
            current = end + 1
            if current > max_index:
                break

        if current <= max_index:
            normalized.append(("no_topic", current, max_index))

        return normalized

    def _build_groups(
        self,
        normalized_ranges: List[Tuple[str, int, int]],
        sentences: List[Dict[str, Any]],
    ) -> Dict[str, List[int]]:
        """Map topic ranges (0-based sentence indices) to sentence numbers (1-based)."""
        groups: Dict[str, List[int]] = {}
        for topic, start_sent, end_sent in normalized_ranges:
            sent_numbers = []
            for s in sentences:
                sent_idx = s["number"] - 1  # Convert 1-based to 0-based
                if start_sent <= sent_idx <= end_sent:
                    sent_numbers.append(s["number"])
            if sent_numbers:
                if topic not in groups:
                    groups[topic] = []
                groups[topic].extend(sent_numbers)
        for topic in groups:
            groups[topic] = sorted(set(groups[topic]))
        return groups

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
