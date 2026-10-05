"""Tag-related worker operations."""

import gzip
import logging
import os.path
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from pymongo import UpdateOne
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer

from rsstag.entity_extractor import RssTagEntityExtractor
from rsstag.html_cleaner import HTMLCleaner
from rsstag.letters import RssTagLetters
from rsstag.posts import PostLemmaSentence, RssTagPosts
from rsstag.post_grouping import RssTagPostGrouping
from rsstag.sentiment import RuSentiLex, SentimentConverter, WordNetAffectRuRom
from rsstag.snippet_clusters import RssTagSnippetClusters
from rsstag.snippets import merge_grouped_snippets
from rsstag import tag_rank_cooc, tag_rank_corpus, tag_rank_embed, tag_rank_llm
from rsstag.tag_rank import compute_base_rank, legacy_temperature, recompute_derived
from rsstag.tags import RssTagTags
from rsstag.tags_builder import TagsBuilder
from rsstag.users import RssTagUsers
from rsstag.w2v import W2VLearn
from rsstag.fasttext import FastTextLearn
from rsstag.web.routes import RSSTagRoutes
from rsstag.tasks import TAG_NOT_IN_PROCESSING
from rsstag.workers.base import BaseWorker


def _tag_occurs_in_topic(tag: str, topic: str) -> bool:
    """Match a tag as a complete word or phrase inside a topic path."""
    tag_value: str = tag.strip()
    topic_value: str = topic.strip()
    if not tag_value or not topic_value:
        return False
    pattern: str = rf"(?<!\w){re.escape(tag_value)}(?!\w)"
    return re.search(pattern, topic_value, flags=re.IGNORECASE) is not None


