import os
import logging
from datetime import datetime
from random import randint
from typing import Optional
from hashlib import sha256
from pymongo import MongoClient

class RssTagUsers:
    indexes = ['sid']
    def __init__(self, db: MongoClient) -> None:
        self._db = db
        self._log = logging.getLogger('users')
        self._settings = {
            'only_unread': True,
            'tags_on_page': 100,
            'posts_on_page': 30,
            'hot_tags': False,
            'similar_posts': True
        }

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self._db.users.create_index(index)
            except Exception as e:
                self._log.warning('Can`t create index %s. May be already exists. Info: %s', index, e)

    def hash_login_password(self, login: str, password: str) -> str:
        return sha256((login + password).encode('utf-8')).hexdigest()

    def create_user(self, login: str, password: str, token: str, provider: str) -> Optional[str]:
        lp = self.hash_login_password(login, password)
        sid = sha256(os.urandom(randint(80, 200))).hexdigest()
        user = {
            'sid': sid,
            'token': token,
            'provider': provider,
            'letter': '',
            'page': '1',
            'settings': self._settings,
            'ready': False,
            'message': 'Click on "Refresh posts" to start downloading data',
            'in_queue':False,
            'created': datetime.utcnow(),
            'lp': lp,
            'retoken': False
        }
        if provider == "telegram":
            user["phone"] = password
            user["telegram_channel"] = login
            user["telegram_limit"] = 5000
        try:
            self._db.users.insert_one(user)
            result = sid
        except Exception as e:
            result = None
            self._log.error('Can`t create user. Info: %s', e)

        return result

    def update_by_sid(self, sid: str, data: dict) -> Optional[bool]:
        """
        Update users fields
        TODO: add fields validation, check result of update operation
        """
        try:
            self._db.users.update_one({'sid': sid}, {'$set': data})
            result = True
        except Exception as e:
            result = None
            self._log.error('Can`t update user %s. Info: %s', sid, e)

        return result

    def get_by_login_password(self, login: str, password: str) -> Optional[dict]:
        lp_hash = self.hash_login_password(login, password)
        try:
            user = self._db.users.find_one({'lp': lp_hash})
            if user:
                result = user
            else:
                result = {}
        except Exception as e:
            result = None
            self._log.error('Can`t find user by hash. %s', e)

        return result

    def get_by_sid(self, sid: str) -> Optional[dict]:
        try:
            user = self._db.users.find_one({'sid': sid})
            if user:
                result = user
            else:
                result = {}
        except Exception as e:
            result = None
            self._log.error('Can`t get user by sid "%s". Info: %s', sid, e)

        return result

    def get_by_id(self, user_id: str) -> Optional[dict]:
        try:
            user = self._db.users.find_one({'_id': user_id})
            if user:
                result = user
            else:
                result = {}
        except Exception as e:
            result = None
            self._log.error('Can`t get user by id "%s". Info: %s', user_id, e)

        return result

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
                        raise ValueError('Bad settings type')
            result = new_settings
        except Exception as e:
            result = None
            self._log.warning('Bad settings. Info: %s', e)

        return result

    def update_settings(self, sid: str, settings: dict) -> Optional[bool]:
        field = 'settings'
        for_update = {}
        try:#TODO: check result of update operation
            for k, v in settings.items():
                for_update[field + '.' + k] = v
            self._db.users.update_one({'sid': sid}, {'$set': for_update})
            result = True
        except Exception as e:
            result = None
            self._log.error('Can`t updat settings for user %s. Info: %s', sid, e)

        return result
