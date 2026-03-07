import logging
import socket
import tempfile
import unittest
from typing import Any, Dict, Optional
from unittest.mock import patch

from rsstag.workers.dispatcher import RSSTagWorkerDispatcher, worker
from rsstag.workers_db import RssTagWorkers
from tests.db_utils import DBHelper
from tests.web_test_utils import create_test_config


def _require_test_mongo() -> None:
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=1):
            pass
    except OSError as exc:
        raise unittest.SkipTest(
            f"MongoDB on port 8765 is required for worker dispatcher tests: {exc}"
        )


class TestWorkerDispatcherInit(unittest.TestCase):
    db_helper: DBHelper
    tmp_dir: tempfile.TemporaryDirectory[str]
    config_path: str
    test_db_name: str

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _require_test_mongo()
        cls.db_helper = DBHelper(port=8765)
        try:
            cls.db_helper.client.admin.command("ping")
        except Exception as exc:
            cls.db_helper.close()
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for worker dispatcher tests: {exc}"
            )
        test_db = cls.db_helper.create_test_db()
        cls.test_db_name = test_db.name
        cls.tmp_dir = tempfile.TemporaryDirectory()
        cls.config_path = create_test_config(
            db_host=cls.db_helper.host,
            db_port=cls.db_helper.port,
            db_name=cls.test_db_name,
            tmp_dir=cls.tmp_dir.name,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db_helper.client.drop_database(cls.test_db_name)
        cls.db_helper.close()
        cls.tmp_dir.cleanup()
        super().tearDownClass()

    def test_dispatcher_construction_succeeds(self) -> None:
        dispatcher: RSSTagWorkerDispatcher = RSSTagWorkerDispatcher(self.config_path)

        self.assertIsInstance(dispatcher, RSSTagWorkerDispatcher)

    def test_dispatcher_db_connection_is_usable(self) -> None:
        dispatcher: RSSTagWorkerDispatcher = RSSTagWorkerDispatcher(self.config_path)

        result: Dict[str, Any] = dispatcher._workers_db._db.client.admin.command("ping")

        self.assertEqual(1.0, result["ok"])

    def test_dispatcher_initializes_workers_db_wrapper(self) -> None:
        dispatcher: RSSTagWorkerDispatcher = RSSTagWorkerDispatcher(self.config_path)

        self.assertIsInstance(dispatcher._workers_db, RssTagWorkers)

    def test_dispatcher_loads_expected_config_sections(self) -> None:
        dispatcher: RSSTagWorkerDispatcher = RSSTagWorkerDispatcher(self.config_path)

        self.assertIn("settings", dispatcher._config)
        self.assertIn("telegram", dispatcher._config)
        self.assertIn("gmail", dispatcher._config)
        self.assertEqual(self.test_db_name, dispatcher._config["settings"]["db_name"])

    def test_worker_function_is_callable(self) -> None:
        self.assertTrue(callable(worker))

    def test_invalid_config_path_raises(self) -> None:
        with self.assertRaises(Exception):
            RSSTagWorkerDispatcher("/app/tests/does-not-exist.conf")

    def test_dispatcher_reads_workers_count_from_config(self) -> None:
        dispatcher: RSSTagWorkerDispatcher = RSSTagWorkerDispatcher(self.config_path)

        self.assertEqual("1", dispatcher._config["settings"]["workers_count"])

    def test_dispatcher_configures_logging(self) -> None:
        with patch.object(logging, "basicConfig") as basic_config_mock:
            RSSTagWorkerDispatcher(self.config_path)

        basic_config_mock.assert_called_once()
        kwargs: Dict[str, Any] = basic_config_mock.call_args.kwargs
        self.assertEqual(
            f"{self.tmp_dir.name}/worker.log",
            kwargs["filename"],
        )
        self.assertEqual(logging.INFO, kwargs["level"])

