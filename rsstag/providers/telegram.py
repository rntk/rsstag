"""RSSTag downloaders"""

import time
import gzip
import logging
from datetime import date, datetime
from random import randint, uniform
from typing import Tuple, List, Optional, Dict, Any
from collections import defaultdict
from io import StringIO
import unicodedata
from threading import Thread
from multiprocessing import Lock
from queue import Queue, Empty
import traceback
import re

from rsstag.tasks import POST_NOT_IN_PROCESSING
from rsstag.web.routes import RSSTagRoutes
from rsstag.users import TelegramAuthData
from rsstag.feeds import RssTagFeeds
from rsstag.posts import RssTagPosts
from rsstag.providers.providers import TELEGRAM
from rsstag.providers.pid import generate_post_pid

from pymongo import MongoClient

from telegram.client import Telegram
from telegram.client import Result as TelegramResult
from telegram.queries import (
    get_message_link,
    get_chat,
    get_chats,
    load_chats,
    get_chat_history,
    search_channel,
    open_chat,
    close_chat,
    view_messages,
)

NOT_CATEGORIZED = "NotCategorized"
TELEGRAM_LOCK = Lock()

ME_BOLD = "textEntityTypeBold"
ME_ITALIC = "textEntityTypeItalic"
ME_CODE = "textEntityTypeCode"
ME_STRIKE = "textEntityTypeStrike"
ME_UNDERLINE = "textEntityTypeUnderline"
ME_PRE = "textEntityTypePre"
ME_TEXT_URL = "textEntityTypeTextUrl"


def tlg_poll_to_html(post: dict) -> str:
    if post["content"]["poll"]["@type"] != "poll":
        return ""

    result_html = StringIO()
    question_text = (
        post["content"]["poll"]["question"].get("text", "")
        if isinstance(post["content"]["poll"]["question"], dict)
        else str(post["content"]["poll"]["question"])
    )
    result_html.write("<p>" + question_text + "</p><ol>")
    for opt in post["content"]["poll"]["options"]:
        if opt["@type"] != "pollOption":
            continue

        option_text = (
            opt["text"].get("text", "")
            if isinstance(opt["text"], dict)
            else str(opt["text"])
        )
        result_html.write("<li>" + option_text + "</li>")
    result_html.write("</ol>")

    return result_html.getvalue()


def tlg_webpage_to_html(post: dict) -> str:
    if "content" not in post:
        return ""
    cont = post["content"]
    if "web_page" not in cont:
        return ""
    wp = cont["web_page"]
    link = wp.get("url", "")
    if wp.get("@type", "") != "webPage":
        return "UNKNOWN_WEB_PAGE"

    html_s = ""
    if "site_name" in wp:
        html_s += wp["site_name"] + "<br />"
    if "title" in wp:
        html_s += wp["title"] + "<br />"
    if "description" in wp:
        html_s += wp["description"].get("text", "") + "<br />"

    html_s = '<br /><p><a href="{}">{}</a></p>'.format(link, html_s)

    return html_s


# https://core.telegram.org/type/MessageEntity
# https://core.telegram.org/api/entities
def tlg_post_to_html(post: dict) -> str:
    if post["content"]["@type"] == "messagePoll":
        return tlg_poll_to_html(post)

    result_html = StringIO()
    entities = []
    post_text = ""
    if "caption" in post["content"]:
        entities = post["content"]["caption"]["entities"]
        post_text = post["content"]["caption"]["text"]
    elif "text" in post["content"]:
        t = post["content"].get("@type", "")
        if t != "messageCustomServiceAction":
            entities = post["content"]["text"]["entities"]
            post_text = post["content"]["text"]["text"]
        else:
            post_text = post["content"]["text"]
    starts = defaultdict(list)
    ends = defaultdict(list)
    for ent in entities:
        if "textEntity" != ent["@type"]:
            continue
        s = ent["offset"]
        e = s + ent["length"] - 1
        t = ent["type"]["@type"]
        starts[s].append(ent)
        ends[e].append(t)
    i = 0
    for symb in post_text:
        if i in starts:
            for enti in starts[i]:
                en = enti["type"]["@type"]
                tag = ""
                if en == ME_BOLD:
                    tag = "<b>"
                elif en == ME_ITALIC:
                    tag = "<i>"
                elif en == ME_CODE:
                    tag = "<code>"
                elif en == ME_STRIKE:
                    tag = "<s>"
                elif en == ME_UNDERLINE:
                    tag = "<u>"
                elif en == ME_PRE:
                    tag = "<i>"
                elif en == ME_TEXT_URL:
                    tag = '<a href="{}">'.format(enti["type"]["url"])

                result_html.write(tag)

        result_html.write(symb)

        if i in ends:
            for en in ends[i]:
                tag = ""
                if en == ME_BOLD:
                    tag = "</b>"
                elif en == ME_ITALIC:
                    tag = "</i>"
                elif en == ME_CODE:
                    tag = "</code>"
                elif en == ME_STRIKE:
                    tag = "</s>"
                elif en == ME_UNDERLINE:
                    tag = "</u>"
                elif en == ME_PRE:
                    tag = "</i>"
                elif en == ME_TEXT_URL:
                    tag = "</a>"

                result_html.write(tag)

        if symb == "\n":
            result_html.write("<br />")

        b = symb.encode("utf-8")
        b_ln = len(b)
        if b_ln > 2:
            cat = unicodedata.category(symb)
            if (b_ln >= 4 and cat == "So") or (b_ln >= 3 and cat == "Sk"):
                i += 2
                continue

        i += 1
    webpage = tlg_webpage_to_html(post)
    if webpage != "":
        result_html.write(" " + webpage)

    s = result_html.getvalue().strip()
    if s == "":
        s = post["content"]["@type"]

    return s


