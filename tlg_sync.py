import sys
import time
from typing import List, Tuple

from rsstag.utils import load_config
from rsstag.feeds import RssTagFeeds
from rsstag.posts import RssTagPosts

from telegram.client import Telegram
from telegram.queries import open_chat, close_chat, view_messages

from pymongo import MongoClient


def get_code() -> str:
    return input("Code: ")

def tlg_sync(cfg: dict, phone: str, sync_ids: List[Tuple[int, int]]) -> None:
    if not tlg_ids:
        return

    t_cfg = cfg["telegram"]
    tlg = Telegram(
        app_id=t_cfg["app_id"],
        app_hash=t_cfg["app_hash"],
        phone=phone,
        db_key=t_cfg["encryption_key"],
        db_path=t_cfg["db_dir"]
    )
    if not tlg.login(get_code):
        return
    tlg.run()
    for chat_id, msg_id in sync_ids:
        print(chat_id, msg_id)
        view(tlg, chat_id, [msg_id])
    time.sleep(60)

    tlg.close()


def view(tlg: Telegram, chat_id: int, ids: List[int]) -> None:
    r = tlg.request(open_chat(chat_id))
    print(r)

    res = tlg.request(view_messages(chat_id, ids))
    print(res)

    r = tlg.request(close_chat(chat_id))
    print(r)


if __name__ == "__main__":
    config_path = "./rsscloud.conf"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    cfg = load_config(config_path)

    cl = MongoClient(cfg["settings"]["db_host"], int(cfg["settings"]["db_port"]))
    db = cl[cfg["settings"]["db_name"]]
    feeds_h = RssTagFeeds(db)
    posts_h = RssTagPosts(db)
    users = db.users.find({})
    for user in users:
        if user["provider"] != "telegram":
            print("Not telegram provider")
            exit()
        user_id = user["sid"]
        feeds = feeds_h.get_all(user_id)
        tlg_ids = []
        for feed in feeds:
            feed_id = int(feed["feed_id"])
            posts = list(posts_h.get_by_feed_id(
                user_id,
                str(feed_id),
                projection={"id": True, "_id": False, "read": True},
            ))
            posts.sort(key=lambda x: x["id"], reverse=False)
            p_id = 0
            n = 0
            for p in posts:
                if not p["read"]:
                    break
                n += 1
                p_id = p["id"]
            print(feed_id, feed["title"], len(posts), n)
            if p_id == 0:
                continue

            tlg_ids.append((feed_id, p_id))

        print(len(tlg_ids))
        if tlg_ids:
            tlg_sync(cfg, user["phone"], tlg_ids)
