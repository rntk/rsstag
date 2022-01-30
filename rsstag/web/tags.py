import os
import re
import json
import gzip
import math
import html
import logging
from collections import Counter
from urllib.parse import unquote_plus, quote
from typing import Optional

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication
from rsstag.tags_builder import TagsBuilder
from rsstag.html_cleaner import HTMLCleaner
from rsstag.lda import LDA

from gensim.models.word2vec import Word2Vec
from gensim.models.fasttext import FastText

from werkzeug.wrappers import Request, Response
from werkzeug.exceptions import NotFound, InternalServerError

from nltk.corpus import stopwords

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN

from navec import Navec
from slovnet import NER


def on_group_by_tags_get(
    app: "RSSTagApplication", user: dict, page_number: int = 1
) -> Response:
    tags_count = app.tags.count(user["sid"], user["settings"]["only_unread"])
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
        p_number, page_count, user["settings"]["tags_on_page"], "on_group_by_tags_get"
    )
    sorted_tags = []
    tags = app.tags.get_all(
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
                "sentiment": t["sentiment"] if "sentiment" in t else [],
            }
        )
    db_letters = app.letters.get(user["sid"], make_sort=True)
    if db_letters:
        letters = app.letters.to_list(db_letters, user["settings"]["only_unread"])
    else:
        letters = []
    page = app.template_env.get_template("group-by-tag.html")

    return Response(
        page.render(
            tags=sorted_tags,
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
            provider=user["provider"],
        ),
        mimetype="text/html",
    )


