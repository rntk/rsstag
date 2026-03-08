import logging
import time
from typing import Optional
from bson import ObjectId
from pymongo import MongoClient, DESCENDING


class RssTagChats:
    def __init__(self, db: MongoClient) -> None:
        self._db = db
        self._log = logging.getLogger("chats")

    def prepare(self) -> None:
        try:
            self._db.chats.create_index("owner")
        except Exception as e:
            self._log.warning("Can't create index owner. Info: %s", e)
        try:
            self._db.chats.create_index([("owner", 1), ("updated_at", DESCENDING)])
        except Exception as e:
            self._log.warning("Can't create compound index. Info: %s", e)

    def create(self, owner: str, title: str, context: Optional[dict] = None) -> Optional[str]:
        try:
            now = time.time()
            doc = {
                "owner": owner,
                "title": title,
                "created_at": now,
                "updated_at": now,
                "forked_from": None,
                "context": context or {"type": "empty", "text": "", "sentences": [], "post_ids": [], "source_url": ""},
                "messages": [],
            }
            result = self._db.chats.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            self._log.error("Error creating chat: %s", e)
            return None

    def get_by_id(self, owner: str, chat_id: str) -> Optional[dict]:
        try:
            doc = self._db.chats.find_one({"_id": ObjectId(chat_id), "owner": owner})
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except Exception as e:
            self._log.error("Error getting chat %s: %s", chat_id, e)
            return None

    def list_chats(self, owner: str, limit: int = 50, skip: int = 0) -> list:
        try:
            cursor = (
                self._db.chats.find(
                    {"owner": owner},
                    projection={"_id": 1, "title": 1, "updated_at": 1, "created_at": 1, "messages": {"$slice": 0}},
                )
                .sort("updated_at", DESCENDING)
                .skip(skip)
                .limit(limit)
            )
            results = []
            for doc in cursor:
                results.append({
                    "_id": str(doc["_id"]),
                    "title": doc.get("title", ""),
                    "updated_at": doc.get("updated_at", 0),
                    "created_at": doc.get("created_at", 0),
                    "message_count": 0,
                })
            return results
        except Exception as e:
            self._log.error("Error listing chats: %s", e)
            return []

    def list_chats_with_count(self, owner: str, limit: int = 50, skip: int = 0) -> list:
        try:
            pipeline = [
                {"$match": {"owner": owner}},
                {"$addFields": {"message_count": {"$size": {"$ifNull": ["$messages", []]}}}},
                {"$project": {"_id": 1, "title": 1, "updated_at": 1, "created_at": 1, "message_count": 1}},
                {"$sort": {"updated_at": DESCENDING}},
                {"$skip": skip},
                {"$limit": limit},
            ]
            results = []
            for doc in self._db.chats.aggregate(pipeline):
                doc["_id"] = str(doc["_id"])
                results.append(doc)
            return results
        except Exception as e:
            self._log.error("Error listing chats with count: %s", e)
            return []

    def add_message(self, owner: str, chat_id: str, role: str, content: str) -> bool:
        try:
            now = time.time()
            message = {"role": role, "content": content, "timestamp": now}
            result = self._db.chats.update_one(
                {"_id": ObjectId(chat_id), "owner": owner},
                {"$push": {"messages": message}, "$set": {"updated_at": now}},
            )
            return result.modified_count > 0
        except Exception as e:
            self._log.error("Error adding message to chat %s: %s", chat_id, e)
            return False

    def rename(self, owner: str, chat_id: str, title: str) -> bool:
        try:
            result = self._db.chats.update_one(
                {"_id": ObjectId(chat_id), "owner": owner},
                {"$set": {"title": title, "updated_at": time.time()}},
            )
            return result.modified_count > 0
        except Exception as e:
            self._log.error("Error renaming chat %s: %s", chat_id, e)
            return False

    def delete(self, owner: str, chat_id: str) -> bool:
        try:
            result = self._db.chats.delete_one({"_id": ObjectId(chat_id), "owner": owner})
            return result.deleted_count > 0
        except Exception as e:
            self._log.error("Error deleting chat %s: %s", chat_id, e)
            return False

    def fork(self, owner: str, chat_id: str, message_index: int) -> Optional[str]:
        try:
            source = self._db.chats.find_one({"_id": ObjectId(chat_id), "owner": owner})
            if not source:
                return None
            now = time.time()
            messages = source.get("messages", [])
            forked_messages = messages[: message_index + 1]
            new_title = source.get("title", "Chat") + " (fork)"
            doc = {
                "owner": owner,
                "title": new_title,
                "created_at": now,
                "updated_at": now,
                "forked_from": {"chat_id": chat_id, "message_index": message_index},
                "context": source.get("context", {"type": "empty", "text": "", "sentences": [], "post_ids": [], "source_url": ""}),
                "messages": forked_messages,
            }
            result = self._db.chats.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            self._log.error("Error forking chat %s: %s", chat_id, e)
            return None

    def update_context(self, owner: str, chat_id: str, context: dict) -> bool:
        try:
            result = self._db.chats.update_one(
                {"_id": ObjectId(chat_id), "owner": owner},
                {"$set": {"context": context, "updated_at": time.time()}},
            )
            return result.modified_count > 0
        except Exception as e:
            self._log.error("Error updating context for chat %s: %s", chat_id, e)
            return False
