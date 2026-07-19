import gzip
import json
import re
from collections import OrderedDict, defaultdict
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from rsstag.html_cleaner import HTMLCleaner
from rsstag.lda import LDA
from rsstag.utils import get_sorted_dict_by_alphabet

from werkzeug.wrappers import Request, Response
from werkzeug.exceptions import NotFound

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication


def on_group_by_category_get(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    page_number = 1
    by_feed = {}
    db_feeds = app.feeds.get_all(user["sid"])
    canvas_url: str = (
        app.routes.get_url_by_endpoint(endpoint="on_canvas_get") or "/canvas"
    )
    hierarchy_url: str = (
        app.routes.get_url_by_endpoint(endpoint="on_hierarchy_get") or "/hierarchy"
    )

    for f in db_feeds:
        by_feed[f["feed_id"]] = f
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None

    grouped = app.posts.get_grouped_stat(user["sid"], only_unread)
    by_category = {
        app.feeds.all_feeds: {
            "unread_count": 0,
            "title": app.feeds.all_feeds,
            "url": app.routes.get_url_by_endpoint(
                endpoint="on_category_get",
                params={"quoted_category": app.feeds.all_feeds},
            ),
            "canvas_url": canvas_url,
            "hierarchy_url": hierarchy_url,
            "feeds": [],
        }
    }
    for g in grouped:
        if g["count"] > 0:
            if g["category_id"] not in by_category:
                category_query: str = urlencode({"category": g["category_id"]})
                by_category[g["category_id"]] = {
                    "unread_count": 0,
                    "category_id": g["category_id"],
                    "title": by_feed[g["_id"]]["category_title"],
                    "url": by_feed[g["_id"]]["category_local_url"],
                    "canvas_url": f"{canvas_url}?{category_query}",
                    "hierarchy_url": f"{hierarchy_url}?{category_query}",
                    "feeds": [],
                }
            by_category[g["category_id"]]["unread_count"] += g["count"]
            by_category[app.feeds.all_feeds]["unread_count"] += g["count"]
            by_category[g["category_id"]]["feeds"].append(
                {
                    "unread_count": g["count"],
                    "feed_id": g["_id"],
                    "url": by_feed[g["_id"]]["local_url"],
                    "title": by_feed[g["_id"]]["title"],
                    "canvas_url": f"{canvas_url}?{urlencode({'feed': g['_id']})}",
                    "hierarchy_url": f"{hierarchy_url}?{urlencode({'feed': g['_id']})}",
                }
            )
    if len(by_category) > 1:
        data = get_sorted_dict_by_alphabet(by_category)
        if app.no_category_name in data:
            data.move_to_end(app.no_category_name)
    else:
        data = OrderedDict()
    page = app.template_env.get_template("group-by-category.html")

    return Response(
        page.render(
            data=data,
            group_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_tags_get", params={"page_number": page_number}
            ),
            user_settings=user["settings"],
            provider=user.get("provider", ""),
        ),
        mimetype="text/html",
    )


