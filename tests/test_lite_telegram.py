import unittest

from typing import Any

from rsstag_lite.telegram import TelegramService, message_link, message_to_html


class TestLiteTelegramRendering(unittest.TestCase):
    def test_message_html_escapes_untrusted_markup(self) -> None:
        message: dict = {
            "content": {
                "@type": "messageText",
                "text": {"text": "<script>alert(1)</script>\nSafe", "entities": []},
            }
        }

        rendered: str = message_to_html(message)

        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("<br>", rendered)

    def test_public_message_link_uses_server_message_id(self) -> None:
        chat: dict = {"id": -100123, "username": "example"}
        message: dict = {"id": 42 << 20}

        self.assertEqual(message_link(chat, message), "https://t.me/example/42")

    def test_history_continues_after_short_pages_until_cursor(self) -> None:
        service: TelegramService = TelegramService.__new__(TelegramService)
        responses: list[dict[str, Any]] = [
            {"messages": [{"id": 300}]},
            {"messages": [{"id": 200}]},
            {"messages": [{"id": 100}]},
        ]

        def request(query: dict[str, Any]) -> dict[str, Any]:
            return responses.pop(0)

        service._request = request  # type: ignore[method-assign]
        messages, reached = service._history({"id": -10}, 100, known_message_id=100)

        self.assertEqual([message["id"] for message in messages], [300, 200])
        self.assertTrue(reached)


if __name__ == "__main__":
    unittest.main()
