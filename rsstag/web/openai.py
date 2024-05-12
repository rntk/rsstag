import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

import gzip

from rsstag.html_cleaner import HTMLCleaner

from werkzeug.wrappers import Response, Request

def on_openai_post(app: "RSSTagApplication", user: dict, rqst: Request):
    data = rqst.get_json()
    if not data:
        return Response(json.dumps({"error": "No data"}), mimetype="application/json", status=400)

    tag = data["tag"]
    if not tag:
        return Response(json.dumps({"error": "No tag"}), mimetype="application/json", status=400)

    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None
    db_posts_c = app.posts.get_by_tags(user["sid"], [tag], only_unread)
    text = ""
    texts_splitter = "\nRSSTAG_TEXT_SPLITTER\n"
    for post in db_posts_c[:50]:
        txt = post["content"]["title"] + ". " + gzip.decompress(post["content"]["content"]).decode(
            "utf-8", "replace"
        )
        txt = txt.strip()
        if txt:
            text += txt + texts_splitter

    if not text:
        result = {"error": "No texts"}
        return Response(json.dumps(result), mimetype="application/json", status=200)
    cleaner = HTMLCleaner()
    cleaner.feed(text)
    sentences = [t.strip() for t in cleaner.get_content() if t.strip()]
    text = "\n".join(sentences)

    user_msgs = ""
    if "user"  in data and data["user"]:
        user_msgs = data["user"]
    if not user_msgs:
        result = {"error": "No user messages"}
        return Response(json.dumps(result), mimetype="application/json", status=400)
    user_msgs = text + texts_splitter + user_msgs + "\n" + "Messages are splited by: " + texts_splitter
    print(user_msgs)

    txt = app.anthropic.call([user_msgs])
    result = {"data": txt}

    return Response(json.dumps(result), mimetype="application/json", status=200)

