"""Routes for rsstag"""
from typing import List, Optional
from werkzeug.routing import Map, Rule


class RSSTagRoutes:
    """Routes list and mapping for rsstag"""

    def __init__(self, host: str) -> None:
        self._host = host
        self._routes = [
            {"url": "/", "endpoint": "on_root_get", "methods": ["GET"]},
            {"url": "/login", "endpoint": "on_login_get", "methods": ["GET"]},
            {"url": "/login", "endpoint": "on_login_post", "methods": ["POST"]},
            {
                "url": "/provider",
                "endpoint": "on_select_provider_get",
                "methods": ["GET"],
            },
            {
                "url": "/provider",
                "endpoint": "on_select_provider_post",
                "methods": ["POST"],
            },
            {
                "url": "/group/tag/<int:page_number>",
                "endpoint": "on_group_by_tags_get",
                "methods": ["GET"],
            },
            {
                "url": "/group/bi-grams/<int:page_number>",
                "endpoint": "on_group_by_bigrams_get",
                "methods": ["GET"],
            },
            {
                "url": "/group/tag/startwith/<string(length: 1):letter>/<int:page_number>",
                "endpoint": "on_group_by_tags_startwith_get",
                "methods": ["GET"],
            },
            {
                "url": "/group/category",
                "endpoint": "on_group_by_category_get",
                "methods": ["GET"],
            },
            {
                "url": "/refresh",
                "endpoint": "on_refresh_get_post",
                "methods": ["GET", "POST"],
            },
            {
                "url": "/tag/<string:quoted_tag>",
                "endpoint": "on_tag_get",
                "methods": ["GET"],
            },
            {
                "url": "/entity/<string:quoted_tag>",
                "endpoint": "on_entity_get",
                "methods": ["GET"],
            },
            {
                "url": "/category/<string:quoted_category>",
                "endpoint": "on_category_get",
                "methods": ["GET"],
            },
            {
                "url": "/feed/<string:quoted_feed>",
                "endpoint": "on_feed_get",
                "methods": ["GET"],
            },
            {
                "url": "/read/posts",
                "endpoint": "on_read_posts_post",
                "methods": ["POST"],
            },
            {
                "url": "/posts-content",
                "endpoint": "on_posts_content_post",
                "methods": ["POST"],
            },
            {
                "url": "/post-links/<int:post_id>",
                "endpoint": "on_post_links_get",
                "methods": ["GET"],
            },
            {"url": "/status", "endpoint": "on_status_get", "methods": ["GET"]},
            {"url": "/settings", "endpoint": "on_settings_post", "methods": ["POST"]},
            {
                "url": "/posts/with/tags/<string:s_tags>",
                "endpoint": "on_get_posts_with_tags",
                "methods": ["GET"],
            },
            {
                "url": "/sentences/with/tags/<string:s_tags>",
                "endpoint": "on_get_sentences_with_tags",
                "methods": ["GET"],
            },
            {
                "url": "/posts/<string:pids>",
                "endpoint": "on_posts_get",
                "methods": ["GET"],
            },
            {
                "url": "/posts/cluster/<int:cluster>",
                "endpoint": "on_cluster_get",
                "methods": ["GET"],
            },
            {
                "url": "/tag-siblings/<string:tag>",
                "endpoint": "on_get_tag_siblings",
                "methods": ["GET"],
            },
            {
                "url": "/tag-similar/<string:model>/<string:tag>",
                "endpoint": "on_get_tag_similar",
                "methods": ["GET"],
            },
            {
                "url": "/tag-bi-grams/<string:tag>",
                "endpoint": "on_get_tag_bi_grams",
                "methods": ["GET"],
            },
            {
                "url": "/tag-pmi/<string:tag>",
                "endpoint": "on_get_tag_pmi",
                "methods": ["GET"],
            },
            {
                "url": "/tags-search",
                "endpoint": "on_post_tags_search",
                "methods": ["POST"],
            },
            {"url": "/speech", "endpoint": "on_post_speech", "methods": ["POST"]},
            {
                "url": "/bi-gram/<string:bi_gram>",
                "endpoint": "on_bi_gram_get",
                "methods": ["GET"],
            },
            {
                "url": "/tag-info/<string:tag>",
                "endpoint": "on_get_tag_page",
                "methods": ["GET"],
            },
            {"url": "/map", "endpoint": "on_get_map", "methods": ["GET"]},
            {
                "url": "/api/tag-net/<string:tag>",
                "endpoint": "on_get_tag_net",
                "methods": ["GET"],
            },
            {"url": "/tag-net", "endpoint": "on_get_tag_net_page", "methods": ["GET"]},
            {
                "url": "/tags/sentiment/<string:sentiment>/<int:page_number>",
                "endpoint": "on_group_by_tags_sentiment",
                "methods": ["GET"],
            },
            {
                "url": "/groups/<int:page_number>",
                "endpoint": "on_get_groups",
                "methods": ["GET"],
            },
            {
                "url": "/tags/group/<string:group>/<int:page_number>",
                "endpoint": "on_group_by_tags_group",
                "methods": ["GET"],
            },
            {
                "url": "/tag-dates/<string:tag>",
                "endpoint": "on_tag_dates_get",
                "methods": ["GET"],
            },
            {
                "url": "/tag-specific/<string:tag>",
                "endpoint": "on_tag_specific_get",
                "methods": ["GET"],
            },
            {
                "url": "/tag-topics/<string:tag>",
                "endpoint": "on_tag_topics_get",
                "methods": ["GET"],
            },
            {
                "url": "/tag-clusters/<string:tag>",
                "endpoint": "on_tag_clusters_get",
                "methods": ["GET"],
            },
            {
                "url": "/tag-tfidf/<string:tag>",
                "endpoint": "on_tag_tfidf_get",
                "methods": ["GET"],
            },
            {
                "url": "/tag-entities/<string:tag>",
                "endpoint": "on_tag_entities_get",
                "methods": ["GET"],
            },
            {
                "url": "/topics-texts/<string:tag>",
                "endpoint": "on_topics_texts_get",
                "methods": ["GET"],
            },
            {
                "url": "/bigrams-dates/<string:tag>",
                "endpoint": "on_bigrams_dates_get",
                "methods": ["GET"],
            },
            {
                "url": "/wordtree-texts/<string:tag>",
                "endpoint": "on_wordtree_texts_get",
                "methods": ["GET"],
            },
            {
                "url": "/topics/<int:page_number>",
                "endpoint": "on_topics_get",
                "methods": ["GET"],
            },
            {"url": "/clusters", "endpoint": "on_clusters_get", "methods": ["GET"]},
            {
                "url": "/telegram-code",
                "endpoint": "on_telegram_code_post",
                "methods": ["POST"],
            }
        ]

        self._rules = []
        for route in self._routes:
            self._rules.append(
                Rule(route["url"], endpoint=route["endpoint"], methods=route["methods"])
            )
        self._werkzeug_routes = Map(self._rules)

    def get_routes(self) -> List[dict]:
        """Get routes list"""
        return self._routes

    def get_werkzeug_routes(self) -> object:
        """Get werkzeug generated routes"""
        return self._werkzeug_routes

    """def get_url_by_endpoint(self, endpoint=None, params=None, full_url=False):
        url = None
        if endpoint:
            if not params:
                params = {}
            if full_url or params:
                all_urls = self.routes.bind(self.request.environ['HTTP_HOST'], '/')
                url = all_urls.build(endpoint, params, force_external=full_url)
            else:
                url = next(self.routes.iter_rules(endpoint=endpoint))
        return url"""

    def get_url_by_endpoint(
        self, endpoint: str, params: dict = None, full_url: bool = False
    ) -> Optional[str]:
        """Return url by endpoint"""
        if not endpoint:
            return None

        rule = next(self._werkzeug_routes.iter_rules(endpoint=endpoint))
        if not rule:
            return None

        all_urls = self._werkzeug_routes.bind(self._host, "/")
        url = all_urls.build(endpoint, params, force_external=full_url)

        return url

    def bind_to_environ(self, environ: dict):
        return self._werkzeug_routes.bind_to_environ(environ)
