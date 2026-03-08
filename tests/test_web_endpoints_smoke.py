"""Module 4: Endpoint smoke tests -- assert no 500 errors across all major routes."""
import json
import unittest
from typing import Any, Dict
from urllib.parse import quote_plus

from werkzeug.test import Client
from werkzeug.wrappers import Response

from tests.web_test_utils import MongoWebTestCase


class TestEndpointSmoke(MongoWebTestCase):
    """Hit every major endpoint with an authenticated client and seeded data.

    The sole assertion for each test is that the response status is not 500.
    This catches import errors, template failures, and broken route wiring.
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user_doc, cls.user_sid = cls.seed_test_user("smokeuser", "smokepass")
        cls.data: Dict[str, Any] = cls.seed_minimal_data(cls.user_sid)
        cls.auth_client: Client = cls.get_authenticated_client(cls.user_sid)

    def _get(self, path: str) -> Response:
        resp = self.auth_client.get(path)
        self.assertNotEqual(resp.status_code, 500, f"GET {path} returned 500")
        return resp

    def _post(self, path: str, **kwargs: Any) -> Response:
        resp = self.auth_client.post(path, **kwargs)
        self.assertNotEqual(resp.status_code, 500, f"POST {path} returned 500")
        return resp

    # ------------------------------------------------------------------
    # Tag browsing
    # ------------------------------------------------------------------

    def test_group_by_tags_page(self) -> None:
        self._get("/group/tag/1")

    def test_group_by_tags_startwith(self) -> None:
        self._get("/group/tag/startwith/t/1")

    def test_tag_page_seeded_tag(self) -> None:
        tag = self.data["tag"]
        self._get(f"/tag/{quote_plus(tag)}")

    def test_tag_info_page_seeded_tag(self) -> None:
        tag = self.data["tag"]
        self._get(f"/tag-info/{quote_plus(tag)}")

    def test_tags_search_post(self) -> None:
        self._post("/tags-search", data={"req": "test"})

    # ------------------------------------------------------------------
    # Post & feed viewing
    # ------------------------------------------------------------------

    def test_feed_page_seeded_feed(self) -> None:
        feed_id = self.data["feed_id"]
        self._get(f"/feed/{quote_plus(feed_id)}")

    def test_category_page_seeded_category(self) -> None:
        cat = self.data["category"]
        self._get(f"/category/{quote_plus(cat)}")

    def test_posts_content_post(self) -> None:
        pid = self.data["post_pids"][0]
        self._post(
            "/posts-content",
            data=json.dumps([pid]),
            content_type="application/json",
        )

    def test_posts_page_seeded_pid(self) -> None:
        pid = self.data["post_pids"][0]
        self._get(f"/posts/{quote_plus(str(pid))}")

    # ------------------------------------------------------------------
    # Category & feed browsing
    # ------------------------------------------------------------------

    def test_group_by_category(self) -> None:
        self._get("/group/category")

    def test_provider_feeds(self) -> None:
        self._get("/provider/feeds")

    # ------------------------------------------------------------------
    # Bigrams
    # ------------------------------------------------------------------

    def test_group_by_bigrams(self) -> None:
        self._get("/group/bi-grams/1")

    # ------------------------------------------------------------------
    # Topics & mindmap
    # ------------------------------------------------------------------

    def test_topics_mindmap(self) -> None:
        self._get("/topics-mindmap")

    def test_topics_list(self) -> None:
        self._get("/topics-list")

    def test_mindmap_node_data(self) -> None:
        self._post(
            "/api/mindmap-node-data",
            json={
                "action": "sentences",
                "scope": {
                    "post_ids": self.data["post_pids"],
                    "topic_path": "",
                    "node_kind": "topic",
                },
            },
        )

    # ------------------------------------------------------------------
    # Tasks & status
    # ------------------------------------------------------------------

    def test_tasks_page(self) -> None:
        self._get("/tasks")

    def test_status_endpoint(self) -> None:
        self._get("/status")

    # ------------------------------------------------------------------
    # User & settings pages
    # ------------------------------------------------------------------

    def test_data_sources(self) -> None:
        self._get("/data-sources")

    def test_tokens_page(self) -> None:
        self._get("/tokens")

    def test_workers_page(self) -> None:
        self._get("/workers")

    def test_statistics_page(self) -> None:
        self._get("/statistics")

    def test_metadata_page(self) -> None:
        self._get("/metadata")

    def test_processing_page(self) -> None:
        self._get("/processing")

    # ------------------------------------------------------------------
    # Visualisation
    # ------------------------------------------------------------------

    def test_prefixes_all(self) -> None:
        self._get("/prefixes/all/2")

    def test_map_page(self) -> None:
        self._get("/map")

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------

    def test_download_posts(self) -> None:
        self._get("/download/posts")


if __name__ == "__main__":
    unittest.main()
