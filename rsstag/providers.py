"""RSSTag downloaders"""
import json
import time
import gzip
import logging
import asyncio
from hashlib import md5
from datetime import date, datetime
from random import randint, uniform
from urllib.parse import quote_plus, urlencode
from http import client
from typing import Tuple, List, Optional, Iterator
from collections import defaultdict
from io import StringIO
import unicodedata
from threading import Thread
from queue import Queue, Empty
import traceback

from rsstag.tasks import POST_NOT_IN_PROCESSING
from rsstag.web.routes import RSSTagRoutes
from rsstag.users import TelegramCode

import aiohttp

from pymongo import MongoClient

from telegram.client import Telegram
from telegram.queries import get_message_link, get_chat, get_chats, get_chat_history, search_channel

NOT_CATEGORIZED = "NotCategorized"


class BazquxProvider:
    """rss downloader from bazqux.com"""

    def __init__(self, config: dict):
        self._config = config
        if self._config["settings"]["no_category_name"]:
            self.no_category_name = self._config["settings"]["no_category_name"]
        else:
            self.no_category_name = NOT_CATEGORIZED

    def get_headers(self, user: dict) -> dict:
        return {
            "Authorization": "GoogleLogin auth={0}".format(user["token"]),
            "Content-type": "application/x-www-form-urlencoded",
        }

    async def fetch(
        self, data: dict, loop: Optional[asyncio.AbstractEventLoop]
    ) -> Tuple[dict, str]:
        posts = []
        max_repetitions = 5
        repetitions = 0
        again = True
        url = data["url"]
        async with aiohttp.ClientSession(loop=loop) as session:
            while again:
                try:
                    async with session.get(url, headers=data["headers"]) as resp:
                        if resp.status == 200:
                            raw_json = await resp.text()
                            try:
                                downloaded = json.loads(raw_json)
                            except Exception as e:
                                logging.error(
                                    "Get strange json from %s. Info: %s", url, e
                                )
                                downloaded = {}
                            if "continuation" in downloaded:
                                again = True
                                url = "{}&c={}".format(
                                    data["url"], downloaded["continuation"]
                                )
                                repetitions = 0
                            else:
                                again = False
                            if "items" in downloaded:
                                posts = posts + downloaded["items"]
                        else:
                            repetitions += 1
                            again = repetitions < max_repetitions
                except Exception as e:
                    logging.error(
                        "Request failed %s. Repeat: %s. Error: %s", url, repetitions, e
                    )
                    repetitions += 1
                    again = repetitions < max_repetitions
            logging.info(
                'Loaded posts %s for category "%s"', len(posts), data["category"]
            )
            return (posts, data["category"])

    def download(self, user: dict) -> Iterator[Tuple[List, List]]:
        posts = []
        feeds = {}
        connection = client.HTTPSConnection(self._config[user["provider"]]["api_host"])
        headers = self.get_headers(user)
        connection.request(
            "GET", "/reader/api/0/subscription/list?output=json", "", headers
        )
        resp = connection.getresponse()
        json_data = resp.read()
        try:
            subscriptions = json.loads(json_data.decode("utf-8"))
        except Exception as e:
            subscriptions = None
            logging.error("Can`t decode subscriptions %s", e)
        if subscriptions:
            routes = RSSTagRoutes(self._config["settings"]["host_name"])
            by_category = {}
            loop = asyncio.new_event_loop()
            futures = []
            for feed in subscriptions["subscriptions"]:
                if len(feed["categories"]) > 0:
                    category_name = feed["categories"][0]["label"]
                else:
                    category_name = self.no_category_name
                    futures.append(
                        self.fetch(
                            {
                                "headers": headers,
                                "url": "https://{}/reader/api/0/stream/contents?s={}&xt=user/-/state/com.google/read&n=5000&output=json".format(
                                    self._config[user["provider"]]["api_host"],
                                    quote_plus(feed["id"]),
                                ),
                                "category": category_name,
                            },
                            loop,
                        )
                    )
                if category_name not in by_category:
                    by_category[category_name] = True
                    if category_name != self.no_category_name:
                        futures.append(
                            self.fetch(
                                {
                                    "headers": headers,
                                    "url": "https://{}/reader/api/0/stream/contents?s=user/-/label/{}&xt=user/-/state/com.google/read&n=1000&output=json".format(
                                        self._config[user["provider"]]["api_host"],
                                        quote_plus(category_name),
                                    ),
                                    "category": category_name,
                                },
                                loop,
                            )
                        )
            future = asyncio.gather(*futures, loop=loop)
            loop.run_until_complete(future)
            cats_data = future.result()
            loop.close()
            pid = 0
            logging.info("Was loaded %s categories", len(cats_data))
            for cat_data in cats_data:
                cat_posts, category = cat_data
                logging.info(
                    'Fetched %s posts for category "%s"', len(cat_posts), category
                )
                for post in cat_posts:
                    stream_id = md5(
                        post["origin"]["streamId"].encode("utf-8")
                    ).hexdigest()
                    if stream_id not in feeds:
                        feeds[stream_id] = {
                            "createdAt": datetime.utcnow(),
                            "title": post["origin"]["title"],
                            "owner": user["sid"],
                            "category_id": category,
                            "feed_id": stream_id,
                            "origin_feed_id": post["origin"]["streamId"],
                            "category_title": category,
                            "category_local_url": routes.get_url_by_endpoint(
                                endpoint="on_category_get",
                                params={"quoted_category": category},
                            ),
                            "local_url": routes.get_url_by_endpoint(
                                endpoint="on_feed_get",
                                params={"quoted_feed": stream_id},
                            ),
                            "favicon": "",
                        }
                    if "published" in post:
                        p_date = date.fromtimestamp(int(post["published"])).strftime(
                            "%x"
                        )
                        pu_date = float(post["published"])
                    else:
                        p_date = -1
                        pu_date = -1.0
                    attachments_list = []
                    if "enclosure" in post:
                        for attachments in post["enclosure"]:
                            if ("href" in attachments) and attachments["href"]:
                                attachments_list.append(attachments["href"])
                    posts.append(
                        {
                            "content": {
                                "title": post["title"],
                                "content": gzip.compress(
                                    post["summary"]["content"].encode(
                                        "utf-8", "replace"
                                    )
                                ),
                            },
                            "feed_id": stream_id,
                            "category_id": category,
                            "id": post["id"],
                            "url": post["canonical"][0]["href"]
                            if post["canonical"]
                            else "http://google.com",
                            "date": p_date,
                            "unix_date": pu_date,
                            "read": False,
                            "favorite": False,
                            "attachments": attachments_list,
                            "tags": [],
                            "bi_grams": [],
                            "pid": pid,
                            "owner": user["sid"],
                            "processing": POST_NOT_IN_PROCESSING,
                        }
                    )
                    pid += 1

        yield (posts, list(feeds.values()))

    def mark(self, data: dict, user: dict) -> Optional[bool]:
        status = data["status"]
        data_id = data["id"]
        headers = self.get_headers(user)
        read_tag = "user/-/state/com.google/read"
        result = False
        if status:
            data = urlencode({"i": data_id, "a": read_tag})
        else:
            data = urlencode({"i": data_id, "r": read_tag})
        max_repetitions = 10
        for i in range(max_repetitions):
            try:
                connection = client.HTTPSConnection(
                    self._config[user["provider"]]["api_host"]
                )
                connection.request(
                    "POST", "/reader/api/0/edit-tag?output=json", data, headers
                )
                resp = connection.getresponse()
                resp_data = resp.read()
                connection.close()
            except Exception as e:
                result = False
                resp_data = None
                logging.warning("Can`t make request %s %s", e, i)

            if resp_data and (resp_data.decode("utf-8").lower() == "ok"):
                result = True
                break
            else:
                logging.warning("Can`t mark. Resp: %s", resp_data)
                if not self.is_valid_user(user):
                    return None

            time.sleep(randint(2, 7))

        return result

    def get_token(self, login: str, password: str) -> Optional[str]:
        connection = client.HTTPSConnection(self._config["bazqux"]["api_host"])
        headers = {"Content-type": "application/x-www-form-urlencoded"}
        data = urlencode({"Email": login, "Passwd": password})
        try:
            connection.request("POST", "/accounts/ClientLogin", data, headers)
            resp = connection.getresponse().read().splitlines()
            if resp and resp[0].decode("utf-8").split("=")[0] != "Error":
                token = resp[-1].decode("utf-8").split("=")[-1]
                result = token
            else:
                result = ""
                logging.error("Wrong Login or Password")
        except Exception as e:
            result = None
            logging.error("Can`t get token from bazqux server. Info: %", e)

        return result

    def is_valid_user(self, user: dict) -> Optional[bool]:
        headers = self.get_headers(user)
        try:
            connection = client.HTTPSConnection(self._config["bazqux"]["api_host"])
            connection.request("GET", "/reader/ping", None, headers)
            if connection.getresponse().read().strip() == "OK":
                result = True
            else:
                result = False
                logging.error("Unauthorized user")
            connection.close()
        except Exception as e:
            result = None
            logging.error("Can`t ping bazqux server. Info: %s", e)

        return result


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
    result_html.write(
        "<p>" +
        post["content"]["poll"]["question"] +
        "</p><ol>"
    )
    for opt in post["content"]["poll"]["options"]:
        if opt["@type"] != "pollOption":
            continue

        result_html.write(
            "<li>" +
            opt["text"] +
            "</li>"
        )
    result_html.write("</ol>")

    return result_html.getvalue()

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

    return result_html.getvalue()


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
            if max_limit == 0:
                if limit <= 0:
                    tasks_q.task_done()
                    # no unread posts
                    continue
                # load only unreaded posts
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
                posts_req = self._tlg.request(get_chat_history(
                    channel["id"], limit=limit, from_message_id=from_id
                ))
                posts_data = posts_req.update
                if (not posts_req.update) or (len(posts_data["messages"]) == 0):
                    has_posts = False
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
                    resp = self._tlg.request(get_message_link(post["chat_id"], post["id"]))
                    posts_links.append(resp.update["link"])

                results_q.put_nowait((channel["id"], posts_data, posts_links))
                time.sleep(uniform(1,3))

            tasks_q.task_done()
            logging.info("Downloaded: %s - %s", channel["title"], posts_n)
            time.sleep(1)

    def download(self, user: dict) -> Tuple[List, List]:
        provider = user["provider"]
        all_channels = user["telegram_channel"].lower() == "all"
        self._tlg: Telegram = Telegram(
            app_id=self._config[provider]["app_id"],
            app_hash=self._config[provider]["app_hash"],
            phone=user["phone"],
            db_key=self._config[provider]["encryption_key"],
            db_path=self._config[provider]["db_dir"],
        )
        tlg_code = TelegramCode(self._db, user["sid"])
        if not self._tlg.login(tlg_code.get_code):
            raise Exception("Telegram login failed")
        self._tlg.run()
        channels = []
        if all_channels:
            list_offset = 9223372036854775807
            prev_chat_id = 0
            uniq_chat_ids = set()
            while True:
                r = self._tlg.request(get_chats(
                    offset_order=list_offset, offset_chat_id=prev_chat_id
                ))
                ids = r.update
                if not ids:
                    break
                if not ids["chat_ids"]:
                    break
                chats_n = ids["total_count"]
                if chats_n <= len(channels):
                    break
                for c_id in ids["chat_ids"]:
                    if c_id in uniq_chat_ids:
                        continue
                    r = self._tlg.request(get_chat(c_id))
                    channels.append(r.update)
                prev_chat_id = ids["chat_ids"][-1]
                uniq_chat_ids.update(ids["chat_ids"])
                r = self._tlg.request(get_chat(prev_chat_id))
                chat_d = r.update
                list_offset = chat_d["positions"][0]["order"]
                time.sleep(randint(1,2))
        else:
            telegram_channels = user["telegram_channel"].split(",")
            for telegram_channel in telegram_channels:
                telegram_channel = telegram_channel.strip()
                if not telegram_channel:
                    continue
                channel_req = self._tlg.request(search_channel(telegram_channel))
                if not channel_req.update:
                    logging.warning("No channel: %s", telegram_channel)
                    self._tlg.close()
                    return ([], [])
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
        workers_n = int(self._config["settings"]["downloaders_count"])
        if not workers_n:
            workers_n = 1
        if len(channels) == 1:
            workers_n = 1
        for i in range(workers_n):
            t = Thread(target=self._fetch, args=(tasks_q, results_q))
            t.start()
            workers.append(t)

        posts = []
        pid = 0
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
                try:
                    post_text = tlg_post_to_html(post)
                    if "caption" in post["content"]:
                        entities = post["content"]["caption"]["entities"]
                    elif "text" in post["content"]:
                        t = post["content"].get("@type", "")
                        if t != "messageCustomServiceAction":
                            entities = post["content"]["text"]["entities"]
                except Exception as e:
                    logging.error("tlg_post_to_html: {}. {}. {}".format(post, e, traceback.format_exc()))
                    continue
                for entity in entities:
                    if "type" in entity and "url" in entity["type"]:
                        attachments_list.append(entity["type"]["url"])

                t_link = posts_links[post_i]
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
                        "pid": pid,
                        "owner": user["sid"],
                        "processing": POST_NOT_IN_PROCESSING,
                    }
                )
                pid += 1
            if len(posts) > 5000:
                yield (posts, list(feeds.values()))
                posts = []
            time.sleep(randint(1, 2))

        self._tlg.close()

        yield (posts, list(feeds.values()))

    def mark(self, data: dict, user: dict) -> Optional[bool]:
        return True

