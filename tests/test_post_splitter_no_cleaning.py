import sys
import re
from typing import Any, Dict, Iterator, List, Tuple

# Add the project directory to sys.path
sys.path.append(
    "/home/rnt/backup/cbed520c-c1a0-4091-ad74-a175cfd2acb6/home/rnt/dev/python/rsstag"
)

from rsstag.post_splitter import PostSplitter, PostSplitterError


def test_add_markers_to_text_with_html() -> bool:
    splitter: PostSplitter = PostSplitter()
    html_text: str = (
        "This is a <b>bold</b> word. And <a href='http://example.com'>a link</a> here."
    )

    result: Dict[str, Any] = splitter.add_markers_to_text(html_text)
    tagged_text: str = result["tagged_text"]

    print(f"Original: {html_text}")
    print(f"Tagged:   {tagged_text}")

    # Check if markers are NOT inside tags
    # A marker looks like {ws1}
    # Find all markers and check if they are inside <...>
    markers: Iterator[re.Match[str]] = re.finditer(r"\{ws\d+\}", tagged_text)
    for m in markers:
        # Check if this marker is inside < >
        before: str = tagged_text[: m.start()]
        after: str = tagged_text[m.end() :]
        if before.count("<") > before.count(">") and after.count(">") > after.count(
            "<"
        ):
            print(f"FAILED: Marker {m.group()} is inside a tag!")
            return False

    print("SUCCESS: No markers inside tags.")
    return True


def test_generate_grouped_data_interface() -> bool:
    # Mock LLM handler
    class MockLLM:
        def call(self, prompts: List[str], temperature: float = 0.0) -> str:
            return "Topic A: (0, 0)-(1, 3)"  # Dummy topic range

    def mock_normalize_topic_ranges(
        ranges: List[Tuple[str, int, int]], max_marker: int
    ) -> List[Tuple[str, int, int]]:
        return ranges

    splitter: PostSplitter = PostSplitter(MockLLM())
    # We also need to mock _normalize_topic_ranges to avoid more LLM calls
    splitter._normalize_topic_ranges = mock_normalize_topic_ranges

    html_content: str = "Sentence one. Sentence <b>two</b> with tag."
    result: Dict[str, Any] = splitter.generate_grouped_data(html_content, "Post Title")

    if not result:
        print("FAILED: generate_grouped_data returned None")
        return False

    sentences: List[Dict[str, Any]] = result["sentences"]
    print(f"Sentences: {sentences}")

    # Check if we got sentences
    if not sentences:
        print("FAILED: No sentences found.")
        return False

    print(f"SUCCESS: Generated {len(sentences)} sentences.")
    return True


def test_error_handling() -> bool:
    # Mock LLM handler that raises exception
    class BrokenLLM:
        def call(self, prompts: List[str], temperature: float = 0.0) -> str:
            raise Exception("API Error")

    splitter: PostSplitter = PostSplitter(BrokenLLM())

    # The new behavior is to handle the error and return a fallback result (single chapter)
    # instead of raising an exception.
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

    print("SUCCESS: Error handled gracefully with fallback.")
    return True


if __name__ == "__main__":
    s1: bool = test_add_markers_to_text_with_html()
    s2: bool = test_generate_grouped_data_interface()
    s3: bool = test_error_handling()

    if s1 and s2 and s3:
        print("\nAll technical tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed!")
        sys.exit(1)
