"""Routes for rsstag"""

from typing import List, Optional, Iterable
import itertools
import inspect
import functools
from werkzeug.routing import Map, Rule


def route(url: str, methods: List[str]):
    """Decorator to register handler routes without editing the static list."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        routes = getattr(func, "_rsstag_routes", [])
        routes.append({"url": url, "endpoint": func.__name__, "methods": methods})
        setattr(wrapper, "_rsstag_routes", routes)
        return wrapper

    return decorator


def _collect_decorated_routes(handlers: object) -> List[dict]:
    collected_routes: List[dict] = []
    for attr_name in dir(handlers):
        attr = getattr(handlers, attr_name)
        if not inspect.ismethod(attr):
            continue
        routes = getattr(attr, "_rsstag_routes", None)
        if routes:
            collected_routes.extend(routes)
    return collected_routes


class RSSTagRoutes:
    """Routes list and mapping for rsstag"""

    def __init__(self, host: str, handlers: Optional[object] = None) -> None:
        self._host = host
        self._default_routes = [
            {"url": "/", "endpoint": "on_root_get", "methods": ["GET"]},
            {"url": "/login", "endpoint": "on_login_get", "methods": ["GET"]},
            {"url": "/login", "endpoint": "on_login_post", "methods": ["POST"]},
            {"url": "/register", "endpoint": "on_register_get", "methods": ["GET"]},
            {"url": "/register", "endpoint": "on_register_post", "methods": ["POST"]},
            {"url": "/logout", "endpoint": "on_logout_get", "methods": ["GET"]},
            {
                "url": "/login/google/auth",
                "endpoint": "on_login_google_auth_get",
                "methods": ["GET"],
            },
            {
                "url": "/oauth2callback",
                "endpoint": "on_oauth2callback_get",
                "methods": ["GET"],
            },
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
                "url": "/provider/feeds",
                "endpoint": "on_provider_feeds_get_post",
                "methods": ["GET", "POST"],
            },
            {
                "url": "/data-sources",
                "endpoint": "on_data_sources_get",
                "methods": ["GET"],
            },
            {
                "url": "/provider/<string:provider>",
                "endpoint": "on_provider_detail_get",
                "methods": ["GET"],
            },
            {
                "url": "/provider/<string:provider>",
                "endpoint": "on_provider_detail_post",
                "methods": ["POST"],
            },
            {
                "url": "/provider/<string:provider>/feeds",
                "endpoint": "on_provider_feeds_get_post",
                "methods": ["GET", "POST"],
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
                "url": "/group/bi-grams-dyn/<int:page_number>",
                "endpoint": "on_group_by_bigrams_dyn_get",
                "methods": ["GET"],
            },
            {
                "url": "/group/tag/startwith/<string:letter>/<int:page_number>",
                "endpoint": "on_group_by_tags_startwith_get",
                "methods": ["GET"],
            },
            {
                "url": "/group/category",
                "endpoint": "on_group_by_category_get",
                "methods": ["GET"],
            },
            {
                "url": "/group/tags-categories/<int:page_number>",
                "endpoint": "on_group_by_tags_categories_get",
                "methods": ["GET"],
            },
            {
                "url": "/tags/category/<string:quoted_category>/<int:page_number>",
                "endpoint": "on_group_by_tags_by_category_get",
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
                "url": "/post-links/<string:post_id>",
                "endpoint": "on_post_links_get",
                "methods": ["GET"],
            },
            {
                "url": "/post-grouped/<string:pids>",
                "endpoint": "on_post_grouped_get",
                "methods": ["GET"],
            },
            {
                "url": "/post-graph/<string:pids>",
                "endpoint": "on_post_graph_get",
                "methods": ["GET"],
            },
            {
                "url": "/post-grouped-snippets/<string:pids>",
                "endpoint": "on_post_grouped_snippets_get",
                "methods": ["GET"],
            },
            {
                "url": "/topics-list",
                "endpoint": "on_topics_list_get",
                "methods": ["GET"],
            },
            {
                "url": "/topics-list/<int:page_number>",
                "endpoint": "on_topics_list_get",
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
                "url": "/s-tree/<string:tag>",
                "endpoint": "on_s_tree_get",
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
                "url": "/api/tag-bi-grams-graph/<string:tag>",
                "endpoint": "on_get_tag_bi_grams_graph",
                "methods": ["GET"],
            },
            {
                "url": "/api/tag-bi-grams-graph-debug/<string:tag>",
                "endpoint": "on_get_tag_bi_grams_graph_debug",
                "methods": ["GET"],
            },
            {
                "url": "/tag-pmi/<string:tag>",
                "endpoint": "on_get_tag_pmi",
                "methods": ["GET"],
            },
            {
                "url": "/tag-similar-tags/<string:tags>",
                "endpoint": "on_get_tag_similar_tags",
                "methods": ["GET"],
            },
            {
                "url": "/tags-search",
                "endpoint": "on_post_tags_search",
                "methods": ["POST"],
            },
            {
                "url": "/topics-search",
                "endpoint": "on_topics_search",
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
            {
                "url": "/context-tags/<string:tags>",
                "endpoint": "on_get_context_tags",
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
                "url": "/api/context-filter",
                "endpoint": "on_context_filter_get",
                "methods": ["GET"],
            },
            {
                "url": "/api/context-filter/tag",
                "endpoint": "on_context_filter_add_tag",
                "methods": ["POST"],
            },
            {
                "url": "/api/context-filter/tag",
                "endpoint": "on_context_filter_remove_tag",
                "methods": ["DELETE"],
            },
            {
                "url": "/api/context-filter/clear",
                "endpoint": "on_context_filter_clear",
                "methods": ["POST"],
            },
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
                "url": "/tag-specific1/<string:tag>",
                "endpoint": "on_tag_specific1_get",
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
                "url": "/clusters-dyn",
                "endpoint": "on_clusters_dyn_get",
                "methods": ["GET"],
            },
            {
                "url": "/clusters-topics-dyn",
                "endpoint": "on_clusters_topics_dyn_get",
                "methods": ["GET"],
            },
            {
                "url": "/clusters-topics-dyn-sentences",
                "endpoint": "on_clusters_topics_dyn_sentences_post",
                "methods": ["POST"],
            },
            {
                "url": "/telegram-auth",
                "endpoint": "on_telegram_auth_post",
                "methods": ["POST"],
            },
            {
                "url": "/telegram-mark",
                "endpoint": "on_mark_telegram_posts_post",
                "methods": ["POST"],
            },
            {
                "url": "/gmail-sort",
                "endpoint": "on_gmail_sort_post",
                "methods": ["POST"],
            },
            {
                "url": "/tfidf-tags",
                "endpoint": "on_tfidf_tags_get",
                "methods": ["GET"],
            },
            {
                "url": "/openai",
                "endpoint": "on_openai_post",
                "methods": ["POST"],
            },
            {
                "url": "/sunburst/<string:tags>",
                "endpoint": "on_sunburst_get",
                "methods": ["GET"],
            },
            {
                "url": "/tree/<string:tags>",
                "endpoint": "on_sunburst_get",
                "methods": ["GET"],
            },
            {
                "url": "/chain/<string:tags>",
                "endpoint": "on_chain_get",
                "methods": ["GET"],
            },
            {
                "url": "/prefixes/all/<int:prefix_len>",
                "endpoint": "on_prefixes_all_get",
                "methods": ["GET"],
            },
            {
                "url": "/prefixes/words/<string:prefix>",
                "endpoint": "on_prefixes_words_get",
                "methods": ["GET"],
            },
            {
                "url": "/prefixes/prefix/<string:prefix>",
                "endpoint": "on_prefixes_prefix_get",
                "methods": ["GET"],
            },
            {
                "url": "/chat",
                "endpoint": "on_chat_post",
                "methods": ["POST"],
            },
            {
                "url": "/tag-contexts-classification/<string:tag>",
                "endpoint": "on_tag_contexts_classification_get",
                "methods": ["GET"],
            },
            {
                "url": "/tasks",
                "endpoint": "on_tasks_get",
                "methods": ["GET"],
            },
            {
                "url": "/tasks",
                "endpoint": "on_tasks_post",
                "methods": ["POST"],
            },
            {
                "url": "/tasks/remove/<string:task_id>",
                "endpoint": "on_tasks_remove_post",
                "methods": ["POST"],
            },
            {
                "url": "/processing",
                "endpoint": "on_processing_get",
                "methods": ["GET"],
            },
            {
                "url": "/processing/reset",
                "endpoint": "on_processing_reset_post",
                "methods": ["POST"],
            },
            {
                "url": "/read/snippets",
                "endpoint": "on_read_snippets_post",
                "methods": ["POST"],
            },
            {
                "url": "/delete-feeds-categories",
                "endpoint": "on_delete_feeds_categories_post",
                "methods": ["POST"],
            },
            {
                "url": "/tag-grouped-topics/<string:tag>",
                "endpoint": "on_tag_grouped_topics_get",
                "methods": ["GET"],
            },
            {
                "url": "/tag-llm-topics/<string:tag>",
                "endpoint": "on_tag_llm_topics_get",
                "methods": ["GET"],
            },
            {
                "url": "/workers",
                "endpoint": "on_workers_get",
                "methods": ["GET"],
            },
            {
                "url": "/workers/spawn",
                "endpoint": "on_workers_spawn_post",
                "methods": ["POST"],
            },
            {
                "url": "/workers/kill/<int:worker_id>",
                "endpoint": "on_workers_kill_post",
                "methods": ["POST"],
            },
            {
                "url": "/workers/delete/<int:worker_id>",
                "endpoint": "on_workers_delete_post",
                "methods": ["POST"],
            },
            {
                "url": "/statistics",
                "endpoint": "on_statistics_get",
                "methods": ["GET"],
            },
            {
                "url": "/tokens",
                "endpoint": "on_tokens_get",
                "methods": ["GET"],
            },
            {
                "url": "/tokens/create",
                "endpoint": "on_tokens_create_post",
                "methods": ["POST"],
            },
            {
                "url": "/tokens/delete/<string:token>",
                "endpoint": "on_tokens_delete_post",
                "methods": ["POST"],
            },
            {
                "url": "/api/external-workers/claim",
                "endpoint": "on_external_workers_claim_post",
                "methods": ["POST"],
            },
            {
                "url": "/api/external-workers/submit",
                "endpoint": "on_external_workers_submit_post",
                "methods": ["POST"],
            },
        ]

        decorated_routes = (
            _collect_decorated_routes(handlers) if handlers is not None else []
        )
        self._routes = self._merge_routes(decorated_routes, self._default_routes)

        self._rules = []
        for route in self._routes:
            self._rules.append(
                Rule(route["url"], endpoint=route["endpoint"], methods=route["methods"])
            )
        self._werkzeug_routes = Map(self._rules)

    @staticmethod
    def _merge_routes(
        routes: Iterable[dict], fallback_routes: Iterable[dict]
    ) -> List[dict]:
        seen = set()
        merged_routes = []
        for route in itertools.chain(routes, fallback_routes):
            key = (route["url"], route["endpoint"], tuple(route["methods"]))
            if key in seen:
                continue
            seen.add(key)
            merged_routes.append(route)
        return merged_routes

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
