import unittest
import os
import json
from tests.db_utils import DBHelper


class TestDBUtils(unittest.TestCase):
    def setUp(self):
        # Default to localhost:27017 for testing, but can be overridden by env vars if needed
        self.db_helper = DBHelper()
        self.db = self.db_helper.create_test_db()

    def tearDown(self):
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()

    def test_db_creation(self):
        self.assertTrue(self.db.name.startswith("rsstag_test_"))
        # Check if we can write to it
        self.db.test_collection.insert_one({"test": "data"})
        doc = self.db.test_collection.find_one({"test": "data"})
        self.assertIsNotNone(doc)
        self.assertEqual(doc["test"], "data")

    def test_init_from_dict(self):
        data = {
            "users": [{"name": "Alice"}, {"name": "Bob"}],
            "posts": [{"title": "Post 1"}],
        }
        self.db_helper.init_db_from_dict(self.db, data)
        self.assertEqual(self.db.users.count_documents({}), 2)
        self.assertEqual(self.db.posts.count_documents({}), 1)

    def test_init_from_json(self):
        temp_file = "test_data.json"
        data = {"tags": [{"tag": "python"}, {"tag": "mongodb"}]}
        with open(temp_file, "w") as f:
            json.dump(data, f)

        try:
            self.db_helper.init_db_from_json(self.db, temp_file)
            self.assertEqual(self.db.tags.count_documents({}), 2)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)


if __name__ == "__main__":
    unittest.main()
