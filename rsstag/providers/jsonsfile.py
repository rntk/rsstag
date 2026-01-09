from typing import Tuple, List, Optional
from datetime import date, datetime
import time
import gzip
import logging
import json

from rsstag.tasks import POST_NOT_IN_PROCESSING
from rsstag.web.routes import RSSTagRoutes
from rsstag.providers.providers import JSONS_FILE
from rsstag.providers.pid import generate_post_pid

NOT_CATEGORIZED = "NotCategorized"


class JSONSFileProvider:
    def __init__(self, config: dict):
        self._config = config
        if self._config["settings"]["no_category_name"]:
            self.no_category_name = self._config["settings"]["no_category_name"]
        else:
            self.no_category_name = NOT_CATEGORIZED

    def download(
        self, user: dict, selection: Optional[dict] = None
    ) -> Tuple[List, List]:
        path = user["text_file"]
        posts = []
        feeds = {}
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
        line_id = 0
        with open(path, "rb") as f:
            for line in f:
                try:
                    ln = line.decode("unicode_escape", "replace").strip().strip('"')
                    dt = json.loads(ln)
                    title, content = self.json_to_post(dt)
                except Exception as e:
                    logging.error("Error: %s %s", e, ln[:50])
                    continue
                pu_date = time.time()
                p_date = date.fromtimestamp(int(pu_date)).strftime("%x")
                pid = generate_post_pid(JSONS_FILE, stream_id, line_id)
                posts.append(
                    {
                        "content": {
                            "title": title,
                            "content": gzip.compress(
                                content.encode("utf-8", "replace")
                            ),
                        },
                        "feed_id": stream_id,
                        "category_id": self.no_category_name,
                        "id": line_id,
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
                line_id += 1
                if line_id % 5000 == 0:
                    yield (posts, list(feeds.values()))
                    posts = []
        logging.info("Loaded: %s", line_id)

        yield (posts, list(feeds.values()))

    def mark(self, data: dict, user: dict) -> Optional[bool]:
        return True

    def json_to_post(self, json: dict) -> Tuple[str, str]:
        title = ""
        content = self.recursive_text(json["data"]["dapi"])

        return (title, content)

    def recursive_text(self, json: dict) -> str:
        content = ""
        for key, value in json.items():
            if isinstance(value, dict):
                content += self.recursive_text(value) + " "
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        content += self.recursive_text(item) + " "
                    else:
                        content += str(item) + " "
            else:
                content += str(value) + " "

        return content
