import json
import gzip
from typing import TYPE_CHECKING
from collections import Counter
from urllib.parse import quote

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

from werkzeug.wrappers import Response

from sklearn.feature_extraction.text import TfidfVectorizer
from nltk.corpus import stopwords


def on_group_by_bigrams_get(
    app: "RSSTagApplication", user: dict, page_number: int = 1
) -> Response:
    tags_count = app.bi_grams.count(
        user["sid"], only_unread=user["settings"]["only_unread"]
    )
    page_count = app.get_page_count(tags_count, user["settings"]["tags_on_page"])
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
        p_number,
        page_count,
        user["settings"]["tags_on_page"],
        "on_group_by_bigrams_get",
    )
    sorted_tags = []
    tags = app.bi_grams.get_all(
        user["sid"],
        user["settings"]["only_unread"],
        user["settings"]["hot_tags"],
        opts={"offset": start_tags_range, "limit": user["settings"]["tags_on_page"]},
    )

    for t in tags:
        sorted_tags.append(
            {
                "tag": t["tag"],
                "url": t["local_url"],
                "words": t["words"],
                "count": t["unread_count"]
                if user["settings"]["only_unread"]
                else t["posts_count"],
                "sentiment": [],
            }
        )
    letters = []
    page = app.template_env.get_template("group-by-tag.html")

    return Response(
        page.render(
            tags=sorted_tags,
            sort_by_title="tags",
            sort_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_bigrams_get",
                params={"page_number": new_cookie_page_value},
            ),
            group_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_category_get"
            ),
            pages_map=pages_map,
            current_page=new_cookie_page_value,
            letters=letters,
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )


def on_get_tag_bi_grams(app: "RSSTagApplication", user: dict, tag: str) -> Response:
    bi_grams = app.bi_grams.get_by_tags(
        user["sid"], [tag], user["settings"]["only_unread"]
    )
    all_bi_grams = []
    for tag in bi_grams:
        all_bi_grams.append(
            {
                "tag": tag["tag"],
                "url": tag["local_url"],
                "words": tag["words"],
                "count": tag["unread_count"]
                if user["settings"]["only_unread"]
                else tag["posts_count"],
                "sentiment": tag["sentiment"] if "sentiment" in tag else [],
            }
        )

    return Response(json.dumps({"data": all_bi_grams}), mimetype="application/json")


def on_bigrams_dates_get(app: "RSSTagApplication", user: dict, tag: str) -> Response:
    if tag:
        cursor = app.posts.get_by_tags(
            user["sid"],
            [tag],
            user["settings"]["only_unread"],
            {"unix_date": True, "bi_grams": True},
        )
        data = {}
        for dt in cursor:
            d = int(dt["unix_date"])
            for bi in dt["bi_grams"]:
                if tag not in bi:
                    continue
                if bi not in data:
                    data[bi] = {}
                if d not in data[bi]:
                    data[bi][d] = 0
                data[bi][d] += 1
        result = {"data": data}
        code = 200
    else:
        result = {"error": "Something wrong with request"}
        code = 400

    return Response(json.dumps(result), mimetype="application/json", status=code)

def on_group_by_bigrams_dyn_get(
    app: "RSSTagApplication", user: dict, page_number: int = 1
) -> Response:
    pages_map, start_tags_range, end_tags_range = app.calc_pager_data(
        1,
        1,
        user["settings"]["tags_on_page"],
        "on_group_by_bigrams_dyn_get",
    )

    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None
    posts = app.posts.get_all(user["sid"], only_unread, projection={"lemmas": True})
    texts = []
    for post in posts:
        texts.append(gzip.decompress(post["lemmas"]).decode("utf-8", "replace"))

    stopw = set(stopwords.words("english") + stopwords.words("russian"))
    vectorizer = TfidfVectorizer(stop_words=list(stopw))
    vectorizer.fit(texts)
    tfidfs = []
    for w, indx in vectorizer.vocabulary_.items():
        tfidfs.append((w, vectorizer.idf_[indx]))
    tfidfs.sort(key=lambda x: x[1], reverse=True)
    words_n = len(tfidfs) // 2
    tfidf_words = set()
    for wf in tfidfs:
        tfidf_words.add(wf[0])

    stopw = set(stopwords.words("english") + stopwords.words("russian"))
    #stopw.update([wf[0] for wf in tfidfs[words_n * 2:]])
    stopw.update([wf[0] for wf in tfidfs[:words_n]])

    window = 20
    bigrams = Counter()
    for p in texts:
        words = p.split(" ")
        lnw = len(words)
        post_bis = set()
        for i, w in enumerate(words):
            if w not in tfidf_words:
                continue

            for j in range(1, window):
                pos = i - j
                bgrms = []
                if pos >= 0 and words[pos] not in stopw:
                    l = [w, words[pos]]
                    l.sort()
                    bgrms.append(" ".join(l))
                pos = i + j
                if pos < lnw and words[pos] not in stopw:
                    l = [w, words[pos]]
                    l.sort()
                    bgrms.append(" ".join(l))
                if len(bgrms) > 0:
                    post_bis.update(bgrms)
        if len(post_bis) > 0:
            bigrams.update(post_bis)

    most_common = bigrams.most_common(user["settings"]["tags_on_page"] * 8)
    sorted_tags = []
    for t, fr in most_common:
        sorted_tags.append(
            {
                "tag": t,
                "url": app.routes.get_url_by_endpoint(
                    endpoint="on_entity_get", params={"quoted_tag": quote(t)}
                ),
                "words": [t],
                "count": fr,
                "sentiment": [],
            }
        )
    letters = []
    page = app.template_env.get_template("group-by-tag.html")

    return Response(
        page.render(
            tags=sorted_tags,
            sort_by_title="tags",
            sort_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_bigrams_get",
                params={"page_number": 1},
            ),
            group_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_category_get"
            ),
            pages_map=pages_map,
            current_page=1,
            letters=letters,
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )
