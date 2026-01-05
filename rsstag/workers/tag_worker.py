"""Tag-related worker operations."""

import gzip
import logging
import math
import os.path
import time
from collections import defaultdict
from functools import lru_cache
from random import randint
from typing import List, Optional

from pymongo import UpdateOne
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer

from rsstag.bi_grams import RssTagBiGrams
from rsstag.entity_extractor import RssTagEntityExtractor
from rsstag.html_cleaner import HTMLCleaner
from rsstag.letters import RssTagLetters
from rsstag.posts import PostLemmaSentence, RssTagPosts
from rsstag.sentiment import RuSentiLex, SentimentConverter, WordNetAffectRuRom
from rsstag.tags import RssTagTags
from rsstag.tags_builder import TagsBuilder
from rsstag.users import RssTagUsers
from rsstag.w2v import W2VLearn
from rsstag.fasttext import FastTextLearn
from rsstag.web.routes import RSSTagRoutes
from rsstag.tasks import TAG_NOT_IN_PROCESSING
from rsstag.workers.base import BaseWorker


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

    def handle_w2v(self, task: dict) -> Optional[bool]:
        return self.make_w2v(task["user"]["sid"])

    def handle_fasttext(self, task: dict) -> Optional[bool]:
        return self.make_fasttext(task["user"]["sid"])

    def handle_tags_groups(self, task: dict) -> Optional[bool]:
        return self.make_tags_groups(task["user"]["sid"])

    def clear_user_data(self, user: dict) -> bool:
        try:
            self._db.posts.delete_many({"owner": user["sid"]})
            self._db.feeds.delete_many({"owner": user["sid"]})
            self._db.tags.delete_many({"owner": user["sid"]})
            self._db.bi_grams.delete_many({"owner": user["sid"]})
            self._db.letters.delete_many({"owner": user["sid"]})
            result = True
        except Exception as e:
            logging.error("Can`t clear user data %s. Info: %s", user["sid"], e)
            result = False

        return result

    def make_tags(
        self,
        posts: List[dict],
    ) -> bool:
        if not posts:
            return False
        posts_updates = []
        tags_updates = []
        bi_grams_updates = []
        sum_tags = {}
        sum_bigrams = {}
        routes = RSSTagRoutes(self._config["settings"]["host_name"])
        owner = posts[0]["owner"]
        for post in posts:
            content = gzip.decompress(post["content"]["content"])
            text = post["content"]["title"] + " " + content.decode("utf-8")
            self._cleaner.purge()
            self._cleaner.feed(text)
            strings = self._cleaner.get_content()
            text = " ".join(strings)
            self._builder.purge()
            self._builder.build_tags_and_bi_grams(text)
            tags = self._builder.get_tags()
            tag_words = self._builder.get_words()
            bi_grams = self._builder.get_bi_grams()
            bi_words = self._builder.get_bi_grams_words()
            post_tags = {
                "lemmas": gzip.compress(
                    self._builder.get_prepared_text().encode("utf-8", "replace")
                ),
                "tags": [""],
                "bi_grams": [],
            }
            if tags:
                post_tags["tags"] = [tag for tag in tags]
            if bi_grams:
                post_tags["bi_grams"] = list(bi_grams.keys())
            posts_updates.append(UpdateOne({"_id": post["_id"]}, {"$set": post_tags}))
            for tag, freq in tags.items():
                if tag not in sum_tags:
                    sum_tags[tag] = {"posts": 0, "freq": 0, "words": set()}
                sum_tags[tag]["posts"] += 1
                sum_tags[tag]["freq"] += freq
                sum_tags[tag]["words"].update(tag_words[tag])
            for bigram, bi_tags in bi_grams.items():
                if bigram not in sum_bigrams:
                    sum_bigrams[bigram] = {
                        "tags": list(bi_tags),
                        "posts": 0,
                        "words": set(),
                    }
                sum_bigrams[bigram]["posts"] += 1
                sum_bigrams[bigram]["words"].update(bi_words[bigram])

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
        for bi_gram, bi_d in sum_bigrams.items():
            has_stop = False
            for bi_t in bi_d["tags"]:
                if bi_t in self._stopw:
                    has_stop = True
                    break
            if has_stop:
                continue
            bi_grams_updates.append(
                UpdateOne(
                    {"owner": owner, "tag": bi_gram},
                    {
                        "$set": {
                            "read": False,
                            "tag": bi_gram,
                            "owner": owner,
                            "temperature": 0,
                            "local_url": routes.get_url_by_endpoint(
                                endpoint="on_bi_gram_get", params={"bi_gram": bi_gram}
                            ),
                            "tags": list(bi_d["tags"]),
                            "processing": TAG_NOT_IN_PROCESSING,
                        },
                        "$inc": {
                            "posts_count": bi_d["posts"],
                            "unread_count": bi_d["posts"],
                        },
                        "$addToSet": {"words": {"$each": list(bi_d["words"])}},
                    },
                    upsert=True,
                )
            )
        try:
            if posts_updates:
                self._db.posts.bulk_write(posts_updates, ordered=False)
            if tags_updates:
                self._db.tags.bulk_write(tags_updates, ordered=False)
            if bi_grams_updates:
                self._db.bi_grams.bulk_write(bi_grams_updates, ordered=False)
            result = True
        except Exception as e:
            result = False
            logging.error("Can`t save tags/bi-grams for posts. Info: %s", e)

        return result

    def process_words(self, tag: dict) -> bool:
        seconds_interval = 3600
        current_time = time.time()
        max_repeats = 5
        result = True
        word_query = {"word": tag["tag"], "owner": tag["owner"]}
        for _ in range(0, max_repeats):
            try:
                word = self._db.words.find_one(word_query)
                if word:
                    old_mid = sum(word["numbers"]) / len(word["numbers"])
                    time_delta = current_time - word["it"]
                    if time_delta > seconds_interval:
                        update_query = {
                            "$set": {"it": current_time},
                            "$push": {"numbers": tag["posts_count"]},
                        }
                        word["numbers"].append(tag["posts_count"])
                        new_mid = sum(word["numbers"]) / len(word["numbers"])
                    else:
                        numbers_length = len(word["numbers"]) - 1
                        key_name = "numbers." + str(numbers_length)
                        update_query = {"$inc": {key_name: tag["posts_count"]}}
                        word["numbers"][-1] += tag["posts_count"]
                        new_mid = sum(word["numbers"]) / len(word["numbers"])
                    temperature = abs(new_mid - old_mid)
                    self._db.tags.find_one_and_update(
                        {"tag": tag["tag"], "owner": tag["owner"]},
                        {"$set": {"temperature": temperature}},
                    )
                    self._db.words.find_one_and_update(word_query, update_query)
                else:
                    self._db.words.insert(
                        {
                            "word": tag["tag"],
                            "owner": tag["owner"],
                            "numbers": [tag["posts_count"]],
                            "it": current_time,
                        }
                    )
            except Exception as e:
                result = False
                logging.error(
                    "Can`t process word %s for user %s. Info: %s",
                    tag["tag"],
                    tag["owner"],
                    e,
                )
            if result:
                break
            time.sleep(randint(3, 10))

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
                    if len(word) > 1:
                        count_ent[word] += 1

        if not count_ent:
            return True

        logging.info("Found %s entities for user %s", len(count_ent), owner)
        tags = RssTagTags(self._db)
        result = tags.add_entities(owner, count_ent)

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

    @lru_cache(maxsize=5128)
    def _tags_freqs(self, user_sid: str, tag: str) -> int:
        tags = RssTagTags(self._db)
        tag_d = tags.get_by_tag(user_sid, tag)
        if tag_d:
            return tag_d["freq"]

        return 0

    def make_bi_grams_rank(self, task: dict) -> bool:
        """
        https://arxiv.org/pdf/1307.0596
        """
        bi_grams = RssTagBiGrams(self._db)
        user_sid = task["user"]["sid"]
        bi_count = bi_grams.count(user_sid)
        if bi_count == 0:
            return False

        posts = RssTagPosts(self._db)
        total_docs = posts.count(user_sid) or 1

        bi_temps = {}
        q = 0.5

        for bi in task["data"]:
            grams = bi["tag"].split(" ")
            if not grams[0] or not grams[1]:
                logging.error("Bigrams bug: %s", bi["tag"])
                continue

            f1 = self._tags_freqs(user_sid, grams[0])
            f2 = self._tags_freqs(user_sid, grams[1])
            d_xy = bi["posts_count"]

            denominator = (f1 * f2) / total_docs

            sqrt_term = math.sqrt(f1) * math.sqrt(math.log(q) / -2) if f1 > 0 else 0

            denominator += sqrt_term

            if denominator > 0 and d_xy > 0:
                cpmi = math.log(d_xy / denominator)
            else:
                cpmi = 0

            if grams[0] in self._stopw or grams[1] in self._stopw:
                cpmi /= f1 + f2

            bi_temps[bi["tag"]] = max(cpmi + 0.01, 0.01)

        bi_grams.set_temperatures(user_sid, bi_temps)

        return True

    def _make_bi_grams_rank(self, user_sid: str) -> bool:
        tags = RssTagTags(self._db)
        bi_grams = RssTagBiGrams(self._db)
        freq_cache = {}
        bi_count = bi_grams.count(user_sid)
        if bi_count == 0:
            return False
        cursor = bi_grams.get_all(
            user_sid, projection={"tag": True, "posts_count": True}
        )
        for bi in cursor:
            grams = bi["tag"].split(" ")
            for_search = []
            for tag in grams:
                if tag not in freq_cache:
                    for_search.append(tag)
            if for_search:
                freqs = tags.get_by_tags(
                    user_sid, for_search, projection={"tag": True, "freq": True}
                )
                for fr in freqs:
                    freq_cache[fr["tag"]] = fr["freq"]
            if not grams[0] or not grams[1]:
                logging.error("Bigrams bug: %s", bi["tag"])
                continue
            f1 = freq_cache[grams[0]]
            f2 = freq_cache[grams[1]]
            bi_f = bi["posts_count"]
            temp = bi_f / math.log(f1 + f2)
            if grams[0] in self._stopw or grams[1] in self._stopw:
                temp /= f1 + f2
            bi_grams.set_temperature(user_sid, bi["tag"], temp)

        return True

    @lru_cache(maxsize=10)
    def _get_posts_count(self, owner: str, task_id: str) -> Optional[int]:
        posts_h = RssTagPosts(self._db)

        return posts_h.count(owner)

    @lru_cache(maxsize=10)
    def _get_tags_count(self, owner: str, task_id: str) -> int:
        tags_h = RssTagTags(self._db)

        return tags_h.get_tags_sum(owner)

    def _make_tags_rank(self, task: dict) -> bool:
        user_sid = task["user"]["sid"]
        posts_count = self._get_posts_count(user_sid, task["_id"])
        if posts_count == 0:
            return True
        if posts_count is None:
            return False
        tags_count = self._get_tags_count(user_sid, task["_id"])
        if tags_count == 0:
            return True
        if tags_count is None:
            return False
        tag_temps = {}
        for tag_d in task["data"]:
            tf = tag_d["freq"] / tags_count
            idf = math.log(posts_count / tag_d["posts_count"])
            temp = tf * idf
            tag_temps[tag_d["tag"]] = temp

        tags_h = RssTagTags(self._db)
        tags_h.add_entities(user_sid, tag_temps, replace=True)

        return True

    def make_tags_rank(self, task: dict) -> bool:
        tag_temps = {}
        for tag_d in task["data"]:
            tf = tag_d["posts_count"] / math.log(1 + tag_d["freq"])
            if tag_d["tag"] in self._stopw:
                tf /= tag_d["freq"]
            tag_temps[tag_d["tag"]] = tf + 0.01

        tags_h = RssTagTags(self._db)
        tags_h.add_entities(task["user"]["sid"], tag_temps)

        return True

    def make_clean_bigrams(self, task: dict) -> bool:
        bi_grams = RssTagBiGrams(self._db)
        return bi_grams.remove_by_count(task["user"]["sid"], 1)
