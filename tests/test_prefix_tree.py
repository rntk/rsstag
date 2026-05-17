import unittest
from rsstag.prefix_tree import text2words, PrefixTreeBuilder


class TestText2Words(unittest.TestCase):
    def test_simple_text(self):
        self.assertEqual(text2words("hello world"), ["hello", "world"])

    def test_punctuation_removed(self):
        self.assertEqual(text2words("hello, world!"), ["hello", "world"])

    def test_multiple_spaces(self):
        self.assertEqual(text2words("hello   world"), ["hello", "world"])

    def test_empty_string(self):
        self.assertEqual(text2words(""), [])

    def test_only_punctuation(self):
        self.assertEqual(text2words("!!! ???"), [])

    def test_case_folding(self):
        self.assertEqual(text2words("Hello WORLD"), ["hello", "world"])

    def test_numbers_and_words(self):
        self.assertEqual(text2words("test123 hello"), ["test123", "hello"])


class TestPrefixTreeBuilder(unittest.TestCase):
    def test_empty_tree(self):
        builder = PrefixTreeBuilder()
        self.assertEqual(builder.tree, {})
        self.assertEqual(builder.get_tails("a"), [])
        self.assertEqual(builder.get_top_n(2), [])
        self.assertIsNone(builder.get_tree("a"))
        self.assertIsNone(builder.get_compact_tree("a"))

    def test_add_single_word(self):
        builder = PrefixTreeBuilder()
        builder.add_words_from_doc("hello")
        self.assertIn("h", builder.tree)
        self.assertEqual(builder.get_tails("h"), ["hello"])
        self.assertEqual(builder.get_tails("he"), ["hello"])
        self.assertEqual(builder.get_tails("hello"), ["hello"])

    def test_add_multiple_words(self):
        builder = PrefixTreeBuilder()
        builder.add_words_from_doc("hello world")
        self.assertEqual(sorted(builder.get_tails("h")), ["hello"])
        self.assertEqual(sorted(builder.get_tails("w")), ["world"])

    def test_common_prefix(self):
        builder = PrefixTreeBuilder()
        builder.add_words_from_doc("test testing tester")
        tails = builder.get_tails("te")
        # "test" is not a leaf (it has children "er" and "ing"), so only leaf tails are returned
        self.assertEqual(sorted(tails), ["tester", "testing"])

    def test_get_top_n(self):
        builder = PrefixTreeBuilder()
        builder.add_words_from_doc("apple apply apt")
        top2 = builder.get_top_n(2)
        # All prefixes of length 2: ap (count 3)
        self.assertEqual(len(top2), 1)
        self.assertEqual(top2[0], ("ap", 3))

    def test_get_top_n_multiple_prefixes(self):
        builder = PrefixTreeBuilder()
        builder.add_words_from_doc("cat car dog")
        top1 = builder.get_top_n(1)
        # Only first characters at root level: 'c' and 'd'
        self.assertEqual(len(top1), 2)
        counts = {prefix: count for prefix, count in top1}
        self.assertEqual(counts["c"], 2)
        self.assertEqual(counts["d"], 1)

    def test_str_representation(self):
        builder = PrefixTreeBuilder()
        builder.add_words_from_doc("hi")
        result = str(builder)
        self.assertIn("h", result)
        self.assertIn("i", result)

    def test_get_tree(self):
        builder = PrefixTreeBuilder()
        builder.add_words_from_doc("apple apply")
        tree = builder.get_tree("ap")
        self.assertIsNotNone(tree)
        self.assertEqual(tree["name"], "ap")
        self.assertTrue("children" in tree)

    def test_get_tree_not_found(self):
        builder = PrefixTreeBuilder()
        builder.add_words_from_doc("hello")
        self.assertIsNone(builder.get_tree("z"))

    def test_get_compact_tree(self):
        builder = PrefixTreeBuilder()
        builder.add_words_from_doc("test testing")
        compact = builder.get_compact_tree("t")
        self.assertIsNotNone(compact)
        # Single paths are merged, so "t" + "est" + "ing" becomes "testing"
        self.assertEqual(compact["name"], "testing")
        self.assertTrue("children" in compact)

    def test_get_compact_tree_not_found(self):
        builder = PrefixTreeBuilder()
        self.assertIsNone(builder.get_compact_tree("z"))

    def test_get_tails_no_match(self):
        builder = PrefixTreeBuilder()
        builder.add_words_from_doc("hello")
        self.assertEqual(builder.get_tails("z"), [])

    def test_get_tails_empty_prefix(self):
        builder = PrefixTreeBuilder()
        builder.add_words_from_doc("a ab abc")
        tails = builder.get_tails("")
        # "a" and "ab" are not leaves (they have children), only "abc" is
        self.assertEqual(sorted(tails), ["abc"])


if __name__ == "__main__":
    unittest.main()
