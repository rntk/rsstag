import json
import gzip
import logging
from typing import TYPE_CHECKING
from collections import Counter
from urllib.parse import quote

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

from werkzeug.wrappers import Response

from sklearn.feature_extraction.text import TfidfVectorizer
from rsstag.stopwords import stopwords


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


def on_get_tag_bi_grams_graph_debug(
    app: "RSSTagApplication", user: dict, tag: str
) -> Response:
    """
    Debug endpoint to test basic connectivity
    """
    try:
        return Response(
            json.dumps(
                {"debug": "success", "tag": tag, "message": "Endpoint is working"}
            ),
            mimetype="application/json",
        )
    except Exception as e:
        return Response(
            json.dumps({"debug": "error", "error": str(e)}),
            mimetype="application/json",
            status=500,
        )


def on_get_tag_bi_grams_graph(
    app: "RSSTagApplication", user: dict, tag: str
) -> Response:
    """
    Get bi-grams graph data for visualization.
    Returns nodes (tags) and edges (bi-grams) for force-directed graph.
    """
    try:
        if not tag:
            return Response(
                json.dumps({"error": "Tag parameter is required"}),
                mimetype="application/json",
                status=400,
            )

        # Get the main tag data
        main_tag_data = app.tags.get_by_tag(user["sid"], tag)
        if not main_tag_data:
            return Response(
                json.dumps({"error": "Tag not found"}),
                mimetype="application/json",
                status=404,
            )

        # Get bi-grams containing the main tag
        try:
            # Always fetch all bi-grams regardless of read status for the graph
            # to ensure the visualization shows the full context
            bi_grams = app.bi_grams.get_by_tags(user["sid"], [tag], False)
            if bi_grams is None:
                bi_grams = []
        except Exception as e:
            logging.warning(f"Failed to get bi-grams for tag {tag}: {e}")
            bi_grams = []

        # Build nodes and edges
        nodes = {}
        edges = []

        # Add main tag as primary node
        main_tag_freq = main_tag_data.get("posts_count", 1)
        if main_tag_freq is None:
            main_tag_freq = 1

        nodes[tag] = {"id": tag, "frequency": main_tag_freq, "type": "main"}

        # Process bi-grams to build the graph
        for bi_gram in bi_grams:
            try:
                bi_gram_tag = bi_gram["tag"]
                bi_gram_freq = bi_gram.get("posts_count", 1)
                if bi_gram_freq is None:
                    bi_gram_freq = 1

                # Skip if frequency is too low
                if bi_gram_freq < 1:
                    continue

                # Split bi-gram into individual tags
                tags_in_bi_gram = bi_gram_tag.split()

                # Skip if not a valid bi-gram (should have exactly 2 tags)
                if len(tags_in_bi_gram) != 2:
                    continue

                # Find the other tag in the bi-gram (not the main tag)
                other_tags = [t for t in tags_in_bi_gram if t != tag]

                for other_tag in other_tags:
                    # Skip if the other tag is the same as the main tag
                    if other_tag == tag:
                        continue

                    # Add other tag as node if not already present
                    if other_tag not in nodes:
                        other_tag_freq = (
                            bi_gram_freq  # Use bi-gram frequency as default
                        )
                        try:
                            other_tag_data = app.tags.get_by_tag(user["sid"], other_tag)
                            if other_tag_data:
                                tag_posts_count = other_tag_data.get(
                                    "posts_count", None
                                )
                                if tag_posts_count is not None and tag_posts_count > 0:
                                    other_tag_freq = tag_posts_count
                        except Exception as e:
                            import logging

                            logging.warning(
                                f"Failed to get tag data for {other_tag}: {e}"
                            )
                            # Use bi-gram frequency as fallback

                        nodes[other_tag] = {
                            "id": other_tag,
                            "frequency": other_tag_freq,
                            "bigram_frequency": bi_gram_freq,  # Also include bi-gram frequency
                            "type": "related",
                        }

                    # Add edge between main tag and other tag
                    # Check for existing edge and combine weights if duplicate
                    existing_edge_index = None
                    for i, edge in enumerate(edges):
                        if (edge["source"] == tag and edge["target"] == other_tag) or (
                            edge["source"] == other_tag and edge["target"] == tag
                        ):
                            existing_edge_index = i
                            break

                    if existing_edge_index is not None:
                        # Combine weights for duplicate edges
                        edges[existing_edge_index]["weight"] += bi_gram_freq
                    else:
                        # Add new edge
                        edges.append(
                            {"source": tag, "target": other_tag, "weight": bi_gram_freq}
                        )
            except Exception:
                # Skip problematic bi-grams but continue processing
                continue

        # Convert nodes dict to list
        try:
            nodes_list = list(nodes.values())
            if nodes_list is None:
                nodes_list = []
        except Exception:
            nodes_list = []

        # Ensure we have at least the main node even if no bi-grams found
        if not nodes_list:
            nodes_list = [{"id": tag, "frequency": main_tag_freq, "type": "main"}]

        # Limit the graph size for performance (max 100 nodes, 200 edges)
        max_nodes = 100
        max_edges = 200

        # Sort nodes by frequency and keep top nodes
        if len(nodes_list) > max_nodes:
            # Separate main tag to ensure it's preserved
            main_node = next((n for n in nodes_list if n["id"] == tag), None)
            other_nodes = [n for n in nodes_list if n["id"] != tag]

            other_nodes.sort(key=lambda x: x["frequency"], reverse=True)
            # Keep top (max_nodes - 1) other nodes
            other_nodes = other_nodes[: max_nodes - 1]

            nodes_list = [main_node] + other_nodes if main_node else other_nodes

        # Filter edges to only include those between remaining nodes
        remaining_node_ids = {node["id"] for node in nodes_list}
        edges = [
            edge
            for edge in edges
            if edge["source"] in remaining_node_ids
            and edge["target"] in remaining_node_ids
        ]

        # Sort edges by weight and keep top edges
        if len(edges) > max_edges:
            edges.sort(key=lambda x: x["weight"], reverse=True)
            edges = edges[:max_edges]

        # Add some metadata about the graph
        original_nodes_count = len(nodes)
        original_edges_count = len(edges)

        result = {
            "data": {"nodes": nodes_list, "links": edges},
            "meta": {
                "main_tag": tag if tag else "unknown",
                "main_tag_frequency": max(0, main_tag_freq),
                "related_tags_count": max(0, len(nodes_list) - 1),
                "bi_grams_count": max(0, len(edges)),
                "has_bigrams": bool(len(edges) > 0),
                "truncated": bool(
                    len(nodes.values()) > max_nodes or len(edges) > max_edges
                ),
                "original_nodes_count": max(0, original_nodes_count),
                "original_edges_count": max(
                    0, original_edges_count if original_edges_count is not None else 0
                ),
            },
        }

        return Response(json.dumps(result), mimetype="application/json")

    except Exception as e:
        # Log the error for debugging
        import traceback
        import logging

        logging.error(f"Error in on_get_tag_bi_grams_graph: {e}")
        logging.error(traceback.format_exc())

        return Response(
            json.dumps({"error": f"Internal server error: {str(e)}"}),
            mimetype="application/json",
            status=500,
        )


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
    # stopw.update([wf[0] for wf in tfidfs[words_n * 2:]])
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
                    pair_list = [w, words[pos]]
                    pair_list.sort()
                    bgrms.append(" ".join(pair_list))
                pos = i + j
                if pos < lnw and words[pos] not in stopw:
                    pair_list = [w, words[pos]]
                    pair_list.sort()
                    bgrms.append(" ".join(pair_list))
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
