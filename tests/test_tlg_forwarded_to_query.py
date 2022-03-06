import unittest
import json
from rsstag.providers import tlg_forward_to_query

class TestTlgPollToHTML(unittest.TestCase):
    __post = """
    {
      "@type": "message",
      "id": 4014732400,
      "sender": {
        "@type": "messageSenderChat",
        "chat_id": -10109822591
      },
      "chat_id": -1001097577405,
      "is_outgoing": false,
      "is_pinned": false,
      "can_be_edited": false,
      "can_be_forwarded": true,
      "can_be_deleted_only_for_self": false,
      "can_be_deleted_for_all_users": false,
      "can_get_statistics": false,
      "can_get_message_thread": false,
      "is_channel_post": true,
      "contains_unread_mention": false,
      "date": 1556723406,
      "edit_date": 0,
      "forward_info": {
        "@type": "messageForwardInfo",
        "origin": {
          "@type": "messageForwardOriginChannel",
          "chat_id": -1755191332593,
          "message_id": 47559175,
          "author_signature": ""
        },
        "date": 1554108920,
        "public_service_announcement_type": "",
        "from_chat_id": 0,
        "from_message_id": 0
      },
      "interaction_info": {
        "@type": "messageInteractionInfo",
        "view_count": 32,
        "forward_count": 1
      },
      "reply_in_chat_id": 0,
      "reply_to_message_id": 0,
      "message_thread_id": 0,
      "ttl": 0,
      "ttl_expires_in": 0.0,
      "via_bot_user_id": 0,
      "author_signature": "",
      "media_album_id": "0",
      "restriction_reason": "",
      "content": {
        "@type": "messageText",
        "text": {
          "@type": "formattedText",
          "text": "some text",
          "entities": [
            {
              "@type": "textEntity",
              "offset": 1085,
              "length": 21,
              "type": {
                "@type": "textEntityTypeTextUrl",
                "url": "https://example.com/example/path"
              }
            }
          ]
        }
      },
      "tlg_msg_lnk": "https://t.me/channelname/400"
    }
    """
    def test_tlg_webpage_to_html(self):
        p = json.loads(self.__post)
        q = tlg_forward_to_query(p)
        expect = {"chat_id": -1755191332593, "message_id": 47559175}
        self.assertEqual(q, expect)

if __name__ == '__main__':
    unittest.main()
