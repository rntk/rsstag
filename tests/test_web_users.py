"""Comprehensive tests for rsstag/web/users.py."""

import json
import unittest
from unittest.mock import patch, MagicMock

from werkzeug.test import Client
from werkzeug.wrappers import Response

from tests.web_test_utils import MongoWebTestCase


class TestWebUsersAuthLifecycle(MongoWebTestCase):
    """Tests for login, register, and logout flows."""

    def test_login_get_renders_form(self) -> None:
        resp = self.client.get("/login")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"html", resp.data.lower())

    def test_register_get_renders_form(self) -> None:
        resp = self.client.get("/register")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"html", resp.data.lower())

    def test_register_post_creates_user_and_redirects(self) -> None:
        resp = self.client.post(
            "/register",
            data={
                "login": "newuser",
                "password": "newpass",
                "password_confirm": "newpass",
            },
        )
        self.assertIn(resp.status_code, (301, 302))
        self.assertIn("sid", resp.headers.get("Set-Cookie", ""))
        user = self.app.users.get_by_username("newuser")
        self.assertIsNotNone(user)

    def test_register_post_mismatched_passwords_shows_error(self) -> None:
        resp = self.client.post(
            "/register",
            data={
                "login": "newuser2",
                "password": "pass1",
                "password_confirm": "pass2",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"html", resp.data.lower())

    def test_register_post_existing_user_shows_error(self) -> None:
        self.app.users.create_account("existinguser", "existingpass")
        resp = self.client.post(
            "/register",
            data={
                "login": "existinguser",
                "password": "pass",
                "password_confirm": "pass",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"html", resp.data.lower())

    def test_login_post_valid_credentials_sets_cookie_and_redirects(self) -> None:
        self.app.users.create_account("loginuser", "loginpass")
        resp = self.client.post(
            "/login",
            data={"login": "loginuser", "password": "loginpass"},
        )
        self.assertIn(resp.status_code, (301, 302))
        self.assertIn("sid", resp.headers.get("Set-Cookie", ""))

    def test_login_post_invalid_credentials_shows_error(self) -> None:
        resp = self.client.post(
            "/login",
            data={"login": "nouser", "password": "wrongpass"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"html", resp.data.lower())

    def test_login_post_empty_credentials_shows_error(self) -> None:
        resp = self.client.post("/login", data={"login": "", "password": ""})
        self.assertEqual(resp.status_code, 200)

    def test_logout_get_clears_cookies_and_redirects(self) -> None:
        sid = self.app.users.create_account("logoutuser", "logoutpass")
        client = self.get_authenticated_client(sid)
        resp = client.get("/logout")
        self.assertIn(resp.status_code, (301, 302))
        set_cookie = resp.headers.get("Set-Cookie", "")
        self.assertIn("sid", set_cookie)


class TestWebUsersSettings(MongoWebTestCase):
    """Tests for user settings updates."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user_doc, cls.user_sid = cls.seed_test_user("settingsuser", "settingspass")
        cls.auth_client = cls.get_authenticated_client(cls.user_sid)

    def test_settings_post_updates_user_settings(self) -> None:
        payload = {"only_unread": False, "tags_on_page": 50}
        resp = self.auth_client.post(
            "/settings",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data, {"data": "ok"})
        updated_user = self.app.users.get_by_sid(self.user_sid)
        self.assertEqual(updated_user["settings"]["only_unread"], False)
        self.assertEqual(updated_user["settings"]["tags_on_page"], 50)

    def test_settings_post_invalid_json_returns_400(self) -> None:
        resp = self.auth_client.post(
            "/settings",
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_settings_post_empty_body_returns_400(self) -> None:
        resp = self.auth_client.post(
            "/settings",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


class TestWebUsersRefreshAndStatus(MongoWebTestCase):
    """Tests for refresh and status endpoints."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user_doc, cls.user_sid = cls.seed_test_user("statususer", "statuspass")
        cls.auth_client = cls.get_authenticated_client(cls.user_sid)

    def test_refresh_get_post_no_providers_redirects(self) -> None:
        resp = self.auth_client.get("/refresh")
        self.assertIn(resp.status_code, (301, 302))

    def test_refresh_get_post_enqueues_download_tasks(self) -> None:
        self.app.users.add_provider(
            self.user_sid,
            "bazqux",
            {"login": "test", "token": "tok"},
            set_active=True,
        )
        resp = self.auth_client.get("/refresh")
        self.assertIn(resp.status_code, (301, 302))
        user = self.app.users.get_by_sid(self.user_sid)
        self.assertTrue(user["in_queue"])

    def test_status_get_authenticated_returns_json(self) -> None:
        resp = self.auth_client.get("/status")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("data", data)
        self.assertIn("is_ok", data["data"])

    def test_status_get_unauthenticated_returns_not_logged_in(self) -> None:
        resp = self.client.get("/status")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("Looks like you are not logged in", data["data"]["msgs"])

    def test_status_get_with_retoken_flag(self) -> None:
        self.app.users.update_by_sid(
            self.user_sid, {"retoken": True}
        )
        resp = self.auth_client.get("/status")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertFalse(data["data"]["is_ok"])


class TestWebUsersDataSources(MongoWebTestCase):
    """Tests for data sources and provider detail pages."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user_doc, cls.user_sid = cls.seed_test_user("sourceuser", "sourcepass")
        cls.auth_client = cls.get_authenticated_client(cls.user_sid)

    def test_data_sources_get_returns_200(self) -> None:
        resp = self.auth_client.get("/data-sources")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"html", resp.data.lower())

    def test_provider_detail_get_known_provider(self) -> None:
        resp = self.auth_client.get("/provider/bazqux")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"html", resp.data.lower())

    def test_provider_detail_get_unknown_provider_redirects(self) -> None:
        resp = self.auth_client.get("/provider/unknown-provider")
        self.assertIn(resp.status_code, (301, 302))


class TestWebUsersOAuth(MongoWebTestCase):
    """Tests for Google and X OAuth flows with mocked external HTTP."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user_doc, cls.user_sid = cls.seed_test_user("oauthuser", "oauthpass")
        cls.auth_client = cls.get_authenticated_client(cls.user_sid)

    def test_login_google_auth_get_redirects_when_authenticated(self) -> None:
        resp = self.auth_client.get("/login/google/auth")
        self.assertIn(resp.status_code, (301, 302))
        location = resp.headers.get("Location", "")
        self.assertIn("accounts.google.com", location)

    def test_login_google_auth_get_redirects_to_login_when_not_authenticated(self) -> None:
        resp = self.client.get("/login/google/auth")
        self.assertIn(resp.status_code, (301, 302))
        location = resp.headers.get("Location", "")
        self.assertIn("/login", location)

    @patch("rsstag.web.users._exchange_code_for_token")
    def test_oauth2callback_get_exchanges_code_and_links_gmail(self, mock_exchange) -> None:
        mock_exchange.return_value = (
            {"access_token": "fake_access", "refresh_token": "fake_refresh"},
            {"email": "test@example.com"},
        )
        resp = self.auth_client.get("/oauth2callback?code=fakecode")
        self.assertIn(resp.status_code, (301, 302))
        user = self.app.users.get_by_sid(self.user_sid)
        self.assertIn("gmail", user.get("providers", {}))

    @patch("rsstag.web.users._exchange_code_for_token")
    def test_oauth2callback_get_no_user_info_shows_error(self, mock_exchange) -> None:
        mock_exchange.return_value = ({"access_token": "tok"}, None)
        resp = self.auth_client.get("/oauth2callback?code=fakecode")
        self.assertEqual(resp.status_code, 200)

    @patch("rsstag.web.users._exchange_code_for_token")
    def test_oauth2callback_get_no_email_shows_error(self, mock_exchange) -> None:
        mock_exchange.return_value = ({"access_token": "tok"}, {"name": "No Email"})
        resp = self.auth_client.get("/oauth2callback?code=fakecode")
        self.assertEqual(resp.status_code, 200)

    def test_oauth2callback_get_error_param_shows_error(self) -> None:
        resp = self.auth_client.get("/oauth2callback?error=access_denied")
        self.assertEqual(resp.status_code, 200)

    def test_oauth2callback_get_no_code_shows_error(self) -> None:
        resp = self.auth_client.get("/oauth2callback")
        self.assertEqual(resp.status_code, 200)

    def test_login_x_auth_get_redirects_when_authenticated(self) -> None:
        resp = self.auth_client.get("/login/x/auth")
        self.assertIn(resp.status_code, (301, 302))
        location = resp.headers.get("Location", "")
        self.assertIn("x.com", location)

    def test_login_x_auth_get_redirects_to_login_when_not_authenticated(self) -> None:
        resp = self.client.get("/login/x/auth")
        self.assertIn(resp.status_code, (301, 302))
        location = resp.headers.get("Location", "")
        self.assertIn("/login", location)

    @patch("rsstag.web.users._exchange_x_code_for_token")
    @patch("rsstag.web.users._get_x_user_info")
    def test_x_oauth2callback_get_exchanges_code_and_links_x(
        self, mock_get_info, mock_exchange
    ) -> None:
        mock_exchange.return_value = {
            "access_token": "x_fake_token",
            "refresh_token": "x_fake_refresh",
        }
        mock_get_info.return_value = {
            "id": "12345",
            "username": "testuser",
        }
        user = self.app.users.get_by_sid(self.user_sid)
        self.app.users.update_by_sid(
            self.user_sid,
            {"x_oauth_state": "test_state", "x_code_verifier": "test_verifier"},
        )
        resp = self.auth_client.get("/x/oauth2callback?code=fakecode&state=test_state")
        self.assertIn(resp.status_code, (301, 302))
        updated_user = self.app.users.get_by_sid(self.user_sid)
        self.assertIn("x", updated_user.get("providers", {}))

    @patch("rsstag.web.users._exchange_x_code_for_token")
    @patch("rsstag.web.users._get_x_user_info")
    def test_x_oauth2callback_get_invalid_state_shows_error(
        self, mock_get_info, mock_exchange
    ) -> None:
        mock_exchange.return_value = {"access_token": "tok"}
        mock_get_info.return_value = {"id": "1", "username": "u"}
        self.app.users.update_by_sid(
            self.user_sid,
            {"x_oauth_state": "valid_state", "x_code_verifier": "verifier"},
        )
        resp = self.auth_client.get("/x/oauth2callback?code=fakecode&state=invalid_state")
        self.assertEqual(resp.status_code, 200)

    def test_x_oauth2callback_get_error_param_shows_error(self) -> None:
        self.app.users.update_by_sid(
            self.user_sid,
            {"x_oauth_state": "s", "x_code_verifier": "v"},
        )
        resp = self.auth_client.get("/x/oauth2callback?error=access_denied")
        self.assertEqual(resp.status_code, 200)


class TestWebUsersTelegramAuth(MongoWebTestCase):
    """Tests for Telegram auth endpoint."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user_doc, cls.user_sid = cls.seed_test_user("tlguser", "tlgpass")
        cls.auth_client = cls.get_authenticated_client(cls.user_sid)

    def test_telegram_auth_post_with_code(self) -> None:
        resp = self.auth_client.post(
            "/telegram-auth",
            data=json.dumps({"telegram_code": "12345"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data, {"data": "ok"})
        user = self.app.users.get_by_sid(self.user_sid)
        self.assertEqual(user["telegram_code"], "12345")

    def test_telegram_auth_post_with_password(self) -> None:
        resp = self.auth_client.post(
            "/telegram-auth",
            data=json.dumps({"telegram_password": "secret"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data, {"data": "ok"})

    def test_telegram_auth_post_empty_body_returns_400(self) -> None:
        resp = self.auth_client.post(
            "/telegram-auth",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_telegram_auth_post_invalid_json_returns_400(self) -> None:
        resp = self.auth_client.post(
            "/telegram-auth",
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


class TestWebUsersUnit(unittest.TestCase):
    """Pure unit tests for rsstag.web.users helpers."""

    def test_base64url_sha256(self) -> None:
        from rsstag.web.users import _base64url_sha256

        result = _base64url_sha256("test")
        self.assertIsInstance(result, str)
        self.assertNotIn("=", result)
        self.assertNotIn("+", result)
        self.assertNotIn("/", result)

    def test_build_redirect_uri(self) -> None:
        from rsstag.web.users import _build_redirect_uri

        app = MagicMock()
        app.config = {"settings": {"host_name": "example.com", "protocol": "https"}}
        app.routes.get_url_by_endpoint.return_value = "/callback"
        result = _build_redirect_uri(app, "on_oauth2callback_get")
        self.assertEqual(result, "https://example.com/callback")


if __name__ == "__main__":
    unittest.main()
