import os
import re
import json
from urllib.parse import quote_plus
import time
import gzip
import logging
from collections import OrderedDict, defaultdict
from typing import Optional, List
import traceback
import random

from rsstag.tasks import RssTagTasks
from rsstag.web.routes import RSSTagRoutes
from rsstag.utils import get_sorted_dict_by_alphabet, load_config
from rsstag.posts import RssTagPosts
from rsstag.feeds import RssTagFeeds
from rsstag.tags import RssTagTags
from rsstag.letters import RssTagLetters
from rsstag.bi_grams import RssTagBiGrams
from rsstag.users import RssTagUsers
from rsstag.lda import LDA
from rsstag.html_cleaner import HTMLCleaner

import rsstag.web.posts as posts_handlers
import rsstag.web.users as users_handlers
import rsstag.web.tags as tags_handlers
import rsstag.web.bigrams as bigrams_handlers
import rsstag.web.openai as openai_handlers
import rsstag.web.prefixes as prefixes_handlers
import rsstag.web.chat as chat_handlers
import rsstag.web.tasks as tasks_handlers

from rsstag.openai import ROpenAI
from rsstag.anthropic import Anthropic
from rsstag.llamacpp import LLamaCPP
from rsstag.llm.groqcom import GroqCom

from rsstag.stopwords import stopwords

from werkzeug.wrappers import Response, Request
from werkzeug.exceptions import HTTPException, NotFound, InternalServerError, BadRequest
from werkzeug.utils import redirect

from jinja2 import Environment, PackageLoader

from pymongo import MongoClient

from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.cluster import DBSCAN



