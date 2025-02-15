import gzip

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication
from rsstag.prefix_tree import PrefixTreeBuilder
from rsstag.html_cleaner import HTMLCleaner

from werkzeug.wrappers import Response

prefixes_builders: dict[str: PrefixTreeBuilder] = {}

def on_prefixes_all_get(app: "RSSTagApplication", user: dict, prefix_len: int) -> Response:
    if user["sid"] not in prefixes_builders:
        cleaner = HTMLCleaner()
        prefix_builder = PrefixTreeBuilder()
        cursor = app.posts.get_all(user["sid"])
        for post in cursor:
            text = gzip.decompress(post["content"]["content"]).decode(
                "utf-8", "replace"
            )
            text = post["content"]["title"] + " " + text
            cleaner.purge()
            cleaner.feed(text)
            text = " ".join(cleaner.get_content())
            prefix_builder.add_words_from_doc(text)

        prefixes_builders[user["sid"]] = prefix_builder
    else:
        prefix_builder = prefixes_builders[user["sid"]]
    prefixes = prefix_builder.get_top_n(prefix_len)

    sorted_prefixes = []
    for p in prefixes:
        sorted_prefixes.append(
            {
                "tag": p[0],
                "url": "",
                "words": [],
                "count": p[1],
                "sentiment": [],
            }
        )
    letters = []
    page = app.template_env.get_template("group-by-tag.html")

    return Response(
        page.render(
            tags=sorted_prefixes,
            sort_by_title="tags",
            sort_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_tags_get",
                params={"page_number":1},
            ),
            group_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_category_get"
            ),
            pages_map=[],
            current_page=1,
            letters=letters,
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )

def on_prefixes_words_get(app: "RSSTagApplication", user: dict, prefix: str) -> Response:
    if user["sid"] not in prefixes_builders:
        cleaner = HTMLCleaner()
        prefix_builder = PrefixTreeBuilder()
        cursor = app.posts.get_all(user["sid"])
        for post in cursor:
            text = gzip.decompress(post["content"]["content"]).decode(
                "utf-8", "replace"
            )
            text = post["content"]["title"] + " " + text
            cleaner.purge()
            cleaner.feed(text)
            text = " ".join(cleaner.get_content())
            prefix_builder.add_words_from_doc(text)

        prefixes_builders[user["sid"]] = prefix_builder
    else:
        prefix_builder = prefixes_builders[user["sid"]]
    words = prefix_builder.get_tails(prefix)

    sorted_prefixes = []
    for w in words:
        sorted_prefixes.append(
            {
                "tag": w,
                "url": "",
                "words": [],
                "count": 0,
                "sentiment": [],
            }
        )
    letters = []
    page = app.template_env.get_template("group-by-tag.html")

    return Response(
        page.render(
            tags=sorted_prefixes,
            sort_by_title="tags",
            sort_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_tags_get",
                params={"page_number":1},
            ),
            group_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_category_get"
            ),
            pages_map=[],
            current_page=1,
            letters=letters,
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )

def on_prefixes_prefix_get(app: "RSSTagApplication", user: dict, prefix: str) -> Response:
    if user["sid"] not in prefixes_builders:
        cleaner = HTMLCleaner()
        prefix_builder = PrefixTreeBuilder()
        cursor = app.posts.get_all(user["sid"])
        for post in cursor:
            text = gzip.decompress(post["content"]["content"]).decode(
                "utf-8", "replace"
            )
            text = post["content"]["title"] + " " + text
            cleaner.purge()
            cleaner.feed(text)
            text = " ".join(cleaner.get_content())
            prefix_builder.add_words_from_doc(text)

        prefixes_builders[user["sid"]] = prefix_builder
    else:
        prefix_builder = prefixes_builders[user["sid"]]

    #root = prefix_builder.get_tree(prefix)
    root = prefix_builder.get_compact_tree(prefix)
    if root is None:
        root = {"name": prefix, "children": []}

    tag_data = {"tag": prefix}
    page = app.template_env.get_template("tag-sunburst.html")

    return Response(
        page.render(
            tag=tag_data,
            root=root,
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )