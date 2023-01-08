from typing import Tuple, List, Optional
from datetime import date, datetime
import time
import gzip
import logging

from rsstag.tasks import POST_NOT_IN_PROCESSING
from rsstag.web.routes import RSSTagRoutes

NOT_CATEGORIZED = "NotCategorized"

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