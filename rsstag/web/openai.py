import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

import gzip

from rsstag.html_cleaner import HTMLCleaner

from werkzeug.wrappers import Response, Request

def on_openai_post_(app: "RSSTagApplication", user: dict, rqst: Request):
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
    for post in db_posts_c[:5]:
        txt = post["content"]["title"] + ". " + gzip.decompress(post["content"]["content"]).decode(
            "utf-8", "replace"
        )
        txt = txt.strip()
        if txt:
            text += f"<message>{txt}</message>\n"

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
    system_msg = f"""
You will receive a list of messages, each containing a keyword "{tag}".
The messages will be enclosed within the <messages></messages> tags,
and each individual message will be wrapped in <message></message> tags. Here is the list of messages:

<messages>{text}</messages>

Your task is to process these messages and assist the user with the following request:
"""
    user_msgs = system_msg + user_msgs
    print(user_msgs)

    txt = app.llamacpp.call([user_msgs])
    result = {"data": txt}

    return Response(json.dumps(result), mimetype="application/json", status=200)

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
    cleaner = HTMLCleaner()
    docs = []
    for post in db_posts_c[:10]:
        txt = post["content"]["title"] + ". " + gzip.decompress(post["content"]["content"]).decode(
            "utf-8", "replace"
        )
        txt = txt.strip()
        cleaner.purge()
        cleaner.feed(txt)
        txt = " ".join(cleaner.get_content())
        docs.append(txt)

    if not docs:
        result = {"error": "No texts"}
        return Response(json.dumps(result), mimetype="application/json", status=200)

    user_msgs = ""
    if "user"  in data and data["user"]:
        user_msgs = data["user"]
    if not user_msgs:
        result = {"error": "No user messages"}
        return Response(json.dumps(result), mimetype="application/json", status=400)
    system_msg = f"""You are provided with a list of messages, each containing a keyword "{tag}".  
Your task is to process these messages and assist the user with the following request: 
{user_msgs}
"""

    #txt = app.llamacpp.call([user_msgs])
    txt = app.anthropic.call_citation(system_msg, docs)
    result = {"data": txt}

    return Response(json.dumps(result), mimetype="application/json", status=200)