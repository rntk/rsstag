import os
import socket
import tempfile
import unittest
from configparser import ConfigParser
from pathlib import Path
from typing import Any, Optional

from pymongo.database import Database
from werkzeug.test import Client
from werkzeug.wrappers import Response

from rsstag.web.app import RSSTagApplication
from rsstag.web.routes import RSSTagRoutes
from tests.db_utils import DBHelper


def create_test_config(
    db_host: str,
    db_port: int,
    db_name: str,
    tmp_dir: str,
) -> str:
    """Write a test config file with all sections app init currently requires."""
    config: ConfigParser = ConfigParser()
    config["settings"] = {
        "host": "127.0.0.1",
        "host_name": "127.0.0.1:8885",
        "port": "8885",
        "templates": "default",
        "downloaders_count": "1",
        "workers_count": "1",
        "providers": "bazqux,telegram,gmail,textfile",
        "db_host": db_host,
        "db_port": str(db_port),
        "db_login": "",
        "db_password": "",
        "db_name": db_name,
        "user_ttl": "60",
        "version": "test",
        "support": "test-support",
        "log_level": "info",
        "log_file": os.path.join(tmp_dir, "app.log"),
        "web_log_file": os.path.join(tmp_dir, "web.log"),
        "worker_log_file": os.path.join(tmp_dir, "worker.log"),
        "post_grouping_batch_lines_limit": "0",
        "speech_dir": tmp_dir,
        "w2v_dir": tmp_dir,
        "fasttext_dir": tmp_dir,
        "no_category_name": "NotCategorized",
        "sentilex": "./data/rusentilex.txt",
        "lilu_wordnet": "./data/wordnet/lilu.fcim.utm.md",
    }
    config["yandex"] = {
        "speach_key": "",
        "speech_host": "tts.voicetech.yandex.net",
        "geocode_key": "",
    }
    config["bazqux"] = {"api_host": "www.bazqux.com"}
    config["telegram"] = {
        "app_id": "1",
        "app_hash": "hash",
        "encryption_key": "test-key",
        "db_dir": tmp_dir,
    }
    config["gmail"] = {
        "client_id": "",
        "client_secret": "",
        "mark_label": "rsstag_mark",
    }
    config["openai"] = {
        "token": "",
        "model": "gpt-5-mini",
        "batch_model": "gpt-5-mini",
        "batch_host": "",
    }
    config["anthropic"] = {"token": ""}
    config["llamacpp"] = {"host": "http://127.0.0.1:8080"}
    config["groqcom"] = {"host": "https://api.groq.com", "token": ""}
    config["cerebras"] = {"token": "", "model": "gpt-oss-120b"}
    config["nebius"] = {
        "token": "",
        "model": "Qwen/Qwen3-235B-A22B",
        "batch_model": "Qwen/Qwen3-235B-A22B",
        "batch_host": "",
    }

    config_path: str = os.path.join(tmp_dir, "test_web.conf")
    with open(config_path, "w", encoding="utf-8") as config_file:
        config.write(config_file)

    return config_path


def get_route_endpoints() -> set[str]:
    """Return all endpoint names currently exposed by the Werkzeug route map."""
    route_map = RSSTagRoutes("localhost").get_werkzeug_routes()
    return {rule.endpoint for rule in route_map.iter_rules()}


class MongoWebTestCase(unittest.TestCase):
    """Base class for DB-backed web tests using an isolated Mongo database."""

    db_helper: DBHelper
    test_db: Database
    config_path: str
    app: RSSTagApplication
    client: Client
    _tmp_dir: tempfile.TemporaryDirectory[str]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        try:
            with socket.create_connection(("127.0.0.1", 8765), timeout=1):
                pass
        except OSError as exc:
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for web integration tests: {exc}"
            )

        cls.db_helper = DBHelper(port=8765)
        try:
            cls.db_helper.client.admin.command("ping")
        except Exception as exc:
            cls.db_helper.close()
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for web integration tests: {exc}"
            )

        cls.test_db = cls.db_helper.create_test_db()
        cls._tmp_dir = tempfile.TemporaryDirectory()
        cls.config_path = create_test_config(
            db_host=cls.db_helper.host,
            db_port=cls.db_helper.port,
            db_name=cls.test_db.name,
            tmp_dir=cls._tmp_dir.name,
        )
        cls.app = RSSTagApplication(cls.config_path)
        cls.client = Client(cls.app.set_response, Response)

    @classmethod
    def tearDownClass(cls) -> None:
        app: Optional[RSSTagApplication] = getattr(cls, "app", None)
        if app is not None:
            app.close()

        test_db: Optional[Database] = getattr(cls, "test_db", None)
        db_helper: Optional[DBHelper] = getattr(cls, "db_helper", None)
        if test_db is not None and db_helper is not None:
            db_helper.drop_test_db(test_db)
            db_helper.close()

        tmp_dir: Optional[tempfile.TemporaryDirectory[str]] = getattr(cls, "_tmp_dir", None)
        if tmp_dir is not None:
            tmp_dir.cleanup()

        super().tearDownClass()

    @staticmethod
    def get_project_root() -> Path:
        return Path(__file__).resolve().parent.parent

    @classmethod
    def build_client(cls) -> Client:
        return Client(cls.app.set_response, Response)
