import json
import html
import gzip
import logging
from collections import defaultdict
from urllib.parse import unquote_plus, unquote
import requests # Add requests import
import re
from rsstag.html_cleaner import HTMLCleaner

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication
from rsstag.tasks import TASK_MARK, TASK_MARK_TELEGRAM, TASK_GMAIL_SORT, TASK_NOT_IN_PROCESSING
from rsstag.utils import text_to_speech

from werkzeug.wrappers import Request, Response
from werkzeug.exceptions import NotFound
from werkzeug.utils import redirect


def on_post_speech(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    try:
        post_id = int(request.form.get("post_id"))
    except Exception as e:
        logging.warning("Wrong post_id: %s. %s", request.form.get("post_id"), e)
        post_id = None
    code = 200
    if post_id:
        post = app.posts.get_by_pid(user["sid"], post_id)
        if post:
            title = html.unescape(post["content"]["title"])
            speech_file = text_to_speech(
                app.config["settings"]["speech_dir"],
                app.config["yandex"]["speech_host"],
                app.config["yandex"]["speech_key"],
                title,
            )
            if speech_file:
                result = {"data": "/static/speech/{}".format(speech_file)}
            else:
                result = {"error": "Can`t get speech file"}
                code = 503
        else:
            result = {"error": "Post not found"}
            code = 404
    else:
        result = {"error": "No post id"}
        code = 400

    return Response(json.dumps(result), mimetype="application/json", status=code)


def on_category_get(
    app: "RSSTagApplication", user: dict, request: Request, quoted_category: str
) -> Response:
    cat = unquote_plus(quoted_category)
    db_feeds = app.feeds.get_by_category(user["sid"], cat)
    by_feed = {}
    for f in db_feeds:
        by_feed[f["feed_id"]] = f

    if not by_feed:
        return app.on_error(user, request, NotFound())

    projection = {"_id": False, "content.content": False}
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None
    if cat != app.feeds.all_feeds:
        db_posts_c = app.posts.get_by_category(
            user["sid"], only_unread, cat, projection
        )
    else:
        db_posts_c = app.posts.get_all(user["sid"], only_unread, projection)

    db_posts = list(db_posts_c)

    if user["settings"]["similar_posts"]:
        clusters = app.posts.get_clusters(db_posts)
        cl_posts = app.posts.get_by_clusters(
            user["sid"], list(clusters), only_unread, projection
        )
        for post in cl_posts:
            if post["feed_id"] not in by_feed:
                feed = app.feeds.get_by_feed_id(user["sid"], post["feed_id"])
                if feed:
                    by_feed[post["feed_id"]] = feed
        db_posts.extend(cl_posts)
    posts = []
    pids = set()
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
        if post["pid"] not in pids:
            pids.add(post["pid"])
            if post["feed_id"] in by_feed:
                posts.append(
                    {
                        "post": post,
                        "pos": post["pid"],
                        "category_title": by_feed[post["feed_id"]]["category_title"],
                        "feed_title": by_feed[post["feed_id"]]["title"],
                        "favicon": by_feed[post["feed_id"]]["favicon"],
                    }
                )
    page = app.template_env.get_template("posts.html")

    return Response(
        page.render(
            posts=posts,
            tag=cat,
            group="category",
            words=[],
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )


def on_tag_get(
    app: "RSSTagApplication", user: dict, request: Request, quoted_tag: str
) -> Response:
    tag = unquote(quoted_tag)
    current_tag = app.tags.get_by_tag(user["sid"], tag)
    if not current_tag:
        return app.on_error(user, request, NotFound())

    projection = {"_id": False, "content.content": False}
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None
    db_posts_c = app.posts.get_by_tags(user["sid"], [tag], only_unread, projection)
    db_posts = list(db_posts_c)

    if user["settings"]["similar_posts"]:
        clusters = app.posts.get_clusters(db_posts)
        cl_posts = app.posts.get_by_clusters(
            user["sid"], list(clusters), only_unread, projection
        )
        db_posts.extend(cl_posts)
    posts = []
    by_feed = {}
    pids = set()
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
        if post["pid"] not in pids:
            pids.add(post["pid"])
            if post["feed_id"] not in by_feed:
                feed = app.feeds.get_by_feed_id(user["sid"], post["feed_id"])
                if feed:
                    by_feed[post["feed_id"]] = feed
            if post["feed_id"] in by_feed:
                posts.append(
                    {
                        "post": post,
                        "pos": post["pid"],
                        "category_title": by_feed[post["feed_id"]]["category_title"],
                        "feed_title": by_feed[post["feed_id"]]["title"],
                        "favicon": by_feed[post["feed_id"]]["favicon"],
                    }
                )
    page = app.template_env.get_template("posts.html")

    return Response(
        page.render(
            posts=posts,
            tag=tag,
            group="tag",
            words=current_tag["words"],
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )


def on_bi_gram_get(
    app: "RSSTagApplication", user: dict, request: Request, bi_gram: str
) -> Response:
    current_bi_gram = app.bi_grams.get_by_bi_gram(user["sid"], bi_gram)
    if not current_bi_gram:
        return app.on_error(user, request, NotFound())

    projection = {"_id": False, "content.content": False}
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None
    db_posts_c = app.posts.get_by_bi_grams(
        user["sid"], [bi_gram], only_unread, projection
    )
    db_posts = list(db_posts_c)

    if user["settings"]["similar_posts"]:
        clusters = app.posts.get_clusters(db_posts)
        cl_posts = app.posts.get_by_clusters(
            user["sid"], list(clusters), only_unread, projection
        )
        db_posts.extend(cl_posts)
    posts = []
    by_feed = {}
    pids = set()
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
        if post["pid"] not in pids:
            pids.add(post["pid"])
            if post["feed_id"] not in by_feed:
                feed = app.feeds.get_by_feed_id(user["sid"], post["feed_id"])
                if feed:
                    by_feed[post["feed_id"]] = feed
            if post["feed_id"] in by_feed:
                posts.append(
                    {
                        "post": post,
                        "pos": post["pid"],
                        "category_title": by_feed[post["feed_id"]]["category_title"],
                        "feed_title": by_feed[post["feed_id"]]["title"],
                        "favicon": by_feed[post["feed_id"]]["favicon"],
                    }
                )
    page = app.template_env.get_template("posts.html")

    return Response(
        page.render(
            posts=posts,
            tag=bi_gram,
            group="tag",
            words=current_bi_gram["words"],
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )


def on_feed_get(
    app: "RSSTagApplication", user: dict, request: Request, quoted_feed: str
) -> Response:
    feed = unquote_plus(quoted_feed)
    current_feed = app.feeds.get_by_feed_id(user["sid"], feed)
    if not current_feed:
        return app.on_error(user, request, NotFound())

    projection = {"_id": False, "content.content": False}
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None
    db_posts_c = app.posts.get_by_feed_id(
        user["sid"], current_feed["feed_id"], only_unread, projection
    )
    db_posts = list(db_posts_c)

    posts = []
    if user["settings"]["similar_posts"]:
        clusters = app.posts.get_clusters(db_posts)
        cl_posts = app.posts.get_by_clusters(
            user["sid"], list(clusters), only_unread, projection
        )
        db_posts.extend(cl_posts)
    pids = set()
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
        if post["pid"] not in pids:
            pids.add(post["pid"])
            posts.append(
                {
                    "post": post,
                    "category_title": current_feed["category_title"],
                    "pos": post["pid"],
                    "feed_title": current_feed["title"],
                    "favicon": current_feed["favicon"],
                }
            )
    page = app.template_env.get_template("posts.html")

    return Response(
        page.render(
            posts=posts,
            tag=current_feed["title"].replace("'", "`"),
            group="feed",
            words=[],
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )


def on_read_posts_post(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    try:
        data = json.loads(request.get_data(as_text=True))
        if data["ids"] and isinstance(data["ids"], list):
            post_ids = data["ids"]
        else:
            raise Exception("Bad ids for posts status")
        readed = bool(data["readed"])
    except Exception as e:
        logging.warning("Send wrond data for read posts. Cause: %s", e)
        post_ids = None
        result = {"error": "Bad ids or status"}
        code = 400

    if post_ids:
        tags = defaultdict(int)
        bi_grams = defaultdict(int)
        letters = defaultdict(int)
        for_insert = []
        db_posts = app.posts.get_by_pids(
            user["sid"],
            post_ids,
            {"id": True, "tags": True, "bi_grams": True, "read": True},
        )
        for d in db_posts:
            if d["read"] != readed:
                for_insert.append(
                    {
                        "user": user["sid"],
                        "id": d["id"],
                        "status": readed,
                        "processing": TASK_NOT_IN_PROCESSING,
                        "type": TASK_MARK,
                    }
                )
                for t in d["tags"]:
                    tags[t] += 1
                    if not t:
                        continue
                    letters[t[0]] += 1
                for bi_g in d["bi_grams"]:
                    bi_grams[bi_g] += 1

        if app.tasks.add_task(
            {"type": TASK_MARK, "user": user["sid"], "data": for_insert}
        ):
            changed = app.posts.change_status(user["sid"], post_ids, readed)
            if changed and tags:
                changed = app.tags.change_unread(user["sid"], tags, readed)
            if changed and bi_grams:
                changed = app.bi_grams.change_unread(user["sid"], bi_grams, readed)
            if changed and letters:
                app.letters.change_unread(user["sid"], letters, readed)
                changed = True
            if changed:
                code = 200
                result = {"data": "ok"}
            else:
                code = 500
                result = {"error": "Database error"}

    return Response(json.dumps(result), mimetype="application/json", status=code)

def on_mark_telegram_posts_post(
        app: "RSSTagApplication", user: dict, _: Request
) -> Response:
    for_insert = [
        {
            "user": user["sid"],
            "id": "",
            "processing": TASK_NOT_IN_PROCESSING,
            "type": TASK_MARK_TELEGRAM,
        }
    ]
    if not app.tasks.add_task(
            {"type": TASK_MARK_TELEGRAM, "user": user["sid"], "data": for_insert}
    ):
        logging.error("Can't add task for mark telegram posts: %s", for_insert)

    return redirect(app.routes.get_url_by_endpoint("on_root_get"))

def on_gmail_sort_post(
        app: "RSSTagApplication", user: dict, _: Request
) -> Response:
    for_insert = [
        {
            "user": user["sid"],
            "id": "",
            "processing": TASK_NOT_IN_PROCESSING,
            "type": TASK_GMAIL_SORT,
        }
    ]
    if not app.tasks.add_task(
            {"type": TASK_GMAIL_SORT, "user": user["sid"], "data": for_insert}
    ):
        logging.error("Can't add task for gmail sort: %s", for_insert)

    return redirect(app.routes.get_url_by_endpoint("on_root_get"))

def on_posts_content_post(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    try:
        wanted_posts = json.loads(request.get_data(as_text=True))
        if not (isinstance(wanted_posts, list) and wanted_posts):
            raise Exception("Empty list of ids for post content")
    except Exception as e:
        logging.warning("Send bad posts ids for posts content. Cause: %s", e)
        wanted_posts = []
        result = {"error": "Bad posts ids"}
        code = 400

    if wanted_posts:
        projection = {"pid": True, "content": True, "attachments": True}
        posts = app.posts.get_by_pids(user["sid"], wanted_posts, projection)
        posts_content = []
        for post in posts:
            attachments = ""
            if post["attachments"]:
                for href in post["attachments"]:
                    attachments += '<a href="{0}">{0}</a><br />'.format(href)
            content = gzip.decompress(post["content"]["content"]).decode(
                "utf-8", "replace"
            )
            if attachments:
                content += "<p>Attachments:<br />{0}<p>".format(attachments)
            posts_content.append({"pos": post["pid"], "content": content})

        if posts_content:
            result = {"data": posts_content}
            code = 200
        else:
            code = 404
            result = {"error": "Not found"}

    return Response(json.dumps(result), mimetype="application/json", status=code)


def on_post_links_get(app: "RSSTagApplication", user: dict, post_id: int) -> Response:
    projection = {"tags": True, "feed_id": True, "url": True, "clusters": True}
    current_post = app.posts.get_by_pid(user["sid"], post_id, projection)
    if current_post:
        feed = app.feeds.get_by_feed_id(user["sid"], current_post["feed_id"])
        if feed:
            code = 200
            result = {
                "data": {
                    "c_url": feed["category_local_url"],
                    "c_title": feed["category_title"],
                    "f_url": feed["local_url"],
                    "f_title": feed["title"],
                    "p_url": current_post["url"],
                    "ctx_url": app.routes.get_url_by_endpoint(
                        endpoint="on_posts_get",
                        params={
                            "pids": post_id,
                            "context": int(user["settings"]["context_n"]),
                        },
                    ),
                    "tags": [],
                }
            }
            if "clusters" in current_post:
                result["data"]["clst_url"] = app.routes.get_url_by_endpoint(
                    endpoint="on_cluster_get",
                    params={"cluster": current_post["clusters"][0]},
                )
            for t in current_post["tags"]:
                result["data"]["tags"].append(
                    {
                        "url": app.routes.get_url_by_endpoint(
                            endpoint="on_get_tag_page", params={"tag": t}
                        ),
                        "tag": t,
                    }
                )
        else:
            code = 500
            result = {"error": "Server trouble"}
    else:
        code = 404
        result = {"error": "Not found"}

    return Response(json.dumps(result), mimetype="application/json", status=code)


# TODO: delete or change or something other
def on_get_posts_with_tags(
    app: "RSSTagApplication", user: dict, s_tags: str
) -> Response:
    if not s_tags:
        return redirect(app.routes.get_url_by_endpoint("on_root_get"))

    tags = s_tags.split("-")
    if tags:
        result = {}
        query = {"owner": user["sid"], "tag": {"$in": tags}}
        tags_cursor = app.db.tags.find(query, {"_id": 0, "tag": 1, "words": 1})
        for tag in tags_cursor:
            result[tag["tag"]] = {"words": ", ".join(tag["words"]), "posts": []}

        query = {"owner": user["sid"], "tags": {"$in": tags}}
        if user["settings"]["only_unread"]:
            query["read"] = False
        posts_cursor = app.db.posts.find(query, {"content.content": 0})
        feeds = {}
        posts = {}
        for post in posts_cursor:
            posts[post["id"]] = post
            if post["feed_id"] not in feeds:
                feeds[post["feed_id"]] = {}
        feeds_cursor = app.db.feeds.find(
            {"owner": user["sid"], "feed_id": {"$in": list(feeds.keys())}}
        )
        for feed in feeds_cursor:
            feeds[feed["feed_id"]] = feed
        for tag in tags:
            posts_for_delete = []
            for p_id in posts:
                if tag in posts[p_id]["tags"]:
                    posts[p_id]["feed_title"] = feeds[posts[p_id]["feed_id"]]["title"]
                    posts[p_id]["category_title"] = feeds[posts[p_id]["feed_id"]][
                        "category_title"
                    ]
                    result[tag]["posts"].append(posts[p_id])
                    posts_for_delete.append(p_id)
            for p_id in posts_for_delete:
                del posts[p_id]
            result[tag]["posts"] = sorted(
                result[tag]["posts"], key=lambda p: p["feed_id"]
            )
        page = app.template_env.get_template("tags-posts.html")

        return Response(
            page.render(
                tags=result,
                selected_tags=",".join(tags),
                group="tag",
                user_settings=user["settings"],
                provider=user["provider"],
            ),
            mimetype="text/html",
        )


def on_entity_get(app: "RSSTagApplication", user: dict, quoted_tag: str, window: Optional[int]=10, rerank: Optional[str]=None) -> Response:
    #print(rerank)
    tag = unquote(quoted_tag)
    tag_words = tag.split()
    projection = {"_id": False}
    if not rerank:
        projection["content.content"] = False
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None
    db_posts_c = app.posts.get_by_tags(
        user["sid"], tag_words, only_unread, projection
    )
    db_posts = list(db_posts_c)

    if user["settings"]["similar_posts"]:
        clusters = app.posts.get_clusters(db_posts)
        cl_posts = app.posts.get_by_clusters(
            user["sid"], list(clusters), only_unread, projection
        )
        db_posts.extend(cl_posts)
    posts = []
    by_feed = {}
    pids = set()
    multi_word_tag = len(tag_words) > 1
    tag_words_set = set(tag_words)
    
    # Maximum length for reranking API
    MAX_CHUNK_LENGTH = 1024
    # Overlap percentage (50%)
    OVERLAP_PERCENT = 0.5
    
    rerank_url = "http://127.0.0.1:8257/v1/rerank" #app.config.get("rerank", {}).get("url")
    
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")

        # If tag has multiple words, check if they are within the window distance
        if multi_word_tag:
            lemmas_list = post["lemmas"].split()
            words_positions = {}

            # Find positions of all tag words in lemmas
            
            for i, lemma in enumerate(lemmas_list):
                if lemma in tag_words_set:
                    if lemma not in words_positions:
                        words_positions[lemma] = []
                    words_positions[lemma].append(i)

            # Check if all words are present
            if len(words_positions) != len(tag_words):
                continue

            # Check if any combination of positions is within window distance
            within_window = False

            # Get all possible combinations of positions
            positions_lists = []
            for word in tag_words:
                if word in words_positions and words_positions[word]:
                    positions_lists.append(words_positions[word])

            # If we have positions for all words
            if len(positions_lists) == len(tag_words):
                # Try each position of the first word with all combinations of other words
                for pos1 in positions_lists[0]:
                    # Create a test set starting with the first word's position
                    test_positions = [pos1]

                    # Try to find positions of other words that are within window distance
                    for positions in positions_lists[1:]:
                        # Find the nearest position to pos1
                        nearest_pos = min(positions, key=lambda x: abs(x - pos1))
                        test_positions.append(nearest_pos)

                    # Check if the max distance is within window
                    max_pos = max(test_positions)
                    min_pos = min(test_positions)
                    if max_pos - min_pos <= window:
                        within_window = True
                        break

            # Skip post if words aren't within window
            if not within_window:
                continue

        if post["pid"] not in pids:
            pids.add(post["pid"])
            if post["feed_id"] not in by_feed:
                feed = app.feeds.get_by_feed_id(user["sid"], post["feed_id"])
                if feed:
                    by_feed[post["feed_id"]] = feed
            if post["feed_id"] in by_feed:
                post_data = {
                    "post": post,
                    "pos": post["pid"],
                    "category_title": by_feed[post["feed_id"]]["category_title"],
                    "feed_title": by_feed[post["feed_id"]]["title"],
                    "favicon": by_feed[post["feed_id"]]["favicon"],
                }
                
                # Process reranking individually for each post
                if rerank and rerank_url:
                    try:
                        # Get content
                        content = gzip.decompress(post["content"]["content"]).decode("utf-8", "replace")
                        
                        # Split content into chunks with 50% overlap
                        chunks = []
                        words = content.split()
                        chunk_size = MAX_CHUNK_LENGTH
                        stride = int(chunk_size * (1 - OVERLAP_PERCENT))
                        
                        if len(words) <= chunk_size:
                            # Content fits in one chunk
                            chunks.append(" ".join(words))
                        else:
                            # Split into overlapping chunks
                            for i in range(0, len(words), stride):
                                chunk = words[i:i + chunk_size]
                                if chunk:
                                    chunks.append(" ".join(chunk))
                                # Stop if this chunk or next would be too small
                                if i + chunk_size >= len(words):
                                    break
                        
                        # Prepare all chunks for a single request
                        rerank_data = [[rerank, chunk] for chunk in chunks]
                        
                        # Send a single request with all chunks
                        response = requests.post(rerank_url, json=rerank_data, timeout=300)
                        response.raise_for_status()
                        scores = response.json()
                        #print(scores)
                        
                        # Find the maximum score from all chunks
                        max_score = -float('inf')
                        if isinstance(scores, list) and scores:
                            for score in scores:
                                max_score = max(max_score, score)
                        
                        # Only add the score if we found a valid one
                        if max_score > -float('inf'):
                            post_data['rerank_score'] = max_score
                            
                    except requests.exceptions.RequestException as e:
                        logging.error('Rerank API call failed for post %d: %s', post["pid"], e)
                    except json.JSONDecodeError as e:
                        logging.error('Failed to decode rerank API JSON response for post %d: %s', post["pid"], e)
                    except Exception as e:
                        logging.error('Unexpected error during reranking for post %d: %s', post["pid"], e)
                    
                    # Remove content to save memory
                    if "content" in post and "content" in post["content"]:
                        del post["content"]["content"]
                
                posts.append(post_data)

    # Sort posts by rerank score if available
    if rerank and rerank_url:
        posts.sort(key=lambda x: x.get('rerank_score', -float('inf')), reverse=True)
        
        # Filter to keep only positively scored posts if we have enough
        filtered_posts = [p for p in posts if p.get('rerank_score', 0) > 0]
        if len(filtered_posts) > 3:
            posts = filtered_posts
        else:
            # Keep at least the top 3 posts regardless of score
            posts = posts[:3]

    tags_cur = app.tags.get_by_tags(user["sid"], tag_words, only_unread=only_unread)
    words = set()
    for tg in tags_cur:
        words.update(tg["words"])

    page = app.template_env.get_template("posts.html")

    return Response(
        page.render(
            posts=posts,
            tag=tag,
            group="tag",
            words=list(words),
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )

def get_embeddings(texts: list[str]) -> list[list[float]]:
    from http.client import HTTPConnection
    conn = HTTPConnection("192.168.178.26:8256")
    conn.request("POST", "/v1/embeddings", json.dumps(texts), {"Content-Type": "application/json"})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()

    return json.loads(data)

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = sum(a * a for a in v1) ** 0.5
    norm_v2 = sum(b * b for b in v2) ** 0.5
    if norm_v1 == 0 or norm_v2 == 0:
        return 0
    return dot_product / (norm_v1 * norm_v2)

def on_entity_get_(app: "RSSTagApplication", user: dict, quoted_tag: str, window: Optional[int]=10, rerank: Optional[str]=None) -> Response:
    #print(rerank)
    tag = unquote(quoted_tag)
    tag_words = tag.split()
    projection = {"_id": False}
    if not rerank:
        projection["content.content"] = False
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None
    db_posts_c = app.posts.get_by_tags(
        user["sid"], tag_words, only_unread, projection
    )
    db_posts = list(db_posts_c)

    if user["settings"]["similar_posts"]:
        clusters = app.posts.get_clusters(db_posts)
        cl_posts = app.posts.get_by_clusters(
            user["sid"], list(clusters), only_unread, projection
        )
        db_posts.extend(cl_posts)
    posts = []
    by_feed = {}
    pids = set()
    multi_word_tag = len(tag_words) > 1
    tag_words_set = set(tag_words)
    
    # Maximum length for chunking
    MAX_CHUNK_LENGTH = 1024
    # Overlap percentage (50%)
    OVERLAP_PERCENT = 0.5
    
    # Get the query embedding only once if reranking is requested
    query_embedding = None
    if rerank:
        try:
            # Get embedding for the rerank query
            query_embeddings = get_embeddings([rerank])
            if query_embeddings and len(query_embeddings) > 0:
                query_embedding = query_embeddings[0]
        except Exception as e:
            logging.error('Failed to get embedding for query "%s": %s', rerank, e)
    
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")

        # If tag has multiple words, check if they are within the window distance
        if multi_word_tag:
            lemmas_list = post["lemmas"].split()
            words_positions = {}

            # Find positions of all tag words in lemmas
            
            for i, lemma in enumerate(lemmas_list):
                if lemma in tag_words_set:
                    if lemma not in words_positions:
                        words_positions[lemma] = []
                    words_positions[lemma].append(i)

            # Check if all words are present
            if len(words_positions) != len(tag_words):
                continue

            # Check if any combination of positions is within window distance
            within_window = False

            # Get all possible combinations of positions
            positions_lists = []
            for word in tag_words:
                if word in words_positions and words_positions[word]:
                    positions_lists.append(words_positions[word])

            # If we have positions for all words
            if len(positions_lists) == len(tag_words):
                # Try each position of the first word with all combinations of other words
                for pos1 in positions_lists[0]:
                    # Create a test set starting with the first word's position
                    test_positions = [pos1]

                    # Try to find positions of other words that are within window distance
                    for positions in positions_lists[1:]:
                        # Find the nearest position to pos1
                        nearest_pos = min(positions, key=lambda x: abs(x - pos1))
                        test_positions.append(nearest_pos)

                    # Check if the max distance is within window
                    max_pos = max(test_positions)
                    min_pos = min(test_positions)
                    if max_pos - min_pos <= window:
                        within_window = True
                        break

            # Skip post if words aren't within window
            if not within_window:
                continue

        if post["pid"] not in pids:
            pids.add(post["pid"])
            if post["feed_id"] not in by_feed:
                feed = app.feeds.get_by_feed_id(user["sid"], post["feed_id"])
                if feed:
                    by_feed[post["feed_id"]] = feed
            if post["feed_id"] in by_feed:
                post_data = {
                    "post": post,
                    "pos": post["pid"],
                    "category_title": by_feed[post["feed_id"]]["category_title"],
                    "feed_title": by_feed[post["feed_id"]]["title"],
                    "favicon": by_feed[post["feed_id"]]["favicon"],
                }
                
                # Process embeddings for reranking if requested and query embedding was obtained
                if rerank and query_embedding:
                    try:
                        # Get content
                        content = gzip.decompress(post["content"]["content"]).decode("utf-8", "replace")
                        
                        # Split content into chunks with 50% overlap
                        chunks = []
                        words = content.split()
                        chunk_size = MAX_CHUNK_LENGTH
                        stride = int(chunk_size * (1 - OVERLAP_PERCENT))
                        
                        if len(words) <= chunk_size:
                            # Content fits in one chunk
                            chunks.append(" ".join(words))
                        else:
                            # Split into overlapping chunks
                            for i in range(0, len(words), stride):
                                chunk = words[i:i + chunk_size]
                                if chunk:
                                    chunks.append(" ".join(chunk))
                                # Stop if this chunk or next would be too small
                                if i + chunk_size >= len(words):
                                    break
                        
                        # Get embeddings for chunks only (query embedding already obtained)
                        chunk_embeddings = get_embeddings(chunks)
                        
                        if chunk_embeddings:
                            # Calculate cosine similarity between query and each chunk
                            similarities = [cosine_similarity(query_embedding, chunk_emb) for chunk_emb in chunk_embeddings]
                            
                            # Find the highest similarity score
                            max_similarity = max(similarities) if similarities else 0
                            
                            # Store the similarity as score
                            post_data['rerank_score'] = max_similarity
                            
                    except Exception as e:
                        logging.error('Embedding/similarity calculation failed for post %d: %s', post["pid"], e)
                    
                    # Remove content to save memory
                    if "content" in post and "content" in post["content"]:
                        del post["content"]["content"]
                
                posts.append(post_data)

    # Sort posts by similarity score if available
    if rerank and query_embedding:
        posts.sort(key=lambda x: x.get('rerank_score', -float('inf')), reverse=True)
        
        # Filter to keep only posts with similarity above threshold if we have enough
        threshold = 0.5  # Adjusted threshold for cosine similarity
        filtered_posts = [p for p in posts if p.get('rerank_score', 0) > threshold]
        if len(filtered_posts) > 3:
            posts = filtered_posts
        else:
            # Keep at least the top 3 posts regardless of score
            posts = posts[:3]

    tags_cur = app.tags.get_by_tags(user["sid"], tag_words, only_unread=only_unread)
    words = set()
    for tg in tags_cur:
        words.update(tg["words"])

    page = app.template_env.get_template("posts.html")

    return Response(
        page.render(
            posts=posts,
            tag=tag,
            group="tag",
            words=list(words),
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )

def on_posts_get(
    app: "RSSTagApplication", user: dict, request: Request, pids: str
) -> Response:
    context_n = 0
    ctx_n = None
    if "context" in request.args:
        ctx_n = request.args["context"]
    if ctx_n:
        context_n = int(ctx_n)
    projection = {"_id": False, "content.content": False}
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None
    pids_i = [int(p) for p in pids.split("_")]
    c_pids = set()
    if context_n > 0:
        only_unread = None
        for pid_i in pids_i:
            for i in range(context_n):
                i += 1
                pd = pid_i - i
                if pd >= 0:
                    c_pids.add(pd)
                c_pids.add(pid_i + i)
    if c_pids:
        pids_i.extend(c_pids)

    db_posts_c = app.posts.get_by_pids(user["sid"], pids_i, projection)
    db_posts = list(db_posts_c)

    if user["settings"]["similar_posts"]:
        clusters = app.posts.get_clusters(db_posts)
        cl_posts = app.posts.get_by_clusters(
            user["sid"], list(clusters), only_unread, projection
        )
        db_posts.extend(cl_posts)
    posts = []
    by_feed = {}
    pids = set()
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
        if post["pid"] not in pids:
            pids.add(post["pid"])
            if post["feed_id"] not in by_feed:
                feed = app.feeds.get_by_feed_id(user["sid"], post["feed_id"])
                if feed:
                    by_feed[post["feed_id"]] = feed
            if post["feed_id"] in by_feed:
                posts.append(
                    {
                        "post": post,
                        "pos": post["pid"],
                        "category_title": by_feed[post["feed_id"]]["category_title"],
                        "feed_title": by_feed[post["feed_id"]]["title"],
                        "favicon": by_feed[post["feed_id"]]["favicon"],
                    }
                )
    page = app.template_env.get_template("posts.html")
    if context_n:
        posts.sort(key=lambda p: p["pos"], reverse=True)

    return Response(
        page.render(
            posts=posts,
            tag="NoTag",
            group="tag",
            words=[],
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )


def on_cluster_get(app: "RSSTagApplication", user: dict, cluster: int) -> Response:
    projection = {"_id": False, "content.content": False}
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None
    db_posts = app.posts.get_by_clusters(
        user["sid"], [cluster], only_unread, projection
    )

    posts = []
    by_feed = {}
    pids = set()
    for post in db_posts:
        post["lemmas"] = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
        if post["pid"] not in pids:
            pids.add(post["pid"])
            if post["feed_id"] not in by_feed:
                feed = app.feeds.get_by_feed_id(user["sid"], post["feed_id"])
                if feed:
                    by_feed[post["feed_id"]] = feed
            if post["feed_id"] in by_feed:
                posts.append(
                    {
                        "post": post,
                        "pos": post["pid"],
                        "category_title": by_feed[post["feed_id"]]["category_title"],
                        "feed_title": by_feed[post["feed_id"]]["title"],
                        "favicon": by_feed[post["feed_id"]]["favicon"],
                    }
                )
    page = app.template_env.get_template("posts.html")

    return Response(
        page.render(
            posts=posts,
            tag="NoTag",
            group="tag",
            words=[],
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )

def on_post_grouped_get(app: "RSSTagApplication", user: dict, request: Request, pids: str) -> Response:
    projection = {"content": True, "feed_id": True, "url": True}
    post_ids = [int(pid) for pid in pids.split('_') if pid]
    if not post_ids:
        return app.on_error(user, request, NotFound())

    # Get the full posts first, we'll need them regardless
    all_posts = []
    feed_titles = []
    for post_id in post_ids:
        post = app.posts.get_by_pid(user["sid"], post_id, projection)
        if post:
            feed = app.feeds.get_by_feed_id(user["sid"], post["feed_id"])
            feed_title = feed["title"] if feed else f"Post {post_id}"
            if feed_title not in feed_titles:
                feed_titles.append(feed_title)
            
            content = gzip.decompress(post["content"]["content"]).decode("utf-8", "replace")
            if post["content"]["title"]:
                content = post["content"]["title"] + ". " + content
            
            all_posts.append({
                "post_id": post_id,
                "content": content,
                "feed_title": feed_title,
                "url": post.get("url", "") or ""
            })
    
    post_to_index_map = {post["post_id"]: idx for idx, post in enumerate(all_posts)}
    combined_feed_title = " | ".join(feed_titles) if feed_titles else "Multiple Posts"

    # Collect grouped data from all posts (single or multiple)
    all_sentences = []
    all_groups = {}
    all_group_colors = {}
    sentence_offset = 0
    has_grouped_data = False

    for post in all_posts:
        # Check if this individual post has grouped data
        post_grouped_data = app.post_grouping.get_grouped_posts(user["sid"], [post["post_id"]])
        
        if post_grouped_data and post_grouped_data.get("sentences"):
            has_grouped_data = True
            # Add sentences with adjusted indices and post_id reference
            for sentence in post_grouped_data["sentences"]:
                all_sentences.append({
                    "text": sentence["text"],
                    "number": sentence_offset + sentence["number"],
                    "post_id": post["post_id"]
                })
            
            # Add groups with adjusted sentence indices
            for group_name, sentence_indices in post_grouped_data["groups"].items():
                # Prefix group name with post info if multiple posts
                if len(all_posts) > 1:
                    full_group_name = f"[{post['feed_title'][:20]}...] {group_name}" if len(post['feed_title']) > 20 else f"[{post['feed_title']}] {group_name}"
                else:
                    full_group_name = group_name
                
                # Adjust sentence indices by offset
                adjusted_indices = [idx + sentence_offset for idx in sentence_indices]
                all_groups[full_group_name] = adjusted_indices
                
                # Use the same color for the group
                if group_name in post_grouped_data.get("group_colors", {}):
                    all_group_colors[full_group_name] = post_grouped_data["group_colors"][group_name]
                else:
                    all_group_colors[full_group_name] = "#4a6baf"
            
            # Update offset for next post
            sentence_offset += len(post_grouped_data["sentences"])
    
    # If no grouped data exists for any post, create default grouping by post
    if not has_grouped_data:
        for post in all_posts:
            group_name = f"Post {post['post_id']}"
            all_groups[group_name] = [post["post_id"]]
            all_group_colors[group_name] = "#4a6baf"
    
    page = app.template_env.get_template("post-grouped.html")
    return Response(
        page.render(
            post_id=pids,
            posts=all_posts,
            sentences=all_sentences,
            groups=all_groups,
            group_colors=all_group_colors,
            hierarchical_segments=[],
            feed_title=combined_feed_title,
            user_settings=user["settings"],
            provider=user["provider"],
            post_to_index_map=post_to_index_map,
            has_grouped_data=has_grouped_data,
        ),
        mimetype="text/html",
    )

def on_topics_list_get(app: "RSSTagApplication", user: dict, request: Request, page_number: int = 1) -> Response:
    """Handler for topics/chapters list page with pagination"""
    # Pagination settings
    topics_per_page = 20
    
    # Get all grouped posts data from the database
    grouped_posts = list(app.db.post_grouping.find(
        {"owner": user["sid"]},
        {"_id": 0, "groups": 1, "post_ids": 1, "feed_title": 1}
    ))
    
    # Count topics/chapters across all posts
    topic_counts = {}
    post_topic_mapping = {}
    
    for post_data in grouped_posts:
        post_id_str = "_".join(str(pid) for pid in post_data["post_ids"])
        post_topic_mapping[post_id_str] = {
            "feed_title": post_data["feed_title"],
            "topics": list(post_data["groups"].keys())
        }
        
        for topic in post_data["groups"].keys():
            if topic not in topic_counts:
                topic_counts[topic] = {
                    "count": 0,
                    "posts": []
                }
            topic_counts[topic]["count"] += 1
            topic_counts[topic]["posts"].append(post_id_str)
    
    # Sort topics by count (descending)
    sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1]["count"], reverse=True)
    
    # Calculate pagination
    total_topics = len(sorted_topics)
    total_pages = max(1, (total_topics + topics_per_page - 1) // topics_per_page)
    page_number = max(1, min(page_number, total_pages))
    
    # Get topics for current page
    start_idx = (page_number - 1) * topics_per_page
    end_idx = start_idx + topics_per_page
    paginated_topics = sorted_topics[start_idx:end_idx]
    
    # Generate pagination links
    pagination = {
        "current_page": page_number,
        "total_pages": total_pages,
        "has_prev": page_number > 1,
        "has_next": page_number < total_pages,
        "prev_page": page_number - 1 if page_number > 1 else None,
        "next_page": page_number + 1 if page_number < total_pages else None,
    }
    
    page = app.template_env.get_template("topics-list.html")
    return Response(
        page.render(
            topics=paginated_topics,
            post_topic_mapping=post_topic_mapping,
            pagination=pagination,
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )
