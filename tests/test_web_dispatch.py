"""Module 3: WSGI dispatch and auth flow integration tests."""
import unittest
from typing import Any, Dict
from unittest.mock import patch

from werkzeug.test import Client
from werkzeug.wrappers import Response

from tests.web_test_utils import MongoWebTestCase


class TestWSGIDispatch(MongoWebTestCase):
    """Tests for the full WSGI dispatch layer, including auth enforcement."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user_doc, cls.user_sid = cls.seed_test_user("dispatchuser", "dispatchpass")
        cls.auth_client: Client = cls.get_authenticated_client(cls.user_sid)

    # ------------------------------------------------------------------
    # Unauthenticated access
    # ------------------------------------------------------------------

    def test_login_page_returns_200_without_auth(self) -> None:
        """/login is in allow_not_logged and must render without a cookie."""
        resp = self.client.get("/login")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"html", resp.data.lower())

    def test_register_page_returns_200_without_auth(self) -> None:
        """/register is in allow_not_logged and must render without a cookie."""
        resp = self.client.get("/register")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"html", resp.data.lower())

    def test_root_page_returns_200_without_auth(self) -> None:
        """on_root_get is in allow_not_logged: renders the anonymous root page."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"html", resp.data.lower())

    def test_protected_endpoint_redirects_without_auth(self) -> None:
        """/group/tag/1 is protected; unauthenticated request must redirect."""
        resp = self.client.get("/group/tag/1")
        self.assertIn(resp.status_code, (301, 302))

    def test_login_post_valid_credentials_redirects_and_sets_cookie(self) -> None:
        """Valid login POST returns a redirect and sets the sid cookie."""
        resp = self.client.post(
            "/login",
            data={"login": "dispatchuser", "password": "dispatchpass"},
        )
        self.assertIn(resp.status_code, (301, 302))
        self.assertIn("sid", resp.headers.get("Set-Cookie", ""))

    def test_login_post_invalid_credentials_shows_error(self) -> None:
        """Invalid credentials return a non-redirect page (login page with errors)."""
        resp = self.client.post(
            "/login",
            data={"login": "dispatchuser", "password": "wrongpassword"},
        )
        self.assertNotIn(resp.status_code, (301, 302))
        self.assertIn(b"html", resp.data.lower())

    # ------------------------------------------------------------------
    # Authenticated access
    # ------------------------------------------------------------------

    def test_root_returns_200_with_auth(self) -> None:
        """Authenticated GET / returns 200 with HTML content."""
        resp = self.auth_client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"html", resp.data.lower())

    def test_status_endpoint_returns_200_with_auth(self) -> None:
        """Authenticated GET /status returns 200."""
        resp = self.auth_client.get("/status")
        self.assertEqual(resp.status_code, 200)

    def test_tags_page_returns_200_with_auth(self) -> None:
        """Authenticated GET /group/tag/1 returns 200."""
        resp = self.auth_client.get("/group/tag/1")
        self.assertEqual(resp.status_code, 200)

    # ------------------------------------------------------------------
    # Error handling & security
    # ------------------------------------------------------------------

    def test_nonexistent_route_returns_404(self) -> None:
        """Request to an unknown path returns a 404 response."""
        resp = self.client.get("/this-route-does-not-exist-xyz-abc")
        self.assertEqual(resp.status_code, 404)

    def test_every_response_includes_x_frame_options_header(self) -> None:
        """set_response always attaches X-Frame-Options: SAMEORIGIN."""
        for path in ("/login", "/register", "/status"):
            with self.subTest(path=path):
                resp = self.client.get(path)
                self.assertEqual(resp.headers.get("X-Frame-Options"), "SAMEORIGIN")

    def test_handler_exception_returns_error_page_not_unhandled_crash(self) -> None:
        """An exception inside a handler produces an HTTP error page, not a raw crash."""
        original_handler = self.app.endpoints["on_group_by_tags_get"]

        def raising_handler(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("intentional test error for dispatch test")

        try:
            self.app.endpoints["on_group_by_tags_get"] = raising_handler
            resp = self.auth_client.get("/group/tag/1")
        finally:
            self.app.endpoints["on_group_by_tags_get"] = original_handler

        # WSGI must always return a valid HTTP response (error page, not a Python traceback)
        self.assertIsNotNone(resp)
        # The set_response dispatcher catches all exceptions and calls on_error (500)
        self.assertEqual(resp.status_code, 500)
        self.assertIn(b"html", resp.data.lower())


if __name__ == "__main__":
    unittest.main()
