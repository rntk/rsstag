import sys
import re
from typing import Any, Dict, Iterator, List, Tuple

# Add the project directory to sys.path
sys.path.append(
    "/home/rnt/backup/cbed520c-c1a0-4091-ad74-a175cfd2acb6/home/rnt/dev/python/rsstag"
)

from rsstag.post_splitter import PostSplitter, PostSplitterError


def test_add_markers_to_text() -> bool:
    splitter: PostSplitter = PostSplitter()
    text: str = "This is sentence one. And this is sentence two."

    result: Dict[str, Any] = splitter.add_markers_to_text(text)
    tagged_text: str = result["tagged_text"]
    sentence_count: int = result["sentence_count"]

    print(f"Original: {text}")
    print(f"Tagged:   {tagged_text}")
    print(f"Sentence count: {sentence_count}")

    # Check sentence markers are present
    if "{0}" not in tagged_text:
        print("FAILED: Missing {0} marker")
        return False
    if "{1}" not in tagged_text:
        print("FAILED: Missing {1} marker")
        return False
    if sentence_count != 2:
        print(f"FAILED: Expected 2 sentences, got {sentence_count}")
        return False

    print("SUCCESS: Markers added correctly.")
    return True


def test_generate_grouped_data_interface() -> bool:
    # Mock LLM handler
    class MockLLM:
        def call(self, prompts: List[str], temperature: float = 0.0) -> str:
            return "Technology>Testing>Unit Tests: 0-1"

    splitter: PostSplitter = PostSplitter(MockLLM())

    text_content: str = "Sentence one about testing. Sentence two about unit tests."
    result: Dict[str, Any] = splitter.generate_grouped_data(text_content, "Post Title")

    if not result:
        print("FAILED: generate_grouped_data returned None")
        return False

    sentences: List[Dict[str, Any]] = result["sentences"]
    groups: Dict[str, List[int]] = result["groups"]
    print(f"Sentences: {sentences}")
    print(f"Groups: {groups}")

    if not sentences:
        print("FAILED: No sentences found.")
        return False

    if not groups:
        print("FAILED: No groups found.")
        return False

    print(f"SUCCESS: Generated {len(sentences)} sentences with {len(groups)} groups.")
    return True


def test_error_handling() -> bool:
    # Mock LLM handler that raises exception
    class BrokenLLM:
        def call(self, prompts: List[str], temperature: float = 0.0) -> str:
            raise Exception("API Error")

    splitter: PostSplitter = PostSplitter(BrokenLLM())

    # The new behavior is to handle the error and return a fallback result (single group)
    result = splitter.generate_grouped_data("Some text", "Title")

    if result is None:
        print("FAILED: generate_grouped_data returned None on error (expected fallback)")
        return False

    if "sentences" not in result or "groups" not in result:
        print("FAILED: Result format invalid on error fallback")
        return False

    if len(result["groups"]) != 1:
        print(f"FAILED: Expected 1 fallback group, got {len(result['groups'])}")
        return False
    if "Main Content" not in result["groups"]:
        print("FAILED: Missing Main Content fallback group")
        return False

    print("SUCCESS: Error handled gracefully with fallback.")
    return True


def test_parse_topic_ranges() -> bool:
    splitter: PostSplitter = PostSplitter()

    response = """Technology>AI>GPT-4: 0-2
Technology>Database>PostgreSQL: 3-5, 8
Sport>Football>England: 6-7"""

    topics, ranges = splitter.parse_topic_ranges_response(response)

    print(f"Topics: {topics}")
    print(f"Ranges: {ranges}")

    if len(topics) != 3:
        print(f"FAILED: Expected 3 topics, got {len(topics)}")
        return False

    if len(ranges) != 4:  # 0-2, 3-5, 8, 6-7
        print(f"FAILED: Expected 4 ranges, got {len(ranges)}")
        return False

    print("SUCCESS: Topic ranges parsed correctly.")
    return True


def test_normalize_topic_ranges() -> bool:
    splitter: PostSplitter = PostSplitter()

    # Gap between 3 and 5, should be filled with "no_topic"
    ranges = [("Topic A", 0, 2), ("Topic B", 5, 7)]
    normalized = splitter._normalize_topic_ranges(ranges, 7)

    print(f"Input: {ranges}")
    print(f"Normalized: {normalized}")

    # Should have: Topic A 0-2, no_topic 3-4, Topic B 5-7
    if len(normalized) != 3:
        print(f"FAILED: Expected 3 ranges, got {len(normalized)}")
        return False

    if normalized[1][0] != "no_topic":
        print(f"FAILED: Expected gap filler 'no_topic', got '{normalized[1][0]}'")
        return False

    if normalized[1][1] != 3 or normalized[1][2] != 4:
        print(f"FAILED: Gap should be 3-4, got {normalized[1][1]}-{normalized[1][2]}")
        return False

    print("SUCCESS: Topic ranges normalized correctly.")
    return True


if __name__ == "__main__":
    s1: bool = test_add_markers_to_text()
    s2: bool = test_generate_grouped_data_interface()
    s3: bool = test_error_handling()
    s4: bool = test_parse_topic_ranges()
    s5: bool = test_normalize_topic_ranges()

    if s1 and s2 and s3 and s4 and s5:
        print("\nAll technical tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed!")
        sys.exit(1)
