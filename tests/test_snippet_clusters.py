import unittest

from rsstag.snippet_clusters import RssTagSnippetClusters
from tests.db_utils import DBHelper


class TestRssTagSnippetClusters(unittest.TestCase):
    def setUp(self) -> None:
        self.db_helper = DBHelper(port=8765)
        self.db = self.db_helper.create_test_db()
        self.storage = RssTagSnippetClusters(self.db)
        self.owner = "snippet-owner"
        self.storage.prepare()

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()

    def test_replace_clusters_overwrites_previous_owner_data(self) -> None:
        initial = [
            {
                "cluster_id": 1,
                "title": "alpha",
                "item_count": 2,
                "post_ids": ["p1"],
                "snippet_refs": [{"post_id": "p1", "topic": "Topic", "indices": [1, 2]}],
            }
        ]
        updated = [
            {
                "cluster_id": 7,
                "title": "beta",
                "item_count": 1,
                "post_ids": ["p2"],
                "snippet_refs": [{"post_id": "p2", "topic": "Other", "indices": [4]}],
            }
        ]

        self.assertTrue(self.storage.replace_clusters(self.owner, initial))
        self.assertTrue(self.storage.replace_clusters(self.owner, updated))

        docs = list(self.storage.get_all_by_owner(self.owner))
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["cluster_id"], 7)
        self.assertEqual(docs[0]["title"], "beta")
        self.assertIn("updated_at", docs[0])

    def test_get_by_cluster_id_returns_cluster(self) -> None:
        payload = [
            {
                "cluster_id": 3,
                "title": "gamma",
                "item_count": 1,
                "post_ids": ["p3"],
                "snippet_refs": [{"post_id": "p3", "topic": "Topic", "indices": [6]}],
            }
        ]
        self.storage.replace_clusters(self.owner, payload)

        cluster = self.storage.get_by_cluster_id(self.owner, 3)

        self.assertIsNotNone(cluster)
        self.assertEqual(cluster["title"], "gamma")


if __name__ == "__main__":
    unittest.main()
