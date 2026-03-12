import unittest
from urllib.parse import quote_plus

from tests.web_test_utils import MongoWebTestCase


class TestWebFrontendContracts(MongoWebTestCase):
    """Protect the HTML contracts that the frontend bundle depends on."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _, sid = cls.seed_test_user("frontend-contracts", "frontend-contracts")
        cls.auth_client = cls.get_authenticated_client(sid)
        cls.data = cls.seed_minimal_data(sid)
        cls.post_ids = "_".join(cls.data["post_pids"])
        path = cls.app.paths.create_or_get(
            sid,
            "sentences",
            {"tags": {"values": [cls.data["tag"]], "logic": "and"}},
            {},
            "Frontend Contract Path",
        )
        cls.path_id = path["path_id"]

    def _get_html(self, path: str) -> str:
        response = self.auth_client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.get_data(as_text=True)

    def assertContainsAll(self, html: str, parts: list[str]) -> None:
        for part in parts:
            with self.subTest(part=part):
                self.assertIn(part, html)

    def test_posts_page_contract(self) -> None:
        html = self._get_html(f"/posts/{quote_plus(self.data['post_pids'][0])}")
        self.assertContainsAll(
            html,
            [
                '/static/js/bundle.js',
                'id="posts_page"',
                'id="context_filter_bar"',
                "window.posts_list =",
                "window.group =",
                "window.group_title =",
                "window.words =",
                "window.rss_settings =",
            ],
        )

    def test_tag_info_page_contract(self) -> None:
        html = self._get_html(f"/tag-info/{quote_plus(self.data['tag'])}")
        self.assertContainsAll(
            html,
            [
                'id="similar_w2v_tags"',
                'id="bi_grams_graph"',
                'id="mentions_chart"',
                'id="wordtree"',
                'id="openai_tool"',
                "var initial_tag =",
            ],
        )

    def test_topics_list_page_contract(self) -> None:
        html = self._get_html("/topics-list")
        self.assertContainsAll(
            html,
            [
                '/static/js/bundle.js',
                'id="topics_search_field"',
                'id="topics_list_container"',
                'id="topics_sunburst_chart"',
                'id="topics_marimekko_chart"',
                "window.sunburst_data =",
            ],
        )

    def test_topics_mindmap_page_contract(self) -> None:
        html = self._get_html("/topics-mindmap")
        self.assertContainsAll(
            html,
            [
                '/static/js/bundle.js',
                'id="topics_mindmap_chart"',
                "window.mindmap_data =",
            ],
        )

    def test_post_grouped_page_contract(self) -> None:
        html = self._get_html(f"/post-grouped/{self.post_ids}")
        self.assertContainsAll(
            html,
            [
                'id="grouped_posts"',
                'id="topics_list"',
                'window.post_id =',
                'window.groups =',
                'window.posts =',
                'window.sentences =',
                'window.post_to_index_map =',
                "import PostGroupedPage from '/static/js/components/post-grouped.js';",
            ],
        )

    def test_post_compare_page_contract(self) -> None:
        html = self._get_html(f"/post-compare/{self.post_ids}")
        self.assertContainsAll(
            html,
            [
                'id="compare_scroll"',
                'id="compare_posts"',
                'window.post_id =',
                'window.groups =',
                'window.posts =',
                'window.current_topic =',
                "import PostComparePage from '/static/js/components/post-compare.js';",
            ],
        )

    def test_post_graph_page_contract(self) -> None:
        html = self._get_html(f"/post-graph/{self.post_ids}")
        self.assertContainsAll(
            html,
            [
                'id="posts_graphs"',
                'class="tab-button active"',
                'window.posts_graphs =',
                'window.user_settings =',
            ],
        )

    def test_path_page_contract(self) -> None:
        html = self._get_html(f"/paths/sentences/{self.path_id}")
        self.assertContainsAll(
            html,
            [
                '/static/js/bundle.js',
                'id="path_recommendations"',
                "window.path_data =",
            ],
        )


if __name__ == "__main__":
    unittest.main()
