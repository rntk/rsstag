import gzip
import json
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np
from sklearn.cluster import AgglomerativeClustering, DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_distances
from sklearn.neighbors import NearestNeighbors

from rsstag.stopwords import stopwords
from werkzeug.wrappers import Request, Response

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication


def on_clusters_get(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    projection = {"_id": True, "clusters": True, "tags": True, "lemmas": True}
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None
    db_posts = app.posts.get_all(user["sid"], only_unread, projection)

    links = {}
    for post in db_posts:
        if "clusters" not in post:
            continue

        text = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
        if not text.strip():
            continue
        for cl in post["clusters"]:
            if cl not in links:
                links[cl] = {
                    "l": app.routes.get_url_by_endpoint(
                        endpoint="on_cluster_get", params={"cluster": cl}
                    ),
                    "n": 0,
                    "texts": [],
                    "tags": [],
                }
            links[cl]["n"] += 1
            links[cl]["texts"].append(text)
            links[cl]["tags"].extend(post.get("tags", []))

    # Compute centroid and top words for each cluster
    stopw = set(stopwords.words("english") + stopwords.words("russian"))
    for cl in links:
        texts = links[cl]["texts"]
        if texts:
            try:
                vectorizer = TfidfVectorizer(stop_words=list(stopw))
                vectors = vectorizer.fit_transform(texts)
                if vectors.shape[1] == 0:
                    raise ValueError("empty vocabulary")
                centroid = vectors.mean(axis=0).A1
                feature_names = vectorizer.get_feature_names_out()
                top_indices = centroid.argsort()[-3:][::-1]
                top_words = [feature_names[i] for i in top_indices]
                links[cl]["top_tags"] = ", ".join(top_words)
            except ValueError:
                # Fall back to tag frequency
                tags = links[cl]["tags"]
                if tags:
                    from collections import Counter

                    counter = Counter(tags)
                    top_tags = [tag for tag, _ in counter.most_common(3)]
                    links[cl]["top_tags"] = ", ".join(top_tags)
                else:
                    links[cl]["top_tags"] = f"Cluster {cl}"
        else:
            links[cl]["top_tags"] = f"Cluster {cl}"

    lnks = [(links[cl]["top_tags"], links[cl]["l"], links[cl]["n"]) for cl in links]
    lnks.sort(key=lambda x: x[2], reverse=True)
    page = app.template_env.get_template("clusters.html")

    return Response(
        page.render(
            links=lnks, user_settings=user["settings"], provider=user.get("provider", "")
        ),
        mimetype="text/html",
    )


def on_clusters_dyn_get(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    projection = {"_id": False, "lemmas": True, "pid": True, "tags": True}
    if user["settings"]["only_unread"]:
        only_unread = user["settings"]["only_unread"]
    else:
        only_unread = None
    db_posts = app.posts.get_all(user["sid"], only_unread, projection)

    texts = []
    pids = []
    post_tags = []
    for post in db_posts:
        text = gzip.decompress(post["lemmas"]).decode("utf-8", "replace")
        if not text.strip():
            continue
        texts.append(text)
        pids.append(post["pid"])
        post_tags.append(post.get("tags", []))

    stopw = set(stopwords.words("english") + stopwords.words("russian"))
    vectorizer = TfidfVectorizer(stop_words=list(stopw))
    vectorizer.fit(texts)
    vectors = vectorizer.transform(texts)
    dbs = DBSCAN(eps=0.7, min_samples=2, metric="cosine")
    cl = dbs.fit_predict(vectors)
    label_pids = defaultdict(list)
    label_texts = defaultdict(list)
    label_tags = defaultdict(list)
    for i, label in enumerate(cl):
        if label < 0:
            continue
        label_pids[label].append(str(pids[i]))
        label_texts[label].append(texts[i])
        label_tags[label].extend(post_tags[i])

    links = {}
    for label, pids_list in label_pids.items():
        links[label] = {
            "l": app.routes.get_url_by_endpoint(
                endpoint="on_posts_get", params={"pids": "_".join(pids_list)}
            ),
            "n": len(pids_list),
            "texts": label_texts[label],
            "tags": label_tags[label],
        }

    # Compute centroid and top words for each cluster
    for label in links:
        texts_for_cluster = links[label]["texts"]
        if texts_for_cluster:
            try:
                cluster_vectorizer = TfidfVectorizer(stop_words=list(stopw))
                cluster_vectors = cluster_vectorizer.fit_transform(
                    texts_for_cluster
                )
                if cluster_vectors.shape[1] == 0:
                    raise ValueError("empty vocabulary")
                centroid = cluster_vectors.mean(axis=0).A1
                feature_names = cluster_vectorizer.get_feature_names_out()
                top_indices = centroid.argsort()[-3:][::-1]
                top_words = [feature_names[i] for i in top_indices]
                links[label]["top_tags"] = ", ".join(top_words)
            except ValueError:
                # Fall back to tag frequency
                tags = links[label]["tags"]
                if tags:
                    from collections import Counter

                    counter = Counter(tags)
                    top_tags = [tag for tag, _ in counter.most_common(3)]
                    links[label]["top_tags"] = ", ".join(top_tags)
                else:
                    links[label]["top_tags"] = f"Cluster {label}"
        else:
            links[label]["top_tags"] = f"Cluster {label}"

    lnks = [(links[cl]["top_tags"], links[cl]["l"], links[cl]["n"]) for cl in links]
    lnks.sort(key=lambda x: x[2], reverse=True)
    page = app.template_env.get_template("clusters.html")

    return Response(
        page.render(
            links=lnks, user_settings=user["settings"], provider=user.get("provider", "")
        ),
        mimetype="text/html",
    )


def on_clusters_topics_dyn_get(app: "RSSTagApplication", user: dict, request: Request) -> Response:
    grouped_posts: List[Dict[str, Any]] = list(
        app.db.post_grouping.find(
            {"owner": user["sid"]},
            {"_id": 0, "post_ids": 1, "sentences": 1, "groups": 1},
        )
    )

    post_ids: set[Any] = set()
    for post_data in grouped_posts:
        post_ids.update(post_data.get("post_ids", []))

    posts_data: Dict[Any, Dict[str, Any]] = {}
    if post_ids:
        posts_projection: Dict[str, int] = {
            "_id": 0,
            "pid": 1,
            "id": 1,
            "content": 1,
            "read": 1,
        }
        posts_list: List[Dict[str, Any]] = list(
            app.db.posts.find(
                {
                    "owner": user["sid"],
                    "$or": [
                        {"pid": {"$in": list(post_ids)}},
                        {"id": {"$in": list(post_ids)}},
                    ],
                },
                posts_projection,
            )
        )
        for post in posts_list:
            pid_value = post.get("pid")
            if pid_value is not None:
                posts_data[pid_value] = post
            post_id_value = post.get("id")
            if post_id_value is not None:
                posts_data[post_id_value] = post

    plain_text_cache: Dict[Any, str] = {}

    def _get_plain_text(post_id: Any) -> str:
        if post_id in plain_text_cache:
            return plain_text_cache[post_id]
        post_obj: Optional[Dict[str, Any]] = posts_data.get(post_id)
        if not post_obj or not post_obj.get("content"):
            plain_text_cache[post_id] = ""
            return ""
        raw_content: str = gzip.decompress(post_obj["content"]["content"]).decode(
            "utf-8", "replace"
        )
        title: str = post_obj["content"].get("title", "")
        if title:
            raw_content = f"{title}. {raw_content}"
        from rsstag.html_utils import build_html_mapping

        plain_text, _ = build_html_mapping(raw_content)
        plain_text_cache[post_id] = plain_text
        return plain_text

    ranges: List[List[Dict[str, Any]]] = []
    texts: List[str] = []
    for post_data in grouped_posts:
        post_ids_list: List[int] = post_data.get("post_ids", [])
        if not post_ids_list:
            continue
        post_id: Any = post_ids_list[0]
        plain_text: str = _get_plain_text(post_id)
        if not plain_text:
            continue

        sent_map = {s.get("number"): s for s in post_data.get("sentences", [])}
        groups = post_data.get("groups", {})

        if not groups:
            continue

        for topic_title, sentence_nums in groups.items():
            topic_sentences = []
            topic_text_parts = []
            for num in sentence_nums:
                sentence = sent_map.get(num)
                if not sentence:
                    continue
                start = sentence.get("start")
                end = sentence.get("end")
                if (
                    start is None
                    or end is None
                    or not isinstance(start, int)
                    or not isinstance(end, int)
                ):
                    continue
                if start < 0 or end > len(plain_text) or start >= end:
                    continue
                text_part = plain_text[start:end].strip()
                if not text_part:
                    continue
                topic_text_parts.append(text_part)
                topic_sentences.append(
                    {
                        "post_id": post_id,
                        "start": start,
                        "end": end,
                        "number": num,
                        "topic_title": topic_title,
                        "read": bool(sentence.get("read", False)),
                    }
                )

            if topic_text_parts:
                texts.append(" ".join(topic_text_parts))
                ranges.append(topic_sentences)

    clusters: List[Dict[str, Any]] = []
    clusters_data: Dict[str, Dict[str, Any]] = {}

    if texts:
        stopw = set(stopwords.words("english") + stopwords.words("russian"))
        try:
            vectorizer = TfidfVectorizer(stop_words=list(stopw))
            vectors = vectorizer.fit_transform(texts)
            if vectors.shape[1] == 0:
                raise ValueError("empty vocabulary")

            # Adaptive epsilon calculation for better clustering
            eps = 0.7  # default
            if vectors.shape[0] > 10:
                try:
                    neighbors = NearestNeighbors(
                        n_neighbors=min(5, vectors.shape[0] // 2), metric="cosine"
                    )
                    neighbors_fit = neighbors.fit(vectors)
                    distances, _ = neighbors_fit.kneighbors(vectors)
                    distances = np.sort(distances[:, -1], axis=0)
                    # Use 75th percentile as eps
                    eps = float(np.percentile(distances, 75))
                    eps = max(0.3, min(0.8, eps))  # Clamp between 0.3-0.8
                except Exception:
                    eps = 0.7

            dbs = DBSCAN(eps=eps, min_samples=2, metric="cosine")
            labels: List[int] = dbs.fit_predict(vectors).tolist()

            # Calculate quality metrics
            unique_labels = set(labels)
            if len(unique_labels) > 1 and -1 in unique_labels:
                # Only positive labels for silhouette score
                valid_mask = np.array(labels) >= 0
                if (
                    np.sum(valid_mask) > 1
                    and len(set(np.array(labels)[valid_mask])) > 1
                ):
                    try:
                        score = silhouette_score(
                            vectors[valid_mask],
                            np.array(labels)[valid_mask],
                            metric="cosine",
                        )
                        total_topics = len(texts)
                        clustered_topics = sum(1 for l in labels if l >= 0)
                        coverage = (
                            clustered_topics / total_topics
                            if total_topics > 0
                            else 0
                        )
                        logging.info(
                            f"Clustering quality: silhouette={score:.3f}, coverage={coverage:.1%}, eps={eps:.3f}"
                        )
                    except Exception as e:
                        logging.warning(f"Could not calculate quality metrics: {e}")
        except ValueError:
            labels = []

        label_ranges: Dict[int, List[List[Dict[str, Any]]]] = defaultdict(list)
        label_texts: Dict[int, List[str]] = defaultdict(list)
        for idx, label in enumerate(labels):
            if label < 0:
                continue
            label_ranges[label].append(ranges[idx])
            label_texts[label].append(texts[idx])

        for label, topic_lists in label_ranges.items():
            all_ranges = []
            all_titles = []
            for topic_sentences in topic_lists:
                # Keep ranges intact, don't flatten
                if topic_sentences:
                    title = topic_sentences[0].get("topic_title", "")
                    if title:
                        all_titles.append(title)
                    # Store each range with its metadata
                    all_ranges.append(
                        {
                            "topic_title": title,
                            "sentences": topic_sentences,
                        }
                    )

            # Find most representative title from original section titles
            top_tags: str = f"Cluster {label}"
            texts_for_cluster: List[str] = label_texts.get(label, [])

            if all_titles and texts_for_cluster:
                try:
                    cluster_vectorizer = TfidfVectorizer(stop_words=list(stopw))
                    cluster_vectors = cluster_vectorizer.fit_transform(
                        texts_for_cluster
                    )
                    if cluster_vectors.shape[1] > 0:
                        centroid = cluster_vectors.mean(axis=0)

                        # Find which original title is closest to centroid
                        title_vectors = cluster_vectorizer.transform(all_titles)
                        distances = cosine_distances(title_vectors, centroid)
                        best_idx = int(np.argmin(distances))
                        top_tags = all_titles[best_idx]
                except (ValueError, Exception):
                    # Fallback to first title if vectorization fails
                    top_tags = all_titles[0] if all_titles else f"Cluster {label}"

            cluster_entry: Dict[str, Any] = {
                "id": label,
                "title": top_tags,
                "count": len(topic_lists),
                "ranges": all_ranges,
            }
            clusters.append(cluster_entry)
            clusters_data[str(label)] = {
                "title": top_tags,
                "count": len(topic_lists),
                "ranges": all_ranges,
            }

        # Filter out clusters with too few items (minimum cluster size)
        MIN_CLUSTER_SIZE = 3
        clusters = [c for c in clusters if c["count"] >= MIN_CLUSTER_SIZE]
        clusters_data = {
            str(c["id"]): clusters_data[str(c["id"])] for c in clusters
        }

        # Add hierarchical super-clusters if we have many clusters
        if len(clusters) > 12:
            try:
                cluster_texts = []
                for c in clusters:
                    cluster_id = c["id"]
                    texts_in_cluster = label_texts.get(cluster_id, [])
                    combined = (
                        c["title"] + " " + " ".join(texts_in_cluster[:5])
                    )  # Limit to first 5
                    cluster_texts.append(combined)

                super_vectorizer = TfidfVectorizer(stop_words=list(stopw))
                super_vectors = super_vectorizer.fit_transform(cluster_texts)

                # Create 3-8 super-clusters
                n_super = max(3, min(8, len(clusters) // 3))
                super_clustering = AgglomerativeClustering(
                    n_clusters=n_super, metric="cosine", linkage="average"
                )
                super_labels = super_clustering.fit_predict(super_vectors.toarray())

                # Add super_cluster_id to each cluster
                for idx, cluster in enumerate(clusters):
                    cluster["super_cluster_id"] = int(super_labels[idx])
                    clusters_data[str(cluster["id"])]["super_cluster_id"] = int(
                        super_labels[idx]
                    )

                logging.info(
                    f"Created {n_super} super-clusters from {len(clusters)} clusters"
                )
            except Exception as e:
                logging.warning(f"Could not create super-clusters: {e}")

    clusters.sort(key=lambda item: item["count"], reverse=True)
    page = app.template_env.get_template("clusters-topics-dyn.html")
    return Response(
        page.render(
            clusters=clusters,
            clusters_data=clusters_data,
            user_settings=user["settings"],
            provider=user.get("provider", ""),
        ),
        mimetype="text/html",
    )


def on_clusters_topics_dyn_sentences_post(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    data: Optional[Dict[str, Any]] = request.get_json(silent=True)
    if not data or "ranges" not in data:
        return Response(
            json.dumps({"error": "Bad data"}),
            mimetype="application/json",
            status=400,
        )

    ranges_data: Any = data.get("ranges", [])
    if not isinstance(ranges_data, list):
        return Response(
            json.dumps({"error": "Bad data"}),
            mimetype="application/json",
            status=400,
        )

    # Collect all unique post IDs from all ranges
    post_ids: set[Any] = set()
    for range_item in ranges_data:
        if not isinstance(range_item, dict):
            continue
        sentences = range_item.get("sentences", [])
        for sentence in sentences:
            if isinstance(sentence, dict):
                post_id_val = sentence.get("post_id")
                if post_id_val is not None:
                    post_ids.add(post_id_val)

    posts_data: Dict[Any, Dict[str, Any]] = {}
    if post_ids:
        posts_projection: Dict[str, int] = {
            "_id": 0,
            "pid": 1,
            "id": 1,
            "content": 1,
        }
        posts_list: List[Dict[str, Any]] = list(
            app.db.posts.find(
                {
                    "owner": user["sid"],
                    "$or": [
                        {"pid": {"$in": list(post_ids)}},
                        {"id": {"$in": list(post_ids)}},
                    ],
                },
                posts_projection,
            )
        )
        for post in posts_list:
            pid_value = post.get("pid")
            if pid_value is not None:
                posts_data[pid_value] = post
            post_id_value = post.get("id")
            if post_id_value is not None:
                posts_data[post_id_value] = post

    plain_text_cache: Dict[Any, str] = {}

    def _get_plain_text(post_id: Any) -> str:
        if post_id in plain_text_cache:
            return plain_text_cache[post_id]
        post_obj: Optional[Dict[str, Any]] = posts_data.get(post_id)
        if not post_obj or not post_obj.get("content"):
            plain_text_cache[post_id] = ""
            return ""
        raw_content: str = gzip.decompress(post_obj["content"]["content"]).decode(
            "utf-8", "replace"
        )
        title: str = post_obj["content"].get("title", "")
        if title:
            raw_content = f"{title}. {raw_content}"
        from rsstag.html_utils import build_html_mapping

        plain_text, _ = build_html_mapping(raw_content)
        plain_text_cache[post_id] = plain_text
        return plain_text

    result_ranges: List[Dict[str, Any]] = []

    for range_item in ranges_data:
        if not isinstance(range_item, dict):
            continue

        topic_title = range_item.get("topic_title", "")
        sentences = range_item.get("sentences", [])

        if not sentences:
            continue

        # Process all sentences in this range
        range_texts: List[str] = []
        sentence_indices: List[int] = []
        sentence_reads: List[bool] = []
        first_post_id = None
        range_start = None
        range_end = None

        for sentence in sentences:
            if not isinstance(sentence, dict):
                continue

            post_id_val = sentence.get("post_id")
            if post_id_val is None:
                continue

            try:
                start_val: int = int(sentence.get("start"))
                end_val: int = int(sentence.get("end"))
                number_val: int = int(sentence.get("number"))
            except (TypeError, ValueError):
                continue

            plain_text = _get_plain_text(post_id_val)
            if not plain_text:
                continue

            if start_val < 0 or end_val > len(plain_text) or start_val >= end_val:
                continue

            text = plain_text[start_val:end_val].strip()
            if not text:
                continue

            range_texts.append(text)
            sentence_indices.append(number_val)
            sentence_reads.append(bool(sentence.get("read", False)))

            # Track the post_id and boundaries for the range
            if first_post_id is None:
                first_post_id = post_id_val
                range_start = start_val
            range_end = end_val

        # Combine all sentence texts into one range text
        if range_texts and first_post_id is not None:
            read_status: bool = bool(sentence_reads) and all(sentence_reads)
            result_ranges.append(
                {
                    "topic_title": topic_title,
                    "text": " ".join(range_texts),
                    "post_id": first_post_id,
                    "start": range_start,
                    "end": range_end,
                    "sentence_indices": sentence_indices,
                    "read": read_status,
                }
            )

    return Response(
        json.dumps({"ranges": result_ranges}),
        mimetype="application/json",
        status=200,
    )
