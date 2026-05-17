import unittest
from rsstag.read_state import ReadStateService


class TestReadStateServiceNormalizeIndices(unittest.TestCase):
    def test_empty_list(self):
        result = ReadStateService._normalize_indices([])
        self.assertEqual(result, [])

    def test_single_int(self):
        result = ReadStateService._normalize_indices([1, 2, 3])
        self.assertEqual(result, [1, 2, 3])

    def test_string_numbers(self):
        result = ReadStateService._normalize_indices(["1", "2", "3"])
        self.assertEqual(result, [1, 2, 3])

    def test_mixed_types(self):
        result = ReadStateService._normalize_indices([1, "2", 3.0])
        self.assertEqual(result, [1, 2, 3])

    def test_invalid_values_skipped(self):
        result = ReadStateService._normalize_indices([1, "abc", None, "3"])
        self.assertEqual(result, [1, 3])

    def test_non_list_input(self):
        result = ReadStateService._normalize_indices("not a list")
        self.assertEqual(result, [])

    def test_none_input(self):
        result = ReadStateService._normalize_indices(None)
        self.assertEqual(result, [])

    def test_negative_numbers(self):
        result = ReadStateService._normalize_indices([-1, -5])
        self.assertEqual(result, [-1, -5])

    def test_float_string(self):
        # Float strings cannot be converted directly by int(), so they are skipped
        result = ReadStateService._normalize_indices(["1.5"])
        self.assertEqual(result, [])


class TestReadStateServiceCollectCounters(unittest.TestCase):
    def test_empty_post(self):
        result = ReadStateService._collect_counters({})
        self.assertEqual(result, ({}, {}, {}))

    def test_post_with_tags(self):
        post = {"tags": ["apple", "banana"]}
        tags, bi_grams, letters = ReadStateService._collect_counters(post)
        self.assertEqual(tags, {"apple": 1, "banana": 1})
        self.assertEqual(letters, {"a": 1, "b": 1})

    def test_post_with_duplicate_tags(self):
        post = {"tags": ["apple", "apple"]}
        tags, bi_grams, letters = ReadStateService._collect_counters(post)
        self.assertEqual(tags, {"apple": 2})
        self.assertEqual(letters, {"a": 2})

    def test_post_with_bi_grams(self):
        post = {"tags": [], "bi_grams": ["apple banana", "banana cherry"]}
        tags, bi_grams, letters = ReadStateService._collect_counters(post)
        self.assertEqual(bi_grams, {"apple banana": 1, "banana cherry": 1})

    def test_post_with_mixed_content(self):
        post = {"tags": ["apple"], "bi_grams": ["apple banana"]}
        tags, bi_grams, letters = ReadStateService._collect_counters(post)
        self.assertEqual(tags, {"apple": 1})
        self.assertEqual(bi_grams, {"apple banana": 1})
        self.assertEqual(letters, {"a": 1})

    def test_empty_string_tags_skipped(self):
        post = {"tags": ["apple", "", "banana"]}
        tags, _, _ = ReadStateService._collect_counters(post)
        self.assertEqual(tags, {"apple": 1, "banana": 1})

    def test_empty_string_bi_grams_skipped(self):
        post = {"bi_grams": ["a b", "", "c d"]}
        _, bi_grams, _ = ReadStateService._collect_counters(post)
        self.assertEqual(bi_grams, {"a b": 1, "c d": 1})

    def test_tag_to_string_conversion(self):
        post = {"tags": [123, "abc"]}
        tags, _, _ = ReadStateService._collect_counters(post)
        self.assertEqual(tags, {"123": 1, "abc": 1})


if __name__ == "__main__":
    unittest.main()
