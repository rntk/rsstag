import os
import logging
import time
from datetime import datetime
from random import randint
from typing import Optional
from hashlib import sha256
from pymongo import MongoClient


TELEGRAM_CODE_FIELD = "telegram_code"

class RssTagUsers:
    indexes = ["sid"]

    def __init__(self, db: MongoClient) -> None:
        self._db = db
        self._log = logging.getLogger("users")
        self._settings = {
            "only_unread": True,
            "tags_on_page": 100,
            "posts_on_page": 30,
            "hot_tags": False,
            "similar_posts": True,
            "context_n": 5,
            "telegram_limit": 1000
        }

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self._db.users.create_index(index)
            except Exception as e:
                self._log.warning(
                    "Can`t create index %s. May be already exists. Info: %s", index, e
                )

    def hash_login_password(self, login: str, password: str) -> str:
        return sha256((login + password).encode("utf-8")).hexdigest()

    def create_user(
        self, login: str, password: str, token: str, provider: str
    ) -> Optional[str]:
        lp = self.hash_login_password(login, password)
        sid = sha256(os.urandom(randint(80, 200))).hexdigest()
        created = datetime.utcnow()
        user = {
            "sid": sid,
            "token": token,
            "provider": provider,
            "settings": self._settings,
            "ready": False,
            "message": 'Click on "Refresh posts" to start downloading data',
            "in_queue": False,
            "created": created,
            "lp": lp,
            "retoken": False,
            "w2v": "{}_{}.w2v".format(created.timestamp(), randint(0, 999999))
        }
        if provider == "telegram":
            user["phone"] = password
            user["telegram_channel"] = login

        if provider == "textfile":
            user["text_file"] = login

        self._db.users.insert_one(user)

        return sid

    def update_by_sid(self, sid: str, data: dict) -> Optional[bool]:
        """
        Update users fields
        TODO: add fields validation, check result of update operation
        """
        self._db.users.update_one({"sid": sid}, {"$set": data})

        return True

    def get_by_login_password(self, login: str, password: str) -> Optional[dict]:
        lp_hash = self.hash_login_password(login, password)

        return self._db.users.find_one({"lp": lp_hash})

    def get_by_sid(self, sid: str) -> Optional[dict]:
        return self._db.users.find_one({"sid": sid})

    def get_by_id(self, user_id: str) -> Optional[dict]:
        return self._db.users.find_one({"_id": user_id})

    def get_validated_settings(self, settings: dict) -> Optional[dict]:
        new_settings = {}
        try:
            for k, v in settings.items():
                if k in self._settings:
                    old_value = self._settings[k]
                    if isinstance(old_value, int):
                        new_settings[k] = int(v)
                    elif isinstance(old_value, float):
                        new_settings[k] = float(v)
                    elif isinstance(old_value, bool):
                        new_settings[k] = bool(v)
                    else:
                        raise ValueError("Bad settings type")
            result = new_settings
        except Exception as e:
            result = None
            self._log.warning("Bad settings. Info: %s", e)

        return result

    def update_settings(self, sid: str, settings: dict) -> Optional[bool]:
        field = "settings"
        for_update = {}
        for k, v in settings.items():
            for_update[field + "." + k] = v
        self._db.users.update_one({"sid": sid}, {"$set": for_update})

        return True

class TelegramCode:
    def __init__(self, db: MongoClient, sid: str):
        self._db = db
        self._sid = sid

    def get_code(self, phone: str) -> str:
        users_h = RssTagUsers(self._db)
        user = users_h.get_by_sid(self._sid)
        field_name = TELEGRAM_CODE_FIELD
        if not user:
            raise Exception("User not found: " + self._sid)
        users_h.update_by_sid(self._sid, {field_name: ""})
        while True:
            user = users_h.get_by_sid(self._sid)
            if not user:
                raise Exception("User not found: " + self._sid)
            if field_name not in user:
                raise Exception("User field not '{}' found not found: {}".format(field_name, self._sid))
            if user[field_name] == "":
                time.sleep(2)
                continue

            return user[field_name]

        return ""