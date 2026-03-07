import logging
import time
import gzip
from typing import Optional, List, Dict, Any, Set, Tuple, Callable
from rsstag.users import RssTagUsers
from pymongo import MongoClient, UpdateOne, ReturnDocument
from bson.objectid import ObjectId
from rsstag.post_grouping import RssTagPostGrouping
from rsstag.tags import RssTagTags

TASK_ALL = -1
TASK_NOOP = 0
TASK_DOWNLOAD = 1
TASK_MARK = 2
TASK_TAGS = 3
TASK_WORDS = 4
TASK_LETTERS = 5
TASK_NER = 6
TASK_CLUSTERING = 7
TASK_W2V = 8
TASK_D2V = 9
TASK_TAGS_SENTIMENT = 10
TASK_TAGS_GROUP = 11
TASK_TAGS_COORDS = 12
TASK_BIGRAMS_RANK = 13
TASK_TAGS_RANK = 14
TASK_FASTTEXT = 15
TASK_CLEAN_BIGRAMS = 16
TASK_MARK_TELEGRAM = 17
TASK_GMAIL_SORT = 18
TASK_POST_GROUPING = 19
TASK_TAG_CLASSIFICATION = 20
TASK_POST_GROUPING_BATCH = 21
TASK_TAG_CLASSIFICATION_BATCH = 22
TASK_DELETE_FEEDS = 23
TASK_POST_GROUPING_CLEANUP = 24
TASK_SNIPPET_CLUSTERING = 25

SCOPE_MODE_ALL = "all"
SCOPE_MODE_POSTS = "posts"
SCOPE_MODE_FEEDS = "feeds"
SCOPE_MODE_CATEGORIES = "categories"
SCOPE_MODE_PROVIDER = "provider"
SUPPORTED_SCOPE_MODES = {
    SCOPE_MODE_ALL,
    SCOPE_MODE_POSTS,
    SCOPE_MODE_FEEDS,
    SCOPE_MODE_CATEGORIES,
    SCOPE_MODE_PROVIDER,
}

SCOPE_REQUIREMENTS: Dict[str, Tuple[str, str]] = {
    SCOPE_MODE_POSTS: ("post_ids", "Scope mode 'posts' requires at least one post id."),
    SCOPE_MODE_FEEDS: ("feed_ids", "Scope mode 'feeds' requires at least one feed id."),
    SCOPE_MODE_CATEGORIES: (
        "category_ids",
        "Scope mode 'categories' requires at least one category id.",
    ),
    SCOPE_MODE_PROVIDER: (
        "provider",
        "Scope mode 'provider' requires a provider value.",
    ),
}

SCOPE_CAPABILITY_GLOBAL_ONLY = "global_only"
SCOPE_CAPABILITY_SCOPED_SUPPORTED = "scoped_supported"

TASK_SCOPE_REGISTRY: Dict[int, Dict[str, Any]] = {
    TASK_W2V: {"scope": SCOPE_CAPABILITY_GLOBAL_ONLY},
    TASK_FASTTEXT: {"scope": SCOPE_CAPABILITY_GLOBAL_ONLY},
    TASK_POST_GROUPING: {"scope": SCOPE_CAPABILITY_SCOPED_SUPPORTED},
    TASK_POST_GROUPING_BATCH: {"scope": SCOPE_CAPABILITY_SCOPED_SUPPORTED},
    TASK_POST_GROUPING_CLEANUP: {"scope": SCOPE_CAPABILITY_SCOPED_SUPPORTED},
}


def get_task_scope_capability(task_type: int) -> str:
    return TASK_SCOPE_REGISTRY.get(task_type, {}).get(
        "scope", SCOPE_CAPABILITY_GLOBAL_ONLY
    )


def get_task_scope_hint(task_type: int) -> str:
    capability = get_task_scope_capability(task_type)
    if capability == SCOPE_CAPABILITY_SCOPED_SUPPORTED:
        return "supports scoped reprocess"
    return "global only"


def get_scoped_supported_tasks() -> Dict[int, str]:
    return {
        task_type: ""
        for task_type, task_data in TASK_SCOPE_REGISTRY.items()
        if task_data.get("scope") == SCOPE_CAPABILITY_SCOPED_SUPPORTED
    }

POST_NOT_IN_PROCESSING = 0
BIGRAM_NOT_IN_PROCESSING = 0
TASK_NOT_IN_PROCESSING = 0
TASK_FREEZED = -1
TAG_NOT_IN_PROCESSING = 0
POST_GROUPING_NOT_IN_PROCESSING = 0
MAX_EXTERNAL_ERROR_LENGTH = 1000
EXTERNAL_WORKER_ALLOWED_TASK_TYPES: Set[int] = {
    TASK_POST_GROUPING,
    TASK_TAG_CLASSIFICATION,
}