def on_get_map(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    projection = {"_id": False}
    cities = app.tags.get_city_tags(
        user["sid"], user["settings"]["only_unread"], projection
    )
    countries = app.tags.get_country_tags(
        user["sid"], user["settings"]["only_unread"], projection
    )
    page = app.template_env.get_template("map.html")

    return Response(
        page.render(
            support=app.config["settings"]["support"],
            version=app.config["settings"]["version"],
            user_settings=user["settings"],
            provider=user.get("provider", ""),
            cities=list(cities),
            countries=list(countries),
        ),
        mimetype="text/html",
    )


def on_get_tag_net(app: "RSSTagApplication", user: dict, request: Request, tag="") -> Response:
    all_tags = []
    edges = defaultdict(set)
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None

    posts = app.posts.get_by_tags(user["sid"], [tag], only_unread, {"tags": True})
    tags_set = set()
    for post in posts:
        for tag in post["tags"]:
            tags_set.add(tag)
            for tg in post["tags"]:
                edges[tag].add(tg)

    if tags_set:
        db_tags = app.tags.get_by_tags(
            user["sid"], list(tags_set), user["settings"]["only_unread"]
        )
        for tag in db_tags:
            edges[tag["tag"]].remove(tag["tag"])
            all_tags.append(
                {
                    "tag": tag["tag"],
                    "url": tag["local_url"],
                    "words": tag["words"],
                    "count": tag["unread_count"]
                    if user["settings"]["only_unread"]
                    else tag["posts_count"],
                    "edges": list(edges[tag["tag"]])[:5],
                    "sentiment": tag["sentiment"] if "sentiment" in tag else [],
                }
            )

    return Response(
        json.dumps({"data": all_tags}),
        mimetype="application/json",
    )


def on_get_tag_net_page(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    page = app.template_env.get_template("tags-net.html")

    return Response(
        page.render(
            support=app.config["settings"]["support"],
            version=app.config["settings"]["version"],
            user_settings=user["settings"],
            provider=user.get("provider", ""),
        ),
        mimetype="text/html",
    )


def on_get_groups(app: "RSSTagApplication", user: dict, request: Request, page_number=1) -> Response:
    groups = app.tags.get_groups(user["sid"], user["settings"]["only_unread"])
    groups_count = len(groups)
    page_count = app.get_page_count(groups_count, user["settings"]["tags_on_page"])
    p_number = page_number
    if page_number <= 0:
        p_number = 1
    elif page_number > page_count:
        p_number = page_count

    p_number -= 1
    if p_number < 0:
        p_number = 1
    pages_map, start_tags_range, end_tags_range = app.calc_pager_data(
        p_number,
        page_count,
        user["settings"]["tags_on_page"],
        "on_get_groups",
    )

    page_groups = sorted(groups.items(), key=lambda el: el[1], reverse=True)
    page = app.template_env.get_template("tags-groups.html")

    return Response(
        page.render(
            support=app.config["settings"]["support"],
            version=app.config["settings"]["version"],
            user_settings=user["settings"],
            provider=user.get("provider", ""),
            pages_map=pages_map,
            groups=page_groups[start_tags_range:end_tags_range],
        ),
        mimetype="text/html",
    )


def on_wordtree_texts_get(app: "RSSTagApplication", user: dict, request: Request, tag: str) -> Response:
    if tag:
        cursor = app.posts.get_by_tags(
            user["sid"], [tag], user["settings"]["only_unread"], {"lemmas": True}
        )
        data = []
        window = 10
        for post in cursor:
            text = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
            words = text.split()
            for i, word in enumerate(words):
                if word == tag:
                    start_pos = i - window
                    if start_pos < 0:
                        start_pos = 0
                    end_pos = i + window
                    data.append(" ".join(words[start_pos:end_pos]))
        result = {"data": data}
        code = 200
    else:
        result = {"error": "Something wrong with request"}
        code = 400

    return Response(json.dumps(result), mimetype="application/json", status=code)


def on_topics_texts_get(app: "RSSTagApplication", user: dict, request: Request, tag: str) -> Response:
    if tag:
        cursor = app.posts.get_by_tags(
            user["sid"], [tag], user["settings"]["only_unread"], {"lemmas": True}
        )
        texts = [
            gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
            for post in cursor
        ]
        lda = LDA()
        topics = lda.topics(texts, top_k=5)
        if tag in topics:
            topics.remove(tag)
        result = {"data": {"texts": texts, "topics": topics}}
        code = 200
    else:
        result = {"error": "Something wrong with request"}
        code = 400

    return Response(json.dumps(result), mimetype="application/json", status=code)


def on_topics_get(
    app: "RSSTagApplication", user: dict, request: Request, page_number: int = 1
) -> Response:
    all_tags = []
    cursor = app.posts.get_all(
        user["sid"], user["settings"]["only_unread"], {"lemmas": True}
    )
    texts = [
        gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
        for post in cursor
    ]
    lda = LDA()
    topics = lda.topics(texts, top_k=10)
    tags = app.tags.get_by_tags(
        user["sid"], topics, user["settings"]["only_unread"]
    )
    for tag in tags:
        all_tags.append(
            {
                "tag": tag["tag"],
                "url": tag["local_url"],
                "words": tag["words"],
                "count": tag["unread_count"]
                if user["settings"]["only_unread"]
                else tag["posts_count"],
                "sentiment": tag["sentiment"] if "sentiment" in tag else [],
                "temp": tag["temperature"],
            }
        )
    all_tags.sort(key=lambda t: t["temp"], reverse=True)
    page_count = app.get_page_count(1, user["settings"]["tags_on_page"])
    p_number = page_number
    if page_number <= 0:
        p_number = 1
    elif page_number > page_count:
        p_number = page_count

    new_cookie_page_value = p_number
    p_number -= 1
    if p_number < 0:
        p_number = 1
    pages_map, start_tags_range, end_tags_range = app.calc_pager_data(
        p_number, page_count, user["settings"]["tags_on_page"], "on_topics_get"
    )
    db_letters = app.letters.get(user["sid"], make_sort=True)
    if db_letters:
        letters = app.letters.to_list(db_letters, user["settings"]["only_unread"])
    else:
        letters = []
    page = app.template_env.get_template("group-by-tag.html")

    return Response(
        page.render(
            tags=all_tags,
            sort_by_title="tags",
            sort_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_tags_get",
                params={"page_number": new_cookie_page_value},
            ),
            group_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_category_get"
            ),
            pages_map=pages_map,
            current_page=new_cookie_page_value,
            letters=letters,
            user_settings=user["settings"],
            provider=user.get("provider", ""),
        ),
        mimetype="text/html",
    )


