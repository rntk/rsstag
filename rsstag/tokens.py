import logging
from typing import Optional, Iterator
from datetime import datetime, timedelta
from hashlib import sha256
import os
from random import randint
from pymongo import MongoClient


class RssTagTokens:
    indexes = ["owner", "token"]

    def __init__(self, db: MongoClient) -> None:
        self._db = db
        self._log = logging.getLogger("tokens")

    def prepare(self) -> None:
        for index in self.indexes:
            try:
                self._db.tokens.create_index(index)
            except Exception as e:
                self._log.warning(
                    "Can`t create index %s. May be already exists. Info: %s", index, e
                )

    def create(self, owner: str, expires_days: int = 30) -> str:
        token = sha256(os.urandom(randint(80, 200))).hexdigest()
        created = datetime.utcnow()
        expires = created + timedelta(days=expires_days)
        
        self._db.tokens.insert_one({
            "token": token,
            "owner": owner,
            "created": created,
            "expires": expires,
        })
        
        return token

    def get_all(self, owner: str) -> Iterator[dict]:
        return self._db.tokens.find({"owner": owner}).sort("created", -1)

    def delete(self, owner: str, token: str) -> bool:
        result = self._db.tokens.delete_one({"owner": owner, "token": token})
        return result.deleted_count > 0

    def validate(self, token: str) -> Optional[dict]:
        token_doc = self._db.tokens.find_one({"token": token})
        if not token_doc:
            return None
        
        if token_doc["expires"] < datetime.utcnow():
            return None
        
        return token_doc