class TextFileProvider:
    def __init__(self, config: dict):
        self._config = config
        if self._config["settings"]["no_category_name"]:
            self.no_category_name = self._config["settings"]["no_category_name"]
        else:
            self.no_category_name = NOT_CATEGORIZED

    def download(self, user: dict) -> Tuple[List, List]:
        path = user["text_file"]
        posts = []
        feeds = {}
        pid = 0
        stream_id = "textfile"
        routes = RSSTagRoutes(self._config["settings"]["host_name"])
        if stream_id not in feeds:
            feeds[stream_id] = {
                "createdAt": datetime.utcnow(),
                "title": "textfile",
                "owner": user["sid"],
                "category_id": self.no_category_name,
                "feed_id": stream_id,
                "origin_feed_id": "textfile",
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
        with open(path) as f:
            for line in f:
                pu_date = time.time()
                p_date = date.fromtimestamp(int(pu_date)).strftime("%x")
                posts.append(
                    {
                        "content": {
                            "title": "",
                            "content": gzip.compress(
                                line.encode("utf-8", "replace")
                            ),
                        },
                        "feed_id": stream_id,
                        "category_id": self.no_category_name,
                        "id": pid,
                        "url": "#",
                        "date": p_date,
                        "unix_date": pu_date,
                        "read": False,
                        "favorite": False,
                        "attachments": [],
                        "tags": [],
                        "bi_grams": [],
                        "pid": pid,
                        "owner": user["sid"],
                        "processing": POST_NOT_IN_PROCESSING,
                    }
                )
                pid += 1
                if pid % 5000 == 0:
                    yield (posts, list(feeds.values()))
                    posts = []
        logging.info("Loaded: %s", pid)

        yield (posts, list(feeds.values()))

    def mark(self, data: dict, user: dict) -> Optional[bool]:
        return True
