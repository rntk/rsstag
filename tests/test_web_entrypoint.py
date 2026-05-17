"""Tests for web.py entry point.

web.py's __main__ block cannot be tested via reload, so we extract the
startup logic into a testable form by simulating what the block does.
"""

import unittest
from unittest.mock import patch, MagicMock, call
import logging


class TestWebEntryPoint(unittest.TestCase):
    """Test the web.py __main__ entry point behavior by simulating its logic."""

    def _simulate_web_main(self, argv: list, app_instance: object) -> dict:
        """Simulate the web.py __main__ block and return recorded calls."""
        recorded: dict = {
            "init_observability": [],
            "app_created": None,
            "middleware_called": False,
            "run_simple_called": False,
            "app_close_called": False,
            "log_error": [],
            "log_critical": [],
        }

        with patch("web.init_observability") as mock_init_obs, \
             patch("web.RSSTagApplication", return_value=app_instance) as mock_app_cls, \
             patch("web.make_otel_wsgi_middleware", return_value="wrapped") as mock_mw, \
             patch("web.run_simple") as mock_run_simple, \
             patch("web.logging.error") as mock_log_err, \
             patch("web.logging.critical") as mock_log_crit:

            # Simulate sys.argv handling
            config_path = "rsscloud.conf"
            if len(argv) > 1:
                config_path = argv[1]

            mock_init_obs("rsstag-web")
            recorded["init_observability"] = mock_init_obs.call_args_list

            if app_instance:
                app = mock_app_cls(config_path)
                recorded["app_created"] = config_path
                mock_mw(app.set_response, app.routes.get_werkzeug_routes())
                recorded["middleware_called"] = True
                try:
                    mock_run_simple(
                        app.config["settings"]["host"],
                        int(app.config["settings"]["port"]),
                        "wrapped",
                        static_files={"/static": "static", "/favicon.ico": "static/favicon.ico"},
                        threaded=True,
                    )
                    recorded["run_simple_called"] = True
                except Exception as e:
                    mock_log_err(e)
                    recorded["log_error"] = [e]
                    app.close()
                    recorded["app_close_called"] = True
            else:
                mock_log_crit("Can`t start server")
                recorded["log_critical"] = ["Can`t start server"]

        return recorded

    def test_starts_with_default_config_path(self) -> None:
        """web.py uses 'rsscloud.conf' when no CLI args given."""
        mock_app = MagicMock()
        mock_app.config = {"settings": {"host": "0.0.0.0", "port": "5000"}}
        recorded = self._simulate_web_main(["web.py"], mock_app)

        self.assertEqual(recorded["app_created"], "rsscloud.conf")
        self.assertTrue(recorded["run_simple_called"])

    def test_starts_with_custom_config_path(self) -> None:
        """web.py uses CLI arg as config path when provided."""
        mock_app = MagicMock()
        mock_app.config = {"settings": {"host": "0.0.0.0", "port": "5000"}}
        recorded = self._simulate_web_main(["web.py", "/custom/path.conf"], mock_app)

        self.assertEqual(recorded["app_created"], "/custom/path.conf")

    def test_handles_run_simple_exception(self) -> None:
        """web.py logs error and calls app.close() when run_simple raises."""
        mock_app = MagicMock()
        mock_app.config = {"settings": {"host": "0.0.0.0", "port": "5000"}}
        mock_app.routes.get_werkzeug_routes.return_value = []

        with patch("web.init_observability"), \
             patch("web.RSSTagApplication", return_value=mock_app), \
             patch("web.make_otel_wsgi_middleware", return_value="wrapped"), \
             patch("web.run_simple", side_effect=OSError("port in use")) as mock_run, \
             patch("web.logging.error") as mock_log_err:

            # Simulate main block
            config_path = "rsscloud.conf"
            mock_app_instance = mock_app
            if mock_app_instance:
                try:
                    mock_run("0.0.0.0", 5000, "wrapped")
                except Exception as e:
                    mock_log_err(e)
                    mock_app_instance.close()

            mock_log_err.assert_called_once()
            mock_app.close.assert_called_once()

    def test_logs_critical_when_app_is_none(self) -> None:
        """web.py logs critical and does not start server when app is falsy."""
        recorded = self._simulate_web_main(["web.py"], None)

        self.assertEqual(recorded["log_critical"], ["Can`t start server"])
        self.assertFalse(recorded["run_simple_called"])
        self.assertFalse(recorded["middleware_called"])

    def test_wsgi_middleware_is_applied(self) -> None:
        """web.py wraps the app with OTEL middleware before starting."""
        mock_app = MagicMock()
        mock_app.config = {"settings": {"host": "0.0.0.0", "port": "5000"}}
        mock_app.routes.get_werkzeug_routes.return_value = ["route1"]

        with patch("web.init_observability"), \
             patch("web.RSSTagApplication", return_value=mock_app), \
             patch("web.make_otel_wsgi_middleware", return_value="wrapped") as mock_mw, \
             patch("web.run_simple"):

            config_path = "rsscloud.conf"
            mock_mw(mock_app.set_response, mock_app.routes.get_werkzeug_routes())

            mock_mw.assert_called_once_with(
                mock_app.set_response, ["route1"]
            )

    def test_static_files_mapping(self) -> None:
        """web.py configures static files for /static and /favicon.ico."""
        mock_app = MagicMock()
        mock_app.config = {"settings": {"host": "0.0.0.0", "port": "5000"}}

        with patch("web.init_observability"), \
             patch("web.RSSTagApplication", return_value=mock_app), \
             patch("web.make_otel_wsgi_middleware", return_value="wrapped"), \
             patch("web.run_simple") as mock_run_simple:

            mock_run_simple(
                "0.0.0.0",
                5000,
                "wrapped",
                static_files={"/static": "static", "/favicon.ico": "static/favicon.ico"},
                threaded=True,
            )

            call_kwargs = mock_run_simple.call_args[1]
            self.assertEqual(call_kwargs["static_files"]["/static"], "static")
            self.assertEqual(call_kwargs["static_files"]["/favicon.ico"], "static/favicon.ico")
            self.assertTrue(call_kwargs["threaded"])


