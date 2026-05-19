import os
import logging
import time
from datetime import datetime, timezone
from random import randint
from typing import Optional, Dict
from hashlib import sha256
from threading import Lock
from pymongo import MongoClient

from rsstag.providers.providers import TELEGRAM, TEXT_FILE, GMAIL, X

TELEGRAM_CODE_FIELD = "telegram_code"
TELEGRAM_PASSWORD_FIELD = "telegram_password"

# In-memory storage for transient Telegram 2FA passwords.
# Keyed by user sid; cleared immediately after TDLib consumes the password.
_tg_password_store: Dict[str, str] = {}
_tg_password_lock = Lock()

# In-memory flag: signals that the frontend should prompt the user for a password.
# Set when TDLib enters authorizationStateWaitPassword; cleared when password is consumed.
_tg_password_prompt: Dict[str, bool] = {}
_tg_prompt_lock = Lock()

# In-memory flag: signals that the frontend should prompt the user for an auth code.
# Set when TDLib enters authorizationStateWaitCode; cleared when the code is consumed.
_tg_code_prompt: Dict[str, bool] = {}
_tg_code_prompt_lock = Lock()


def set_telegram_password(sid: str, password: str) -> None:
    with _tg_password_lock:
        _tg_password_store[sid] = password
    with _tg_prompt_lock:
        _tg_password_prompt.pop(sid, None)


def get_and_clear_telegram_password(sid: str) -> str:
    with _tg_password_lock:
        return _tg_password_store.pop(sid, "")


def request_telegram_password(sid: str) -> None:
    """Signal the frontend that TDLib is waiting for a 2FA password."""
    with _tg_prompt_lock:
        _tg_password_prompt[sid] = True


def check_telegram_password_prompt(sid: str) -> bool:
    with _tg_prompt_lock:
        return _tg_password_prompt.get(sid, False)


def clear_telegram_password_prompt(sid: str) -> None:
    with _tg_prompt_lock:
        _tg_password_prompt.pop(sid, None)


def request_telegram_code(sid: str) -> None:
    """Signal the frontend that TDLib is waiting for an auth code."""
    with _tg_code_prompt_lock:
        _tg_code_prompt[sid] = True


def check_telegram_code_prompt(sid: str) -> bool:
    with _tg_code_prompt_lock:
        return _tg_code_prompt.get(sid, False)


