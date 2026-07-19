import os
import json
import functools
from urllib.parse import quote_plus
import time
import logging
from typing import Any, Dict, List, Optional
import traceback

from rsstag.tasks import RssTagTasks
from rsstag.web.routes import RSSTagRoutes
from rsstag.utils import load_config
from rsstag.posts import RssTagPosts
from rsstag.anthologies import RssTagAnthologies, RssTagAnthologyRuns
from rsstag.chats import RssTagChats
from rsstag.paths import RssTagPaths
from rsstag.feeds import RssTagFeeds
from rsstag.tags import RssTagTags
from rsstag.letters import RssTagLetters
from rsstag.bi_grams import RssTagBiGrams
from rsstag.users import RssTagUsers
from rsstag.tokens import RssTagTokens
from rsstag.workers_db import RssTagWorkers
from rsstag.snippet_clusters import RssTagSnippetClusters

import rsstag.web.posts as posts_handlers
import rsstag.web.users as users_handlers
import rsstag.web.tags as tags_handlers
import rsstag.web.bigrams as bigrams_handlers
import rsstag.web.keywords as keywords_handlers
import rsstag.web.openai as openai_handlers
import rsstag.web.prefixes as prefixes_handlers
import rsstag.web.chat as chat_handlers
import rsstag.web.tasks as tasks_handlers
import rsstag.web.processing as processing_handlers
import rsstag.web.providers as providers_handlers
import rsstag.web.feeds as feeds_handlers
import rsstag.web.metadata as metadata_handlers
import rsstag.web.context_filter_handlers as context_filter_handlers
import rsstag.web.chats as chats_handlers
import rsstag.web.anthologies as anthologies_handlers
import rsstag.web.paths_handlers as paths_handlers
import rsstag.web.clusters as clusters_handlers
import rsstag.web.system as system_handlers
import rsstag.web.browse as browse_handlers

from rsstag.llm.router import LLMRouter
from rsstag.llm import LLMCache

from werkzeug.wrappers import Response, Request
from werkzeug.exceptions import HTTPException, InternalServerError, BadRequest
from werkzeug.utils import redirect

from jinja2 import Environment, PackageLoader

from pymongo import MongoClient


HANDLER_MODULES = (
    posts_handlers,
    users_handlers,
    tags_handlers,
    bigrams_handlers,
    keywords_handlers,
    openai_handlers,
    prefixes_handlers,
    chat_handlers,
    tasks_handlers,
    processing_handlers,
    providers_handlers,
    feeds_handlers,
    metadata_handlers,
    context_filter_handlers,
    chats_handlers,
    anthologies_handlers,
    paths_handlers,
    clusters_handlers,
    system_handlers,
    browse_handlers,
)


