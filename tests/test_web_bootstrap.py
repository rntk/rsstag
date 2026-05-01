import importlib
import inspect
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from rsstag.utils import load_config
from rsstag.web.app import RSSTagApplication
from rsstag.web.routes import RSSTagRoutes
from tests.web_test_utils import create_test_config, get_route_endpoints


class TestWebBootstrap(unittest.TestCase):
    def test_import_smoke_for_web_modules(self) -> None:
        module_names: list[str] = [
            "rsstag.web.app",
            "rsstag.web.routes",
            "rsstag.web",
            "rsstag.web.bigrams",
            "rsstag.web.chat",
            "rsstag.web.context_filter_handlers",
            "rsstag.web.feeds",
            "rsstag.web.keywords",
            "rsstag.web.metadata",
            "rsstag.web.openai",
            "rsstag.web.posts",
            "rsstag.web.prefixes",
            "rsstag.web.processing",
            "rsstag.web.providers",
            "rsstag.web.tags",
            "rsstag.web.tasks",
            "rsstag.web.anthologies",
            "rsstag.web.users",
        ]

        for module_name in module_names:
            with self.subTest(module=module_name):
                module = importlib.import_module(module_name)
                self.assertIsNotNone(module)

    def test_load_config_reads_generated_test_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path: str = create_test_config(
                db_host="127.0.0.1",
                db_port=8765,
                db_name="rsstag_test",
                tmp_dir=tmp_dir,
            )

            config: dict = load_config(config_path)

        self.assertIn("settings", config)
        self.assertEqual(config["settings"]["db_host"], "127.0.0.1")
        self.assertEqual(config["settings"]["db_port"], "8765")
        self.assertIn("openai", config)
        self.assertIn("llamacpp", config)

    def test_routes_standalone_returns_large_map_with_known_endpoints(self) -> None:
        routes = RSSTagRoutes("localhost", handlers=MagicMock())
        route_map = routes.get_werkzeug_routes()
        rules = list(route_map.iter_rules())
        endpoints = {rule.endpoint for rule in rules}

        self.assertGreaterEqual(len(rules), 100)
        self.assertIn("on_root_get", endpoints)
        self.assertIn("on_login_get", endpoints)
        self.assertIn("on_login_post", endpoints)

    def test_route_completeness_matches_application_methods(self) -> None:
        endpoints: set[str] = get_route_endpoints()

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                self.assertTrue(hasattr(RSSTagApplication, endpoint))
                self.assertTrue(
                    inspect.isfunction(getattr(RSSTagApplication, endpoint)),
                )

    def test_web_module_import_does_not_run_server(self) -> None:
        module = importlib.import_module("web")
        self.assertIsNotNone(module)
        self.assertTrue(hasattr(module, "RSSTagApplication"))

    def test_load_config_respects_db_env_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path: str = create_test_config(
                db_host="10.0.0.1",
                db_port=1000,
                db_name="rsstag_test",
                tmp_dir=tmp_dir,
            )
            previous_host: str = os.environ.get("DB_HOST", "")
            previous_port: str = os.environ.get("DB_PORT", "")
            os.environ["DB_HOST"] = "127.0.0.2"
            os.environ["DB_PORT"] = "8765"
            try:
                config: dict = load_config(config_path)
            finally:
                if previous_host:
                    os.environ["DB_HOST"] = previous_host
                else:
                    os.environ.pop("DB_HOST", None)
                if previous_port:
                    os.environ["DB_PORT"] = previous_port
                else:
                    os.environ.pop("DB_PORT", None)

        self.assertEqual(config["settings"]["db_host"], "127.0.0.2")
        self.assertEqual(config["settings"]["db_port"], "8765")


if __name__ == "__main__":
    unittest.main()