def clear_telegram_code_prompt(sid: str) -> None:
    with _tg_code_prompt_lock:
        _tg_code_prompt.pop(sid, None)


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
            "telegram_limit": 1000,
            "x_max_results": 50,
            "batch_llm": "openai",
            "worker_llm": "llamacpp",
            "realtime_llm": "llamacpp",
            "context_filter": {},
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

    def create_account(self, username: str, password: str) -> Optional[str]:
        lp = self.hash_login_password(username, password)
        sid = sha256(os.urandom(randint(80, 200))).hexdigest()
        created = datetime.now(timezone.utc)
        user = {
            "sid": sid,
            "username": username,
            "provider": "",
            "providers": {},
            "settings": self._settings,
            "message": 'Click on "Refresh posts" to start downloading data',
            "in_queue": False,
            "created": created,
            "lp": lp,
            "retoken": False,
            "w2v": "{}_{}.w2v".format(created.timestamp(), randint(0, 999999)),
            "fasttext": "{}_{}.fasttext".format(
                created.timestamp(), randint(0, 999999)
            ),
        }
        self._db.users.insert_one(user)

        return sid

    def create_user(
        self, login: str, password: str, token: str, provider: str
    ) -> Optional[str]:
        """Legacy helper to create an account and attach a provider."""
        sid = self.create_account(login, password)
        if sid:
            self.add_provider(
                sid,
                provider,
                self.build_provider_data(login, password, token, provider),
            )
        return sid

    def build_provider_data(
        self, login: str, password: str, token: str, provider: str
    ) -> dict:
        data = {"login": login, "token": token, "retoken": False}
        if provider == TELEGRAM:
            data["phone"] = password
            data["telegram_channel"] = login
        if provider == TEXT_FILE:
            data["text_file"] = login
        if provider in (GMAIL, X):
            data["login"] = login
        return data

    def add_provider(self, sid: str, provider: str, data: dict) -> Optional[bool]:
        update = {f"providers.{provider}": data}
        self._db.users.update_one({"sid": sid}, {"$set": update})
        return True

    def update_provider(self, sid: str, provider: str, data: dict) -> Optional[bool]:
        update = {f"providers.{provider}.{k}": v for k, v in data.items()}
        self._db.users.update_one({"sid": sid}, {"$set": update})
        return True

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

    def get_by_username(self, username: str) -> Optional[dict]:
        return self._db.users.find_one({"username": username})

    def get_by_provider_login(self, provider: str, login: str) -> Optional[dict]:
        return self._db.users.find_one({f"providers.{provider}.login": login})

    def get_provider_entry(self, user: dict, provider: str) -> Optional[dict]:
        providers = user.get("providers", {})
        entry = providers.get(provider)
        if entry:
            return entry
        if user.get("provider") == provider:
            legacy = {
                "login": user.get("login", ""),
                "token": user.get("token", ""),
                "retoken": user.get("retoken", False),
            }
            if provider == TELEGRAM:
                legacy["phone"] = user.get("phone", "")
                legacy["telegram_channel"] = user.get("telegram_channel", "")
            if provider == TEXT_FILE:
                legacy["text_file"] = user.get("text_file", "")
            if provider == GMAIL:
                legacy["refresh_token"] = user.get("refresh_token", "")
            if provider == X:
                legacy["refresh_token"] = user.get("refresh_token", "")
                legacy["access_token"] = user.get("access_token", "")
                legacy["x_user_id"] = user.get("x_user_id", "")
                legacy["x_username"] = user.get("x_username", "")
            return legacy
        return None

    def get_provider_user(self, user: dict, provider: str) -> Optional[dict]:
        entry = self.get_provider_entry(user, provider)
        if not entry:
            return None
        provider_user = dict(user)
        provider_user.update(entry)
        provider_user["provider"] = provider
        return provider_user

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
                    if isinstance(old_value, bool):
                        new_settings[k] = bool(v)
                    elif isinstance(old_value, int):
                        new_settings[k] = int(v)
                    elif isinstance(old_value, float):
                        new_settings[k] = float(v)
                    elif isinstance(old_value, str):
                        new_settings[k] = str(v)
                    elif isinstance(old_value, dict):
                        new_settings[k] = v
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


class TelegramAuthData:
    def __init__(self, db: MongoClient, sid: str):
        self._db = db
        self._sid = sid

    def clear_code(self) -> None:
        """Remove any previously stored code so stale values aren't reused."""
        users_h = RssTagUsers(self._db)
        users_h.update_by_sid(self._sid, {TELEGRAM_CODE_FIELD: ""})

    def get_code(self, phone: str) -> str:
        users_h = RssTagUsers(self._db)
        user = users_h.get_by_sid(self._sid)
        field_name = TELEGRAM_CODE_FIELD
        if not user:
            raise Exception("User not found: " + self._sid)

        # If a code was already entered before we started polling, use it
        # immediately to avoid losing it in a race condition.
        existing_code = user.get(field_name, "")
        if existing_code:
            users_h.update_by_sid(self._sid, {field_name: ""})
            return existing_code

        # Signal the UI that TDLib is actively waiting for a code.
        request_telegram_code(self._sid)
        try:
            users_h.update_by_sid(self._sid, {field_name: ""})
            while True:
                user = users_h.get_by_sid(self._sid)
                if not user:
                    raise Exception("User not found: " + self._sid)
                code = user.get(field_name, "")
                if code == "":
                    time.sleep(2)
                    continue

                users_h.update_by_sid(self._sid, {field_name: ""})
                return code
        finally:
            clear_telegram_code_prompt(self._sid)

    def get_password(self, phone: str) -> str:
        # Signal the frontend that TDLib is waiting for a 2FA password.
        request_telegram_password(self._sid)
        # Password is stored transiently in memory, not persisted to the database.
        # If not available yet, poll until the web UI sets it.
        while True:
            pwd = get_and_clear_telegram_password(self._sid)
            if pwd:
                return pwd
            time.sleep(2)

        return ""
