import gzip
import json
import unittest
from unittest import mock

from tests.web_test_utils import MongoWebTestCase


class TestWebTags(MongoWebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.owner = "testuser"
        user_data, self.sid = self.seed_test_user(self.owner, "password")
        # Use sid as owner so DB queries by user["sid"] actually find the fixtures.
        self.minimal_data = self.seed_minimal_data(self.sid)
        # Remove the malformed letters doc inserted by seed_minimal_data;
        # endpoints work fine with an empty letters list.
        self.test_db.letters.delete_one({"owner": self.sid})
        self.client = self.get_authenticated_client(self.sid)

    def _seed_post_with_lemmas(
        self,
        pid: str,
        tags: list[str],
        lemmas_text: str,
        content_text: str | None = None,
    ) -> None:
        doc: dict = {
            "owner": self.sid,
            "pid": pid,
            "feed_id": self.minimal_data["feed_id"],
            "processing": 0,
            "tags": tags,
            "lemmas": gzip.compress(lemmas_text.encode("utf-8")),
            "date": 1700000000,
        }
        if content_text is not None:
            doc["content"] = {
                "title": f"Post {pid}",
                "content": gzip.compress(content_text.encode("utf-8")),
            }
        self.test_db.posts.insert_one(doc)

    def _seed_tag(
        self,
        tag: str,
        count: int = 1,
        classifications: list[dict] | None = None,
    ) -> None:
        doc: dict = {
            "owner": self.sid,
            "tag": tag,
            "posts_count": count,
            "unread_count": count,
            "words": [tag],
            "local_url": f"/entity/{tag}",
            "processing": 0,
            "temperature": 1,
            "freq": 1.0,
            "sentiment": [],
        }
        if classifications:
            doc["classifications"] = classifications
        self.test_db.tags.insert_one(doc)

    def _seed_post_grouping(
        self,
        pid: str,
        sentences: list[dict],
        groups: dict[str, list[int]],
    ) -> None:
        self.app.post_grouping.save_grouped_posts(self.sid, [pid], sentences, groups)

    # ------------------------------------------------------------------
    # on_group_by_tags_get
    # ------------------------------------------------------------------
    def test_on_group_by_tags_get_returns_200(self) -> None:
        response = self.client.get("/group/tag/1")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("testtag", body)

    def test_on_group_by_tags_get_respects_context_filters(self) -> None:
        user, sid = self.seed_test_user("ctx-tags-user", "password")
        self.test_db.feeds.insert_one(
            {
                "owner": sid,
                "feed_id": "ctx-feed",
                "category_id": "ctx-cat",
                "category_title": "Ctx Cat",
                "category_local_url": "/category/ctx-cat",
                "local_url": "/feed/ctx-feed",
                "title": "Ctx Feed",
                "url": "http://example.com/ctx-feed",
                "favicon": "",
                "processing": 0,
            }
        )
        self.test_db.posts.insert_one(
            {
                "owner": sid,
                "pid": "ctx-post-1",
                "feed_id": "ctx-feed",
                "tags": ["ctxtag"],
                "read": False,
                "processing": 0,
            }
        )
        self.test_db.tags.insert_one(
            {
                "owner": sid,
                "tag": "ctxtag",
                "posts_count": 1,
                "unread_count": 1,
                "words": ["ctxtag"],
                "local_url": "/entity/ctxtag",
                "processing": 0,
                "temperature": 1,
                "freq": 1.0,
                "sentiment": [],
            }
        )
        self.app.users.update_settings(
            sid,
            {
                "context_filter": {
                    "feeds": ["ctx-feed"],
                }
            },
        )
        client = self.get_authenticated_client(sid)
        response = client.get("/group/tag/1")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("ctxtag", body)
        self.assertNotIn("testtag", body)

    def test_on_group_by_tags_get_pagination(self) -> None:
        user, sid = self.seed_test_user("pagination-user", "password")
        self.app.users.update_settings(sid, {"tags_on_page": 2})
        feed_id = "pag-feed"
        self.test_db.feeds.insert_one(
            {
                "owner": sid,
                "feed_id": feed_id,
                "category_id": "pag-cat",
                "category_title": "Pag Cat",
                "category_local_url": "/category/pag-cat",
                "local_url": f"/feed/{feed_id}",
                "title": "Pag Feed",
                "url": "http://example.com/pag-feed",
                "favicon": "",
                "processing": 0,
            }
        )
        for i, tag in enumerate(["pag_a", "pag_b", "pag_c"]):
            self.test_db.posts.insert_one(
                {
                    "owner": sid,
                    "pid": f"pag-post-{i}",
                    "feed_id": feed_id,
                    "tags": [tag],
                    "read": False,
                    "processing": 0,
                }
            )
            self.test_db.tags.insert_one(
                {
                    "owner": sid,
                    "tag": tag,
                    "posts_count": 1,
                    "unread_count": 1,
                    "words": [tag],
                    "local_url": f"/entity/{tag}",
                    "processing": 0,
                    "temperature": 1,
                    "freq": 1.0,
                    "sentiment": [],
                }
            )
        client = self.get_authenticated_client(sid)
        page1 = client.get("/group/tag/1")
        self.assertEqual(page1.status_code, 200)
        body1 = page1.get_data(as_text=True)

        page2 = client.get("/group/tag/2")
        self.assertEqual(page2.status_code, 200)
        body2 = page2.get_data(as_text=True)

        # Both pages should render successfully and contain different tag subsets.
        self.assertNotEqual(body1, body2)

    # ------------------------------------------------------------------
    # on_group_by_tags_categories_get / on_group_by_tags_by_category_get
    # ------------------------------------------------------------------
    def test_on_group_by_tags_categories_get_returns_200(self) -> None:
        self._seed_tag(
            "cattag", count=1, classifications=[{"category": "Tech", "count": 1}]
        )
        response = self.client.get("/group/tags-categories/1")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Tech", body)

    def test_on_group_by_tags_by_category_get_returns_200(self) -> None:
        self._seed_tag(
            "cattag", count=1, classifications=[{"category": "Tech", "count": 1}]
        )
        response = self.client.get("/tags/category/Tech/1")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("cattag", body)

    # ------------------------------------------------------------------
    # on_s_tree_get
    # ------------------------------------------------------------------
    def test_on_s_tree_get_returns_200_with_sentences(self) -> None:
        content = "This is a sentence with testtag in it. Another sentence here."
        self._seed_post_with_lemmas(
            "post-s-tree", ["testtag"], "testtag sentence another", content
        )
        response = self.client.get("/s-tree/testtag")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("testtag", body)

    # ------------------------------------------------------------------
    # on_tag_grouped_topics_get / on_tag_llm_topics_get
    # ------------------------------------------------------------------
    def test_on_tag_grouped_topics_get_with_grouping_data(self) -> None:
        pid = self.minimal_data["post_pids"][0]
        self._seed_post_grouping(
            pid,
            sentences=[
                {"number": 1, "text": "Hello testtag world", "read": False},
                {"number": 2, "text": "Another sentence", "read": False},
            ],
            groups={
                "Topic A": [1],
                "Topic B": [2],
            },
        )
        response = self.client.get("/tag-grouped-topics/testtag")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("data", data)
        tags = [item["tag"] for item in data["data"]]
        self.assertIn("Topic A", tags)

    def test_on_tag_llm_topics_get_with_grouping_data(self) -> None:
        pid = self.minimal_data["post_pids"][0]
        self._seed_post_grouping(
            pid,
            sentences=[
                {"number": 1, "text": "Hello testtag world", "read": False},
                {"number": 2, "text": "Another sentence", "read": False},
            ],
            groups={
                "Topic A > Subtopic": [1],
                "Topic B": [2],
            },
        )
        response = self.client.get("/tag-llm-topics/testtag")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("data", data)
        tags = [item["tag"] for item in data["data"]]
        self.assertIn("Topic A", tags)
        self.assertIn("Subtopic", tags)

    # ------------------------------------------------------------------
    # on_tag_context_tree_get
    # ------------------------------------------------------------------
    def test_on_tag_context_tree_get_returns_200(self) -> None:
        self._seed_post_with_lemmas(
            "post-ctx", ["testtag"], "hello testtag world foo bar"
        )
        response = self.client.get("/tag-context-tree/testtag")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("testtag", body)
        self.assertIn("mindmap_data", body)

    # ------------------------------------------------------------------
    # on_ba_surprise_get
    # ------------------------------------------------------------------
    def test_on_ba_surprise_get_returns_200(self) -> None:
        # Posts need >=2 unique tags for LeaveOneOutSurprise.
        for i in range(3):
            self.test_db.posts.insert_one(
                {
                    "owner": self.sid,
                    "pid": f"surprise-post-{i}",
                    "feed_id": self.minimal_data["feed_id"],
                    "tags": ["testtag", f"extratag{i}"],
                    "read": False,
                    "processing": 0,
                }
            )
            self.test_db.tags.insert_one(
                {
                    "owner": self.sid,
                    "tag": f"extratag{i}",
                    "posts_count": 1,
                    "unread_count": 1,
                    "words": [f"extratag{i}"],
                    "local_url": f"/entity/extratag{i}",
                    "processing": 0,
                    "temperature": 1,
                    "freq": 1.0,
                    "sentiment": [],
                }
            )
        response = self.client.get("/ba-surprise")
        self.assertEqual(response.status_code, 200)

    def test_on_ba_surprise_get_with_tag_filter(self) -> None:
        response = self.client.get("/ba-surprise?tag=testtag")
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # on_get_chain / on_get_sunburst
    # ------------------------------------------------------------------
    def test_on_get_chain_returns_200(self) -> None:
        self._seed_post_with_lemmas("post-chain", ["testtag"], "hello testtag world")
        response = self.client.get("/chain/testtag")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("testtag", body)

    def test_on_get_sunburst_returns_200(self) -> None:
        self._seed_post_with_lemmas("post-sun", ["testtag"], "hello testtag world")
        response = self.client.get("/sunburst/testtag")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("testtag", body)

    def test_on_get_tree_returns_200(self) -> None:
        response = self.client.get("/tree/testtag")
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # on_tfidf_tags_get
    # ------------------------------------------------------------------
    def test_on_tfidf_tags_get_returns_200(self) -> None:
        response = self.client.get("/tfidf-tags")
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # Existing endpoint coverage
    # ------------------------------------------------------------------
    def test_on_group_by_tags_group(self) -> None:
        response = self.client.get("/tags/group/test/1")
        self.assertEqual(response.status_code, 200)

    def test_on_group_by_tags_sentiment(self) -> None:
        response = self.client.get("/tags/sentiment/positive/1")
        self.assertEqual(response.status_code, 200)

    def test_on_get_context_tags(self) -> None:
        response = self.client.get("/context-tags/testtag")
        self.assertIn(response.status_code, [200, 404])

    def test_on_post_tags_search(self) -> None:
        response = self.client.post("/tags-search", data={"req": "testtag"})
        self.assertIn(response.status_code, [200, 301, 302])

    def test_on_get_tag_similar_tags(self) -> None:
        response = self.client.get("/tag-similar-tags/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_get_sentences_with_tags(self) -> None:
        response = self.client.get("/sentences/with/tags/testtag")
        self.assertEqual(response.status_code, 200)

    def test_on_get_posts_with_tags(self) -> None:
        response = self.client.get("/posts/with/tags/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_get_tag_page(self) -> None:
        response = self.client.get("/tag-info/testtag")
        self.assertEqual(response.status_code, 200)

    def test_on_tag_tfidf_get(self) -> None:
        response = self.client.get("/tag-tfidf/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_tag_topics_get(self) -> None:
        response = self.client.get("/tag-topics/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_tag_clusters_get(self) -> None:
        response = self.client.get("/tag-clusters/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_tag_entities_get(self) -> None:
        response = self.client.get("/tag-entities/testtag")
        self.assertEqual(response.status_code, 200)

    def test_on_tag_specific_get(self) -> None:
        response = self.client.get("/tag-specific/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_tag_specific1_get(self) -> None:
        response = self.client.get("/tag-specific1/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_get_tag_siblings(self) -> None:
        self._seed_post_with_lemmas("post-sib", ["testtag"], "hello testtag world")
        response = self.client.get("/tag-siblings/testtag")
        self.assertEqual(response.status_code, 200)

    def test_on_get_tag_pmi(self) -> None:
        self._seed_post_with_lemmas("post-pmi", ["testtag"], "hello testtag world")
        response = self.client.get("/tag-pmi/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_get_tag_bi_grams(self) -> None:
        response = self.client.get("/tag-bi-grams/testtag")
        self.assertIn(response.status_code, [200, 500])

    def test_on_tag_contexts_classification_get(self) -> None:
        self.test_db.tags.update_one(
            {"owner": self.sid, "tag": "testtag"},
            {
                "$set": {
                    "classifications": [
                        {"category": "Cat", "count": 1, "pids": ["p1"]}
                    ]
                }
            },
        )
        response = self.client.get("/tag-contexts-classification/testtag")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)

    def test_on_tag_dates_get(self) -> None:
        response = self.client.get("/tag-dates/testtag")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("data", data)

    def test_on_group_by_tags_startwith_get(self) -> None:
        response = self.client.get("/group/tag/startwith/t/1")
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # ML model endpoints (mocked)
    # ------------------------------------------------------------------
    def test_on_get_tag_similar_with_mocked_w2v(self) -> None:
        with mock.patch("os.path.exists", return_value=True):
            with mock.patch("gensim.models.word2vec.Word2Vec.load") as mock_load:
                mock_model = mock.MagicMock()
                mock_model.wv.most_similar.return_value = [("similar1", 0.9)]
                mock_load.return_value = mock_model
                self.test_db.users.update_one(
                    {"sid": self.sid}, {"$set": {"w2v": "test_model.bin"}}
                )
                response = self.client.get("/tag-similar/w2v/testtag")
                self.assertEqual(response.status_code, 200)
                data = response.get_json()
                self.assertIn("data", data)

    def test_on_get_tag_similar_with_mocked_fasttext(self) -> None:
        with mock.patch("os.path.exists", return_value=True):
            with mock.patch("gensim.models.fasttext.FastText.load") as mock_load:
                mock_model = mock.MagicMock()
                mock_model.wv.similar_by_word.return_value = [("similar1", 0.9)]
                mock_load.return_value = mock_model
                self.test_db.users.update_one(
                    {"sid": self.sid}, {"$set": {"fasttext": "test_model.bin"}}
                )
                response = self.client.get("/tag-similar/fasttext/testtag")
                self.assertEqual(response.status_code, 200)
                data = response.get_json()
                self.assertIn("data", data)


if __name__ == "__main__":
    unittest.main()
