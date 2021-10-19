import sys
import time
from typing import List, Tuple

from telegram.client import Telegram
from rsstag.utils import load_config
from rsstag.feeds import RssTagFeeds
from rsstag.posts import RssTagPosts

from pymongo import MongoClient


def tlg_sync(cfg: dict, phone: str, sync_ids: List[Tuple[int, int]]) -> None:
    if not tlg_ids:
        return

    t_cfg = cfg["telegram"]
    tlg = Telegram(
        api_id=t_cfg["app_id"],
        api_hash=t_cfg["app_hash"],
        phone=phone,
        database_encryption_key=t_cfg["encryption_key"],
        files_directory=t_cfg["db_dir"],
    )
    tlg.login(blocking=True)
    for chat_id, msg_id in sync_ids:
        print(chat_id, msg_id)
        view(tlg, chat_id, [msg_id])
    time.sleep(5)

    tlg.stop()


def view(tlg: Telegram, chat_id: int, ids: List[int]) -> None:
    r = tlg.open_chat(chat_id)
    r.wait()
    print(r.update)

    res = tlg.view_messages(chat_id, ids)
    res.wait()
    print(res.update)

    r = tlg.close_chat(chat_id)
    r.wait()
    print(r.update)


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
            posts = posts_h.get_by_feed_id(
                user_id,
                str(feed_id),
                projection={"id": True, "_id": False, "read": True},
            )
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
