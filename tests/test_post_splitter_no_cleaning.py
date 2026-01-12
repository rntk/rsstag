import sys
import re

# Add the project directory to sys.path
sys.path.append(
    "/home/rnt/backup/cbed520c-c1a0-4091-ad74-a175cfd2acb6/home/rnt/dev/python/rsstag"
)

from rsstag.post_splitter import PostSplitter, PostSplitterError


def test_add_markers_to_text_with_html():
    splitter = PostSplitter()
    html_text = (
        "This is a <b>bold</b> word. And <a href='http://example.com'>a link</a> here."
    )

    result = splitter.add_markers_to_text(html_text)
    tagged_text = result["tagged_text"]

    print(f"Original: {html_text}")
    print(f"Tagged:   {tagged_text}")

    # Check if markers are NOT inside tags
    # A marker looks like {ws1}
    # Find all markers and check if they are inside <...>
    markers = re.finditer(r"\{ws\d+\}", tagged_text)
    for m in markers:
        # Check if this marker is inside < >
        before = tagged_text[: m.start()]
        after = tagged_text[m.end() :]
        if before.count("<") > before.count(">") and after.count(">") > after.count(
            "<"
        ):
            print(f"FAILED: Marker {m.group()} is inside a tag!")
            return False

    print("SUCCESS: No markers inside tags.")
    return True


def test_generate_grouped_data_interface():
    # Mock LLM handler
    class MockLLM:
        def call(self, prompts, temperature=0.0):
            return "1 - 2"  # Dummy range

    splitter = PostSplitter(MockLLM())
    # We also need to mock _generate_title_for_chunk and _resolve_gaps to avoid more LLM calls
    splitter._generate_title_for_chunk = lambda x: "Test Title"
    splitter._generate_title_for_chunk = lambda x: "Test Title"
    splitter._validate_boundaries = lambda b, m: b

    html_content = "Sentence one. Sentence <b>two</b> with tag."
    result = splitter.generate_grouped_data(html_content, "Post Title")

    if not result:
        print("FAILED: generate_grouped_data returned None")
        return False

    sentences = result["sentences"]
    print(f"Sentences: {sentences}")

    # Check if we got sentences
    if not sentences:
        print("FAILED: No sentences found.")
        return False

    print(f"SUCCESS: Generated {len(sentences)} sentences.")
    return True


def test_error_handling():
    # Mock LLM handler that raises exception
    class BrokenLLM:
        def call(self, prompts, temperature=0.0):
            raise Exception("API Error")

    splitter = PostSplitter(BrokenLLM())

    try:
        splitter.generate_grouped_data("Some text", "Title")
        print("FAILED: Should have raised PostSplitterError")
        return False
    except PostSplitterError as e:
        print(f"SUCCESS: Caught expected error: {e}")
        return True
    except Exception as e:
        print(f"FAILED: Caught unexpected exception type: {type(e)}")
        return False

    return True


if __name__ == "__main__":
    s1 = test_add_markers_to_text_with_html()
    s2 = test_generate_grouped_data_interface()
    s3 = test_error_handling()

    if s1 and s2 and s3:
        print("\nAll technical tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed!")
        sys.exit(1)