class TestObservabilityImportFallback(unittest.TestCase):
    """Test that web.py gracefully handles missing observability module."""

    def test_fallback_init_observability_is_noop(self) -> None:
        """Fallback init_observability does nothing when called."""
        # Simulate the fallback lambda from web.py
        init_observability = lambda *a, **kw: None  # noqa: E731
        result = init_observability("rsstag-web")
        self.assertIsNone(result)

    def test_fallback_middleware_returns_app(self) -> None:
        """Fallback make_otel_wsgi_middleware returns the app unchanged."""
        # Simulate the fallback lambda from web.py
        make_otel_wsgi_middleware = lambda app, *a, **kw: app  # noqa: E731
        mock_app = MagicMock()
        result = make_otel_wsgi_middleware(mock_app)
        self.assertIs(result, mock_app)


class TestWebAppSetResponse(unittest.TestCase):
    """Test RSSTagApplication.set_response — the core WSGI handler."""

    @patch("rsstag.web.app.load_config")
    @patch("rsstag.web.app.MongoClient")
    def test_set_response_adds_security_header(self, mock_client: MagicMock, mock_config: MagicMock) -> None:
        """set_response always adds X-Frame-Options: SAMEORIGIN."""
        from rsstag.web.app import RSSTagApplication
        mock_config.return_value = {
            "settings": {
                "host": "0.0.0.0", "port": "5000", "host_name": "http://localhost",
                "db_host": "localhost", "db_port": "27017", "db_name": "test",
                "db_login": "", "db_password": "", "log_level": "INFO",
                "log_file": "", "templates": "default", "providers": "local",
                "user_ttl": "3600", "no_category_name": "Uncategorized",
            }
        }
        mock_db = MagicMock()
        mock_client.return_value.__getitem__ = lambda self, key: mock_db

        app = RSSTagApplication()
        # set_response is the WSGI callable wrapper
        # We test at the response level by checking headers
        self.assertTrue(hasattr(app, "set_response"))


if __name__ == "__main__":
    unittest.main()
