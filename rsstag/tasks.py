import logging
import time
import gzip
from typing import Optional, List, Dict, Any, Set, Tuple
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

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self._db.tasks.create_index(index)
            except Exception as e:
                self._log.warning(
                    "Can`t create index %s. May be already exists. Info: %s", index, e
                )

    def add_task(self, data: dict, manual: bool = True):
        result = True
        if data and "type" in data:
            try:
                if data["type"] == TASK_DOWNLOAD:  # TODO: check insertion results
                    self._db.tasks.update_one(
                        {"user": data["user"]},
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
                        can_delete = False
                        if user_task.get("manual", False):
                            can_delete = True
                        elif self.add_next_tasks(
                            task["user"]["sid"], user_task["type"]
                        ):
                            can_delete = True
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
                    can_delete = False
                    if user_task.get("manual", False):
                        can_delete = True
                    elif self.add_next_tasks(task["user"]["sid"], user_task["type"]):
                        can_delete = True
                    if can_delete:
                        self._db.tasks.delete_one({"_id": user_task["_id"]})
            elif user_task["type"] == TASK_POST_GROUPING:
                data = []
                # Get posts that need grouping
                ps = self._db.posts.find(
                    {
                        "owner": task["user"]["sid"],
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
                        {"owner": task["user"]["sid"], "grouping": {"$exists": False}}
                    )
                    if psc == 0:
                        can_delete = False
                        if user_task.get("manual", False):
                            can_delete = True
                        elif self.add_next_tasks(
                            task["user"]["sid"], user_task["type"]
                        ):
                            can_delete = True
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
                unlock_task = True
                batch_state = user_task.get("batch", {})
                batch_ids = batch_state.get("item_ids", [])
                ids = []
                if batch_ids:
                    ids = [
                        ObjectId(tag_id) if isinstance(tag_id, str) else tag_id
                        for tag_id in batch_ids
                    ]
                    ps = self._db.posts.find({"_id": {"$in": ids}})
                    for p in ps:
                        data.append(p)
                else:
                    ps = self._db.posts.find(
                        {
                            "owner": task["user"]["sid"],
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
                                "owner": task["user"]["sid"],
                                "grouping": {"$exists": False},
                            }
                        )
                        if psc == 0:
                            can_delete = False
                            if user_task.get("manual", False):
                                can_delete = True
                            elif self.add_next_tasks(
                                task["user"]["sid"], user_task["type"]
                            ):
                                can_delete = True
                            if can_delete:
                                self._db.tasks.delete_one({"_id": user_task["_id"]})
                                unlock_task = False
                if unlock_task:
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
                    can_delete = False
                    if user_task.get("manual", False):
                        can_delete = True
                    elif self.add_next_tasks(task["user"]["sid"], user_task["type"]):
                        can_delete = True
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
                        can_delete = False
                        if user_task.get("manual", False):
                            can_delete = True
                        elif self.add_next_tasks(
                            task["user"]["sid"], user_task["type"]
                        ):
                            can_delete = True
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
                            can_delete = False
                            if user_task.get("manual", False):
                                can_delete = True
                            elif self.add_next_tasks(
                                task["user"]["sid"], user_task["type"]
                            ):
                                can_delete = True
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
                        can_delete = False
                        if user_task.get("manual", False):
                            can_delete = True
                        elif self.add_next_tasks(
                            task["user"]["sid"], user_task["type"]
                        ):
                            can_delete = True
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
                    info["count"] = self._db.posts.count_documents(
                        {"owner": user_id, "grouping": {"$exists": False}}
                    )
                elif task["type"] == TASK_TAG_CLASSIFICATION:
                    info["count"] = self._db.tags.count_documents(
                        {"owner": user_id, "classifications": {"$exists": False}}
                    )
                elif task["type"] == TASK_POST_GROUPING_BATCH:
                    info["count"] = self._db.posts.count_documents(
                        {"owner": user_id, "grouping": {"$exists": False}}
                    )
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
            TASK_W2V: "Learning Word2Vec",
            TASK_D2V: "Learning Doc2Vec",
            TASK_FASTTEXT: "Learning FastText",
            TASK_TAGS_SENTIMENT: "Tags sentiment",
            TASK_TAGS_GROUP: "Tags groups searching",
            TASK_TAGS_COORDS: "Searching geo objects in tags",
            TASK_BIGRAMS_RANK: "Bi-grams ranking",
            TASK_TAGS_RANK: "Tags ranking",
            TASK_CLEAN_BIGRAMS: "Clean bi-grams",
            TASK_POST_GROUPING: "Post grouping",
            TASK_TAG_CLASSIFICATION: "Tags classification",
            TASK_POST_GROUPING_BATCH: "Post grouping (batch)",
            TASK_TAG_CLASSIFICATION_BATCH: "Tags classification (batch)",
            TASK_DELETE_FEEDS: "Delete feeds",
        }

        if task_type in task_titles:
            result = task_titles[task_type]
        else:
            result = ""
            self._log.error('Unknow task type "%s"', task_type)

        return result

    def _complete_user_task_if_done(self, owner: str, task_type: int) -> bool:
        if task_type == TASK_POST_GROUPING:
            pending_count = self._db.posts.count_documents(
                {"owner": owner, "grouping": {"$exists": False}}
            )
        elif task_type == TASK_TAG_CLASSIFICATION:
            pending_count = self._db.tags.count_documents(
                {"owner": owner, "classifications": {"$exists": False}}
            )
        else:
            return False

        if pending_count > 0:
            return False

        user_task = self._db.tasks.find_one({"user": owner, "type": task_type})
        if not user_task:
            return True

        can_delete = False
        if user_task.get("manual", False):
            can_delete = True
        elif self.add_next_tasks(owner, task_type):
            can_delete = True

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
            post = self._db.posts.find_one_and_update(
                {
                    "owner": owner,
                    "grouping": {"$exists": False},
                    "processing": POST_NOT_IN_PROCESSING,
                },
                {"$set": claim_set},
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
