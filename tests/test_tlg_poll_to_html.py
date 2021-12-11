import unittest
import json
from rsstag.providers import tlg_poll_to_html

class TestTlgPollToHTML(unittest.TestCase):
    __post = """
    {
      "@type": "message",
      "id": 2,
      "sender": {
        "@type": "messageSenderChat",
        "chat_id": -1
      },
      "chat_id": -1,
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
      "date": 1625487394,
      "edit_date": 0,
      "interaction_info": {
        "@type": "messageInteractionInfo",
        "view_count": 2297,
        "forward_count": 0
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
        "@type": "messagePoll",
        "poll": {
          "@type": "poll",
          "id": "5",
          "question": "Poll question?",
          "options": [
            {
              "@type": "pollOption",
              "text": "Yes",
              "voter_count": 196,
              "vote_percentage": 27,
              "is_chosen": false,
              "is_being_chosen": false
            },
            {
              "@type": "pollOption",
              "text": "No",
              "voter_count": 415,
              "vote_percentage": 58,
              "is_chosen": false,
              "is_being_chosen": false
            },
            {
              "@type": "pollOption",
              "text": "May be",
              "voter_count": 107,
              "vote_percentage": 15,
              "is_chosen": false,
              "is_being_chosen": false
            }
          ],
          "total_voter_count": 718,
          "recent_voter_user_ids": [],
          "is_anonymous": true,
          "type": {
            "@type": "pollTypeRegular",
            "allow_multiple_answers": false
          },
          "open_period": 0,
          "close_date": 0,
          "is_closed": true
        }
      },
      "tlg_msg_lnk": "https://t.me/test/1"
    }
    """
    def test_tlg_poll_to_html(self):
        p = json.loads(self.__post)
        html = tlg_poll_to_html(p)
        expect = "<p>Poll question?</p><ol><li>Yes</li><li>No</li><li>May be</li></ol>"
        self.assertEqual(html, expect)

if __name__ == '__main__':
    unittest.main()
