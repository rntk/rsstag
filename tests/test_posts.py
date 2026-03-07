import unittest
import gzip
from rsstag.posts import RssTagPosts, PostLemmaSentence
from tests.db_utils import DBHelper


class TestRssTagPosts(unittest.TestCase):
    def setUp(self):
        self.db_helper = DBHelper(port=8765)
        self.db = self.db_helper.create_test_db()
        self.posts = RssTagPosts(self.db)
        self.owner = "test_user"
        self.other_owner = "other_user"

    def tearDown(self):
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()

    def test_prepare(self):
        self.posts.prepare()
        indices = self.db.posts.index_information()
        for index in self.posts.indexes:
            self.assertIn(f"{index}_1", indices)

    def test_get_by_category(self):
        data = {
            "posts": [
                {
                    "owner": self.owner,
                    "category_id": "cat1",
                    "read": False,
                    "feed_id": "f1",
                    "unix_date": 100,
                    "pid": "p1",
                },
                {
                    "owner": self.owner,
                    "category_id": "cat1",
                    "read": True,
                    "feed_id": "f1",
                    "unix_date": 200,
                    "pid": "p2",
                },
                {
                    "owner": self.owner,
                    "category_id": "cat2",
                    "read": False,
                    "feed_id": "f2",
                    "unix_date": 300,
                    "pid": "p3",
                },
                {
                    "owner": self.other_owner,
                    "category_id": "cat1",
                    "read": False,
                    "feed_id": "f3",
                    "unix_date": 400,
                    "pid": "p4",
                },
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)

        # Test owner filtering
        results = list(self.posts.get_by_category(self.owner))
        self.assertEqual(len(results), 3)

        # Test category filtering
        results = list(self.posts.get_by_category(self.owner, category="cat1"))
        self.assertEqual(len(results), 2)

        # Test only_unread filtering
        results = list(self.posts.get_by_category(self.owner, only_unread=True))
        self.assertEqual(len(results), 2)
        for p in results:
            self.assertFalse(p["read"])

    def test_get_all(self):
        data = {
            "posts": [
                {"owner": self.owner, "read": False},
                {"owner": self.owner, "read": True},
                {"owner": self.other_owner, "read": False},
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)

        results = list(self.posts.get_all(self.owner))
        self.assertEqual(len(results), 2)

        results = list(self.posts.get_all(self.owner, only_unread=True))
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["read"])

    def test_get_grouped_stat(self):
        data = {
            "posts": [
                {
                    "owner": self.owner,
                    "feed_id": "f1",
                    "category_id": "c1",
                    "read": False,
                },
                {
                    "owner": self.owner,
                    "feed_id": "f1",
                    "category_id": "c1",
                    "read": True,
                },
                {
                    "owner": self.owner,
                    "feed_id": "f2",
                    "category_id": "c2",
                    "read": False,
                },
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)

        results = list(self.posts.get_grouped_stat(self.owner))
        self.assertEqual(len(results), 2)

        f1_stat = next(r for r in results if r["_id"] == "f1")
        self.assertEqual(f1_stat["count"], 2)
        self.assertEqual(f1_stat["category_id"], "c1")

    def test_get_by_tags(self):
        data = {
            "posts": [
                {
                    "owner": self.owner,
                    "tags": ["t1", "t2"],
                    "read": False,
                    "feed_id": "f1",
                    "unix_date": 100,
                    "pid": "p1",
                },
                {
                    "owner": self.owner,
                    "tags": ["t1"],
                    "read": False,
                    "feed_id": "f1",
                    "unix_date": 200,
                    "pid": "p2",
                },
                {
                    "owner": self.owner,
                    "tags": ["t2"],
                    "read": False,
                    "feed_id": "f1",
                    "unix_date": 300,
                    "pid": "p3",
                },
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)

        results = list(self.posts.get_by_tags(self.owner, ["t1"]))
        self.assertEqual(len(results), 2)

        results = list(self.posts.get_by_tags(self.owner, ["t1", "t2"]))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["pid"], "p1")

    def test_get_by_bi_grams(self):
        data = {
            "posts": [
                {
                    "owner": self.owner,
                    "bi_grams": ["b1", "b2"],
                    "feed_id": "f1",
                    "unix_date": 100,
                },
                {
                    "owner": self.owner,
                    "bi_grams": ["b1"],
                    "feed_id": "f1",
                    "unix_date": 200,
                },
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)

        results = list(self.posts.get_by_bi_grams(self.owner, ["b1"]))
        self.assertEqual(len(results), 2)

        results = list(self.posts.get_by_bi_grams(self.owner, ["b1", "b2"]))
        self.assertEqual(len(results), 1)

    def test_get_by_feed_id(self):
        data = {
            "posts": [
                {"owner": self.owner, "feed_id": "f1", "unix_date": 100},
                {"owner": self.owner, "feed_id": "f2", "unix_date": 200},
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)

        results = list(self.posts.get_by_feed_id(self.owner, "f1"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["feed_id"], "f1")

    def test_get_by_pid_and_id(self):
        data = {
            "posts": [
                {"owner": self.owner, "pid": "p1", "id": "id1"},
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)

        p = self.posts.get_by_pid(self.owner, "p1")
        self.assertIsNotNone(p)
        self.assertEqual(p["pid"], "p1")

        p = self.posts.get_by_id(self.owner, "id1")
        self.assertIsNotNone(p)
        self.assertEqual(p["id"], "id1")

    def test_get_by_pids(self):
        data = {
            "posts": [
                {"owner": self.owner, "pid": "p1"},
                {"owner": self.owner, "pid": "p2"},
                {"owner": self.owner, "pid": "p3"},
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)

        results = list(self.posts.get_by_pids(self.owner, ["p1", "p3"]))
        self.assertEqual(len(results), 2)
        pids = [r["pid"] for r in results]
        self.assertIn("p1", pids)
        self.assertIn("p3", pids)

    def test_change_status(self):
        data = {
            "posts": [
                {"owner": self.owner, "pid": "p1", "read": False},
                {"owner": self.owner, "pid": "p2", "read": False},
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)

        self.posts.change_status(self.owner, ["p1"], True)
        p1 = self.db.posts.find_one({"pid": "p1"})
        self.assertTrue(p1["read"])
        p2 = self.db.posts.find_one({"pid": "p2"})
        self.assertFalse(p2["read"])

    def test_get_stat(self):
        data = {
            "posts": [
                {"owner": self.owner, "read": True},
                {"owner": self.owner, "read": False},
                {"owner": self.owner, "read": False},
            ],
            "tags": [
                {"owner": self.owner, "tag": "t1"},
                {"owner": self.owner, "tag": "t2"},
            ],
        }
        self.db_helper.init_db_from_dict(self.db, data)

        stat = self.posts.get_stat(self.owner)
        self.assertEqual(stat["read"], 1)
        self.assertEqual(stat["unread"], 2)
        self.assertEqual(stat["tags"], 2)

    def test_set_clusters(self):
        data = {
            "posts": [
                {"owner": self.owner, "pid": "p1"},
                {"owner": self.owner, "pid": "p2"},
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)

        similars = {"cluster1": ["p1", "p2"]}
        self.posts.set_clusters(self.owner, similars)

        p1 = self.db.posts.find_one({"pid": "p1"})
        self.assertIn("cluster1", p1["clusters"])

    def test_get_by_clusters(self):
        data = {
            "posts": [
                {
                    "owner": self.owner,
                    "clusters": ["c1", "c2"],
                    "feed_id": "f1",
                    "unix_date": 100,
                },
                {
                    "owner": self.owner,
                    "clusters": ["c1"],
                    "feed_id": "f1",
                    "unix_date": 200,
                },
                {
                    "owner": self.owner,
                    "clusters": ["c3"],
                    "feed_id": "f1",
                    "unix_date": 300,
                },
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)

        results = list(self.posts.get_by_clusters(self.owner, ["c1"]))
        self.assertEqual(len(results), 2)

        results = list(self.posts.get_by_clusters(self.owner, ["c1", "c3"]))
        self.assertEqual(len(results), 3)

    def test_get_clusters_method(self):
        posts = [
            {"clusters": ["c1", "c2"]},
            {"clusters": ["c2", "c3"]},
            {"no_clusters": "here"},
        ]
        clusters = self.posts.get_clusters(posts)
        self.assertEqual(clusters, {"c1", "c2", "c3"})

    def test_count(self):
        data = {
            "posts": [
                {"owner": self.owner},
                {"owner": self.owner},
                {"owner": self.other_owner},
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)
        self.assertEqual(self.posts.count(self.owner), 2)

    def test_get_neighbors_by_unix_date(self):
        data = {
            "posts": [
                {"owner": self.owner, "unix_date": 10, "pid": "p1"},
                {"owner": self.owner, "unix_date": 20, "pid": "p2"},
                {"owner": self.owner, "unix_date": 30, "pid": "p3"},
                {"owner": self.owner, "unix_date": 40, "pid": "p4"},
                {"owner": self.owner, "unix_date": 50, "pid": "p5"},
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)

        neighbors = self.posts.get_neighbors_by_unix_date(self.owner, 30, 1)
        # Should return p2 (closest < 30) and p4 (closest > 30)
        pids = [p["pid"] for p in neighbors]
        self.assertIn("p2", pids)
        self.assertIn("p4", pids)
        self.assertEqual(len(pids), 2)

    def test_post_lemma_sentence(self):
        lemmas1 = "word1 word2"
        lemmas2 = "word3 word4"
        data = {
            "posts": [
                {"owner": self.owner, "lemmas": gzip.compress(lemmas1.encode("utf-8"))},
                {"owner": self.owner, "lemmas": gzip.compress(lemmas2.encode("utf-8"))},
            ]
        }
        self.db_helper.init_db_from_dict(self.db, data)

        # Test default (no split)
        it = PostLemmaSentence(self.db, self.owner)
        results = list(it)
        self.assertIn(lemmas1, results)
        self.assertIn(lemmas2, results)

        # Test split
        it_split = PostLemmaSentence(self.db, self.owner, split=True)
        results_split = list(it_split)
        self.assertIn(["word1", "word2"], results_split)
        self.assertIn(["word3", "word4"], results_split)

        self.assertEqual(it.count(), 2)


if __name__ == "__main__":
    unittest.main()