def on_group_by_tags_sentiment(
    app: "RSSTagApplication", user: dict, sentiment: str, page_number: int = 1
) -> Response:
    sentiment = sentiment.replace("|", "/")
    tags_count = app.tags.count(
        user["sid"], user["settings"]["only_unread"], sentiments=[sentiment]
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
        "on_group_by_tags_sentiment",
        sentiment=sentiment,
    )
    sorted_tags = []
    tags = app.tags.get_by_sentiment(
        user["sid"],
        [sentiment],
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
                "sentiment": t["sentiment"] if "sentiment" in t else [],
            }
        )
    db_letters = app.letters.get(user["sid"], make_sort=True)
    if db_letters:
        letters = app.letters.to_list(db_letters, user["settings"]["only_unread"])
    else:
        letters = []
    page = app.template_env.get_template("group-by-tag.html")

    return Response(
        page.render(
            tags=sorted_tags,
            sort_by_title="tags",
            sort_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_tags_sentiment",
                params={"sentiment": sentiment, "page_number": new_cookie_page_value},
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


def on_group_by_tags_startwith_get(
    app: "RSSTagApplication", user: dict, request: Request, letter: str, page_number=1
) -> Response:
    db_letters = app.letters.get(user["sid"], make_sort=True)
    if db_letters is None:
        return app.on_error(user, request, InternalServerError())

    if letter not in db_letters["letters"]:
        return app.on_error(user, request, NotFound())

    tags_count = app.tags.count(
        user["sid"], user["settings"]["only_unread"], "^{}".format(letter)
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
        "on_group_by_tags_startwith_get",
        letter=letter,
    )
    sorted_tags = []
    tags = app.tags.get_all(
        user["sid"],
        user["settings"]["only_unread"],
        user["settings"]["hot_tags"],
        opts={
            "offset": start_tags_range,
            "limit": user["settings"]["tags_on_page"],
            "regexp": "^{}".format(letter),
        },
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
                "sentiment": t["sentiment"] if "sentiment" in t else [],
            }
        )
    if db_letters:
        letters = app.letters.to_list(db_letters, user["settings"]["only_unread"])
    else:
        letters = []
    app.users.update_by_sid(user["sid"], {"letter": letter})
    page = app.template_env.get_template("group-by-tag.html")

    return Response(
        page.render(
            tags=sorted_tags,
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
            provider=user["provider"],
        ),
        mimetype="text/html",
    )


def on_group_by_tags_group(
    app: "RSSTagApplication", user: dict, group: str, page_number=1
) -> Response:
    tags_count = app.tags.count(
        user["sid"], user["settings"]["only_unread"], groups=[group]
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
        "on_group_by_tags_group",
        group=group,
    )
    sorted_tags = []
    tags = app.tags.get_by_group(
        user["sid"],
        [group],
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
                "sentiment": t["sentiment"] if "sentiment" in t else [],
            }
        )
    db_letters = app.letters.get(user["sid"], make_sort=True)
    if db_letters:
        letters = app.letters.to_list(db_letters, user["settings"]["only_unread"])
    else:
        letters = []

    page = app.template_env.get_template("group-by-tag.html")

    return Response(
        page.render(
            tags=sorted_tags,
            sort_by_title="tags",
            sort_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_tags_group",
                params={"group": group, "page_number": new_cookie_page_value},
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


def on_get_tag_page(
    app: "RSSTagApplication", user: dict, request: Request, tag: str
) -> Response:
    tag_data = app.tags.get_by_tag(user["sid"], tag)
    if not tag_data:
        return app.on_error(user, request, NotFound())

    del tag_data["_id"]
    page = app.template_env.get_template("tag-info.html")

    return Response(
        page.render(
            tag=tag_data,
            posts_link=tag_data["local_url"],
            sort_by_title="tags",
            sort_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_tags_get", params={"page_number": 1}
            ),
            group_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_category_get"
            ),
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )


def on_post_tags_search(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    s_request = unquote_plus(request.form.get("req"))
    if s_request:
        search_result = app.tags.get_all(
            user["sid"],
            only_unread=user["settings"]["only_unread"],
            opts={"regexp": "^{}.*".format(s_request), "limit": 10},
        )
        code = 200
        result = {"data": []}
        for tag in search_result:
            result["data"].append(
                {
                    "tag": tag["tag"],
                    "unread": tag["unread_count"],
                    "all": tag["posts_count"],
                    "url": tag["local_url"],
                    "info_url": app.routes.get_url_by_endpoint(
                        "on_get_tag_page", {"tag": tag["tag"]}
                    ),
                }
            )
    else:
        code = 400
        result = {"error": "Request can`t be empty"}

    return Response(json.dumps(result), mimetype="application/json", status=code)


def on_get_tag_similar(
    app: "RSSTagApplication", user: dict, model: str, tags: str
) -> Response:
    tags_set = set()
    all_tags = []
    tags_l = tags.split()
    if model in app.models:
        if model == app.models["w2v"]:
            w2v = None
            path = os.path.join(app.config["settings"]["w2v_dir"], user["w2v"])
            if os.path.exists(path):
                w2v = Word2Vec.load(path)

            try:
                if len(tags_l) > 1:
                    siblings = w2v.wv.most_similar(tags_l, topn=30)
                else:
                    siblings = w2v.wv.similar_by_word(tags, topn=30)
                for sibling in siblings:
                    tags_set.add(sibling[0])
            except Exception as e:
                logging.warning(
                    "In %s not found tag %s. %s", path, tags, e
                )
        elif model == app.models["fasttext"]:
            ft: Optional[FastText] = None
            path = os.path.join(app.config["settings"]["fasttext_dir"], user["fasttext"])
            if os.path.exists(path):
                ft = FastText.load(path)

            try:
                if len(tags_l) > 1:
                    siblings = ft.wv.most_similar(tags_l, topn=30)
                else:
                    siblings = ft.wv.similar_by_word(tags, topn=30)
                for sibling in siblings:
                    tags_set.add(sibling[0])
            except Exception as e:
                logging.warning(
                    "In %s not found tag %s. %s", path, tags, e
                )

        if tags_set:
            db_tags = app.tags.get_by_tags(
                user["sid"], list(tags_set), user["settings"]["only_unread"]
            )
            for tag in db_tags:
                all_tags.append(
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
            code = 200
            result = {"data": all_tags}
        else:
            code = 200
            result = {"data": all_tags}
    else:
        code = 404
        result = {"error": "Unknown model"}

    return Response(json.dumps(result), mimetype="application/json", status=code)

def on_get_tag_siblings(app: "RSSTagApplication", user: dict, tags: str) -> Response:
    req_tags = tags.split()
    all_tags = []
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None
    posts = app.posts.get_by_tags(user["sid"], req_tags, only_unread, {"lemmas": True})
    tags_set = set()
    window = 5
    stopw = set(stopwords.words("english") + stopwords.words("russian"))
    req_tags_s = set(req_tags)
    for post in posts:
        txt = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
        words = txt.split()
        words_ln = len(words)
        for i, w in enumerate(words):
            if w not in req_tags_s:
                continue
            for j in range(1, window):
                pos = i - j
                if pos >= 0:
                    sw = words[pos]
                    if sw not in stopw:
                        tags_set.add(sw)
                pos = i + j
                if pos < words_ln:
                    sw = words[pos]
                    if sw not in stopw:
                        tags_set.add(sw)

    if tags_set:
        db_tags = app.tags.get_by_tags(
            user["sid"], list(tags_set), user["settings"]["only_unread"]
        )
        for tag in db_tags:
            all_tags.append(
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

    return Response(
        json.dumps({"data": all_tags}),
        mimetype="application/json",
    )


def on_get_tag_pmi(app: "RSSTagApplication", user: dict, tag: str) -> Response:
    if tag:
        req_tags = set(tag.split())
        cursor = app.posts.get_by_tags(
            user["sid"], list(req_tags), user["settings"]["only_unread"], {"lemmas": True}
        )
        stopw = set(stopwords.words("english") + stopwords.words("russian"))
        texts = [
            gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
            for post in cursor
        ]
        uniq_words = set()
        bigrams = Counter()
        bigrams_count = Counter()
        window = 5
        for text in texts:
            words_l = [
                word for word in text.split() if word not in stopw and word not in req_tags
            ]
            uniq_words.update(words_l)
            bi_grams = []
            for word_pos, word in enumerate(words_l):
                for i in range(window):
                    i += 1
                    bi_words = []
                    prev_pos = word_pos - i
                    if prev_pos >= 0:
                        bi_words.append(words_l[prev_pos])
                    next_pos = word_pos + i
                    if next_pos < len(words_l):
                        bi_words.append(words_l[next_pos])
                    for bi_word in bi_words:
                        if word == bi_word:
                            continue
                        bi_grams_l = [word, bi_word]
                        bi_grams_l.sort()
                        bi_gram = " ".join(bi_grams_l)
                        bi_grams.append(bi_gram)
            bigrams.update(bi_grams)
            bigrams_count.update(set(bi_grams))

        tags = app.tags.get_by_tags(
            user["sid"], list(uniq_words), user["settings"]["only_unread"]
        )
        tags_d = {}
        for tg in tags:
            tags_d[tg["tag"]] = tg

        pmis = []
        for bi, bi_freq in bigrams.items():
            if bi_freq < 2:
                continue
            bi_words = bi.split(" ")
            f1 = tags_d[bi_words[0]]["freq"]
            f2 = tags_d[bi_words[1]]["freq"]
            pmi = bi_freq / (abs(f1 - f2) + 1)
            pmis.append((bi, pmi))
        pmis.sort(key=lambda x: x[1], reverse=True)

        all_pmis = []
        for bi, temp in pmis[:4000]:
            bi_words = bi.split(" ")
            all_pmis.append(
                {
                    "tag": bi,
                    "url": "/entity/" + quote(tag + " " + bi),
                    "words": tags_d[bi_words[0]]["words"] + tags_d[bi_words[1]]["words"],
                    "count": bigrams_count[bi],
                    "sentiment": [],
                    "temp": temp,
                    "freq": bigrams[bi],
                }
            )
        all_pmis.sort(key=lambda x: x["count"], reverse=True)
        result = {"data": all_pmis}
        code = 200
    else:
        result = {"error": "Something wrong with request"}
        code = 400

    return Response(json.dumps(result), mimetype="application/json", status=code)


def on_tag_tfidf_get(app: "RSSTagApplication", user: dict, tag: str) -> Response:
    if tag:
        req_tags_s = set(tag.split())
        cursor = app.posts.get_by_tags(
            user["sid"], list(req_tags_s), user["settings"]["only_unread"], {"lemmas": True}
        )
        topics = set()
        stopw = set(stopwords.words("english") + stopwords.words("russian"))
        texts = [
            gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
            for post in cursor
        ]
        freq_d = Counter()
        for text in texts:
            words = [word for word in text.split() if word not in stopw]
            st = set(words)
            freq_d.update(st)
        for text in texts:
            words = [word for word in text.split() if word not in stopw]
            tfidf = []
            freq = Counter(words)
            for word in words:
                tf = freq[word] / len(words)
                idf = math.log(len(texts) / freq_d[word])
                tfidf.append((word, tf * idf))
            tfidf.sort(key=lambda x: x[1], reverse=True)
            topics.update([ti[0] for ti in tfidf[:5]])
        topics.update(req_tags_s)
        topics = list(topics)

        tags_c = app.tags.get_by_tags(
            user["sid"], topics, user["settings"]["only_unread"]
        )
        tags = list(tags_c)
        t_words = []
        for tg in tags:
            if tg["tag"] in req_tags_s:
                t_words += tg["words"]
                break
        all_tags = []
        for tg in tags:
            if tg["tag"] in req_tags_s:
                continue
            all_tags.append(
                {
                    "tag": tag + " " + tg["tag"],
                    "url": "/entity/" + quote(tag + " " + tg["tag"]),
                    "words": tg["words"] + t_words,
                    "count": freq_d[tg["tag"]],
                    "sentiment": tg["sentiment"] if "sentiment" in tg else [],
                    "temp": tg["temperature"],
                    "freq": tg["freq"],
                }
            )
            all_tags.sort(key=lambda t: t["count"] / t["freq"], reverse=True)
        result = {"data": all_tags}
        code = 200
    else:
        result = {"error": "Something wrong with request"}
        code = 400

    return Response(json.dumps(result), mimetype="application/json", status=code)


def on_tag_clusters_get(app: "RSSTagApplication", user: dict, tag: str) -> Response:
    if tag:
        cursor = app.posts.get_by_tags(
            user["sid"],
            tag.split(),
            user["settings"]["only_unread"],
            {"lemmas": True, "pid": True},
        )
        pids = []
        texts = []
        for post in cursor:
            texts.append(gzip.decompress(post["lemmas"]).decode("utf-8", "replace"))
            pids.append(post["pid"])
        stopw = set(stopwords.words("english") + stopwords.words("russian"))
        vectorizer = TfidfVectorizer(stop_words=stopw)
        vectorizer.fit(texts)
        vectors = vectorizer.transform(texts)
        dbs = DBSCAN(eps=0.7, min_samples=2, metric="cosine")
        cl = dbs.fit_predict(vectors)
        label_txt = {}
        for i, label in enumerate(cl):
            if label < 0:
                continue
            label = str(label)
            if label not in label_txt:
                label_txt[label] = []
            label_txt[label].append({"txt": texts[i], "pid": pids[i]})
        result = {"data": label_txt}
        code = 200
    else:
        result = {"error": "Something wrong with request"}
        code = 400

    return Response(json.dumps(result), mimetype="application/json", status=code)


def on_tag_entities_get(app: "RSSTagApplication", user: dict, tag: str) -> Response:
    if tag:
        cursor = app.posts.get_by_tags(
            user["sid"],
            tag.split(),
            user["settings"]["only_unread"],
            {"content": True, "tags": True, "bi_grams": True},
        )
        html_cleaner = HTMLCleaner()
        tags_builder = TagsBuilder()
        if app.navec is None:
            app.navec = Navec.load("./data/navec_news_v1_1B_250K_300d_100q.tar")
        if app.ner is None:
            app.ner = NER.load("./data/slovnet_ner_news_v1.tar")
            app.ner.navec(app.navec)
        ners = {}
        text_clearing = re.compile(r"[^\w\d ]")
        for post in cursor:
            html_cleaner.purge()
            txt = post["content"]["title"] + ". " + gzip.decompress(post["content"]["content"]).decode("utf-8", "replace")
            html_cleaner.feed(txt)
            txt = html.unescape(" ".join(html_cleaner.get_content()))
            markup = app.ner(txt)
            if len(markup.spans) == 0:
                continue
            for span in markup.spans:
                n = txt[span.start:span.stop].casefold()
                n = text_clearing.sub(" ", n).strip()
                if " " in n:
                    words = n.split(" ")
                    ns = map(lambda w: tags_builder.process_word(w), words)
                    n = " ".join(ns)
                else:
                    words = [n]
                    n = tags_builder.process_word(n)
                if n not in ners:
                    ners[n] = {
                        "tag": n,
                        "url": "/entity/" + quote(n),
                        "words": [],
                        "count": 0,
                        "sentiment": [],
                        "temp": 0,
                    }
                ners[n]["count"] += 1
                ners[n]["words"] = list(set(ners[n]["words"] + words))

        result = {"data": [ners[n] for n in ners]}
        code = 200
    else:
        result = {"error": "Something wrong with request"}
        code = 400

    return Response(json.dumps(result), mimetype="application/json", status=code)


def on_tag_topics_get(app: "RSSTagApplication", user: dict, tags: str) -> Response:
    if tags:
        req_tags = tags.split()
        cursor = app.posts.get_by_tags(
            user["sid"], req_tags, user["settings"]["only_unread"], {"lemmas": True}
        )
        texts = [
            gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
            for post in cursor
        ]
        lda = LDA()
        topics = lda.topics(texts, top_k=5)
        for tg in req_tags:
            if tg in topics:
                topics.remove(tg)
        tags = app.tags.get_by_tags(
            user["sid"], topics, user["settings"]["only_unread"]
        )
        all_tags = []
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
        result = {"data": all_tags}
        code = 200
    else:
        result = {"error": "Something wrong with request"}
        code = 400

    return Response(json.dumps(result), mimetype="application/json", status=code)


def on_tag_dates_get(app: "RSSTagApplication", user: dict, tag: str) -> Response:
    if tag:
        cursor = app.posts.get_by_tags(
            user["sid"], tag.split(), user["settings"]["only_unread"], {"unix_date": True}
        )
        data = []
        for dt in cursor:
            data.append(dt["unix_date"])
        result = {"data": data}
        code = 200
    else:
        result = {"error": "Something wrong with request"}
        code = 400

    return Response(json.dumps(result), mimetype="application/json", status=code)

def on_tag_specific_get(app: "RSSTagApplication", user: dict, tags: str) -> Response:
    if tags:
        tags = tags.casefold()
        req_tags_s = set(tags.split())
        cursor = app.posts.get_all(
            user["sid"], user["settings"]["only_unread"], projection={"lemmas": True}
        )
        tag_words = set()
        other_words = set()
        for post in cursor:
            txt = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
            words = set(txt.split(" "))
            diff_s = words.difference(req_tags_s)
            if len(diff_s) == len(req_tags_s):
                tag_words.update(words)
                continue
            other_words.update(words)
        spec = tag_words - other_words
        #spec.remove(tags)
        del tag_words
        del other_words
        cursor = app.tags.get_by_tags(user["sid"], list(spec), user["settings"]["only_unread"], projection={"_id": False})
        all_tags = []
        for tag in cursor:
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
        all_tags.sort(key=lambda x: x["count"], reverse=True)

        result = {"data": all_tags}
        code = 200
    else:
        result = {"error": "Something wrong with request"}
        code = 400

    return Response(json.dumps(result), mimetype="application/json", status=code)

def on_get_context_tags(
    app: "RSSTagApplication", user: dict, request: Request, tags: str
) -> Response:
    tags_l = tags.split()
    cursor = app.tags.get_by_tags(user["sid"], tags_l, projection={"_id": False})
    tag_data = None
    for t in cursor:
        if tag_data is None:
            tag_data = t
            continue
        tag_data["tag"] += " " + t["tag"]
        tag_data["words"] += t["words"]

    if not tag_data:
        return app.on_error(user, request, NotFound())

    cursor = app.posts.get_by_tags(user["sid"], tags_l, projection={"read": True})
    n_r = 0
    n_ur = 0
    for p in cursor:
        if p["read"]:
            n_r += 1
        else:
            n_ur += 1
    tag_data["unread_count"] = n_ur
    tag_data["posts_count"] = n_ur + n_r

    page = app.template_env.get_template("tag-info.html")

    if len(tags_l) > 1:
        posts_link = app.routes.get_url_by_endpoint(
            endpoint="on_entity_get", params={"quoted_tag": tag_data["tag"]}
        )
    else:
        posts_link = app.routes.get_url_by_endpoint(
            endpoint="on_tag_get", params={"quoted_tag": tag_data["tag"]}
        )

    return Response(
        page.render(
            tag=tag_data,
            posts_link=posts_link,
            sort_by_title="tags",
            sort_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_tags_get", params={"page_number": 1}
            ),
            group_by_link=app.routes.get_url_by_endpoint(
                endpoint="on_group_by_category_get"
            ),
            user_settings=user["settings"],
            provider=user["provider"],
        ),
        mimetype="text/html",
    )