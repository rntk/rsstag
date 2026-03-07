import socket
import tempfile
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from configparser import ConfigParser
from pymongo.database import Database

from tests.db_utils import DBHelper


def create_worker_test_config(
    db_host: str,
    db_port: int,
    db_name: str,
    tmp_dir: str,
) -> str:
    """Write a worker-compatible config file and return its path."""
    config: ConfigParser = ConfigParser()
    config["settings"] = {
        "host": "127.0.0.1",
        "host_name": "127.0.0.1:8885",
        "port": "8885",
        "templates": "default",
        "downloaders_count": "1",
        "workers_count": "2",
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
        "log_file": f"{tmp_dir}/app.log",
        "web_log_file": f"{tmp_dir}/web.log",
        "worker_log_file": f"{tmp_dir}/worker.log",
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

    config_path: str = f"{tmp_dir}/test_worker.conf"
    with open(config_path, "w", encoding="utf-8") as config_file:
        config.write(config_file)
    return config_path


def create_mock_providers() -> Dict[str, MagicMock]:
    """Return a provider mapping suitable for ProviderWorker tests."""
    return {
        "bazqux": MagicMock(name="bazqux_provider"),
        "telegram": MagicMock(name="telegram_provider"),
        "textfile": MagicMock(name="textfile_provider"),
        "gmail": MagicMock(name="gmail_provider"),
    }


def seed_task(db: Database, task_type: int, user: str, **kwargs: Any) -> Dict[str, Any]:
    """Insert a task document and return the stored row."""
    task: Dict[str, Any] = {
        "user": user,
        "type": task_type,
        "processing": 0,
        "manual": kwargs.pop("manual", True),
    }
    task.update(kwargs)
    inserted_id = db.tasks.insert_one(task).inserted_id
    task["_id"] = inserted_id
    return task


class MongoWorkerTestCase(unittest.TestCase):
    """Base class for DB-backed worker tests with isolated Mongo databases."""

    db_helper: DBHelper
    db: Database
    config_path: str
    _tmp_dir: tempfile.TemporaryDirectory[str]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        try:
            with socket.create_connection(("127.0.0.1", 8765), timeout=1):
                pass
        except OSError as exc:
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for worker tests: {exc}"
            )

        cls.db_helper = DBHelper(port=8765)
        try:
            cls.db_helper.client.admin.command("ping")
        except Exception as exc:
            cls.db_helper.close()
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for worker tests: {exc}"
            )

        cls.db = cls.db_helper.create_test_db()
        cls._tmp_dir = tempfile.TemporaryDirectory()
        cls.config_path = create_worker_test_config(
            db_host=cls.db_helper.host,
            db_port=cls.db_helper.port,
            db_name=cls.db.name,
            tmp_dir=cls._tmp_dir.name,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        db: Database | None = getattr(cls, "db", None)
        db_helper: DBHelper | None = getattr(cls, "db_helper", None)
        if db is not None and db_helper is not None:
            db_helper.drop_test_db(db)
            db_helper.close()

        tmp_dir: tempfile.TemporaryDirectory[str] | None = getattr(cls, "_tmp_dir", None)
        if tmp_dir is not None:
            tmp_dir.cleanup()

        super().tearDownClass()