class RSSTagApplication(object):
    def __init__(self, config_path=None):
        self.config = load_config(config_path)
        self.no_category_name = "NotCategorized"
        if self.config["settings"]["no_category_name"]:
            self.no_category_name = self.config["settings"]["no_category_name"]

        try:
            logging.basicConfig(
                filename=self.config["settings"]["log_file"],
                filemode="a",
                level=getattr(logging, self.config["settings"]["log_level"].upper()),
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
        self.template_env.filters["json"] = json.dumps
        self.template_env.filters["url_encode"] = quote_plus
        self.template_env.filters["find_group"] = self._find_group_for_sentence
        # Add filter to convert hex color to rgba with alpha for softer highlights
        def _hex_to_rgba(hex_color: str, alpha: float = 0.15) -> str:
            try:
                hex_color = hex_color.lstrip('#')
                if len(hex_color) == 3:
                    hex_color = ''.join([c*2 for c in hex_color])
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
            username=self.config["settings"]["db_login"] if self.config["settings"]["db_login"] else None,
            password=self.config["settings"]["db_password"] if self.config["settings"]["db_password"] else None,
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
        self.routes = RSSTagRoutes(self.config["settings"]["host_name"])
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
            "on_select_provider_post",
            "on_select_provider_get",
            "on_status_get",
            "on_refresh_get_post",
            "on_login_google_auth_get",
            "on_oauth2callback_get",
        )
        self.allow_not_ready = {
            "on_telegram_auth_post",
            "on_settings_post",
            "on_tasks_get",
            "on_tasks_post",
            "on_tasks_remove_post"
        }

        self.openai = ROpenAI(self.config["openai"]["token"])
        self.anthropic = Anthropic(self.config["anthropic"]["token"])
        self.llamacpp = LLamaCPP(self.config["llamacpp"]["host"])
        self.groqcom = GroqCom(host=self.config["groqcom"]["host"], token=self.config["groqcom"]["token"])
        
        # Initialize post grouping (after LLM handlers are available)
        from rsstag.post_grouping import RssTagPostGrouping
        self.post_grouping = RssTagPostGrouping(self.db, self.llamacpp)
        self.post_grouping.prepare()

    def _find_group_for_sentence(self, sentence_num, groups):
        """Custom filter to find which group a sentence belongs to"""
        for group_id, group_sentences in groups.items():
            if sentence_num in group_sentences:
                return group_id
        return None

    def _generate_similar_color(self, base_color, color_range):
        """Generate a color similar to base_color within the specified range"""
        # Convert base color to RGB
        base_rgb = self._hex_to_rgb(base_color)
        
        # Generate new RGB values within the specified range
        new_rgb = []
        for value in base_rgb:
            min_val = max(0, value - color_range)
            max_val = min(255, value + color_range)
            new_value = random.randint(min_val, max_val)
            new_rgb.append(new_value)
        
        # Convert back to hex
        return self._rgb_to_hex(new_rgb)

    def _hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _rgb_to_hex(self, rgb):
        """Convert RGB tuple to hex color"""
        return '#' + ''.join(f'{x:02x}' for x in rgb)

    def close(self):
        logging.info("Goodbye!")

    def update_endpoints(self):
        routes = self.routes.get_werkzeug_routes()
        for i in routes.iter_rules():
            self.endpoints[i.endpoint] = getattr(self, i.endpoint)

    def create_new_session(
        self, login: str, password: str, token: str, provider: str
    ) -> Optional[dict]:
        sid = self.users.create_user(login, password, token, provider)

        return self.users.get_by_sid(sid)

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
            if user and (user["ready"] or handler in self.allow_not_ready):
                response = self.endpoints[handler](user, request, **values)
            else:
                if handler in self.allow_not_logged:
                    response = self.endpoints[handler](user, request, **values)
                else:
                    response = redirect(self.routes.get_url_by_endpoint("on_root_get"))
        except Exception as e:
            logging.error("{} - {}. {}".format(request.base_url, e, traceback.format_exc()))
            response = self.on_error(user, request, InternalServerError())
        request.close()
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        logging.info("%s", time.time() - st)

        return response(http_env, start_resp)

    def on_select_provider_get(self, _: Optional[dict], __: Request) -> Response:
        return users_handlers.on_select_provider_get(self)

    def on_select_provider_post(self, _: Optional[dict], request: Request) -> Response:
        return users_handlers.on_select_provider_post(self, request)

    def on_post_speech(self, user: dict, request: Request) -> Response:
        return posts_handlers.on_post_speech(self, user, request)

    def on_login_get(
        self, _: Optional[dict], request: Request, err: Optional[List[str]] = None
    ) -> Response:
        return users_handlers.on_login_get(self, request, err=err)

    def on_login_google_auth_get(self, _: Optional[dict], request: Request) -> Response:
        return users_handlers.on_login_google_auth_get(self, request)

    def on_oauth2callback_get(self, _: Optional[dict], request: Request) -> Response:
        return users_handlers.on_oauth2callback_get(self, request)

    def on_login_post(self, _: Optional[dict], request: Request) -> Response:
        return users_handlers.on_login_post(self, request)

    def on_refresh_get_post(self, user: dict, request: Request) -> Response:
        return users_handlers.on_refresh_get_post(self, user, request)

    def on_status_get(self, user: Optional[dict], _: Request) -> Response:
        return users_handlers.on_status_get(self, user)

    def on_settings_post(self, user: dict, request: Request) -> Response:
        return users_handlers.on_settings_post(self, user, request)

    def on_tasks_get(self, user: dict, request: Request) -> Response:
        return tasks_handlers.on_tasks_get(self, user, request)

    def on_tasks_post(self, user: dict, request: Request) -> Response:
        return tasks_handlers.on_tasks_post(self, user, request)

    def on_tasks_remove_post(self, user: dict, request: Request, task_id: str) -> Response:
        return tasks_handlers.on_tasks_remove_post(self, user, request, task_id)

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

    def on_group_by_category_get(self, user: dict, request: Request) -> Response:
        page_number = 1
        by_feed = {}
        db_feeds = self.feeds.get_all(user["sid"])

        for f in db_feeds:
            by_feed[f["feed_id"]] = f
        if user["settings"]["only_unread"]:
            only_unread = user["settings"]["only_unread"]
        else:
            only_unread = None

        grouped = self.posts.get_grouped_stat(user["sid"], only_unread)
        by_category = {
            self.feeds.all_feeds: {
                "unread_count": 0,
                "title": self.feeds.all_feeds,
                "url": self.routes.get_url_by_endpoint(
                    endpoint="on_category_get",
                    params={"quoted_category": self.feeds.all_feeds},
                ),
                "feeds": [],
            }
        }
        for g in grouped:
            if g["count"] > 0:
                if g["category_id"] not in by_category:
                    by_category[g["category_id"]] = {
                        "unread_count": 0,
                        "title": by_feed[g["_id"]]["category_title"],
                        "url": by_feed[g["_id"]]["category_local_url"],
                        "feeds": [],
                    }
                by_category[g["category_id"]]["unread_count"] += g["count"]
                by_category[self.feeds.all_feeds]["unread_count"] += g["count"]
                by_category[g["category_id"]]["feeds"].append(
                    {
                        "unread_count": g["count"],
                        "url": by_feed[g["_id"]]["local_url"],
                        "title": by_feed[g["_id"]]["title"],
                    }
                )
        if len(by_category) > 1:
            data = get_sorted_dict_by_alphabet(by_category)
            if self.no_category_name in data:
                data.move_to_end(self.no_category_name)
        else:
            data = OrderedDict()
        page = self.template_env.get_template("group-by-category.html")

        return Response(
            page.render(
                data=data,
                group_by_link=self.routes.get_url_by_endpoint(
                    endpoint="on_group_by_tags_get", params={"page_number": page_number}
                ),
                user_settings=user["settings"],
                provider=user["provider"],
            ),
            mimetype="text/html",
        )

    def on_category_get(
        self, user: dict, request: Request, quoted_category: str
    ) -> Response:
        return posts_handlers.on_category_get(self, user, request, quoted_category)

    def on_tag_get(self, user: dict, request: Request, quoted_tag: str) -> Response:
        return posts_handlers.on_tag_get(self, user, request, quoted_tag)

    def on_bi_gram_get(self, user: dict, request: Request, bi_gram: str) -> Response:
        return posts_handlers.on_bi_gram_get(self, user, request, bi_gram)

    def on_feed_get(self, user: dict, request: Request, quoted_feed: str) -> Response:
        return posts_handlers.on_feed_get(self, user, request, quoted_feed)

    def on_read_posts_post(self, user: dict, request: Request) -> Response:
        return posts_handlers.on_read_posts_post(self, user, request)

    def calc_pager_data(
        self,
        p_number,
        page_count,
        items_per_page,
        endpoint,
        sentiment="",
        group="",
        letter="",
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

    def on_get_tag_page(self, user: dict, request: Request, tag: str) -> Response:
        return tags_handlers.on_get_tag_page(self, user, request, tag)

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

    def on_get_tag_bi_grams_graph_debug(self, user: dict, _: Request, tag: str) -> Response:
        return bigrams_handlers.on_get_tag_bi_grams_graph_debug(self, user, tag)

    def on_posts_content_post(self, user: dict, request: Request) -> Response:
        return posts_handlers.on_posts_content_post(self, user, request)

    def on_post_links_get(self, user: dict, _: Request, post_id: int) -> Response:
        return posts_handlers.on_post_links_get(self, user, post_id)

    def on_post_grouped_get(self, user: dict, request: Request, pids: str) -> Response:
        return posts_handlers.on_post_grouped_get(self, user, request, pids)

    def on_post_grouped_snippets_get(self, user: dict, request: Request, pids: str) -> Response:
        return posts_handlers.on_post_grouped_snippets_get(self, user, request, pids)

    def on_topics_list_get(self, user: dict, request: Request, page_number: int = 1) -> Response:
        return posts_handlers.on_topics_list_get(self, user, request, page_number)

    def on_post_graph_get(self, user: dict, request: Request, pids: str) -> Response:
        return posts_handlers.on_post_graph_get(self, user, request, pids)

    def _handle_sentence_grouping_chunking(self, sentences_list: list, original_prompt: str, temperature: float = 0.0, max_sentences_per_chunk: int = 10) -> str:
        """
        Handle chunking for sentence grouping when request is too large.
        Splits sentences into smaller batches and includes the prompt with each batch.
        """
        # Extract the prompt template and instructions from the original prompt
        sentences_start = original_prompt.find("Sentences:\n") + 11
        if sentences_start == 10:  # "Sentences:\n" not found
            logging.error("Cannot parse grouping prompt for chunking")
            return ""
        
        prompt_template = original_prompt[:sentences_start]
        
        # Split sentences into chunks
        chunks = []
        for i in range(0, len(sentences_list), max_sentences_per_chunk):
            chunk = sentences_list[i:i + max_sentences_per_chunk]
            chunks.append(chunk)
        
        logging.info(f"Splitting {len(sentences_list)} sentences into {len(chunks)} chunks")
        
        # Process each chunk with the full prompt
        all_groups = {}
        
        for chunk_idx, sentence_chunk in enumerate(chunks):
            # Build numbered sentences for this chunk
            chunk_lines = []
            for s in sentence_chunk:
                txt = s["text"].strip()
                chunk_lines.append(f"{s['number']}. {txt}")
            
            numbered_sentences_chunk = "\n".join(chunk_lines)
            chunk_prompt = prompt_template + numbered_sentences_chunk
            
            try:
                logging.info(f"Processing chunk {chunk_idx + 1}/{len(chunks)} with {len(sentence_chunk)} sentences")
                response = self.llamacpp.call([chunk_prompt], temperature).strip()
                
                # Parse groups from response
                lines = [ln.strip() for ln in response.strip().split('\n') if ln.strip()]
                for ln in lines:
                    if ':' in ln:
                        parts = ln.split(':', 1)
                        if len(parts) == 2:
                            topic, nums = parts
                            topic = topic.strip()
                            nums = nums.strip()
                            if nums and topic:
                                # Create unique topic name if it already exists
                                original_topic = topic
                                counter = 1
                                while topic in all_groups:
                                    topic = f"{original_topic} (Part {counter})"
                                    counter += 1
                                all_groups[topic] = nums
                                
            except Exception as e:
                logging.error(f"Chunked grouping failed for chunk {chunk_idx + 1}: %s", e)
                continue
        
        # Combine results into the expected format
        result_lines = []
        for topic, nums in all_groups.items():
            result_lines.append(f"{topic}: {nums}")
        
        return '\n'.join(result_lines)

    # TODO: delete or change or something other
    def on_get_posts_with_tags(self, user: dict, _: Request, s_tags: str) -> Response:
        return posts_handlers.on_get_posts_with_tags(self, user, s_tags)

    def on_post_tags_search(self, user: dict, request: Request) -> Response:
        return tags_handlers.on_post_tags_search(self, user, request)

    def on_get_map(self, user: dict, request: Request) -> Response:
        projection = {"_id": False}
        cities = self.tags.get_city_tags(
            user["sid"], user["settings"]["only_unread"], projection
        )
        countries = self.tags.get_country_tags(
            user["sid"], user["settings"]["only_unread"], projection
        )
        page = self.template_env.get_template("map.html")

        return Response(
            page.render(
                support=self.config["settings"]["support"],
                version=self.config["settings"]["version"],
                user_settings=user["settings"],
                provider=user["provider"],
                cities=list(cities),
                countries=list(countries),
            ),
            mimetype="text/html",
        )

    def on_get_tag_net(self, user: dict, request: Request, tag="") -> Response:
        all_tags = []
        edges = defaultdict(set)
        if user["settings"]["only_unread"]:
            only_unread = user["settings"]["only_unread"]
        else:
            only_unread = None

        posts = self.posts.get_by_tags(user["sid"], [tag], only_unread, {"tags": True})
        tags_set = set()
        for post in posts:
            for tag in post["tags"]:
                tags_set.add(tag)
                for tg in post["tags"]:
                    edges[tag].add(tg)

        if tags_set:
            db_tags = self.tags.get_by_tags(
                user["sid"], list(tags_set), user["settings"]["only_unread"]
            )
            for tag in db_tags:
                edges[tag["tag"]].remove(tag["tag"])
                all_tags.append(
                    {
                        "tag": tag["tag"],
                        "url": tag["local_url"],
                        "words": tag["words"],
                        "count": tag["unread_count"]
                        if user["settings"]["only_unread"]
                        else tag["posts_count"],
                        "edges": list(edges[tag["tag"]])[:5],
                        "sentiment": tag["sentiment"] if "sentiment" in tag else [],
                    }
                )

        return Response(
            json.dumps({"data": all_tags}),
            mimetype="application/json",
        )

    def on_get_tag_net_page(self, user: dict, request: Request) -> Response:
        page = self.template_env.get_template("tags-net.html")

        return Response(
            page.render(
                support=self.config["settings"]["support"],
                version=self.config["settings"]["version"],
                user_settings=user["settings"],
                provider=user["provider"],
            ),
            mimetype="text/html",
        )

    def on_get_groups(self, user: dict, request: Request, page_number=1) -> Response:
        groups = self.tags.get_groups(user["sid"], user["settings"]["only_unread"])
        groups_count = len(groups)
        page_count = self.get_page_count(groups_count, user["settings"]["tags_on_page"])
        p_number = page_number
        if page_number <= 0:
            p_number = 1
        elif page_number > page_count:
            p_number = page_count

        p_number -= 1
        if p_number < 0:
            p_number = 1
        pages_map, start_tags_range, end_tags_range = self.calc_pager_data(
            p_number,
            page_count,
            user["settings"]["tags_on_page"],
            "on_get_groups",
        )

        page_groups = sorted(groups.items(), key=lambda el: el[1], reverse=True)
        page = self.template_env.get_template("tags-groups.html")

        return Response(
            page.render(
                support=self.config["settings"]["support"],
                version=self.config["settings"]["version"],
                user_settings=user["settings"],
                provider=user["provider"],
                pages_map=pages_map,
                groups=page_groups[start_tags_range:end_tags_range],
            ),
            mimetype="text/html",
        )

    def on_tag_dates_get(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_tag_dates_get(self, user, tag)

    def on_bigrams_dates_get(self, user: dict, _: Request, tag: str) -> Response:
        return bigrams_handlers.on_bigrams_dates_get(self, user, tag)

    def on_wordtree_texts_get(self, user: dict, request: Request, tag: str) -> Response:
        if tag:
            cursor = self.posts.get_by_tags(
                user["sid"], [tag], user["settings"]["only_unread"], {"lemmas": True}
            )
            data = []
            window = 10
            for post in cursor:
                text = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
                words = text.split()
                for i, word in enumerate(words):
                    if word == tag:
                        start_pos = i - window
                        if start_pos < 0:
                            start_pos = 0
                        end_pos = i + window
                        data.append(" ".join(words[start_pos:end_pos]))
            result = {"data": data}
            code = 200
        else:
            result = {"error": "Something wrong with request"}
            code = 400

        return Response(json.dumps(result), mimetype="application/json", status=code)

    def on_tag_topics_get(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_tag_topics_get(self, user, tag)

    def on_topics_texts_get(self, user: dict, request: Request, tag: str) -> Response:
        if tag:
            cursor = self.posts.get_by_tags(
                user["sid"], [tag], user["settings"]["only_unread"], {"lemmas": True}
            )
            texts = [
                gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
                for post in cursor
            ]
            lda = LDA()
            topics = lda.topics(texts, top_k=5)
            if tag in topics:
                topics.remove(tag)
            result = {"data": {"texts": texts, "topics": topics}}
            code = 200
        else:
            result = {"error": "Something wrong with request"}
            code = 400

        return Response(json.dumps(result), mimetype="application/json", status=code)

    def on_topics_get(
        self, user: dict, request: Request, page_number: int = 1
    ) -> Response:
        all_tags = []
        cursor = self.posts.get_all(
            user["sid"], user["settings"]["only_unread"], {"lemmas": True}
        )
        texts = [
            gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
            for post in cursor
        ]
        lda = LDA()
        topics = lda.topics(texts, top_k=10)
        tags = self.tags.get_by_tags(
            user["sid"], topics, user["settings"]["only_unread"]
        )
        for tag in tags:
            all_tags.append(
                {
                    "tag": tag["tag"],
                    "url": tag["local_url"],
                    "words": tag["words"],
                    "count": tag["unread_count"]
                    if user["settings"]["only_unread"]
                    else tag["posts_count"],
                    "sentiment": tag["sentiment"] if "sentiment" in tag else [],
                    "temp": tag["temperature"],
                }
            )
        all_tags.sort(key=lambda t: t["temp"], reverse=True)
        page_count = self.get_page_count(1, user["settings"]["tags_on_page"])
        p_number = page_number
        if page_number <= 0:
            p_number = 1
        elif page_number > page_count:
            p_number = page_count

        new_cookie_page_value = p_number
        p_number -= 1
        if p_number < 0:
            p_number = 1
        pages_map, start_tags_range, end_tags_range = self.calc_pager_data(
            p_number, page_count, user["settings"]["tags_on_page"], "on_topics_get"
        )
        db_letters = self.letters.get(user["sid"], make_sort=True)
        if db_letters:
            letters = self.letters.to_list(db_letters, user["settings"]["only_unread"])
        else:
            letters = []
        page = self.template_env.get_template("group-by-tag.html")

        return Response(
            page.render(
                tags=all_tags,
                sort_by_title="tags",
                sort_by_link=self.routes.get_url_by_endpoint(
                    endpoint="on_group_by_tags_get",
                    params={"page_number": new_cookie_page_value},
                ),
                group_by_link=self.routes.get_url_by_endpoint(
                    endpoint="on_group_by_category_get"
                ),
                pages_map=pages_map,
                current_page=new_cookie_page_value,
                letters=letters,
                user_settings=user["settings"],
                provider=user["provider"],
            ),
            mimetype="text/html",
        )

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

    def on_tag_tfidf_get(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_tag_tfidf_get(self, user, tag)

    def on_tag_clusters_get(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_tag_clusters_get(self, user, tag)

    def on_tag_contexts_classification_get(
        self, user: dict, request: Request, tag: str
    ) -> Response:
        return tags_handlers.on_tag_contexts_classification_get(self, user, request, tag)

    def on_posts_get(self, user: dict, request: Request, pids: str) -> Response:
        return posts_handlers.on_posts_get(self, user, request, pids)

    def on_get_tag_pmi(self, user: dict, _: Request, tag: str) -> Response:
        return tags_handlers.on_get_tag_pmi(self, user, tag)

    def on_get_sentences_with_tags(
        self, user: dict, request: Request, s_tags: str
    ) -> Response:
        if not s_tags:
            return self.on_error(user, request, NotFound())

        q_tags = s_tags.split(" ")
        if user["settings"]["only_unread"]:
            only_unread = user["settings"]["only_unread"]
        else:
            only_unread = None

        db_posts = self.posts.get_by_tags(user["sid"], q_tags, only_unread=only_unread)
        db_tags = self.tags.get_by_tags(user["sid"], q_tags, only_unread=only_unread)

        words = set()
        for t in db_tags:
            words.update(t["words"])
        by_feed = {}
        sentences = []
        html_c = HTMLCleaner()
        w_cond = "|".join(words)
        w_reg = re.compile(".*({}).*".format(w_cond), re.I|re.S)
        for post in db_posts:
            txt = gzip.decompress(post["content"]["content"]).decode("utf-8", "replace")
            if post["content"]["title"]:
                txt = post["content"]["title"] + ". " + txt
            html_c.purge()
            html_c.feed(txt)
            txt = " ".join(html_c.get_content())
            if post["feed_id"] not in by_feed:
                feed = self.feeds.get_by_feed_id(user["sid"], post["feed_id"])
                if feed:
                    by_feed[post["feed_id"]] = feed
            sents = []
            #t = t.replace(mtch.group(1), "<b>{}</b>".format(mtch.group(1)))
            if not sents:
                continue
            sentences.append(
                {
                    "sentence": sents,
                    "pid": post["pid"],
                    "category_title": by_feed[post["feed_id"]]["category_title"],
                    "feed_title": by_feed[post["feed_id"]]["title"],
                    "favicon": by_feed[post["feed_id"]]["favicon"],
                    "date": post["date"],
                }
            )
        page = self.template_env.get_template("sentences.html")

        return Response(
            page.render(
                sentences=sentences,
                tag=s_tags,
                group="tag",
                words=list(words),
                user_settings=user["settings"],
                provider=user["provider"],
            ),
            mimetype="text/html",
        )

    def on_s_tree_get(self, user: dict, request: Request, tag: str) -> Response:
        return tags_handlers.on_s_tree_get(self, user, request, tag)

    def on_cluster_get(self, user: dict, _: Request, cluster: int) -> Response:
        return posts_handlers.on_cluster_get(self, user, cluster)

    def on_clusters_get(self, user: dict, request: Request) -> Response:
        projection = {"_id": True, "clusters": True, "tags": True, "lemmas": True}
        if user["settings"]["only_unread"]:
            only_unread = user["settings"]["only_unread"]
        else:
            only_unread = None
        db_posts = self.posts.get_all(user["sid"], only_unread, projection)

        links = {}
        for post in db_posts:
            if "clusters" not in post:
                continue

            text = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
            if not text.strip():
                continue
            for cl in post["clusters"]:
                if cl not in links:
                    links[cl] = {
                        "l": self.routes.get_url_by_endpoint(
                            endpoint="on_cluster_get", params={"cluster": cl}
                        ),
                        "n": 0,
                        "texts": [],
                        "tags": [],
                    }
                links[cl]["n"] += 1
                links[cl]["texts"].append(text)
                links[cl]["tags"].extend(post.get("tags", []))

        # Compute centroid and top words for each cluster
        stopw = set(stopwords.words("english") + stopwords.words("russian"))
        for cl in links:
            texts = links[cl]["texts"]
            if texts:
                try:
                    vectorizer = TfidfVectorizer(stop_words=list(stopw))
                    vectors = vectorizer.fit_transform(texts)
                    if vectors.shape[1] == 0:
                        raise ValueError("empty vocabulary")
                    centroid = vectors.mean(axis=0).A1
                    feature_names = vectorizer.get_feature_names_out()
                    top_indices = centroid.argsort()[-3:][::-1]
                    top_words = [feature_names[i] for i in top_indices]
                    links[cl]["top_tags"] = ", ".join(top_words)
                except ValueError:
                    # Fall back to tag frequency
                    tags = links[cl]["tags"]
                    if tags:
                        from collections import Counter
                        counter = Counter(tags)
                        top_tags = [tag for tag, _ in counter.most_common(3)]
                        links[cl]["top_tags"] = ", ".join(top_tags)
                    else:
                        links[cl]["top_tags"] = f"Cluster {cl}"
            else:
                links[cl]["top_tags"] = f"Cluster {cl}"

        lnks = [(links[cl]["top_tags"], links[cl]["l"], links[cl]["n"]) for cl in links]
        lnks.sort(key=lambda x: x[2], reverse=True)
        page = self.template_env.get_template("clusters.html")

        return Response(
            page.render(
                links=lnks, user_settings=user["settings"], provider=user["provider"]
            ),
            mimetype="text/html",
        )

    def on_clusters_dyn_get(self, user: dict, request: Request) -> Response:
        projection = {"_id": False, "lemmas": True, "pid": True, "tags": True}
        if user["settings"]["only_unread"]:
            only_unread = user["settings"]["only_unread"]
        else:
            only_unread = None
        db_posts = self.posts.get_all(user["sid"], only_unread, projection)

        texts = []
        pids = []
        post_tags = []
        for post in db_posts:
            text = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
            if not text.strip():
                continue
            texts.append(text)
            pids.append(post["pid"])
            post_tags.append(post.get("tags", []))

        stopw = set(stopwords.words("english") + stopwords.words("russian"))
        vectorizer = TfidfVectorizer(stop_words=list(stopw))
        vectorizer.fit(texts)
        vectors = vectorizer.transform(texts)
        dbs = DBSCAN(eps=0.7, min_samples=2, metric="cosine")
        cl = dbs.fit_predict(vectors)
        label_pids = defaultdict(list)
        label_texts = defaultdict(list)
        label_tags = defaultdict(list)
        for i, label in enumerate(cl):
            if label < 0:
                continue
            label_pids[label].append(str(pids[i]))
            label_texts[label].append(texts[i])
            label_tags[label].extend(post_tags[i])

        links = {}
        for label, pids_list in label_pids.items():
            links[label] = {
                "l": self.routes.get_url_by_endpoint(
                    endpoint="on_posts_get", params={"pids": "_".join(pids_list)}
                ),
                "n": len(pids_list),
                "texts": label_texts[label],
                "tags": label_tags[label],
            }

        # Compute centroid and top words for each cluster
        for label in links:
            texts_for_cluster = links[label]["texts"]
            if texts_for_cluster:
                try:
                    cluster_vectorizer = TfidfVectorizer(stop_words=list(stopw))
                    cluster_vectors = cluster_vectorizer.fit_transform(texts_for_cluster)
                    if cluster_vectors.shape[1] == 0:
                        raise ValueError("empty vocabulary")
                    centroid = cluster_vectors.mean(axis=0).A1
                    feature_names = cluster_vectorizer.get_feature_names_out()
                    top_indices = centroid.argsort()[-3:][::-1]
                    top_words = [feature_names[i] for i in top_indices]
                    links[label]["top_tags"] = ", ".join(top_words)
                except ValueError:
                    # Fall back to tag frequency
                    tags = links[label]["tags"]
                    if tags:
                        from collections import Counter
                        counter = Counter(tags)
                        top_tags = [tag for tag, _ in counter.most_common(3)]
                        links[label]["top_tags"] = ", ".join(top_tags)
                    else:
                        links[label]["top_tags"] = f"Cluster {label}"
            else:
                links[label]["top_tags"] = f"Cluster {label}"

        lnks = [(links[cl]["top_tags"], links[cl]["l"], links[cl]["n"]) for cl in links]
        lnks.sort(key=lambda x: x[2], reverse=True)
        page = self.template_env.get_template("clusters.html")

        return Response(
            page.render(
                links=lnks, user_settings=user["settings"], provider=user["provider"]
            ),
            mimetype="text/html",
        )

    def on_telegram_auth_post(self, user: dict, request: Request) -> Response:
        return users_handlers.on_telegram_auth_post(self, user, request)

    def on_tag_specific_get(self, user: dict, _: Request, tag: str):
        return tags_handlers.on_tag_specific_get(self, user, tag)

    def on_tag_specific1_get(self, user: dict, _: Request, tag: str):
        return tags_handlers.on_tag_specific1_get(self, user, tag)

    def on_get_context_tags(self, user: dict, request: Request, tags: str):
        return tags_handlers.on_get_context_tags(self, user, request, tags)

    def on_get_tag_similar_tags(self, user: dict, _: Request, tags: str):
        return tags_handlers.on_get_tag_similar_tags(self, user, tags)

    def on_group_by_bigrams_dyn_get(self, user: dict, _: Request, page_number: int):
        return bigrams_handlers.on_group_by_bigrams_dyn_get(self, user, page_number)

    def on_mark_telegram_posts_post(self, user: dict, request: Request):
        return posts_handlers.on_mark_telegram_posts_post(self, user, request)

    def on_read_snippet_post(self, user: dict, request: Request) -> Response:
        return posts_handlers.on_read_snippet_post(self, user, request)

    def on_gmail_sort_post(self, user: dict, request: Request):
        return posts_handlers.on_gmail_sort_post(self, user, request)

    def on_tfidf_tags_get(self, user: dict, rqst: Request):
        return tags_handlers.on_get_tfidf_tags(self, user, rqst)

    def on_sunburst_get(self, user: dict, _: Request, tags: str):
        return tags_handlers.on_get_sunburst(self, user, tags)

    def on_chain_get(self, user: dict, _: Request, tags: str):
        return tags_handlers.on_get_chain(self, user, tags)

    def on_openai_post(self, user: dict, request: Request):
        return openai_handlers.on_openai_post(self, user, request)

    def on_chat_post(self, user: dict, request: Request):
        return chat_handlers.on_chat_post(self, user, request)

    def on_prefixes_all_get(self, user: dict, _: Request, prefix_len: int):
        return prefixes_handlers.on_prefixes_all_get(self, user, prefix_len)

    def on_prefixes_words_get(self, user: dict, _: Request, prefix: str):
        return prefixes_handlers.on_prefixes_words_get(self, user, prefix)

    def on_prefixes_prefix_get(self, user: dict, _: Request, prefix: str):
        return prefixes_handlers.on_prefixes_prefix_get(self, user, prefix)
