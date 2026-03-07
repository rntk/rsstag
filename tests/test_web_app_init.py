import os
import tempfile
import unittest

from rsstag.web.app import RSSTagApplication
from tests.web_test_utils import MongoWebTestCase, create_test_config


class TestWebAppInit(MongoWebTestCase):
    def test_full_app_construction_succeeds(self) -> None:
        self.assertIsNotNone(self.app)

    def test_storage_objects_are_initialized(self) -> None:
        storage_attrs: tuple[str, ...] = (
            "posts",
            "feeds",
            "tags",
            "letters",
            "bi_grams",
            "users",
            "tokens",
            "workers",
            "tasks",
            "post_grouping",
        )

        for attr_name in storage_attrs:
            with self.subTest(attr=attr_name):
                self.assertIsNotNone(getattr(self.app, attr_name))

    def test_expected_db_indexes_exist_on_key_collections(self) -> None:
        expected_indexes: dict[str, set[str]] = {
            "posts": {"owner", "feed_id", "pid", "processing"},
            "tags": {"owner", "tag", "processing"},
            "feeds": {"owner", "feed_id"},
            "users": {"sid"},
            "tasks": {"user", "processing"},
        }

        for collection_name, index_names in expected_indexes.items():
            with self.subTest(collection=collection_name):
                info: dict = self.test_db[collection_name].index_information()
                existing_keys: set[str] = {
                    key_name
                    for data in info.values()
                    for key_name, _direction in data["key"]
                }
                self.assertTrue(index_names.issubset(existing_keys))

    def test_routes_are_wired_into_endpoints_map(self) -> None:
        self.assertIn("on_root_get", self.app.endpoints)
        self.assertIn("on_login_get", self.app.endpoints)
        self.assertIn("on_login_post", self.app.endpoints)

    def test_wsgi_callable_is_available(self) -> None:
        self.assertTrue(callable(self.app.set_response))

    def test_close_does_not_raise(self) -> None:
        self.app.close()

    def test_env_vars_override_db_host_and_port_during_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path: str = create_test_config(
                db_host="10.10.10.10",
                db_port=9999,
                db_name=self.test_db.name,
                tmp_dir=tmp_dir,
            )
            previous_host: str = os.environ.get("DB_HOST", "")
            previous_port: str = os.environ.get("DB_PORT", "")
            os.environ["DB_HOST"] = self.db_helper.host
            os.environ["DB_PORT"] = str(self.db_helper.port)
            try:
                app = RSSTagApplication(config_path)
            finally:
                if previous_host:
                    os.environ["DB_HOST"] = previous_host
                else:
                    os.environ.pop("DB_HOST", None)
                if previous_port:
                    os.environ["DB_PORT"] = previous_port
                else:
                    os.environ.pop("DB_PORT", None)

            self.addCleanup(app.close)

        self.assertEqual(app.config["settings"]["db_host"], self.db_helper.host)
        self.assertEqual(app.config["settings"]["db_port"], str(self.db_helper.port))

    def test_invalid_config_path_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            RSSTagApplication("nonexistent.conf")


if __name__ == "__main__":
    unittest.main()
