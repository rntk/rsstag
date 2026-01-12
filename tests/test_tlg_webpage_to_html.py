import unittest
import json
from rsstag.providers import tlg_webpage_to_html


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
        },
        "web_page": {
          "@type": "webPage",
          "url": "https://example.com/example/path",
          "display_url": "example.com/example/path",
          "type": "photo",
          "site_name": "Site name",
          "title": "Site title",
          "description": {
            "@type": "formattedText",
            "text": "Site description",
            "entities": []
          },
          "photo": {
            "@type": "photo",
            "has_stickers": false,
            "sizes": [
              {
                "@type": "photoSize",
                "type": "s",
                "photo": {
                  "@type": "file",
                  "id": 3100,
                  "size": 1089,
                  "expected_size": 1089,
                  "local": {
                    "@type": "localFile",
                    "path": "",
                    "can_be_downloaded": true,
                    "can_be_deleted": false,
                    "is_downloading_active": false,
                    "is_downloading_completed": false,
                    "download_offset": 0,
                    "downloaded_prefix_size": 0,
                    "downloaded_size": 0
                  },
                  "remote": {
                    "@type": "remoteFile",
                    "id": "id",
                    "unique_id": "uniq_id",
                    "is_uploading_active": false,
                    "is_uploading_completed": true,
                    "uploaded_size": 1089
                  }
                },
                "width": 90,
                "height": 45,
                "progressive_sizes": []
              },
              {
                "@type": "photoSize",
                "type": "m",
                "photo": {
                  "@type": "file",
                  "id": 3101,
                  "size": 9269,
                  "expected_size": 9269,
                  "local": {
                    "@type": "localFile",
                    "path": "",
                    "can_be_downloaded": true,
                    "can_be_deleted": false,
                    "is_downloading_active": false,
                    "is_downloading_completed": false,
                    "download_offset": 0,
                    "downloaded_prefix_size": 0,
                    "downloaded_size": 0
                  },
                  "remote": {
                    "@type": "remoteFile",
                    "id": "id",
                    "unique_id": "uniq_id",
                    "is_uploading_active": false,
                    "is_uploading_completed": true,
                    "uploaded_size": 9269
                  }
                },
                "width": 320,
                "height": 160,
                "progressive_sizes": []
              },
              {
                "@type": "photoSize",
                "type": "x",
                "photo": {
                  "@type": "file",
                  "id": 3102,
                  "size": 28079,
                  "expected_size": 28079,
                  "local": {
                    "@type": "localFile",
                    "path": "",
                    "can_be_downloaded": true,
                    "can_be_deleted": false,
                    "is_downloading_active": false,
                    "is_downloading_completed": false,
                    "download_offset": 0,
                    "downloaded_prefix_size": 0,
                    "downloaded_size": 0
                  },
                  "remote": {
                    "@type": "remoteFile",
                    "id": "id",
                    "unique_id": "uniq_id",
                    "is_uploading_active": false,
                    "is_uploading_completed": true,
                    "uploaded_size": 28079
                  }
                },
                "width": 800,
                "height": 400,
                "progressive_sizes": []
              },
              {
                "@type": "photoSize",
                "type": "y",
                "photo": {
                  "@type": "file",
                  "id": 3103,
                  "size": 49368,
                  "expected_size": 49368,
                  "local": {
                    "@type": "localFile",
                    "path": "",
                    "can_be_downloaded": true,
                    "can_be_deleted": false,
                    "is_downloading_active": false,
                    "is_downloading_completed": false,
                    "download_offset": 0,
                    "downloaded_prefix_size": 0,
                    "downloaded_size": 0
                  },
                  "remote": {
                    "@type": "remoteFile",
                    "id": "id",
                    "unique_id": "uniq_id",
                    "is_uploading_active": false,
                    "is_uploading_completed": true,
                    "uploaded_size": 49368
                  }
                },
                "width": 1280,
                "height": 640,
                "progressive_sizes": []
              },
              {
                "@type": "photoSize",
                "type": "w",
                "photo": {
                  "@type": "file",
                  "id": 3104,
                  "size": 84236,
                  "expected_size": 84236,
                  "local": {
                    "@type": "localFile",
                    "path": "",
                    "can_be_downloaded": true,
                    "can_be_deleted": false,
                    "is_downloading_active": false,
                    "is_downloading_completed": false,
                    "download_offset": 0,
                    "downloaded_prefix_size": 0,
                    "downloaded_size": 0
                  },
                  "remote": {
                    "@type": "remoteFile",
                    "id": "id",
                    "unique_id": "uniq_id",
                    "is_uploading_active": false,
                    "is_uploading_completed": true,
                    "uploaded_size": 84236
                  }
                },
                "width": 2048,
                "height": 1024,
                "progressive_sizes": []
              }
            ]
          },
          "embed_url": "",
          "embed_type": "",
          "embed_width": 0,
          "embed_height": 0,
          "duration": 0,
          "author": "https://example.com/athor-name",
          "instant_view_version": 0
        }
      },
      "tlg_msg_lnk": "https://t.me/channelname/400"
    }
    """

    def test_tlg_webpage_to_html(self):
        p = json.loads(self.__post)
        html = tlg_webpage_to_html(p)
        expect = '<br /><p><a href="https://example.com/example/path">Site name<br />Site title<br />Site description<br /></a></p>'
        self.assertEqual(html, expect)


if __name__ == "__main__":
    unittest.main()