def tlg_forward_to_query(post: dict) -> Optional[dict]:
    if "forward_info" not in post:
        return None

    fi = post["forward_info"]
    if fi.get("@type", "") != "messageForwardInfo":
        return None

    if "origin" not in fi:
        return None

    orig = fi["origin"]
    if orig.get("@type", "") != "messageForwardOriginChannel":
        return None

    chat_id = orig.get("chat_id", None)
    if not chat_id:
        return None

    msg_id = orig.get("message_id", None)
    if not msg_id:
        return None

    return {"chat_id": chat_id, "message_id": msg_id}


class TelegramProvider:
    def __init__(self, config: dict, db: MongoClient):
        self._config = config
        self._db = db
        if self._config["settings"]["no_category_name"]:
            self.no_category_name = self._config["settings"]["no_category_name"]
        else:
            self.no_category_name = NOT_CATEGORIZED

    def _fetch(self, tasks_q: Queue, results_q: Queue):
        while not tasks_q.empty():
            try:
                dt = tasks_q.get_nowait()
            except Empty:
                return
            all_channels, max_limit, channel = dt

            if all_channels:
                if "is_channel" in channel["type"]:
                    if not channel["type"]["is_channel"]:
                        logging.warning("Skip not channel %s: ", channel)
                        tasks_q.task_done()
                        continue
                else:
                    logging.warning("Skip no is_channel: %s", channel)
                    tasks_q.task_done()
                    continue
            limit = channel["unread_count"]
            if max_limit <= 0:
                if limit <= 0:
                    tasks_q.task_done()
                    # no unread posts
                    continue
                # load only unreaded posts
                if max_limit < 0:
                    max_limit = abs(max_limit)
                    if limit < max_limit:
                        max_limit = limit
                    else:
                        limit = max_limit
                else:
                    max_limit = limit
            else:
                limit = max_limit

            from_id = 0
            posts_n = 0
            has_posts = True
            while has_posts and posts_n < max_limit:
                if limit <= 0:
                    has_posts = False
                    continue
                posts_req = self.__requests_repeater(
                    get_chat_history(
                        channel["id"], limit=limit, from_message_id=from_id
                    )
                )
                posts_data = posts_req.update
                if (not posts_req.update) or (len(posts_data["messages"]) == 0):
                    has_posts = False
                    if posts_req.error:
                        logging.warning(
                            "Channel history error %s: %s",
                            channel["id"],
                            posts_req.error,
                        )
                    continue
                logging.info(
                    "Batch loaded. Channel %s from %s. Posts - %s. All Posts - %s",
                    channel["id"],
                    from_id,
                    len(posts_data["messages"]),
                    posts_n,
                )
                if len(posts_data["messages"]) > 0:
                    from_id = posts_data["messages"][-1]["id"]
                    limit -= len(posts_data["messages"])
                posts_n += len(posts_data["messages"])
                posts_links = []
                for post in posts_data["messages"]:
                    resp = self.__requests_repeater(
                        get_message_link(post["chat_id"], post["id"])
                    )
                    frw_q = tlg_forward_to_query(post)
                    post_l = resp.update["link"]
                    if frw_q:
                        # resp = self.__requests_repeater(get_message_link(frw_q["chat_id"], frw_q["message_id"]))
                        # if resp.update:
                        # TODO: refactor may be add link as additional field
                        #    post_l += "\n" + resp.update["link"]
                        post_l += "\n" + "https://t.me/{}/{}".format(
                            frw_q["chat_id"], frw_q["message_id"]
                        )

                    posts_links.append(post_l)

                results_q.put_nowait((channel["id"], posts_data, posts_links))
                time.sleep(uniform(1, 3))

            tasks_q.task_done()
            logging.info("Downloaded: %s - %s", channel["title"], posts_n)
            time.sleep(1)

    def __requests_repeater(self, query: Dict[str, Any]) -> TelegramResult:
        on_error_repeats = 3
        repeats = 0
        all_repeats = 0
        r = None
        while True:
            if all_repeats > 0:
                logging.warning(
                    "Repeat telegram request: %d. %s. %s", all_repeats, query, r
                )
            all_repeats += 1
            r = self._tlg.request(query)
            if r.update is not None:
                return r
            if r.error:
                # example: {'@type': 'error', 'code': 429, 'message': 'Too Many Requests: retry after 77616', '@extra': {'req_id': '1643864060.31774_9523'}, '@client_id': 1}
                if "code" in r.error:
                    code = r.error["code"]
                    if code == 429 or code == 420:
                        wait_time = randint(7, 20)
                        if "message" in r.error:
                            msg = r.error["message"]
                            matches = re.findall(r"\d+", msg)
                            if matches:
                                wait_time = int(matches[0]) + 1

                        logging.warning(
                            "Flood wait detected: %d seconds. Message: %s",
                            wait_time,
                            r.error.get("message"),
                        )
                        time.sleep(wait_time)
                        continue

                repeats += 1
                if repeats > on_error_repeats:
                    logging.warning(
                        "Max repeats reached for telegram request: %s", query
                    )
                    return r

            wait_time = randint(1, 10)
            logging.info(
                "Waiting %d seconds before repeating telegram request: %s",
                wait_time,
                query,
            )
            time.sleep(wait_time)

    def list_channels(self, user: dict) -> List[dict]:
        provider = user["provider"]
        logging.info("Starting Telegram provider for user: %s", user.get("sid"))
        self._tlg = Telegram(
            app_id=self._config[provider]["app_id"],
            app_hash=self._config[provider]["app_hash"],
            phone=user["phone"],
            db_key=self._config[provider]["encryption_key"],
            db_path=self._config[provider]["db_dir"],
        )
        tlg_code = TelegramAuthData(self._db, user["sid"])
        if not self._tlg.login(tlg_code.get_code, tlg_code.get_password):
            logging.error("Telegram login failed for user: %s", user.get("sid"))
            raise Exception("Telegram login failed")

        logging.info("Telegram login successful, starting TDLib client")
        self._tlg.run()

        logging.info("Waiting 30 seconds for TDLib to initialize...")
        time.sleep(30)

        channels = []
        # Pre-load chats into TDLib memory to avoid flood waits on getChat
        logging.info("Pre-loading chats (load_chats)...")
        self.__requests_repeater(load_chats(limit=1000))

        uniq_chat_ids = set()
        logging.info("Fetching chat IDs (get_chats)...")
        r = self.__requests_repeater(get_chats(limit=1000))
        ids = r.update
        if ids and ids["chat_ids"]:
            total_chats = len(ids["chat_ids"])
            logging.info(
                "Found %d chat IDs. Fetching individual chat details...", total_chats
            )
            for i, c_id in enumerate(ids["chat_ids"]):
                if c_id in uniq_chat_ids:
                    continue
                uniq_chat_ids.add(c_id)

                if i % 10 == 0:
                    logging.info("Processing chat %d/%d", i + 1, total_chats)

                r = self.__requests_repeater(get_chat(c_id))
                time.sleep(randint(1, 3))
                if not r.update:
                    logging.warning("Failed to get chat details for chat_id: %d", c_id)
                    continue
                channel = r.update
                channels.append(
                    {"id": channel["id"], "title": channel.get("title", str(c_id))}
                )
        else:
            logging.warning("No chat IDs found in get_chats response")

        logging.info("Closing Telegram client")
        self._tlg.close()

        return channels

    def download(
        self, user: dict, selection: Optional[dict] = None
    ) -> Tuple[List, List]:
        provider = user["provider"]
        all_channels = user["telegram_channel"].lower() == "all"
        selected_channels = []
        if selection:
            selected_channels = [
                channel_id for channel_id in selection.get("channels", []) if channel_id
            ]
        self._tlg: Telegram = Telegram(
            app_id=self._config[provider]["app_id"],
            app_hash=self._config[provider]["app_hash"],
            phone=user["phone"],
            db_key=self._config[provider]["encryption_key"],
            db_path=self._config[provider]["db_dir"],
        )
        tlg_code = TelegramAuthData(self._db, user["sid"])
        if not self._tlg.login(tlg_code.get_code, tlg_code.get_password):
            raise Exception("Telegram login failed")
        self._tlg.run()
        time.sleep(120)
        # Pre-load chats into TDLib memory to avoid flood waits on getChat
        self.__requests_repeater(load_chats(limit=1000))
        channels = []
        if selected_channels:
            for channel_id in selected_channels:
                try:
                    channel_id_int = int(channel_id)
                except (TypeError, ValueError):
                    logging.warning("Skip invalid channel id: %s", channel_id)
                    continue
                r = self.__requests_repeater(get_chat(channel_id_int))
                time.sleep(randint(1, 3))
                if not r.update:
                    continue
                channels.append(r.update)
        elif all_channels:
            uniq_chat_ids = set()
            r = self.__requests_repeater(get_chats(limit=1000))
            ids = r.update
            if ids and ids["chat_ids"]:
                for c_id in ids["chat_ids"]:
                    if c_id in uniq_chat_ids:
                        continue
                    uniq_chat_ids.add(c_id)
                    r = self.__requests_repeater(get_chat(c_id))
                    time.sleep(randint(1, 3))
                    if not r.update:
                        continue
                    logging.info("Loading chat data: %d", c_id)
                    channels.append(r.update)
        else:
            telegram_channels = user["telegram_channel"].split(",")
            for telegram_channel in telegram_channels:
                telegram_channel = telegram_channel.strip()
                if not telegram_channel:
                    continue
                channel_req = self.__requests_repeater(search_channel(telegram_channel))
                if not channel_req.update:
                    logging.warning(
                        "No channel: %s. %s", telegram_channel, channel_req.error
                    )
                    continue
                    # self._tlg.close()
                    # return ([], [])
                channels.append(channel_req.update)
        tasks_q = Queue()
        results_q = Queue()
        max_limit = user["settings"]["telegram_limit"]
        feeds = {}
        routes = RSSTagRoutes(self._config["settings"]["host_name"])
        for channel in channels:
            tasks_q.put_nowait((all_channels, max_limit, channel))
            stream_id = str(channel["id"])
            if stream_id not in feeds:
                feeds[stream_id] = {
                    "createdAt": datetime.utcnow(),
                    "title": channel["title"],
                    "owner": user["sid"],
                    "category_id": self.no_category_name,
                    "feed_id": stream_id,
                    "origin_feed_id": channel["id"],
                    "category_title": self.no_category_name,
                    "category_local_url": routes.get_url_by_endpoint(
                        endpoint="on_category_get",
                        params={"quoted_category": self.no_category_name},
                    ),
                    "local_url": routes.get_url_by_endpoint(
                        endpoint="on_feed_get", params={"quoted_feed": stream_id}
                    ),
                    "favicon": "",
                }
        workers = []
        workers_n = 1  # int(self._config["settings"]["downloaders_count"])
        if not workers_n:
            workers_n = 1
        if len(channels) == 1:
            workers_n = 1
        for i in range(workers_n):
            t = Thread(target=self._fetch, args=(tasks_q, results_q))
            t.start()
            workers.append(t)

        posts = []
        while True:
            try:
                data = results_q.get(timeout=1)
                stream_id, posts_data, posts_links = data
                results_q.task_done()
            except Empty:
                if tasks_q.empty():
                    if results_q.empty():
                        has_worker = False
                        for w in workers:
                            if w.is_alive():
                                has_worker = True
                                break

                        if has_worker:
                            continue
                        if results_q.empty():
                            break
                continue
            for post_i, post in enumerate(posts_data["messages"]):
                p_date = date.fromtimestamp(int(post["date"])).strftime("%x")
                pu_date = post["date"]

                attachments_list = []
                entities = []
                t_link = posts_links[post_i]
                if "\n" in t_link:
                    # TODO: refactor may be add link as additional field
                    parts = t_link.split("\n")
                    t_link = parts[0]
                    attachments_list.append(parts[1])
                try:
                    post_text = tlg_post_to_html(post)
                    if "caption" in post["content"]:
                        entities = post["content"]["caption"]["entities"]
                    elif "text" in post["content"]:
                        t = post["content"].get("@type", "")
                        if t != "messageCustomServiceAction":
                            entities = post["content"]["text"]["entities"]
                except Exception as e:
                    logging.error(
                        "tlg_post_to_html: {}. {}. {}".format(
                            post, e, traceback.format_exc()
                        )
                    )
                    continue
                for entity in entities:
                    if "type" in entity and "url" in entity["type"]:
                        attachments_list.append(entity["type"]["url"])

                posts.append(
                    {
                        "content": {
                            "title": "",
                            "content": gzip.compress(
                                post_text.encode("utf-8", "replace")
                            ),
                        },
                        "feed_id": str(stream_id),
                        "category_id": self.no_category_name,
                        "id": post["id"],
                        "url": t_link,
                        "date": p_date,
                        "unix_date": pu_date,
                        "read": False,
                        "favorite": False,
                        "attachments": attachments_list,
                        "tags": [],
                        "bi_grams": [],
                        "pid": generate_post_pid(
                            TELEGRAM, str(stream_id), str(post["id"])
                        ),
                        "owner": user["sid"],
                        "processing": POST_NOT_IN_PROCESSING,
                    }
                )
            if len(posts) > 5000:
                yield (posts, list(feeds.values()))
                posts = []
            time.sleep(randint(1, 3))

        self._tlg.close()

        yield (posts, list(feeds.values()))

    def _tlg_sync(self, phone: str, sid: str, sync_ids: List[Tuple[int, int]]) -> None:
        if not sync_ids:
            return
        TELEGRAM_LOCK.acquire()
        try:
            t_cfg = self._config[TELEGRAM]
            tlg = Telegram(
                app_id=t_cfg["app_id"],
                app_hash=t_cfg["app_hash"],
                phone=phone,
                db_key=t_cfg["encryption_key"],
                db_path=t_cfg["db_dir"],
            )
            tlg_code = TelegramAuthData(self._db, sid)
            if not tlg.login(tlg_code.get_code, tlg_code.get_password):
                return

            tlg.run()
            for chat_id, msg_id in sync_ids:
                logging.info("%s %s", chat_id, msg_id)
                self._view(tlg, chat_id, [msg_id])
                time.sleep(1)
            time.sleep(60)

            tlg.close()
        finally:
            TELEGRAM_LOCK.release()

    def _view(self, tlg: Telegram, chat_id: int, ids: List[int]) -> None:
        r = tlg.request(open_chat(chat_id))
        logging.info("Mark: open chat: %s %s", chat_id, r)

        res = tlg.request(view_messages(chat_id, ids))
        logging.info("Mark view message: %s %s", ids, res)

        r = tlg.request(close_chat(chat_id))
        logging.info("Mark: close char %s %s", chat_id, r)

    def mark(self, data: dict, user: dict) -> Optional[bool]:
        return True

    def mark_all(self, data: dict, user: dict) -> Optional[bool]:
        feeds_h = RssTagFeeds(self._db)
        posts_h = RssTagPosts(self._db)
        if user["provider"] != TELEGRAM:
            logging.error("Not telegram provider")
            return False

        user_id = user["sid"]
        feeds = feeds_h.get_all(user_id)
        tlg_ids = []
        for feed in feeds:
            feed_id = int(feed["feed_id"])
            posts = list(
                posts_h.get_by_feed_id(
                    user_id,
                    str(feed_id),
                    projection={"id": True, "_id": False, "read": True},
                )
            )
            posts.sort(key=lambda x: x["id"], reverse=False)
            p_id = 0
            n = 0
            for p in posts:
                if not p["read"]:
                    break
                n += 1
                p_id = p["id"]
            logging.info("%s %s %d %d", feed_id, feed["title"], len(posts), n)
            if p_id == 0:
                continue

            tlg_ids.append((feed_id, p_id))

        logging.info("Telegram ids to mark: %d", len(tlg_ids))
        if not tlg_ids:
            logging.info("No ids to mark")
            return True

        self._tlg_sync(user["phone"], user_id, tlg_ids)

        return True
