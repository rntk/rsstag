import unittest

from rsstag.web.posts import _build_topics_tree


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


if __name__ == "__main__":
    unittest.main()
