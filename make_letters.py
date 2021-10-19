import sys
from rsstag.routes import RSSTagRoutes
from rsstag.letters import RssTagLetters
from rsstag.utils import load_config
from rsstag.tags import RssTagTags
from pymongo import MongoClient


def make_letters(db, config):
    router = RSSTagRoutes(config["settings"]["host_name"])
    user = db.users.find_one({})
    letters = RssTagLetters(db)
    tags = RssTagTags(db)
    all_tags = tags.get_all(user["sid"], projection={"tag": True, "unread_count": True})
    result = False
    if tags:
        result = letters.sync_with_tags(user["sid"], all_tags, router)

    return result


if __name__ == "__main__":
    config_path = "rsscloud.conf"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    config = load_config(config_path)
    cl = MongoClient(config["settings"]["db_host"], int(config["settings"]["db_port"]))
    db = cl[config["settings"]["db_name"]]
    result = make_letters(db, config)
    if result:
        print("Done")
    else:
        print("Not done, result - ", result)
