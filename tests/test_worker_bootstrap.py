import importlib
import logging
import os
import tempfile
import unittest
from argparse import ArgumentParser, Namespace
from typing import Any, Dict
from unittest.mock import patch

import worker

from rsstag.utils import load_config
from tests.worker_test_utils import create_worker_test_config


class TestWorkerBootstrap(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.config_path: str = create_worker_test_config(
            db_host="127.0.0.1",
            db_port=8765,
            db_name="rsstag_test_bootstrap",
            tmp_dir=self._tmp_dir.name,
        )
        self.config: Dict[str, Any] = load_config(self.config_path)

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_worker_modules_import_without_error(self) -> None:
        module_names: list[str] = [
            "rsstag.workers.dispatcher",
            "rsstag.workers.external_worker",
            "rsstag.workers.registry",
            "rsstag.workers.base",
            "rsstag.workers.tag_worker",
            "rsstag.workers.llm_worker",
            "rsstag.workers.provider_worker",
            "rsstag.tasks",
        ]

        for module_name in module_names:
            with self.subTest(module_name=module_name):
                module = importlib.import_module(module_name)
                self.assertIsNotNone(module)

    def test_tasks_module_exposes_expected_symbols(self) -> None:
        tasks_module = importlib.import_module("rsstag.tasks")

        expected_names: list[str] = [
            "RssTagTasks",
            "TASK_DOWNLOAD",
            "TASK_TAGS",
            "TASK_POST_GROUPING",
        ]
        for name in expected_names:
            with self.subTest(name=name):
                self.assertTrue(hasattr(tasks_module, name))

    def test_worker_module_import_does_not_crash(self) -> None:
        imported = importlib.import_module("worker")
        self.assertIs(imported, worker)

    def test_build_parser_returns_parser_with_expected_defaults(self) -> None:
        parser: ArgumentParser = worker._build_parser()

        self.assertIsInstance(parser, ArgumentParser)
        parsed: Namespace = parser.parse_args([])
        self.assertEqual(parsed.mode, "internal")
        self.assertEqual(parsed.config_path, "rsscloud.conf")
        self.assertEqual(parsed.api_base_url, "")
        self.assertEqual(parsed.token, "")
        self.assertEqual(parsed.poll_interval, 2.0)
        self.assertEqual(parsed.request_timeout, 60.0)
        self.assertFalse(parsed.once)

    def test_parser_accepts_external_mode_arguments(self) -> None:
        parser: ArgumentParser = worker._build_parser()

        parsed: Namespace = parser.parse_args(
            ["--mode", "external", "--token", "abc", "my.conf"]
        )

        self.assertEqual(parsed.mode, "external")
        self.assertEqual(parsed.token, "abc")
        self.assertEqual(parsed.config_path, "my.conf")

    def test_parser_uses_environment_variables(self) -> None:
        with patch.dict(
            os.environ,
            {"RSSTAG_WORKER_TOKEN": "env-token", "RSSTAG_API_BASE_URL": "http://env"},
            clear=False,
        ):
            parser: ArgumentParser = worker._build_parser()
            parsed: Namespace = parser.parse_args([])

        self.assertEqual(parsed.token, "env-token")
        self.assertEqual(parsed.api_base_url, "http://env")

    def test_build_default_api_base_url_normalizes_host_name(self) -> None:
        cases: list[tuple[Dict[str, Any], str]] = [
            ({"settings": {"host_name": "example.com"}}, "http://example.com"),
            ({"settings": {"host_name": "https://example.com/"}}, "https://example.com"),
            (
                {"settings": {"host_name": "  127.0.0.1:8885  "}},
                "http://127.0.0.1:8885",
            ),
        ]

        for config, expected in cases:
            with self.subTest(config=config):
                self.assertEqual(worker._build_default_api_base_url(config), expected)

    def test_configure_logging_accepts_valid_config(self) -> None:
        worker._configure_logging(self.config)
        logger: logging.Logger = logging.getLogger()
        self.assertIsInstance(logger, logging.Logger)

    def test_external_main_uses_env_token_and_runner(self) -> None:
        with patch.dict(os.environ, {"RSSTAG_WORKER_TOKEN": "env-token"}, clear=False):
            parser: ArgumentParser = worker._build_parser()
            args: Namespace = parser.parse_args(["--mode", "external", self.config_path])

        with patch.object(worker, "_build_parser", return_value=parser), patch.object(
            parser, "parse_args", return_value=args
        ), patch("rsstag.workers.external_worker.ExternalWorkerRunner") as runner_cls:
            runner = runner_cls.return_value
            exit_code: int = worker.main()

        self.assertEqual(exit_code, 0)
        runner.start.assert_called_once_with(once=False)
