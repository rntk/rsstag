import uuid
import json
import logging
from typing import Dict, List, Any, Optional
from pymongo import MongoClient
from pymongo.database import Database


class DBHelper:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 27017,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client = MongoClient(
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
        )
        self.test_dbs: List[str] = []

    def create_test_db(self) -> Database:
        db_name = f"rsstag_test_{uuid.uuid4().hex}"
        self.test_dbs.append(db_name)
        return self.client[db_name]

    def drop_test_db(self, db: Database):
        if db.name in self.test_dbs:
            self.client.drop_database(db.name)
            self.test_dbs.remove(db.name)

    def init_db_from_dict(self, db: Database, data: Dict[str, List[Dict[str, Any]]]):
        for collection_name, documents in data.items():
            if documents:
                db[collection_name].insert_many(documents)

    def init_db_from_json(self, db: Database, file_path: str):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.init_db_from_dict(db, data)
        except Exception as e:
            logging.error(f"Failed to load DB data from {file_path}: {e}")
            raise

    def close(self):
        self.client.close()

    def teardown_all(self):
        for db_name in list(self.test_dbs):
            self.client.drop_database(db_name)
        self.test_dbs = []