class TagWorker(BaseWorker):
    def __init__(self, db, config):
        super().__init__(db, config)
        self._builder = TagsBuilder()
        self._cleaner = HTMLCleaner()

    def handle_tags(self, task: dict) -> bool:
        if task["data"]:
            return self.make_tags(task["data"])
        logging.warning("Error while make tags: %s", task)
        return True

    def handle_letters(self, task: dict) -> bool:
        return self.make_letters(task["user"]["sid"])

    def handle_ner(self, task: dict) -> bool:
        return self.make_ner(task["data"])

    def handle_tags_sentiment(self, task: dict) -> bool:
        return self.make_tags_sentiment(task["user"]["sid"])

    def handle_clustering(self, task: dict) -> Optional[bool]:
        return self.make_clustering(task["user"]["sid"])

    def handle_snippet_clustering(self, task: dict) -> Optional[bool]:
        return self.make_snippet_clustering(task["user"]["sid"])

    def handle_w2v(self, task: dict) -> Optional[bool]:
        return self.make_w2v(task["user"]["sid"])

    def handle_fasttext(self, task: dict) -> Optional[bool]:
        return self.make_fasttext(task["user"]["sid"])

    def handle_tags_groups(self, task: dict) -> Optional[bool]:
        return self.make_tags_groups(task["user"]["sid"])

    def handle_tags_topics(self, task: dict[str, Any]) -> bool:
        return self.make_tags_topics(task["user"]["sid"])

    def handle_tags_corpus_rank(self, task: dict[str, Any]) -> bool:
        return tag_rank_corpus.run(self._db, self._config, task["user"]["sid"])

    def handle_tags_cooc_rank(self, task: dict[str, Any]) -> bool:
        return tag_rank_cooc.run(self._db, self._config, task["user"]["sid"])

    def handle_tags_embed_rank(self, task: dict[str, Any]) -> bool:
        return tag_rank_embed.run(self._db, self._config, task["user"]["sid"])

    def handle_tags_llm_rank(self, task: dict[str, Any]) -> bool:
        return tag_rank_llm.run(self._db, self._config, task["user"]["sid"])

    def clear_user_data(self, user: dict) -> bool:
        try:
            self._db.posts.delete_many({"owner": user["sid"]})
            self._db.feeds.delete_many({"owner": user["sid"]})
            self._db.tags.delete_many({"owner": user["sid"]})
            self._db.letters.delete_many({"owner": user["sid"]})
            result = True
        except Exception as e:
            logging.error("Can`t clear user data %s. Info: %s", user["sid"], e)
            result = False

        return result

    def clear_user_processed_data(self, user: dict) -> bool:
        try:
            self._db.tags.delete_many({"owner": user["sid"]})
            self._db.letters.delete_many({"owner": user["sid"]})
            result = True
        except Exception as e:
            logging.error("Can`t clear user processed data %s. Info: %s", user["sid"], e)
            result = False

        return result

    def make_tags(
        self,
        posts: List[dict],
    ) -> bool:
        if not posts:
            return False
        posts_updates: list[UpdateOne] = []
        tags_updates: list[UpdateOne] = []
        sum_tags: dict[str, dict[str, Any]] = {}
        routes: RSSTagRoutes = RSSTagRoutes(self._config["settings"]["host_name"])
        owner: str = posts[0]["owner"]
        for post in posts:
            content: bytes = gzip.decompress(post["content"]["content"])
            text: str = post["content"]["title"] + " " + content.decode("utf-8")
            self._cleaner.purge()
            self._cleaner.feed(text)
            strings: list[str] = self._cleaner.get_content()
            text = " ".join(strings)
            self._builder.purge()
            self._builder.build_tags(text)
            tags: dict[str, int] = self._builder.get_tags()
            tag_words: dict[str, set[str]] = self._builder.get_words()
            post_tags: dict[str, Any] = {
                "lemmas": gzip.compress(
                    self._builder.get_prepared_text().encode("utf-8", "replace")
                ),
                "tags": [""],
            }
            if tags:
                post_tags["tags"] = [tag for tag in tags]
            posts_updates.append(UpdateOne({"_id": post["_id"]}, {"$set": post_tags}))
            for tag, freq in tags.items():
                if tag not in sum_tags:
                    sum_tags[tag] = {"posts": 0, "freq": 0, "words": set()}
                sum_tags[tag]["posts"] += 1
                sum_tags[tag]["freq"] += freq
                sum_tags[tag]["words"].update(tag_words[tag])
        for tag, tag_d in sum_tags.items():
            tags_updates.append(
                UpdateOne(
                    {"owner": owner, "tag": tag},
                    {
                        "$set": {
                            "read": False,
                            "tag": tag,
                            "owner": owner,
                            "temperature": 0,
                            "local_url": routes.get_url_by_endpoint(
                                endpoint="on_tag_get", params={"quoted_tag": tag}
                            ),
                            "processing": TAG_NOT_IN_PROCESSING,
                        },
                        "$inc": {
                            "posts_count": tag_d["posts"],
                            "unread_count": tag_d["posts"],
                            "freq": tag_d["freq"],
                        },
                        "$addToSet": {"words": {"$each": list(tag_d["words"])}},
                    },
                    upsert=True,
                )
            )
        try:
            if posts_updates:
                self._db.posts.bulk_write(posts_updates, ordered=False)
            if tags_updates:
                self._db.tags.bulk_write(tags_updates, ordered=False)
            result = True
        except Exception as e:
            result = False
            logging.error("Can`t save tags for posts. Info: %s", e)

        return result

    def make_letters(self, owner: str) -> bool:
        router = RSSTagRoutes(self._config["settings"]["host_name"])
        letters = RssTagLetters(self._db)
        tags = RssTagTags(self._db)
        all_tags = tags.get_all(owner, projection={"tag": True, "unread_count": True})
        letters.sync_with_tags(owner, list(all_tags), router)

        return True

    def make_ner(self, all_posts: List[dict]) -> Optional[bool]:
        if not all_posts:
            return True
        owner = all_posts[0]["owner"]
        count_ent = defaultdict(int)
        ent_ex = RssTagEntityExtractor()
        for post in all_posts:
            text = (
                post["content"]["title"]
                + " "
                + gzip.decompress(post["content"]["content"]).decode("utf-8", "ignore")
            )
            if not text.strip():
                continue
            entities = ent_ex.extract_entities(text)
            for entity in entities:
                cl_entity = ent_ex.clean_entity(entity)
                if not cl_entity:
                    continue
                for word in entity:
                    tag: str = self._builder.process_word(word) if len(word) > 1 else ""
                    if tag:
                        count_ent[tag] += 1

        if not count_ent:
            return True

        logging.info("Found %s entity tags for user %s", len(count_ent), owner)
        tags = RssTagTags(self._db)
        result = tags.mark_entities(owner, dict(count_ent))
        if result:
            recompute_derived(self._db, owner, list(count_ent))

        return result

    def make_clustering(self, owner: str) -> Optional[bool]:
        posts = RssTagPosts(self._db)
        all_posts = posts.get_all(owner, projection={"lemmas": True, "pid": True})
        clusters = None
        texts_for_vec = []
        post_pids = []
        for post in all_posts:
            post_pids.append(post["pid"])
            text = gzip.decompress(post["lemmas"]).decode("utf-8", "ignore")
            texts_for_vec.append(text)

        if texts_for_vec:
            vectorizer = TfidfVectorizer(stop_words=list(self._stopw))
            dbs = DBSCAN(eps=0.9, min_samples=2, n_jobs=1)
            dbs.fit(vectorizer.fit_transform(texts_for_vec))
            clusters = defaultdict(set)
            for i, cluster in enumerate(dbs.labels_):
                clusters[int(cluster)].add(post_pids[i])

            if clusters and -1 in clusters:
                del clusters[-1]

        if clusters:
            logging.info(
                "Posts: %s. Clusters: %s. User: %s",
                len(post_pids),
                len(clusters),
                owner,
            )

            return posts.set_clusters(owner, clusters)

        return True

    def _build_snippet_cluster_title(self, snippets: List[Dict[str, Any]]) -> str:
        """Build a short human-readable title for a snippet cluster."""
        texts: List[str] = [str(snippet.get("text", "")).strip() for snippet in snippets]
        texts = [text for text in texts if text]
        if texts:
            try:
                vectorizer = TfidfVectorizer(stop_words=list(self._stopw))
                vectors = vectorizer.fit_transform(texts)
                if vectors.shape[1] > 0:
                    centroid = vectors.mean(axis=0).A1
                    feature_names = vectorizer.get_feature_names_out()
                    top_indices = centroid.argsort()[-3:][::-1]
                    top_words = [feature_names[index] for index in top_indices]
                    title = ", ".join(word for word in top_words if word)
                    if title:
                        return title
            except ValueError:
                pass

        topic_counter: Counter[str] = Counter(
            str(snippet.get("topic", "")).strip()
            for snippet in snippets
            if str(snippet.get("topic", "")).strip()
        )
        if topic_counter:
            return ", ".join(topic for topic, _count in topic_counter.most_common(2))
        return "Snippet Cluster"

    def make_snippet_clustering(self, owner: str) -> Optional[bool]:
        """Cluster merged snippet ranges produced by post grouping."""
        post_grouping = RssTagPostGrouping(self._db)
        snippet_clusters = RssTagSnippetClusters(self._db)
        grouped_posts: List[Dict[str, Any]] = list(
            post_grouping.get_all_by_owner(
                owner,
                projection={"post_ids": 1, "sentences": 1, "groups": 1},
            )
        )
        if not grouped_posts:
            return snippet_clusters.replace_clusters(owner, [])

        post_ids: List[str] = sorted(
            {
                str(post_id)
                for grouped_post in grouped_posts
                for post_id in grouped_post.get("post_ids", [])
                if post_id
            }
        )
        posts_map: Dict[str, Dict[str, Any]] = {
            str(post.get("pid")): post
            for post in self._db.posts.find(
                {"owner": owner, "pid": {"$in": post_ids}},
                projection={"pid": 1, "content": 1, "feed_id": 1, "url": 1},
            )
        }
        feed_ids: List[str] = sorted(
            {
                str(post.get("feed_id"))
                for post in posts_map.values()
                if post.get("feed_id") is not None
            }
        )
        feeds_map: Dict[str, Dict[str, Any]] = {
            str(feed.get("feed_id")): feed
            for feed in self._db.feeds.find(
                {"owner": owner, "feed_id": {"$in": feed_ids}},
                projection={"feed_id": 1, "title": 1},
            )
        }

        snippets: List[Dict[str, Any]] = []
        for grouped_post in grouped_posts:
            doc_post_ids: List[str] = [
                str(post_id) for post_id in grouped_post.get("post_ids", []) if post_id
            ]
            if len(doc_post_ids) != 1:
                continue

            post_id: str = doc_post_ids[0]
            post: Optional[Dict[str, Any]] = posts_map.get(post_id)
            if not post:
                continue

            raw_content_bytes: Any = post.get("content", {}).get("content", b"")
            try:
                raw_content: str = gzip.decompress(raw_content_bytes).decode(
                    "utf-8", "replace"
                )
            except Exception:
                continue

            title: str = str(post.get("content", {}).get("title", ""))
            if title:
                raw_content = f"{title}. {raw_content}"

            feed_id: str = str(post.get("feed_id", ""))
            topic_snippets: Dict[str, List[Dict[str, Any]]] = merge_grouped_snippets(
                raw_content,
                list(grouped_post.get("sentences", [])),
                dict(grouped_post.get("groups", {})),
                {
                    "post_id": post_id,
                    "post_title": title or f"Post {post_id}",
                    "url": post.get("url"),
                    "feed_id": feed_id,
                    "feed_title": feeds_map.get(feed_id, {}).get(
                        "title", f"Post {post_id}"
                    ),
                },
            )
            for topic_items in topic_snippets.values():
                snippets.extend(topic_items)

        clusterable_snippets: List[Dict[str, Any]] = [
            snippet for snippet in snippets if str(snippet.get("text", "")).strip()
        ]
        if len(clusterable_snippets) < 2:
            return snippet_clusters.replace_clusters(owner, [])

        try:
            vectorizer = TfidfVectorizer(stop_words=list(self._stopw))
            vectors = vectorizer.fit_transform(
                [str(snippet["text"]) for snippet in clusterable_snippets]
            )
            if vectors.shape[1] == 0:
                return snippet_clusters.replace_clusters(owner, [])
            labels = DBSCAN(eps=0.7, min_samples=2, metric="cosine").fit_predict(vectors)
        except ValueError:
            return snippet_clusters.replace_clusters(owner, [])

        grouped_clusters: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for label, snippet in zip(labels, clusterable_snippets):
            cluster_id: int = int(label)
            if cluster_id < 0:
                continue
            grouped_clusters[cluster_id].append(snippet)

        payload: List[Dict[str, Any]] = []
        for cluster_id in sorted(grouped_clusters):
            cluster_snippets: List[Dict[str, Any]] = grouped_clusters[cluster_id]
            payload.append(
                {
                    "cluster_id": cluster_id,
                    "title": self._build_snippet_cluster_title(cluster_snippets),
                    "item_count": len(cluster_snippets),
                    "post_ids": sorted(
                        {str(snippet["post_id"]) for snippet in cluster_snippets}
                    ),
                    "snippet_refs": [
                        {
                            "post_id": str(snippet["post_id"]),
                            "topic": str(snippet.get("topic", "")),
                            "indices": [int(index) for index in snippet.get("indices", [])],
                        }
                        for snippet in cluster_snippets
                    ],
                }
            )

        logging.info(
            "Snippet clusters for user %s: snippets=%s clusters=%s",
            owner,
            len(clusterable_snippets),
            len(payload),
        )
        return snippet_clusters.replace_clusters(owner, payload)

    def make_w2v(self, owner: str) -> Optional[bool]:
        l_sent = PostLemmaSentence(self._db, owner, split=True)
        if l_sent.count() == 0:
            return True

        users_h = RssTagUsers(self._db)
        user = users_h.get_by_sid(owner)
        if not user:
            return False

        path = os.path.join(self._config["settings"]["w2v_dir"], user["w2v"])
        try:
            learn = W2VLearn(path)
            learn.learn(l_sent)
            result = True
        except Exception as e:
            result = None
            logging.error("Can`t W2V. Info: %s", e)

        return result

    def make_fasttext(self, owner: str) -> Optional[bool]:
        l_sent = PostLemmaSentence(self._db, owner, split=True)
        if l_sent.count() == 0:
            return True

        users_h = RssTagUsers(self._db)
        user = users_h.get_by_sid(owner)
        if not user:
            return False

        path = os.path.join(self._config["settings"]["fasttext_dir"], user["fasttext"])
        try:
            learn = FastTextLearn(path)
            learn.learn(l_sent)
            result = True
        except Exception as e:
            result = None
            logging.error("Can`t FastText. Info: %s", e)

        return result

    def make_tags_topics(self, owner: str) -> bool:
        """Mark tags that occur in a topic belonging to one of their posts."""
        try:
            topics_by_post: dict[str, set[str]] = defaultdict(set)
            groupings = self._db.post_grouping.find(
                {"owner": owner},
                projection={"post_ids": 1, "groups": 1, "_id": 0},
            )
            for grouping in groupings:
                groups: Any = grouping.get("groups")
                post_ids: Any = grouping.get("post_ids")
                if not isinstance(groups, dict) or not isinstance(post_ids, list):
                    continue
                topics: set[str] = {
                    str(topic).strip()
                    for topic in groups
                    if str(topic).strip()
                }
                if not topics:
                    continue
                for post_id in post_ids:
                    topics_by_post[str(post_id)].update(topics)

            topic_backed_tags: set[str] = set()
            posts = self._db.posts.find(
                {"owner": owner},
                projection={"pid": 1, "tags": 1, "_id": 0},
            )
            for post in posts:
                post_topics: set[str] = topics_by_post.get(str(post.get("pid")), set())
                raw_tags: Any = post.get("tags", [])
                if not post_topics or not isinstance(raw_tags, list):
                    continue
                for raw_tag in raw_tags:
                    tag: str = str(raw_tag).strip()
                    if tag and any(
                        _tag_occurs_in_topic(tag, topic) for topic in post_topics
                    ):
                        topic_backed_tags.add(tag.casefold())

            self._db.tags.update_many(
                {"owner": owner},
                {"$set": {"topic_backed": False}},
            )
            updates: list[UpdateOne] = []
            for tag_doc in self._db.tags.find(
                {"owner": owner}, projection={"tag": 1}
            ):
                tag_name: str = str(tag_doc.get("tag", "")).strip()
                if tag_name.casefold() in topic_backed_tags:
                    updates.append(
                        UpdateOne(
                            {"_id": tag_doc["_id"]},
                            {"$set": {"topic_backed": True}},
                        )
                    )
            if updates:
                self._db.tags.bulk_write(updates, ordered=False)

            logging.info(
                "Marked %d topic-backed tags for owner %s",
                len(updates),
                owner,
            )
            return True
        except Exception as exc:
            logging.exception("Unable to mark tags appearing in topics: %s", exc)
            return False

    def make_tags_groups(self, owner: str) -> Optional[bool]:
        tags_h = RssTagTags(self._db)
        all_tags = tags_h.get_all(owner, projection={"tag": True})
        try:
            users_h = RssTagUsers(self._db)
            user = users_h.get_by_sid(owner)
            if not user:
                return False

            path = os.path.join(self._config["settings"]["w2v_dir"], user["w2v"])
            learn = W2VLearn(path)
            koef = 0.6
            top_n = 10
            groups = learn.make_groups([tag["tag"] for tag in all_tags], top_n, koef)
            tag_groups = defaultdict(list)
            for group, tags in groups.items():
                if len(tags) > 3:
                    for tag in tags:
                        tag_groups[tag].append(group)
            if tag_groups:
                tags_h.add_groups(owner, tag_groups)
            result = True
        except Exception as e:
            result = None
            logging.error("Can`t group tags. Info: %s", e)

        return result

    def make_tags_sentiment(self, owner: str) -> Optional[bool]:
        """
        TODO: may be will be need RuSentiLex and WordNetAffectRuRom caching
        """
        try:
            with open(self._config["settings"]["sentilex"], "r", encoding="utf-8") as f:
                strings = f.read().splitlines()
            ru_sent = RuSentiLex()
            wrong = ru_sent.sentiment_validation(strings, ",", "!")
            if not wrong:
                ru_sent.load(strings, ",", "!")
                tags = RssTagTags(self._db)
                all_tags = tags.get_all(owner, projection={"tag": True})
                wna_dir = self._config["settings"]["lilu_wordnet"]
                wn_en = WordNetAffectRuRom("en", 4)
                wn_en.load_dicts_from_dir(wna_dir)
                wn_ru = WordNetAffectRuRom("ru", 4)
                wn_ru.load_dicts_from_dir(wna_dir)
                conv = SentimentConverter()
                for tag in all_tags:
                    sentiment = ru_sent.get_sentiment(tag["tag"])
                    if not sentiment:
                        affects = wn_en.get_affects_by_word(tag["tag"])
                        if not affects:
                            affects = wn_ru.get_affects_by_word(tag["tag"])
                        if affects:
                            sentiment = conv.convert_sentiment(affects)

                    if sentiment:
                        sentiment = sorted(sentiment)
                        tags.add_sentiment(owner, tag["tag"], sentiment)
            result = True
        except Exception as e:
            result = False
            logging.error("Can`t make tags santiment. Info: %s", e)

        return result

    def _total_posts(self, owner: str) -> int:
        try:
            return int(RssTagPosts(self._db).count(owner) or 0)
        except Exception as e:
            logging.error("Can`t count posts for %s. Info: %s", owner, e)
            return -1

    def _tag_rank_update(self, tag_d: dict, total_posts: int) -> UpdateOne:
        posts_count: int = int(tag_d.get("posts_count") or 0)
        freq: int = int(tag_d.get("freq") or 0)
        is_stopword: bool = tag_d["tag"] in self._stopw
        base_rank: dict[str, Any] = compute_base_rank(
            tag_d["tag"], posts_count, freq, total_posts, is_stopword
        )
        fields: dict[str, Any] = {f"rank.{key}": value for key, value in base_rank.items()}
        fields["rank_pending"] = True
        fields["temperature"] = legacy_temperature(posts_count, freq, is_stopword)
        return UpdateOne({"_id": tag_d["_id"]}, {"$set": fields})

    def make_tags_rank(self, task: dict) -> bool:
        """Write ridf/burst/df_ratio/shape_junk for the claimed tags batch."""
        tags_batch: List[dict] = list(task.get("data") or [])
        if not tags_batch:
            return True
        owner: str = task["user"]["sid"]
        total_posts: int = self._total_posts(owner)
        if total_posts < 0:
            return False
        updates: List[UpdateOne] = [
            self._tag_rank_update(tag_d, total_posts) for tag_d in tags_batch
        ]
        try:
            self._db.tags.bulk_write(updates, ordered=False)
            recompute_derived(self._db, owner, [tag_d["tag"] for tag_d in tags_batch])
        except Exception as e:
            logging.error("Can`t save tags rank for %s. Info: %s", owner, e)
            return False
        return True

    def handle_delete_feeds(self, task: dict) -> bool:
        user_sid = task["user"]["sid"]
        feed_ids = task.get("feed_ids", [])
        if not feed_ids:
            logging.info("Delete feeds task for user %s skipped: no feed_ids", user_sid)
            return True

        logging.info("Starting delete feeds for user %s: %s", user_sid, feed_ids)

        try:
            # 2. Query all posts with those feed_ids
            posts_cursor = self._db.posts.find(
                {"owner": user_sid, "feed_id": {"$in": feed_ids}},
                projection={
                    "tags": True,
                    "read": True,
                    "_id": True,
                    "pid": True,
                },
            )

            tag_stats = defaultdict(lambda: {"posts_count": 0, "unread_count": 0})
            post_ids = []
            pids = []

            for post in posts_cursor:
                post_ids.append(post["_id"])
                if "pid" in post:
                    pids.append(post["pid"])
                is_unread = not post.get("read", False)
                for tag in post.get("tags", []):
                    if not tag:
                        continue
                    tag_stats[tag]["posts_count"] += 1
                    if is_unread:
                        tag_stats[tag]["unread_count"] += 1
            logging.info(
                "Collected %s posts and %s pids for deletion", len(post_ids), len(pids)
            )

            # 4. Delete posts in batches (500)
            batch_size = 500
            for i in range(0, len(post_ids), batch_size):
                batch = post_ids[i : i + batch_size]
                self._db.posts.delete_many({"_id": {"$in": batch}})
                logging.info("Deleted batch of %s posts", len(batch))

            # 6. Delete post_grouping entries
            if pids:
                # Delete any grouping that contains at least one of the pids
                res = self._db.post_grouping.delete_many(
                    {"owner": user_sid, "post_ids": {"$in": pids}}
                )
                logging.info("Deleted %s post_grouping entries", res.deleted_count)

            # 5. Update counters
            tag_updates = []
            for tag, stats in tag_stats.items():
                tag_updates.append(
                    UpdateOne(
                        {"owner": user_sid, "tag": tag},
                        {
                            "$inc": {
                                "posts_count": -stats["posts_count"],
                                "unread_count": -stats["unread_count"],
                            }
                        },
                    )
                )

            if tag_updates:
                self._db.tags.bulk_write(tag_updates, ordered=False)
                logging.info("Updated counters for %s tags", len(tag_updates))

            # 7. Delete feed documents
            res = self._db.feeds.delete_many(
                {"owner": user_sid, "feed_id": {"$in": feed_ids}}
            )
            logging.info("Deleted %s feed documents", res.deleted_count)

            # 8. Cleanup orphans
            res_tags = self._db.tags.delete_many(
                {"owner": user_sid, "posts_count": {"$lte": 0}}
            )
            logging.info("Orphan cleanup: deleted %s tags", res_tags.deleted_count)

            # Sync letters
            self.make_letters(user_sid)
            logging.info("Refreshed letters for user %s", user_sid)

            return True
        except Exception as e:
            logging.error("Failed to delete feeds for user %s: %s", user_sid, e)
            return False
