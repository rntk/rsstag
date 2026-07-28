import gzip
import unittest
from typing import Any

from rsstag.web.posts import _build_topics_tree, _decode_post_lemmas


class TestWebPostsTopicsTree(unittest.TestCase):
    def test_parent_count_sums_descendants_with_shared_post(self) -> None:
        topic_counts: dict[str, dict] = {
            "Philosophy > Religion > Gods Debris (Part 1)": {
                "count": 1,
                "posts": ["101"],
            },
            "Philosophy > Religion > Gods Debris (Part 2 - Holy Land Debate)": {
                "count": 1,
                "posts": ["101"],
            },
        }

        tree: list[dict] = _build_topics_tree(topic_counts)

        philosophy: dict = tree[0]
        religion: dict = philosophy["children"][0]
        self.assertEqual(philosophy["count"], 2)
        self.assertEqual(religion["count"], 2)
        self.assertEqual(len(philosophy["posts"]), 1)


class TestDecodePostLemmas(unittest.TestCase):
    def test_decodes_processed_lemmas(self) -> None:
        post: dict[str, Any] = {
            "pid": "post-1",
            "lemmas": gzip.compress(b"hello world"),
        }

        self.assertEqual(_decode_post_lemmas(post), "hello world")

    def test_returns_empty_text_while_post_is_unprocessed(self) -> None:
        post: dict[str, Any] = {"pid": "post-1"}

        self.assertEqual(_decode_post_lemmas(post), "")


if __name__ == "__main__":
    unittest.main()
