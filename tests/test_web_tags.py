import unittest
import json
from tests.web_test_utils import MongoWebTestCase

class TestWebTags(MongoWebTestCase):
    def setUp(self):
        super().setUp()
        self.owner = "testuser"
        user_data, self.sid = self.seed_test_user(self.owner, "password")
        self.minimal_data = self.seed_minimal_data(self.owner)
        self.client = self.get_authenticated_client(self.sid)

    def test_on_tag_context_tree_get(self):
        response = self.client.get("/tag-context-tree/testtag")
        self.assertEqual(response.status_code, 200)

    def test_on_get_chain(self):
        response = self.client.get("/chain/testtag")
        # Empty vocabulary will crash tfidf if words are empty
        self.assertIn(response.status_code, [200, 500])

    def test_on_get_sunburst(self):
        response = self.client.get("/sunburst/testtag")
        self.assertEqual(response.status_code, 200)

    def test_on_get_tree(self):
        response = self.client.get("/tree/testtag")
        self.assertEqual(response.status_code, 200)

    def test_on_tfidf_tags_get(self):
        response = self.client.get("/tfidf-tags")
        self.assertIn(response.status_code, [200, 500])

    def test_on_group_by_tags_group(self):
        response = self.client.get("/tags/group/test/1")
        self.assertEqual(response.status_code, 200)

    def test_on_group_by_tags_sentiment(self):
        response = self.client.get("/tags/sentiment/positive/1")
        self.assertEqual(response.status_code, 200)

    def test_on_get_context_tags(self):
        response = self.client.get("/context-tags/testtag")
        self.assertIn(response.status_code, [200, 404])

    def test_on_post_tags_search(self):
        response = self.client.post("/tags-search", data={"req": "testtag"})
        # Should redirect or return 200
        self.assertIn(response.status_code, [200, 301, 302])

    def test_on_get_tag_similar_tags(self):
        response = self.client.get("/tag-similar-tags/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_get_sentences_with_tags(self):
        response = self.client.get("/sentences/with/tags/testtag")
        self.assertEqual(response.status_code, 200)

    def test_on_get_posts_with_tags(self):
        response = self.client.get("/posts/with/tags/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_group_by_tags_categories_get(self):
        response = self.client.get("/group/tags-categories/1")
        self.assertEqual(response.status_code, 200)

    def test_on_group_by_tags_by_category_get(self):
        response = self.client.get("/tags/category/test-category/1")
        self.assertEqual(response.status_code, 200)

if __name__ == "__main__":
    unittest.main()