class RSSTagApplication(object):
    def __init__(self, config_path=None, log_file=None):
        self.config = load_config(config_path)
        self.no_category_name = "NotCategorized"
        if self.config["settings"]["no_category_name"]:
            self.no_category_name = self.config["settings"]["no_category_name"]

        try:
            target_log = log_file
            if not target_log:
                target_log = self.config["settings"].get("web_log_file", self.config["settings"]["log_file"])
            logging.basicConfig(
                filename=target_log,
                filemode="a",
                level=getattr(logging, self.config["settings"]["log_level"].upper()),
                force=True,
            )
        except Exception as e:
            logging.critical("Error in logging configuration: %s", e)
        self.config_path = config_path
        self.template_env = Environment(
            loader=PackageLoader(
                "rsstag.web",
                os.path.join("templates", self.config["settings"]["templates"]),
            )
        )
        self.template_env.filters["json"] = lambda d: json.dumps(d, default=str)
        self.template_env.filters["tojson"] = lambda d: json.dumps(d, default=str)
        self.template_env.filters["url_encode"] = quote_plus
        self.template_env.filters["find_group"] = self._find_group_for_sentence
        self.template_env.filters["timestamp_to_datetime"] = lambda ts: time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts)) if ts else 'N/A'

        # Add filter to convert hex color to rgba with alpha for softer highlights
        def _hex_to_rgba(hex_color: str, alpha: float = 0.15) -> str:
            try:
                hex_color = hex_color.lstrip("#")
                if len(hex_color) == 3:
                    hex_color = "".join([c * 2 for c in hex_color])
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                alpha = max(0.0, min(1.0, alpha))
                return f"rgba({r},{g},{b},{alpha})"
            except Exception:
                return "rgba(215,215,175,0.25)"  # fallback similar to previous base

        self.template_env.filters["hex_to_rgba"] = _hex_to_rgba
        self.providers = self.config["settings"]["providers"].split(",")
        self.user_ttl = int(self.config["settings"]["user_ttl"])
        cl = MongoClient(
            self.config["settings"]["db_host"],
            int(self.config["settings"]["db_port"]),
            username=self.config["settings"]["db_login"]
            if self.config["settings"]["db_login"]
            else None,
            password=self.config["settings"]["db_password"]
            if self.config["settings"]["db_password"]
            else None,
        )
        self.db = cl[self.config["settings"]["db_name"]]
        self.posts = RssTagPosts(self.db)
        self.posts.prepare()
        self.feeds = RssTagFeeds(self.db)
        self.feeds.prepare()
        self.tags = RssTagTags(self.db)
        self.tags.prepare()
        self.letters = RssTagLetters(self.db)
        self.letters.prepare()
        self.bi_grams = RssTagBiGrams(self.db)
        self.bi_grams.prepare()
        self.users = RssTagUsers(self.db)
        self.users.prepare()
        self.tokens = RssTagTokens(self.db)
        self.tokens.prepare()
        self.workers = RssTagWorkers(self.db)
        self.workers.prepare()
        self.snippet_clusters = RssTagSnippetClusters(self.db)
        self.snippet_clusters.prepare()
        self.chats = RssTagChats(self.db)
        self.chats.prepare()
        self.anthologies = RssTagAnthologies(self.db)
        self.anthologies.prepare()
        self.anthology_runs = RssTagAnthologyRuns(self.db)
        self.anthology_runs.prepare()
        self.paths = RssTagPaths(self.db)
        self.paths.prepare()
        self.routes = RSSTagRoutes(self.config["settings"]["host_name"], handlers=self)
        self.endpoints = {}
        self.update_endpoints()
        self.tasks = RssTagTasks(self.db)
        self.tasks.prepare()

        self.count_showed_numbers = 4
        self.models = {"d2v": "d2v", "w2v": "w2v", "fasttext": "fasttext"}
        self.allow_not_logged = (
            "on_root_get",
            "on_login_get",
            "on_login_post",
            "on_register_get",
            "on_register_post",
            "on_status_get",
            "on_refresh_get_post",
            "on_login_google_auth_get",
            "on_oauth2callback_get",
            "on_login_x_auth_get",
            "on_x_oauth2callback_get",
            "on_external_workers_claim_post",
            "on_external_workers_submit_post",
        )
        self.llm = LLMRouter(self.config)
        self.llm_cache = LLMCache(self.db)
        self.llm_cache.prepare()
        try:
            from rsstag.observability.business_metrics import register_business_metrics
            from rsstag.observability.worker_instrumentation import instrument_tasks
            from rsstag.observability.llm_instrumentation import instrument_llm_router
            register_business_metrics(self.db)
            instrument_tasks(self.tasks)
            instrument_llm_router(self.llm)
        except ImportError:
            pass

        from rsstag.post_grouping import RssTagPostGrouping
        from rsstag.post_splitter import PostSplitter

        self.post_splitter = PostSplitter(self.llm.get_handler(None))
        self.post_grouping = RssTagPostGrouping(self.db)
        self.post_grouping.prepare()

        from rsstag.topic_aliases import RssTagTopicAliases

        self.topic_aliases = RssTagTopicAliases(self.db)
        self.topic_aliases.prepare()

    def _find_group_for_sentence(self, sentence_num, groups):
        """Custom filter to find which group a sentence belongs to"""
        for group_id, group_sentences in groups.items():
            if sentence_num in group_sentences:
                return group_id
        return None

    def close(self):
        logging.info("Goodbye!")

    def _resolve_endpoint(self, name: str):
        """Resolve a werkzeug endpoint name to a callable.

        A bound method on ``self`` takes priority (covers handlers with
        real logic or non-trivial argument mapping). Otherwise look up a
        module-level function of the same name across ``HANDLER_MODULES``
        and bind it to ``self`` via ``functools.partial``.
        """
        if hasattr(self, name):
            return getattr(self, name)

        found_modules = [module for module in HANDLER_MODULES if hasattr(module, name)]
        if not found_modules:
            raise RuntimeError(f"No handler found for endpoint '{name}'")
        if len(found_modules) > 1:
            module_names = ", ".join(module.__name__ for module in found_modules)
            raise RuntimeError(
                f"Endpoint '{name}' is ambiguous: found in multiple modules ({module_names})"
            )

        return functools.partial(getattr(found_modules[0], name), self)

    def update_endpoints(self) -> None:
        routes = self.routes.get_werkzeug_routes()
        for rule in routes.iter_rules():
            self.endpoints[rule.endpoint] = self._resolve_endpoint(rule.endpoint)

    def get_page_count(self, items_count, items_on_page_count):
        page_count = divmod(items_count, items_on_page_count)
        if page_count[1] == 0:
            page_count = page_count[0]
        elif (page_count[1] > 0) or (page_count[0] == 0):
            page_count = page_count[0] + 1
        return page_count

    def set_response(self, http_env, start_resp):
        request = Request(http_env)
        st = time.time()
        adapter = self.routes.bind_to_environ(request.environ)
        user = None
        sid = request.cookies.get("sid")
        if sid:
            user = self.users.get_by_sid(sid)
        try:
            handler, values = adapter.match()
            logging.info("%s", handler)
            if user:
                response = self.endpoints[handler](user, request, **values)
            else:
                if handler in self.allow_not_logged:
                    response = self.endpoints[handler](user, request, **values)
                else:
                    response = redirect(self.routes.get_url_by_endpoint("on_root_get"))
        except Exception as e:
            logging.error(
                "{} - {}. {}".format(request.base_url, e, traceback.format_exc())
            )
            response = self.on_error(user, request, InternalServerError())
        request.close()
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        logging.info("%s", time.time() - st)

        return response(http_env, start_resp)

    @staticmethod
    def _json_response(payload: Dict[str, Any], status: int = 200) -> Response:
        return Response(
            json.dumps(payload, default=str),
            mimetype="application/json",
            status=status,
        )

    def on_login_get(
        self, _: Optional[dict], request: Request, err: Optional[List[str]] = None
    ) -> Response:
        return users_handlers.on_login_get(self, request, err=err)

    def on_login_post(self, _: Optional[dict], request: Request) -> Response:
        return users_handlers.on_login_post(self, request)

    def on_register_get(self, _: Optional[dict], request: Request) -> Response:
        return users_handlers.on_register_get(self, request)

    def on_register_post(self, _: Optional[dict], request: Request) -> Response:
        return users_handlers.on_register_post(self, request)

    def on_logout_get(self, _: Optional[dict], __: Request) -> Response:
        return users_handlers.on_logout_get(self)

    def on_provider_feeds_get_post(
        self, user: dict, request: Request, provider: Optional[str] = None
    ) -> Response:
        return providers_handlers.on_provider_feeds_get_post(
            self, user, request, provider
        )

    def on_status_get(self, user: Optional[dict], _: Request) -> Response:
        return users_handlers.on_status_get(self, user)

    def on_data_sources_get(self, user: dict, _: Request) -> Response:
        return users_handlers.on_data_sources_get(self, user)

    def on_provider_detail_get(self, user: dict, _: Request, provider: str) -> Response:
        return users_handlers.on_provider_detail_get(self, user, provider)

    def on_provider_detail_post(
        self, user: dict, request: Request, provider: str
    ) -> Response:
        return users_handlers.on_provider_detail_post(self, user, provider, request)

    def on_error(self, _: Optional[dict], __: Request, e: HTTPException) -> Response:
        page = self.template_env.get_template("error.html")
        return Response(
            page.render(
                title="ERROR", body="Error: {0}, {1}".format(e.code, e.description)
            ),
            mimetype="text/html",
            status=e.code,
        )

    def on_root_get(
        self, user: Optional[dict], _: Request, err: Optional[List[str]] = None
    ) -> Response:
        return users_handlers.on_root_get(self, user, err)

    def calc_pager_data(
        self,
        p_number,
        page_count,
        items_per_page,
        endpoint,
        sentiment="",
        group="",
        letter="",
        quoted_category="",
    ):
        pages_map = {}
        page_count = round(page_count)
        numbers_start_range = p_number - self.count_showed_numbers + 1
        numbers_end_range = p_number + self.count_showed_numbers + 1
        if numbers_start_range <= 0:
            numbers_start_range = 1
        if numbers_end_range > page_count:
            numbers_end_range = page_count + 1
        params = {}
        if sentiment:
            params["sentiment"] = sentiment
        if group:
            params["group"] = group
        if letter:
            params["letter"] = letter
        if quoted_category:
            params["quoted_category"] = quoted_category
        if page_count > 11:
            pages_map["middle"] = []
            for i in range(numbers_start_range, numbers_end_range):
                params["page_number"] = i
                pages_map["middle"].append(
                    {
                        "p": i,
                        "url": self.routes.get_url_by_endpoint(
                            endpoint=endpoint, params=params
                        ),
                    }
                )
            if numbers_start_range > 1:
                params["page_number"] = 1
                pages_map["start"] = [
                    {
                        "p": "first",
                        "url": self.routes.get_url_by_endpoint(
                            endpoint=endpoint, params=params
                        ),
                    }
                ]
            if numbers_end_range <= (page_count):
                params["page_number"] = page_count
                pages_map["end"] = [
                    {
                        "p": "last",
                        "url": self.routes.get_url_by_endpoint(
                            endpoint=endpoint, params=params
                        ),
                    }
                ]
        else:
            pages_map["start"] = []
            for i in range(1, page_count + 1):
                params["page_number"] = i
                pages_map["start"].append(
                    {
                        "p": i,
                        "url": self.routes.get_url_by_endpoint(
                            endpoint=endpoint, params=params
                        ),
                    }
                )
        start_tags_range = round(((p_number - 1) * items_per_page) + items_per_page)
        end_tags_range = round(start_tags_range + items_per_page)
        return (pages_map, start_tags_range, end_tags_range)

    def on_group_by_tags_get(
        self, user: dict, _: Request, page_number: int = 1
    ) -> Response:
        return tags_handlers.on_group_by_tags_get(self, user, page_number)

    def on_group_by_bigrams_get(
        self, user: dict, _: Request, page_number: int = 1
    ) -> Response:
        return bigrams_handlers.on_group_by_bigrams_get(self, user, page_number)

    def on_group_by_tags_sentiment(
        self, user: dict, _: Request, sentiment: str, page_number: int = 1
    ) -> Response:
        return tags_handlers.on_group_by_tags_sentiment(
            self, user, sentiment, page_number
        )

    def on_group_by_tags_startwith_get(
        self, user: dict, request: Request, letter: str, page_number: int = 1
    ) -> Response:
        return tags_handlers.on_group_by_tags_startwith_get(
            self, user, request, letter, page_number
        )

    def on_group_by_tags_group(
        self, user: dict, _: Request, group: str, page_number: int = 1
    ) -> Response:
        return tags_handlers.on_group_by_tags_group(self, user, group, page_number)

    def on_get_tag_similar(
        self, user: dict, _: Request, model: str, tag: str
    ) -> Response:
        return tags_handlers.on_get_tag_similar(self, user, model, tag)

    def on_get_tag_siblings(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_get_tag_siblings(self, user, tag)

    def on_get_tag_bi_grams(self, user: dict, _: Request, tag: str) -> Response:
        return bigrams_handlers.on_get_tag_bi_grams(self, user, tag)

    def on_get_tag_bi_grams_graph(self, user: dict, _: Request, tag: str) -> Response:
        return bigrams_handlers.on_get_tag_bi_grams_graph(self, user, tag)

    def on_get_tag_bi_grams_graph_debug(
        self, user: dict, _: Request, tag: str
    ) -> Response:
        return bigrams_handlers.on_get_tag_bi_grams_graph_debug(self, user, tag)

    def on_post_links_get(self, user: dict, _: Request, post_id: str) -> Response:
        return posts_handlers.on_post_links_get(self, user, post_id)

    def on_topics_list_get(
        self, user: dict, request: Request, page_number: int = 1
    ) -> Response:
        return posts_handlers.on_topics_list_get(self, user, request, page_number)

    # TODO: delete or change or something other
    def on_get_posts_with_tags(self, user: dict, _: Request, s_tags: str) -> Response:
        return posts_handlers.on_get_posts_with_tags(self, user, s_tags)

    def on_tag_dates_get(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_tag_dates_get(self, user, tag)

    def on_bigrams_dates_get(self, user: dict, _: Request, tag: str) -> Response:
        return bigrams_handlers.on_bigrams_dates_get(self, user, tag)

    def on_tag_topics_get(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_tag_topics_get(self, user, tag)

    def on_tag_grouped_topics_get(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_tag_grouped_topics_get(self, user, tag)

    def on_tag_llm_topics_get(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_tag_llm_topics_get(self, user, tag)

    def on_tag_entities_get(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_tag_entities_get(self, user, tag)

    def on_entity_get(self, user: dict, req: Request, quoted_tag=None) -> Response:
        try:
            window = int(req.args.get("window", 10))
        except ValueError:
            return self.on_error(user, req, BadRequest())
        if window < 1:
            return self.on_error(user, req, BadRequest())

        rerank = None
        if "rerank" in req.args:
            rerank = req.args.get("rerank")

        return posts_handlers.on_entity_get(self, user, quoted_tag, window, rerank)

    def on_entity_grouped_snippets_get(
        self, user: dict, req: Request, quoted_tag=None
    ) -> Response:
        try:
            window = int(req.args.get("window", 10))
        except ValueError:
            return self.on_error(user, req, BadRequest())
        if window < 1:
            return self.on_error(user, req, BadRequest())

        return posts_handlers.on_entity_grouped_snippets_get(
            self, user, req, quoted_tag, window
        )

    def on_tag_tfidf_get(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_tag_tfidf_get(self, user, tag)

    def on_tag_clusters_get(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_tag_clusters_get(self, user, tag)

    def on_get_tag_pmi(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_get_tag_pmi(self, user, tag)

    def on_cluster_get(self, user: dict, _: Request, cluster: int) -> Response:
        return posts_handlers.on_cluster_get(self, user, cluster)

    def on_tag_specific_get(self, user: dict, _: Request, tag: str):
        return tags_handlers.on_tag_specific_get(self, user, tag)

    def on_tag_specific1_get(self, user: dict, _: Request, tag: str):
        return tags_handlers.on_tag_specific1_get(self, user, tag)

    def on_get_tag_similar_tags(self, user: dict, _: Request, tags: str):
        return tags_handlers.on_get_tag_similar_tags(self, user, tags)

    def on_group_by_tags_categories_get(
        self, user: dict, _: Request, page_number: int = 1
    ):
        return tags_handlers.on_group_by_tags_categories_get(self, user, page_number)

    def on_group_by_tags_by_category_get(
        self, user: dict, _: Request, quoted_category: str, page_number: int = 1
    ):
        return tags_handlers.on_group_by_tags_by_category_get(
            self, user, quoted_category, page_number
        )

    def on_group_by_bigrams_dyn_get(self, user: dict, _: Request, page_number: int):
        return bigrams_handlers.on_group_by_bigrams_dyn_get(self, user, page_number)

    def on_group_by_rake_dyn_get(self, user: dict, _: Request, page_number: int):
        return keywords_handlers.on_group_by_rake_dyn_get(self, user, page_number)

    def on_group_by_yake_dyn_get(self, user: dict, _: Request, page_number: int):
        return keywords_handlers.on_group_by_yake_dyn_get(self, user, page_number)

    def on_tfidf_tags_get(self, user: dict, rqst: Request):
        return tags_handlers.on_get_tfidf_tags(self, user, rqst)

    def on_sunburst_get(self, user: dict, _: Request, tags: str):
        return tags_handlers.on_get_sunburst(self, user, tags)

    def on_chain_get(self, user: dict, _: Request, tags: str):
        return tags_handlers.on_get_chain(self, user, tags)

    def on_prefixes_all_get(self, user: dict, _: Request, prefix_len: int):
        return prefixes_handlers.on_prefixes_all_get(self, user, prefix_len)

    def on_prefixes_words_get(self, user: dict, _: Request, prefix: str):
        return prefixes_handlers.on_prefixes_words_get(self, user, prefix)

    def on_prefixes_prefix_get(self, user: dict, _: Request, prefix: str):
        return prefixes_handlers.on_prefixes_prefix_get(self, user, prefix)