class RssTagTasks:
    indexes = ["user", "processing"]
    _tasks_after = {
        TASK_DOWNLOAD: [TASK_TAGS],
        TASK_TAGS: [TASK_CLEAN_BIGRAMS],
        TASK_CLEAN_BIGRAMS: [
            TASK_BIGRAMS_RANK,
            TASK_TAGS_RANK,
            TASK_LETTERS,
            TASK_TAGS_SENTIMENT,
        ],  # TASK_TAGS_COORDS
        TASK_BIGRAMS_RANK: [TASK_NER],
        TASK_NER: [TASK_CLUSTERING],
        TASK_CLUSTERING: [TASK_W2V],
        TASK_W2V: [TASK_FASTTEXT],
        TASK_FASTTEXT: [TASK_POST_GROUPING],
        # TASK_W2V: [TASK_TAGS_GROUP],
        # TASK_TAGS_GROUP: [TASK_FASTTEXT]
    }

    def __init__(self, db: MongoClient) -> None:
        self._db = db
        self._log = logging.getLogger("tasks")
        self._posts_bath_size = 200
        self._bigrams_bath_size = 1000
        self._tags_bath_size = 1000
        self._scope_filter_builders: Dict[str, Callable[[str, Dict[str, Any]], Dict[str, Any]]] = {
            SCOPE_MODE_POSTS: self._scope_filter_for_posts,
            SCOPE_MODE_FEEDS: self._scope_filter_for_feeds,
            SCOPE_MODE_CATEGORIES: self._scope_filter_for_categories,
            SCOPE_MODE_PROVIDER: self._scope_filter_for_provider,
        }

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self._db.tasks.create_index(index)
            except Exception as e:
                self._log.warning(
                    "Can`t create index %s. May be already exists. Info: %s", index, e
                )

    def _normalize_scope(self, scope: Optional[dict]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {
            "mode": SCOPE_MODE_ALL,
            "post_ids": [],
            "feed_ids": [],
            "category_ids": [],
            "provider": "",
        }
        if not isinstance(scope, dict):
            return normalized

        mode = scope.get("mode", SCOPE_MODE_ALL)
        if mode not in SUPPORTED_SCOPE_MODES:
            mode = SCOPE_MODE_ALL
        normalized["mode"] = mode

        for ids_key in ("post_ids", "feed_ids", "category_ids"):
            ids = scope.get(ids_key, [])
            if isinstance(ids, list):
                normalized[ids_key] = [str(value) for value in ids if value]

        provider = scope.get("provider", "")
        if isinstance(provider, str):
            normalized["provider"] = provider.strip()

        return normalized

    def validate_task_scope(self, task_type: int, scope: Optional[dict]) -> Tuple[bool, str]:
        normalized = self._normalize_scope(scope)
        capability = get_task_scope_capability(task_type)

        if capability == SCOPE_CAPABILITY_GLOBAL_ONLY and normalized["mode"] != SCOPE_MODE_ALL:
            return (
                False,
                f"Task {task_type} is global-only and does not support scope mode '{normalized['mode']}'.",
            )

        required_field = SCOPE_REQUIREMENTS.get(normalized["mode"])
        if required_field and not normalized.get(required_field[0]):
            return False, required_field[1]

        return True, ""

    def _scope_filter_for_posts(self, _owner: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        return {"pid": {"$in": scope.get("post_ids", [])}}

    def _scope_filter_for_feeds(self, _owner: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        return {"feed_id": {"$in": list(scope.get("feed_ids", []))}}

    def _scope_filter_for_categories(self, owner: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        feed_ids = self._resolve_scope_feed_ids(owner, scope)
        return {"feed_id": {"$in": feed_ids}}

    def _scope_filter_for_provider(self, _owner: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        provider = scope.get("provider")
        if not provider:
            return {}
        return {"provider": provider}

    def mark_task_failed(self, task_id: Any, error: str) -> None:
        self._db.tasks.update_one(
            {"_id": task_id},
            {
                "$set": {
                    "processing": TASK_FREEZED,
                    "failed": True,
                    "failed_at": time.time(),
                    "error": error,
                }
            },
        )

    def _resolve_scope_feed_ids(self, owner: str, scope: Dict[str, Any]) -> List[str]:
        mode = scope.get("mode")
        if mode == SCOPE_MODE_FEEDS:
            return list(scope.get("feed_ids", []))
        if mode != SCOPE_MODE_CATEGORIES:
            return []

        category_ids = list(scope.get("category_ids", []))
        if not category_ids:
            return []

        feeds = self._db.feeds.find(
            {"owner": owner, "category_id": {"$in": category_ids}},
            projection={"feed_id": True},
        )
        return [feed.get("feed_id") for feed in feeds if feed.get("feed_id")]

    def _build_post_scope_predicate(self, owner: str, task_doc: dict) -> Dict[str, Any]:
        query: Dict[str, Any] = {"owner": owner}
        scope = self._normalize_scope(task_doc.get("scope"))
        mode = scope["mode"]
        builder = self._scope_filter_builders.get(mode)
        if builder:
            query.update(builder(owner, scope))

        return query

    def _count_pending_grouping_posts(self, owner: str, task_doc: dict) -> int:
        scope_query = self._build_post_scope_predicate(owner, task_doc)
        return self._db.posts.count_documents({**scope_query, "grouping": {"$exists": False}})

    def _find_pending_grouping_post(
        self,
        owner: str,
        task_doc: dict,
        extra_query: Optional[Dict[str, Any]] = None,
        claim_set: Optional[Dict[str, Any]] = None,
    ) -> Optional[dict]:
        query: Dict[str, Any] = {
            **self._build_post_scope_predicate(owner, task_doc),
            "grouping": {"$exists": False},
        }
        if extra_query:
            query.update(extra_query)

        update = {"$set": claim_set} if claim_set else None
        if update:
            return self._db.posts.find_one_and_update(query, update)
        return self._db.posts.find_one(query)

    def add_task(self, data: dict, manual: bool = True):
        result = True
        if data and "type" in data:
            try:
                normalized_scope = self._normalize_scope(data.get("scope"))
                is_scope_valid, scope_error = self.validate_task_scope(data["type"], normalized_scope)
                if not is_scope_valid:
                    self._log.warning(
                        "Can`t add task %s for user %s. Invalid scope: %s",
                        data["type"],
                        data.get("user", ""),
                        scope_error,
                    )
                    return False

                if data["type"] == TASK_DOWNLOAD:  # TODO: check insertion results
                    self._db.tasks.update_one(
                        {"user": data["user"], "provider": data.get("provider", "")},
                        {
                            "$set": {
                                "user": data["user"],
                                "type": TASK_DOWNLOAD,
                                "processing": TASK_NOT_IN_PROCESSING,
                                "host": data["host"],
                                "manual": manual,
                                "selection": data.get("selection", {}),
                                "provider": data.get("provider", ""),
                            }
                        },
                        upsert=True,
                    )
                elif data["type"] in [TASK_MARK, TASK_MARK_TELEGRAM]:
                    if data["data"]:
                        self._db.tasks.insert_many(data["data"])
                    else:
                        result = False
                else:
                    update_data = {
                        "user": data["user"],
                        "type": data["type"],
                        "processing": TASK_NOT_IN_PROCESSING,
                        "manual": manual,
                        "provider": data.get("provider", ""),
                    }
                    if data.get("scope") is not None or data["type"] in (TASK_POST_GROUPING, TASK_POST_GROUPING_BATCH, TASK_POST_GROUPING_CLEANUP):
                        update_data["scope"] = normalized_scope
                    for key in data:
                        if key not in update_data:
                            update_data[key] = data[key]
                    self._db.tasks.update_one(
                        {"user": data["user"], "type": data["type"]},
                        {"$set": update_data},
                        upsert=True,
                    )
            except Exception as e:
                result = None
                self._log.warning(
                    "Can`t add task %s for user %s. Info: %s",
                    data["type"],
                    data["user"],
                    e,
                )
        else:
            result = False
            self._log.warning("Can`t add task. Bad task data: %s", data)

        return result

    def add_next_tasks(self, user: str, task_type: int) -> Optional[bool]:
        result = False
        if task_type in self._tasks_after:
            for_insert = [
                {
                    "user": user,
                    "type": task,
                    "processing": TASK_NOT_IN_PROCESSING,
                    "manual": False,
                }
                for task in self._tasks_after[task_type]
            ]
            try:
                self._db.tasks.insert_many(for_insert)
                result = True
            except Exception as e:
                result = None
                self._log.warning(
                    "Can`t add tasks after %s for user %s. Info: %s", task_type, user, e
                )

        return result

    def _can_finalize_completed_task(self, user_task: dict) -> bool:
        if user_task.get("manual", False):
            return True

        task_type = user_task.get("type")
        if task_type not in self._tasks_after:
            return True

        return bool(self.add_next_tasks(user_task["user"], task_type))

    def get_task(self, users: RssTagUsers) -> dict:
        task = {"type": TASK_NOOP, "user": None, "data": None, "_id": ""}
        try:
            # Use aggregation with $sample to randomize task selection.
            # This ensures that if multiple tasks are in the queue, all of them
            # get a chance to be processed, preventing one large task from
            # monopolizing the workers through its subtasks/batches.
            pipeline = [
                {"$match": {"processing": TASK_NOT_IN_PROCESSING}},
                {"$sample": {"size": 5}},
            ]
            candidates = list(self._db.tasks.aggregate(pipeline))
            if not candidates:
                return task

            user_task = None
            for candidate in candidates:
                user_task = self._db.tasks.find_one_and_update(
                    {"_id": candidate["_id"], "processing": TASK_NOT_IN_PROCESSING},
                    {"$set": {"processing": time.time()}},
                )
                if user_task:
                    break

            if not user_task:
                return task

            user = users.get_by_sid(user_task["user"])
            if not user:
                return task

            task.update(user_task)
            task["user"] = user
            task["_id"] = user_task["_id"]
            task["type"] = user_task["type"]
            task["manual"] = user_task.get("manual", False)
            task["batch"] = user_task.get("batch", {})
            is_scope_valid, scope_error = self.validate_task_scope(
                user_task["type"], user_task.get("scope")
            )
            if not is_scope_valid:
                self._log.warning(
                    "Ignoring invalid task+scope combination. task_id=%s type=%s user=%s error=%s",
                    user_task.get("_id"),
                    user_task.get("type"),
                    user_task.get("user"),
                    scope_error,
                )
                self.mark_task_failed(user_task["_id"], scope_error)
                task["type"] = TASK_NOOP
                return task
            data = user_task
            if user_task["type"] == TASK_TAGS:
                data = []
                ps = self._db.posts.find(
                    {
                        "owner": task["user"]["sid"],
                        "tags": [],
                        "processing": POST_NOT_IN_PROCESSING,
                    }
                ).limit(self._posts_bath_size)
                ids = []
                for p in ps:
                    data.append(p)
                    ids.append(p["_id"])
                unlock_task = True
                if ids:
                    self._db.posts.update_many(
                        {"_id": {"$in": ids}},
                        {"$set": {"processing": time.time()}},
                    )
                else:
                    task["type"] = TASK_NOOP
                    psc = self._db.posts.count_documents(
                        {
                            "owner": task["user"]["sid"],
                            "tags": [],
                        }
                    )
                    if psc == 0:
                        can_delete = self._can_finalize_completed_task(user_task)
                        if can_delete:
                            self._db.tasks.delete_one({"_id": user_task["_id"]})
                            unlock_task = False
                if unlock_task:
                    self._db.tasks.update_one(
                        {"_id": user_task["_id"]},
                        {"$set": {"processing": TASK_NOT_IN_PROCESSING}},
                    )
            elif user_task["type"] == TASK_BIGRAMS_RANK:
                data = []
                bis_dt = self._db.bi_grams.find(
                    {
                        "owner": task["user"]["sid"],
                        "temperature": 0,
                        "processing": BIGRAM_NOT_IN_PROCESSING,
                    },
                    projection={"tag": True, "posts_count": True},
                ).limit(self._bigrams_bath_size)
                ids = []
                for bi_dt in bis_dt:
                    data.append(bi_dt)
                    ids.append(bi_dt["_id"])
                if ids:
                    self._db.bi_grams.update_many(
                        {"_id": {"$in": ids}},
                        {"$set": {"processing": time.time()}},
                    )
                    self._db.tasks.update_one(
                        {"_id": user_task["_id"]},
                        {"$set": {"processing": TASK_NOT_IN_PROCESSING}},
                    )
                else:
                    task["type"] = TASK_NOOP
                    can_delete = self._can_finalize_completed_task(user_task)
                    if can_delete:
                        self._db.tasks.delete_one({"_id": user_task["_id"]})
            elif user_task["type"] == TASK_POST_GROUPING:
                data = []
                scope_query = self._build_post_scope_predicate(task["user"]["sid"], user_task)
                # Get posts that need grouping
                ps = self._db.posts.find(
                    {
                        **scope_query,
                        "grouping": {"$exists": False},
                        "processing": POST_NOT_IN_PROCESSING,
                    }
                ).limit(1)
                ids = []
                for p in ps:
                    data.append(p)
                    ids.append(p["_id"])
                unlock_task = True
                if ids:
                    self._db.posts.update_many(
                        {"_id": {"$in": ids}},
                        {"$set": {"processing": time.time()}},
                    )
                else:
                    task["type"] = TASK_NOOP
                    psc = self._db.posts.count_documents(
                        {**scope_query, "grouping": {"$exists": False}}
                    )
                    if psc == 0:
                        can_delete = self._can_finalize_completed_task(user_task)
                        if can_delete:
                            self._db.tasks.delete_one({"_id": user_task["_id"]})
                            unlock_task = False
                if unlock_task:
                    self._db.tasks.update_one(
                        {"_id": user_task["_id"]},
                        {"$set": {"processing": TASK_NOT_IN_PROCESSING}},
                    )
            elif user_task["type"] == TASK_POST_GROUPING_BATCH:
                data = []
                scope_query = self._build_post_scope_predicate(task["user"]["sid"], user_task)
                unlock_task = True
                batch_state = user_task.get("batch", {})
                batch_ids = batch_state.get("item_ids", [])
                ids = []
                if batch_ids:
                    ids = [
                        ObjectId(tag_id) if isinstance(tag_id, str) else tag_id
                        for tag_id in batch_ids
                    ]
                    ps = self._db.posts.find({"_id": {"$in": ids}, **scope_query})
                    for p in ps:
                        data.append(p)
                else:
                    ps = self._db.posts.find(
                        {
                            **scope_query,
                            "grouping": {"$exists": False},
                            "processing": POST_NOT_IN_PROCESSING,
                        }
                    ).limit(10000)
                    for p in ps:
                        data.append(p)
                        ids.append(p["_id"])
                    if ids:
                        self._db.posts.update_many(
                            {"_id": {"$in": ids}},
                            {"$set": {"processing": time.time()}},
                        )
                    else:
                        task["type"] = TASK_NOOP
                        psc = self._db.posts.count_documents(
                            {
                                **scope_query,
                                "grouping": {"$exists": False},
                            }
                        )
                        if psc == 0:
                            can_delete = self._can_finalize_completed_task(user_task)
                            if can_delete:
                                self._db.tasks.delete_one({"_id": user_task["_id"]})
                                unlock_task = False
                if unlock_task:
                    self._db.tasks.update_one(
                        {"_id": user_task["_id"]},
                        {"$set": {"processing": TASK_NOT_IN_PROCESSING}},
                    )
            elif user_task["type"] == TASK_POST_GROUPING_CLEANUP:
                data = []
                self._db.tasks.update_one(
                    {"_id": user_task["_id"]},
                    {"$set": {"processing": TASK_NOT_IN_PROCESSING}},
                )
            elif user_task["type"] == TASK_TAGS_RANK:
                data = []
                tags_dt = self._db.tags.find(
                    {
                        "owner": task["user"]["sid"],
                        "temperature": 0,
                        "processing": TAG_NOT_IN_PROCESSING,
                    },
                    projection={"tag": True, "posts_count": True, "freq": True},
                ).limit(self._tags_bath_size)
                ids = []
                for tag_dt in tags_dt:
                    data.append(tag_dt)
                    ids.append(tag_dt["_id"])
                if ids:
                    self._db.tags.update_many(
                        {"_id": {"$in": ids}},
                        {"$set": {"processing": time.time()}},
                    )
                    self._db.tasks.update_one(
                        {"_id": user_task["_id"]},
                        {"$set": {"processing": TASK_NOT_IN_PROCESSING}},
                    )
                else:
                    task["type"] = TASK_NOOP
                    can_delete = self._can_finalize_completed_task(user_task)
                    if can_delete:
                        self._db.tasks.delete_one({"_id": user_task["_id"]})
            elif user_task["type"] == TASK_NER:
                data = []
                ps = self._db.posts.find(
                    {
                        "owner": task["user"]["sid"],
                        "ner": {"$exists": False},
                        "processing": POST_NOT_IN_PROCESSING,
                    }
                ).limit(self._posts_bath_size)
                ids = []
                for p in ps:
                    data.append(p)
                    ids.append(p["_id"])
                unlock_task = True
                if ids:
                    self._db.posts.update_many(
                        {"_id": {"$in": ids}},
                        {"$set": {"processing": time.time()}},
                    )
                else:
                    task["type"] = TASK_NOOP
                    psc = self._db.posts.count_documents(
                        {"owner": task["user"]["sid"], "ner": {"$exists": False}}
                    )
                    if psc == 0:
                        can_delete = self._can_finalize_completed_task(user_task)
                        if can_delete:
                            self._db.tasks.delete_one({"_id": user_task["_id"]})
                            unlock_task = False
                if unlock_task:
                    self._db.tasks.update_one(
                        {"_id": user_task["_id"]},
                        {"$set": {"processing": TASK_NOT_IN_PROCESSING}},
                    )
            elif user_task["type"] == TASK_TAG_CLASSIFICATION_BATCH:
                data = []
                unlock_task = True
                batch_state = user_task.get("batch", {})
                batch_ids = batch_state.get("item_ids", [])
                ids = []
                if batch_ids:
                    ids = [
                        ObjectId(tag_id) if isinstance(tag_id, str) else tag_id
                        for tag_id in batch_ids
                    ]
                    tags_dt = self._db.tags.find({"_id": {"$in": ids}})
                    for tag_dt in tags_dt:
                        data.append(tag_dt)
                else:
                    tags_dt = self._db.tags.find(
                        {
                            "owner": task["user"]["sid"],
                            "classifications": {"$exists": False},
                            "processing": TAG_NOT_IN_PROCESSING,
                        }
                    ).limit(10000)
                    for tag_dt in tags_dt:
                        data.append(tag_dt)
                        ids.append(tag_dt["_id"])
                    if ids:
                        self._db.tags.update_many(
                            {"_id": {"$in": ids}},
                            {"$set": {"processing": time.time()}},
                        )
                    else:
                        task["type"] = TASK_NOOP
                        psc = self._db.tags.count_documents(
                            {
                                "owner": task["user"]["sid"],
                                "classifications": {"$exists": False},
                            }
                        )
                        if psc == 0:
                            can_delete = self._can_finalize_completed_task(user_task)
                            if can_delete:
                                self._db.tasks.delete_one({"_id": user_task["_id"]})
                                unlock_task = False
                if unlock_task:
                    self._db.tasks.update_one(
                        {"_id": user_task["_id"]},
                        {"$set": {"processing": TASK_NOT_IN_PROCESSING}},
                    )
            elif user_task["type"] == TASK_TAG_CLASSIFICATION:
                data = []
                unlock_task = True
                tags_dt = self._db.tags.find(
                    {
                        "owner": task["user"]["sid"],
                        "classifications": {"$exists": False},
                        "processing": TAG_NOT_IN_PROCESSING,
                    }
                ).limit(self._tags_bath_size)
                ids = []
                for tag_dt in tags_dt:
                    data.append(tag_dt)
                    ids.append(tag_dt["_id"])
                if ids:
                    self._db.tags.update_many(
                        {"_id": {"$in": ids}},
                        {"$set": {"processing": time.time()}},
                    )
                else:
                    task["type"] = TASK_NOOP
                    psc = self._db.tags.count_documents(
                        {
                            "owner": task["user"]["sid"],
                            "classifications": {"$exists": False},
                        }
                    )
                    if psc == 0:
                        can_delete = self._can_finalize_completed_task(user_task)
                        if can_delete:
                            self._db.tasks.delete_one({"_id": user_task["_id"]})
                            unlock_task = False
                if unlock_task:
                    self._db.tasks.update_one(
                        {"_id": user_task["_id"]},
                        {"$set": {"processing": TASK_NOT_IN_PROCESSING}},
                    )

            """if task_type == TASK_WORDS:
                if task['type'] == TASK_NOOP:
                    data = db.tags.find_one_and_update(
                        {
                            'processing': TASK_NOT_IN_PROCESSING,
                            'worded': {'$exists': False}
                        },
                        {'$set': {'processing': time.time()}}
                    )
                    if data and (data['processing'] == TASK_NOT_IN_PROCESSING):
                        task['type'] = TASK_WORDS"""
            task["data"] = data
        except Exception as e:
            task["type"] = TASK_NOOP
            self._log.error("Worker can`t get tasks: %s", e)

        # self._log.info('Get task: %s', task)
        return task

    def remove_task(self, _id) -> Optional[bool]:
        try:
            if isinstance(_id, str):
                _id = ObjectId(_id)
            self._db.tasks.delete_one({"_id": _id})
            result = True
        except Exception as e:
            result = None
            self._log.error("Remove tasks: %s. Info: %s", _id, e)

        return result

    def finish_task(self, task: dict) -> bool:
        remove_task = True
        try:
            if task["type"] == TASK_TAGS:
                remove_task = False
                updates = []
                for post in task["data"]:
                    updates.append(
                        UpdateOne(
                            {"_id": post["_id"]},
                            {"$set": {"processing": POST_NOT_IN_PROCESSING}},
                        )
                    )
                self._db.posts.bulk_write(updates, ordered=False)
                """elif task['type'] == TASK_WORDS:
                    self._db.tags.find_one_and_update(
                        {'_id': task['data']['_id']},
                        {'$set': {
                            'processing': POST_NOT_IN_PROCESSING,
                            'worded': True
                        }}
                    )"""
            elif task["type"] == TASK_BIGRAMS_RANK:
                remove_task = False
                updates = []
                for bigram in task["data"]:
                    updates.append(
                        UpdateOne(
                            {"_id": bigram["_id"]},
                            {"$set": {"processing": BIGRAM_NOT_IN_PROCESSING}},
                        )
                    )
                self._db.bi_grams.bulk_write(updates, ordered=False)
            elif task["type"] == TASK_TAGS_RANK:
                remove_task = False
                updates = []
                for tag in task["data"]:
                    updates.append(
                        UpdateOne(
                            {"_id": tag["_id"]},
                            {"$set": {"processing": TAG_NOT_IN_PROCESSING}},
                        )
                    )
                self._db.tags.bulk_write(updates, ordered=False)
            elif task["type"] == TASK_NER:
                remove_task = False
                updates = []
                for post in task["data"]:
                    updates.append(
                        UpdateOne(
                            {"_id": post["_id"]},
                            {"$set": {"processing": POST_NOT_IN_PROCESSING, "ner": 1}},
                        )
                    )
                self._db.posts.bulk_write(updates, ordered=False)
            elif task["type"] == TASK_POST_GROUPING:
                remove_task = False
                updates = []
                for post in task["data"]:
                    updates.append(
                        UpdateOne(
                            {"_id": post["_id"]},
                            {
                                "$set": {
                                    "processing": POST_NOT_IN_PROCESSING,
                                    "grouping": 1,
                                }
                            },
                        )
                    )
                self._db.posts.bulk_write(updates, ordered=False)
            elif task["type"] == TASK_TAG_CLASSIFICATION:
                remove_task = False
                updates = []
                for tag in task["data"]:
                    updates.append(
                        UpdateOne(
                            {"_id": tag["_id"]},
                            {"$set": {"processing": TAG_NOT_IN_PROCESSING}},
                        )
                    )
                self._db.tags.bulk_write(updates, ordered=False)
            elif task["type"] == TASK_POST_GROUPING_BATCH:
                remove_task = False
                batch_state = task.get("batch", {}) or {}
                batch_status = batch_state.get("status", "")
                updates = []
                for post in task["data"]:
                    if batch_status == "failed":
                        # Batch failed - only reset processing, don't mark as grouped
                        updates.append(
                            UpdateOne(
                                {"_id": post["_id"]},
                                {"$set": {"processing": POST_NOT_IN_PROCESSING}},
                            )
                        )
                    else:
                        updates.append(
                            UpdateOne(
                                {"_id": post["_id"]},
                                {
                                    "$set": {
                                        "processing": POST_NOT_IN_PROCESSING,
                                        "grouping": 1,
                                    }
                                },
                            )
                        )
                if updates:
                    self._db.posts.bulk_write(updates, ordered=False)
            elif task["type"] == TASK_TAG_CLASSIFICATION_BATCH:
                remove_task = False
                updates = []
                for tag in task["data"]:
                    updates.append(
                        UpdateOne(
                            {"_id": tag["_id"]},
                            {"$set": {"processing": TAG_NOT_IN_PROCESSING}},
                        )
                    )
                if updates:
                    self._db.tags.bulk_write(updates, ordered=False)
            if remove_task:
                self.remove_task(task["_id"])
                if not task.get("manual", False):
                    self.add_next_tasks(task["user"]["sid"], task["type"])

            result = True
        except Exception as e:
            result = False
            self._log.error(
                "Can`t finish task %s, type %s. Info: %s",
                task["data"]["_id"],
                task["type"],
                e,
            )

        return result

    def get_current_tasks(self, user_id: str) -> List[dict]:
        try:
            curr = self._db.tasks.find({"user": user_id})
            result = []
            for task in curr:
                result.append(
                    {
                        "id": str(task["_id"]),
                        "type": task["type"],
                        "title": self.get_task_title(task["type"]),
                        "processing": task.get("processing", 0),
                    }
                )

        except Exception as e:
            result = []
            self._log.error("Can`t get user tasks states %s. Info: %s", user_id, e)

        return result

    def get_current_tasks_titles(self, user_id: str) -> Optional[List[str]]:
        try:
            curr = self._db.tasks.find({"user": user_id})
            task_types = set()
            result = []
            for task in curr:
                if task["type"] not in task_types:
                    task_types.add(task["type"])
                    result.append(self.get_task_title(task["type"]))

        except Exception as e:
            result = None
            self._log.error("Can`t get user tasks state %s. Info: %s", user_id, e)

        return result

    def get_tasks_status(self, user_id: str) -> List[dict]:
        status = []
        try:
            curr = self._db.tasks.find({"user": user_id})
            task_types = set()
            for task in curr:
                if task["type"] in task_types:
                    continue
                task_types.add(task["type"])

                info = {
                    "type": task["type"],
                    "title": self.get_task_title(task["type"]),
                    "count": -1,
                }

                if task["type"] == TASK_TAGS:
                    info["count"] = self._db.posts.count_documents(
                        {"owner": user_id, "tags": []}
                    )
                elif task["type"] == TASK_BIGRAMS_RANK:
                    info["count"] = self._db.bi_grams.count_documents(
                        {"owner": user_id, "temperature": 0}
                    )
                elif task["type"] == TASK_TAGS_RANK:
                    info["count"] = self._db.tags.count_documents(
                        {"owner": user_id, "temperature": 0}
                    )
                elif task["type"] == TASK_NER:
                    info["count"] = self._db.posts.count_documents(
                        {"owner": user_id, "ner": {"$exists": False}}
                    )
                elif task["type"] == TASK_POST_GROUPING:
                    info["count"] = self._count_pending_grouping_posts(user_id, task)
                elif task["type"] == TASK_TAG_CLASSIFICATION:
                    info["count"] = self._db.tags.count_documents(
                        {"owner": user_id, "classifications": {"$exists": False}}
                    )
                elif task["type"] == TASK_POST_GROUPING_BATCH:
                    info["count"] = self._count_pending_grouping_posts(user_id, task)
                elif task["type"] == TASK_TAG_CLASSIFICATION_BATCH:
                    info["count"] = self._db.tags.count_documents(
                        {"owner": user_id, "classifications": {"$exists": False}}
                    )

                status.append(info)
        except Exception as e:
            self._log.error("Can`t get user tasks status %s. Info: %s", user_id, e)

        return status

    def get_task_title(self, task_type: int) -> str:
        task_titles = {
            TASK_DOWNLOAD: "Downloading posts from provider",
            TASK_MARK: 'Sync posts "read" state with provider',
            TASK_MARK_TELEGRAM: 'Sync posts "read" state with Telegram',
            TASK_GMAIL_SORT: "Sort Gmail emails by sender domain",
            TASK_TAGS: "Bulding posts tags",
            TASK_WORDS: "",
            TASK_LETTERS: "Buildings first letters dictionary",
            TASK_NER: "Named entity recognition",
            TASK_CLUSTERING: "Posts clusterization",
            TASK_W2V: "Learning Word2Vec (global only)",
            TASK_D2V: "Learning Doc2Vec",
            TASK_FASTTEXT: "Learning FastText (global only)",
            TASK_TAGS_SENTIMENT: "Tags sentiment",
            TASK_TAGS_GROUP: "Tags groups searching",
            TASK_TAGS_COORDS: "Searching geo objects in tags",
            TASK_BIGRAMS_RANK: "Bi-grams ranking",
            TASK_TAGS_RANK: "Tags ranking",
            TASK_CLEAN_BIGRAMS: "Clean bi-grams",
            TASK_POST_GROUPING: "Post grouping (supports scoped reprocess)",
            TASK_TAG_CLASSIFICATION: "Tags classification",
            TASK_POST_GROUPING_BATCH: "Post grouping (batch, supports scoped reprocess)",
            TASK_TAG_CLASSIFICATION_BATCH: "Tags classification (batch)",
            TASK_DELETE_FEEDS: "Delete feeds",
            TASK_POST_GROUPING_CLEANUP: "Post grouping cleanup (supports scoped reprocess)",
            TASK_SNIPPET_CLUSTERING: "Snippet clustering",
        }

        if task_type in task_titles:
            result = task_titles[task_type]
        else:
            result = ""
            self._log.error('Unknow task type "%s"', task_type)

        return result

    def _complete_user_task_if_done(self, owner: str, task_type: int) -> bool:
        user_task = self._db.tasks.find_one({"user": owner, "type": task_type})
        if task_type == TASK_POST_GROUPING:
            pending_count = self._count_pending_grouping_posts(owner, user_task or {})
        elif task_type == TASK_TAG_CLASSIFICATION:
            pending_count = self._db.tags.count_documents(
                {"owner": owner, "classifications": {"$exists": False}}
            )
        else:
            return False

        if pending_count > 0:
            return False

        if not user_task:
            return True

        can_delete = self._can_finalize_completed_task(user_task)

        if can_delete:
            self._db.tasks.delete_one({"_id": user_task["_id"]})
        return can_delete

    def _find_external_user_task(self, owner: str) -> Optional[dict]:
        pipeline = [
            {
                "$match": {
                    "user": owner,
                    "type": {"$in": list(EXTERNAL_WORKER_ALLOWED_TASK_TYPES)},
                    "processing": {"$ne": TASK_FREEZED},
                }
            },
            {"$sample": {"size": 1}},
        ]
        candidates = list(self._db.tasks.aggregate(pipeline))
        if not candidates:
            return None
        return candidates[0]

    def _build_tag_classification_snippets(
        self, owner: str, tag: str, words: List[str]
    ) -> List[Dict[str, Any]]:
        snippets: List[Dict[str, Any]] = []
        max_posts = 2000
        max_snippets = 5000
        processed_posts = 0
        tag_words = set([tag] + words)

        cursor = self._db.posts.find(
            {"owner": owner, "tags": {"$all": [tag]}},
            projection={"lemmas": True, "pid": True},
        )

        for post in cursor:
            if processed_posts >= max_posts or len(snippets) >= max_snippets:
                break

            lemmas_data = post.get("lemmas")
            if not isinstance(lemmas_data, (bytes, bytearray)):
                continue

            try:
                lemmas_text = gzip.decompress(lemmas_data).decode("utf-8", "replace")
            except Exception:
                continue

            if not lemmas_text:
                continue

            words_list = lemmas_text.split()
            tag_indices = [i for i, word in enumerate(words_list) if word in tag_words]
            if not tag_indices:
                continue

            ranges = [(max(0, i - 20), min(len(words_list), i + 21)) for i in tag_indices]
            ranges.sort()

            merged_ranges: List[Tuple[int, int]] = []
            if ranges:
                curr_start, curr_end = ranges[0]
                for next_start, next_end in ranges[1:]:
                    if next_start <= curr_end:
                        curr_end = max(curr_end, next_end)
                    else:
                        merged_ranges.append((curr_start, curr_end))
                        curr_start, curr_end = next_start, next_end
                merged_ranges.append((curr_start, curr_end))

            for start, end in merged_ranges:
                if len(snippets) >= max_snippets:
                    break
                snippets.append(
                    {
                        "pid": post.get("pid"),
                        "snippet": " ".join(words_list[start:end]),
                    }
                )

            processed_posts += 1

        return snippets

    def claim_external_task(
        self, owner: str, worker_token_id: Optional[str] = None
    ) -> Optional[dict]:
        user_task = self._find_external_user_task(owner)
        if not user_task:
            return None

        task_type = user_task["type"]
        now_ts = time.time()
        claim_set: Dict[str, Any] = {"processing": now_ts}
        if worker_token_id:
            claim_set["external_claim_worker_token_id"] = worker_token_id
            claim_set["external_claimed_at"] = now_ts

        if task_type == TASK_POST_GROUPING:
            post = self._find_pending_grouping_post(
                owner,
                user_task,
                extra_query={"processing": POST_NOT_IN_PROCESSING},
                claim_set=claim_set,
            )
            if not post:
                self._complete_user_task_if_done(owner, task_type)
                return None

            content = ""
            title = ""
            try:
                title = post.get("content", {}).get("title", "")
                raw_content = post.get("content", {}).get("content", b"")
                if isinstance(raw_content, (bytes, bytearray)):
                    content = gzip.decompress(raw_content).decode("utf-8", "replace")
                elif isinstance(raw_content, str):
                    content = raw_content
            except Exception:
                content = ""

            return {
                "task_id": str(user_task["_id"]),
                "task_type": task_type,
                "task_title": self.get_task_title(task_type),
                "item": {
                    "post_id": str(post["_id"]),
                    "pid": post.get("pid"),
                    "title": title,
                    "content": content,
                },
            }

        if task_type == TASK_TAG_CLASSIFICATION:
            tag = self._db.tags.find_one_and_update(
                {
                    "owner": owner,
                    "classifications": {"$exists": False},
                    "processing": TAG_NOT_IN_PROCESSING,
                },
                {"$set": claim_set},
            )
            if not tag:
                self._complete_user_task_if_done(owner, task_type)
                return None

            return {
                "task_id": str(user_task["_id"]),
                "task_type": task_type,
                "task_title": self.get_task_title(task_type),
                "item": {
                    "tag_id": str(tag["_id"]),
                    "tag": tag.get("tag", ""),
                    "words": tag.get("words", []),
                    "snippets": self._build_tag_classification_snippets(
                        owner,
                        tag.get("tag", ""),
                        tag.get("words", []),
                    ),
                },
            }

        return None

    def submit_external_task_result(
        self,
        owner: str,
        task_type: int,
        item_id: str,
        success: bool,
        result: Optional[Dict[str, Any]] = None,
        error: str = "",
        worker_token_id: Optional[str] = None,
    ) -> bool:
        if task_type not in EXTERNAL_WORKER_ALLOWED_TASK_TYPES:
            return False

        if not item_id:
            return False

        if result is None:
            result = {}

        try:
            item_object_id = ObjectId(item_id)
        except Exception:
            return False

        submit_ts = time.time()
        submit_audit_set: Dict[str, Any] = {"external_submitted_at": submit_ts}
        if worker_token_id:
            submit_audit_set["external_result_worker_token_id"] = worker_token_id

        if task_type == TASK_POST_GROUPING:
            submit_filter: Dict[str, Any] = {
                "_id": item_object_id,
                "owner": owner,
                "grouping": {"$exists": False},
                "processing": {"$ne": POST_NOT_IN_PROCESSING},
            }
            if worker_token_id:
                submit_filter["external_claim_worker_token_id"] = worker_token_id
            post = self._db.posts.find_one_and_update(
                submit_filter,
                {"$set": {"processing": submit_ts}},
                return_document=ReturnDocument.BEFORE,
            )
            if not post:
                return False

            if success:
                sentences = result.get("sentences")
                groups = result.get("groups")
                if not isinstance(sentences, list) or not isinstance(groups, dict):
                    self._db.posts.update_one(
                        {
                            "_id": item_object_id,
                            "owner": owner,
                            "processing": submit_ts,
                        },
                        {
                            "$set": {
                                "processing": POST_NOT_IN_PROCESSING,
                                "external_error": "Invalid result format",
                                **submit_audit_set,
                            },
                            "$unset": {
                                "external_claim_worker_token_id": "",
                                "external_claimed_at": "",
                            },
                        },
                    )
                    return False

                post_pid = post.get("pid")
                if post_pid is None:
                    self._db.posts.update_one(
                        {
                            "_id": item_object_id,
                            "owner": owner,
                            "processing": submit_ts,
                        },
                        {
                            "$set": {
                                "processing": POST_NOT_IN_PROCESSING,
                                "external_error": "Missing post pid",
                                **submit_audit_set,
                            },
                            "$unset": {
                                "external_claim_worker_token_id": "",
                                "external_claimed_at": "",
                            },
                        },
                    )
                    return False

                post_grouping = RssTagPostGrouping(self._db)
                saved = post_grouping.save_grouped_posts(
                    owner,
                    [str(post_pid)],
                    sentences,
                    groups,
                )
                if not saved:
                    self._db.posts.update_one(
                        {
                            "_id": item_object_id,
                            "owner": owner,
                            "processing": submit_ts,
                        },
                        {
                            "$set": {
                                "processing": POST_NOT_IN_PROCESSING,
                                "external_error": "Failed to save grouping",
                                **submit_audit_set,
                            },
                            "$unset": {
                                "external_claim_worker_token_id": "",
                                "external_claimed_at": "",
                            },
                        },
                    )
                    return False

                self._db.posts.update_one(
                    {
                        "_id": item_object_id,
                        "owner": owner,
                        "processing": submit_ts,
                    },
                    {
                        "$set": {
                            "processing": POST_NOT_IN_PROCESSING,
                            "grouping": 1,
                            **submit_audit_set,
                        },
                        "$unset": {
                            "external_claim_worker_token_id": "",
                            "external_claimed_at": "",
                        },
                    },
                )
                self._complete_user_task_if_done(owner, task_type)
                return True

            self._db.posts.update_one(
                {
                    "_id": item_object_id,
                    "owner": owner,
                    "grouping": {"$exists": False},
                    "processing": submit_ts,
                },
                {
                    "$set": {
                        "processing": POST_NOT_IN_PROCESSING,
                        "external_error": error[:MAX_EXTERNAL_ERROR_LENGTH],
                        **submit_audit_set,
                    },
                    "$unset": {
                        "external_claim_worker_token_id": "",
                        "external_claimed_at": "",
                    },
                },
            )
            return True

        if task_type == TASK_TAG_CLASSIFICATION:
            submit_filter = {
                "_id": item_object_id,
                "owner": owner,
                "classifications": {"$exists": False},
                "processing": {"$ne": TAG_NOT_IN_PROCESSING},
            }
            if worker_token_id:
                submit_filter["external_claim_worker_token_id"] = worker_token_id
            tag = self._db.tags.find_one_and_update(
                submit_filter,
                {"$set": {"processing": submit_ts}},
                return_document=ReturnDocument.BEFORE,
            )
            if not tag:
                return False

            if success:
                classifications = result.get("classifications", [])
                if not isinstance(classifications, list):
                    self._db.tags.update_one(
                        {
                            "_id": item_object_id,
                            "owner": owner,
                            "processing": submit_ts,
                        },
                        {
                            "$set": {
                                "processing": TAG_NOT_IN_PROCESSING,
                                "external_error": "Invalid classifications format",
                                **submit_audit_set,
                            },
                            "$unset": {
                                "external_claim_worker_token_id": "",
                                "external_claimed_at": "",
                            },
                        },
                    )
                    return False

                tags_h = RssTagTags(self._db)
                tags_h.add_classifications(owner, tag.get("tag", ""), classifications)
                self._db.tags.update_one(
                    {
                        "_id": item_object_id,
                        "owner": owner,
                        "processing": submit_ts,
                    },
                    {
                        "$set": {
                            "processing": TAG_NOT_IN_PROCESSING,
                            **submit_audit_set,
                        },
                        "$unset": {
                            "external_claim_worker_token_id": "",
                            "external_claimed_at": "",
                        },
                    },
                )
                self._complete_user_task_if_done(owner, task_type)
                return True

            self._db.tags.update_one(
                {
                    "_id": item_object_id,
                    "owner": owner,
                    "classifications": {"$exists": False},
                    "processing": submit_ts,
                },
                {
                    "$set": {
                        "processing": TAG_NOT_IN_PROCESSING,
                        "external_error": error[:MAX_EXTERNAL_ERROR_LENGTH],
                        **submit_audit_set,
                    },
                    "$unset": {
                        "external_claim_worker_token_id": "",
                        "external_claimed_at": "",
                    },
                },
            )
            return True

        return False

    def freeze_tasks(self, user: dict, type: int) -> Optional[bool]:
        try:
            query = {"user": user["sid"]}
            if type != TASK_ALL:
                query["type"] = type
            self._db.tasks.update_many(
                query, {"$set": {"processing": TASK_FREEZED}}
            )  # TODO: check result?
            result = True
        except Exception as e:
            result = None
            self._log.error(
                "Can`t freeze tasks? user %s, type %s. Info: %s", user["sid"], type, e
            )

        return result

    def unfreeze_tasks(self, user: dict, type: int) -> Optional[bool]:
        try:
            query = {"user": user["sid"]}
            if type != TASK_ALL:
                query["type"] = type
            self._db.tasks.update_many(
                query, {"$set": {"processing": TASK_NOT_IN_PROCESSING}}
            )  # TODO: check result?
            result = True
        except Exception as e:
            result = None
            self._log.error(
                "Can`t freeze tasks? user %s, type %s. Info: %s", user["sid"], type, e
            )

        return result