def on_get_sentences_with_tags(
    app: "RSSTagApplication", user: dict, request: Request, s_tags: str
) -> Response:
    if not s_tags:
        return app.on_error(user, request, NotFound())

    q_tags = s_tags.split(" ")
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None

    db_posts = app.posts.get_by_tags(user["sid"], q_tags, only_unread=only_unread)
    db_tags = app.tags.get_by_tags(user["sid"], q_tags, only_unread=only_unread)

    words = set()
    for t in db_tags:
        words.update(t["words"])
    by_feed = {}
    sentences = []
    html_c = HTMLCleaner()
    w_cond = "|".join(re.escape(word) for word in words)
    re_words = re.compile(r"(\b({})\b)".format(w_cond), re.IGNORECASE | re.UNICODE)
    for post in db_posts:
        txt = gzip.decompress(post["content"]["content"]).decode("utf-8", "replace")
        if post["content"]["title"]:
            txt = post["content"]["title"] + ". " + txt
        html_c.purge()
        html_c.feed(txt)
        txt = " ".join(html_c.get_content())
        if post["feed_id"] not in by_feed:
            feed = app.feeds.get_by_feed_id(user["sid"], post["feed_id"])
            if feed:
                by_feed[post["feed_id"]] = feed
        sents = []
        raw_sents = re.split(r"(?<=[.!?])\s+", txt)
        for s in raw_sents:
            if re_words.search(s):
                highlighted = re_words.sub(r"<b>\1</b>", s)
                sents.append(highlighted)

        if not sents:
            continue
        sentences.append(
            {
                "sentence": sents,
                "pid": post["pid"],
                "category_title": by_feed[post["feed_id"]]["category_title"],
                "feed_title": by_feed[post["feed_id"]]["title"],
                "favicon": by_feed[post["feed_id"]]["favicon"],
                "date": post["date"],
            }
        )
    page = app.template_env.get_template("sentences.html")

    return Response(
        page.render(
            sentences=sentences,
            tag=s_tags,
            group="tag",
            words=list(words),
            user_settings=user["settings"],
            provider=user.get("provider", ""),
        ),
        mimetype="text/html",
    )


def on_download_posts_get(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    page_number = int(request.args.get("page", 1))
    tag = request.args.get("tag", "").strip()
    post_id = request.args.get("id", "").strip()

    items_per_page = 50
    query = {"owner": user["sid"]}

    if tag:
        query["tags"] = tag
    if post_id:
        try:
            query["pid"] = int(post_id)
        except ValueError:
            query["pid"] = post_id

    total = app.db.posts.count_documents(query)
    page_count = app.get_page_count(total, items_per_page)

    if page_number < 1:
        page_number = 1
    elif page_number > page_count:
        page_number = page_count if page_count > 0 else 1

    skip = (page_number - 1) * items_per_page
    posts = list(app.db.posts.find(query, {"pid": 1, "content.title": 1, "date": 1})
                 .sort("date", -1).skip(skip).limit(items_per_page))

    page = app.template_env.get_template("download-posts.html")
    return Response(
        page.render(
            posts=posts,
            current_page=page_number,
            total_pages=page_count,
            tag=tag,
            post_id=post_id,
            user_settings=user["settings"],
            provider=user.get("provider", ""),
        ),
        mimetype="text/html",
    )


def on_download_post_get(app: "RSSTagApplication", user: dict, request: Request, post_id: str) -> Response:
    post = app.posts.get_by_pid(user["sid"], post_id, {"content": 1})

    if not post or "content" not in post:
        return Response("Post not found", status=404)

    content = gzip.decompress(post["content"]["content"]).decode("utf-8", "replace")
    title = post["content"].get("title", f"post_{post_id}")
    safe_title = title[:50].encode("ascii", "ignore").decode("ascii")

    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{post_id}_{safe_title}.txt"'},
    )
