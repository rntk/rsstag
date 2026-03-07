import unittest
from rsstag.post_grouping import RssTagPostGrouping
from tests.db_utils import DBHelper

class TestRssTagPostGrouping(unittest.TestCase):
    def setUp(self):
        self.db_helper = DBHelper(port=8765)
        self.db = self.db_helper.create_test_db()
        self.post_grouping = RssTagPostGrouping(self.db)
        self.owner = "test_user"
        self.post_grouping.prepare()

    def tearDown(self):
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()

    def test_save_and_get_grouped_posts(self):
        post_ids = [1, 2, 3]
        sentences = [{"number": 0, "text": "start"}, {"number": 1, "text": "end"}]
        groups = {"topic1": [0, 1]}
        
        saved = self.post_grouping.save_grouped_posts(self.owner, post_ids, sentences, groups)
        self.assertTrue(saved)
        
        doc = self.post_grouping.get_grouped_posts(self.owner, post_ids)
        self.assertIsNotNone(doc)
        self.assertEqual(doc["owner"], self.owner)
        self.assertEqual(doc["sentences"], sentences)
        self.assertEqual(doc["groups"], groups)

    def test_update_snippets_read_status(self):
        post_id = 100
        sentences = [
            {"number": 0, "text": "s0", "read": False},
            {"number": 1, "text": "s1", "read": False},
            {"number": 2, "text": "s2", "read": False}
        ]
        groups = {"t1": [0, 1, 2]}
        self.post_grouping.save_grouped_posts(self.owner, [post_id], sentences, groups)

        # Mark 0 and 1 as read
        all_read = self.post_grouping.update_snippets_read_status(self.owner, post_id, [0, 1], True)
        self.assertFalse(all_read) # s2 is still unread

        doc = self.post_grouping.get_grouped_posts(self.owner, [post_id])
        self.assertTrue(doc["sentences"][0]["read"])
        self.assertTrue(doc["sentences"][1]["read"])
        self.assertFalse(doc["sentences"][2]["read"])

        # Mark 2 as read
        all_read = self.post_grouping.update_snippets_read_status(self.owner, post_id, [2], True)
        self.assertTrue(all_read) # All are read now

        doc = self.post_grouping.get_grouped_posts(self.owner, [post_id])
        for s in doc["sentences"]:
            self.assertTrue(s["read"])

        # Mark 0 as unread
        all_read = self.post_grouping.update_snippets_read_status(self.owner, post_id, [0], False)
        self.assertFalse(all_read)

        doc = self.post_grouping.get_grouped_posts(self.owner, [post_id])
        self.assertFalse(doc["sentences"][0]["read"])

    def test_post_ids_hash_is_stable_for_int_and_string_ids(self):
        post_id = 321
        sentences = [{"number": 0, "text": "s0"}]
        groups = {"topic": [0]}

        saved = self.post_grouping.save_grouped_posts(
            self.owner,
            [post_id],
            sentences,
            groups,
        )
        self.assertTrue(saved)

        by_int = self.post_grouping.get_grouped_posts(self.owner, [post_id])
        by_str = self.post_grouping.get_grouped_posts(self.owner, [str(post_id)])

        self.assertIsNotNone(by_int)
        self.assertIsNotNone(by_str)
        self.assertEqual(by_int["_id"], by_str["_id"])

    def test_mark_sequences_read(self):
        post_id = 200
        sentences = [
            {"number": 0, "text": "s0", "read": False},
            {"number": 1, "text": "s1", "read": True}
        ]
        self.post_grouping.save_grouped_posts(self.owner, [post_id], sentences, {})

        # Mark all read
        self.post_grouping.mark_sequences_read(self.owner, post_id, True)
        doc = self.post_grouping.get_grouped_posts(self.owner, [post_id])
        for s in doc["sentences"]:
            self.assertTrue(s["read"])

        # Mark all unread
        self.post_grouping.mark_sequences_read(self.owner, post_id, False)
        doc = self.post_grouping.get_grouped_posts(self.owner, [post_id])
        for s in doc["sentences"]:
            self.assertFalse(s["read"])

if __name__ == "__main__":
    unittest.main()
