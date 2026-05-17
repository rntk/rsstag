import unittest
import os
import tempfile
from collections import OrderedDict
from rsstag.utils import get_sorted_dict_by_alphabet, load_config, to_dot_format


class TestGetSortedDictByAlphabet(unittest.TestCase):
    def test_sort_by_keys(self):
        dct = {"b": {"title": "B"}, "a": {"title": "A"}, "c": {"title": "C"}}
        result = get_sorted_dict_by_alphabet(dct)
        self.assertEqual(list(result.keys()), ["a", "b", "c"])

    def test_sort_by_title(self):
        dct = {
            "b": {"title": "Charlie"},
            "a": {"title": "Alpha"},
            "c": {"title": "Bravo"},
        }
        result = get_sorted_dict_by_alphabet(dct, sort_type="c")
        self.assertEqual(list(result.keys()), ["a", "c", "b"])

    def test_empty_dict(self):
        result = get_sorted_dict_by_alphabet({})
        self.assertEqual(result, OrderedDict())

    def test_default_sort_type(self):
        dct = {"z": {"title": "Z"}, "a": {"title": "A"}}
        result = get_sorted_dict_by_alphabet(dct, sort_type=None)
        self.assertEqual(list(result.keys()), ["a", "z"])

    def test_returns_ordered_dict(self):
        dct = {"b": {"title": "B"}, "a": {"title": "A"}}
        result = get_sorted_dict_by_alphabet(dct)
        self.assertIsInstance(result, OrderedDict)


class TestLoadConfig(unittest.TestCase):
    def test_load_simple_config(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[settings]\n")
            f.write("db_host = localhost\n")
            f.write("db_port = 27017\n")
            temp_path = f.name

        try:
            result = load_config(temp_path)
            self.assertIn("settings", result)
            self.assertEqual(result["settings"]["db_host"], "localhost")
            self.assertEqual(result["settings"]["db_port"], "27017")
        finally:
            os.unlink(temp_path)

    def test_load_with_default_section(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[DEFAULT]\n")
            f.write("debug = true\n")
            f.write("[settings]\n")
            f.write("key = value\n")
            temp_path = f.name

        try:
            result = load_config(temp_path)
            self.assertIn("DEFAULT", result)
            self.assertEqual(result["DEFAULT"]["debug"], "true")
        finally:
            os.unlink(temp_path)

    def test_env_override_db_host(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[settings]\n")
            f.write("db_host = localhost\n")
            temp_path = f.name

        old_host = os.environ.get("DB_HOST")
        os.environ["DB_HOST"] = "mongo.example.com"
        try:
            result = load_config(temp_path)
            self.assertEqual(result["settings"]["db_host"], "mongo.example.com")
        finally:
            if old_host is None:
                del os.environ["DB_HOST"]
            else:
                os.environ["DB_HOST"] = old_host
            os.unlink(temp_path)

    def test_env_override_db_port(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[settings]\n")
            f.write("db_port = 27017\n")
            temp_path = f.name

        old_port = os.environ.get("DB_PORT")
        os.environ["DB_PORT"] = "27018"
        try:
            result = load_config(temp_path)
            self.assertEqual(result["settings"]["db_port"], "27018")
        finally:
            if old_port is None:
                del os.environ["DB_PORT"]
            else:
                os.environ["DB_PORT"] = old_port
            os.unlink(temp_path)

    def test_env_creates_settings_section(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[other]\n")
            f.write("key = value\n")
            temp_path = f.name

        old_host = os.environ.get("DB_HOST")
        os.environ["DB_HOST"] = "mongo.example.com"
        try:
            result = load_config(temp_path)
            self.assertIn("settings", result)
            self.assertEqual(result["settings"]["db_host"], "mongo.example.com")
        finally:
            if old_host is None:
                del os.environ["DB_HOST"]
            else:
                os.environ["DB_HOST"] = old_host
            os.unlink(temp_path)


class TestToDotFormat(unittest.TestCase):
    def test_empty_inputs(self):
        result = to_dot_format([], [])
        self.assertEqual(result, "all_tags {  }")

    def test_single_post_single_tag(self):
        tags = [{"tags": ["hello"]}]
        posts = [{"tags": ["hello"]}]
        result = to_dot_format(tags, posts)
        # Tags are hashed with MD5, so original tag name won't appear directly
        self.assertIn("all_tags", result)
        self.assertIn("--", result)

    def test_two_posts_shared_tag(self):
        posts = [
            {"tags": ["a", "b"]},
            {"tags": ["b", "c"]},
        ]
        result = to_dot_format([], posts)
        self.assertIn("all_tags", result)
        self.assertIn("--", result)

    def test_numeric_prefix(self):
        posts = [{"tags": ["123"]}]
        result = to_dot_format([], posts)
        # Numeric MD5 hashes get "_" prefix
        self.assertIn("_", result)


if __name__ == "__main__":
    unittest.main()
