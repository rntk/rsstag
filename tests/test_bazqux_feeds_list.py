"""Tests for BazquxProvider.list_feeds (the "refresh sources list" capability).

Bazqux joins the provider-agnostic sources-list feature by implementing
``list_feeds``, exactly like Telegram. The property that matters most is the
feed identity: ``download`` hashes ``origin.streamId`` of a post, so
``list_feeds`` must hash the subscription id to the very same ``feed_id``,
otherwise a refresh and a later download store two rows for one source.
"""

import json
import unittest
from hashlib import md5
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from rsstag.providers.bazqux import BazquxProvider
from rsstag.providers.providers import BAZQUX, supports_feeds_list

_SUBSCRIPTIONS: Dict[str, Any] = {
    "subscriptions": [
        {
            "id": "feed/http://news.example/rss",
            "title": "News",
            "categories": [{"label": "Tech"}],
        },
        {
            "id": "feed/http://blog.example/rss",
            "title": "Blog",
            "categories": [],
        },
    ]
}


def _config() -> Dict[str, Any]:
    return {
        "settings": {"host_name": "rsstag.test", "no_category_name": ""},
        BAZQUX: {"api_host": "bazqux.test"},
    }


def _connection_returning(body: Any) -> MagicMock:
    payload: bytes = body if isinstance(body, bytes) else json.dumps(body).encode()
    connection: MagicMock = MagicMock()
    connection.getresponse.return_value.read.return_value = payload
    return connection


class TestBazquxListFeeds(unittest.TestCase):
    def setUp(self) -> None:
        self.provider: BazquxProvider = BazquxProvider(_config())
        self.user: Dict[str, Any] = {"sid": "alice", "token": "t0ken"}

    def _list_feeds(self, body: Any) -> List[dict]:
        with patch(
            "rsstag.providers.bazqux.client.HTTPSConnection",
            return_value=_connection_returning(body),
        ):
            return self.provider.list_feeds(self.user)

    def test_provider_advertises_the_capability(self) -> None:
        self.assertTrue(supports_feeds_list(BazquxProvider))

    def test_builds_one_feed_document_per_subscription(self) -> None:
        feeds: List[dict] = self._list_feeds(_SUBSCRIPTIONS)

        self.assertEqual(len(feeds), 2)
        self.assertEqual([feed["title"] for feed in feeds], ["News", "Blog"])
        self.assertEqual([feed["owner"] for feed in feeds], ["alice", "alice"])
        self.assertEqual([feed["provider"] for feed in feeds], [BAZQUX, BAZQUX])

    def test_feed_id_matches_the_one_download_derives_from_posts(self) -> None:
        feeds: List[dict] = self._list_feeds(_SUBSCRIPTIONS)

        # download() stores md5(post["origin"]["streamId"]), and bazqux echoes
        # back the subscription id it was asked for as that streamId.
        stream_id: str = "feed/http://news.example/rss"
        self.assertEqual(
            feeds[0]["feed_id"], md5(stream_id.encode("utf-8")).hexdigest()
        )
        self.assertEqual(feeds[0]["origin_feed_id"], stream_id)

    def test_uses_the_subscription_category_label(self) -> None:
        feeds: List[dict] = self._list_feeds(_SUBSCRIPTIONS)

        self.assertEqual(feeds[0]["category_id"], "Tech")
        self.assertEqual(feeds[0]["category_title"], "Tech")

    def test_falls_back_to_the_no_category_name(self) -> None:
        feeds: List[dict] = self._list_feeds(_SUBSCRIPTIONS)

        self.assertEqual(feeds[1]["category_id"], self.provider.no_category_name)

    def test_local_urls_point_at_the_feed_and_category_pages(self) -> None:
        feeds: List[dict] = self._list_feeds(_SUBSCRIPTIONS)

        self.assertEqual(feeds[0]["local_url"], "/feed/{}".format(feeds[0]["feed_id"]))
        self.assertEqual(feeds[0]["category_local_url"], "/category/Tech")

    def test_empty_subscriptions_list_yields_no_feeds(self) -> None:
        self.assertEqual(self._list_feeds({"subscriptions": []}), [])
        self.assertEqual(self._list_feeds({}), [])

    def test_raises_when_the_subscriptions_can_not_be_read(self) -> None:
        # A broken response must fail the task instead of silently reporting
        # "0 sources", which would look like a successful refresh.
        with self.assertRaises(RuntimeError):
            self._list_feeds(b"not json")

    def test_raises_when_the_request_fails(self) -> None:
        connection: MagicMock = MagicMock()
        connection.request.side_effect = OSError("connection refused")
        with patch(
            "rsstag.providers.bazqux.client.HTTPSConnection", return_value=connection
        ):
            with self.assertRaises(RuntimeError):
                self.provider.list_feeds(self.user)


class TestBazquxDownloadSubscriptionsFailure(unittest.TestCase):
    """``download`` shares the fetch, so it must fail loudly too.

    ``handle_download`` reports success for a run that yields nothing, so an
    unreadable subscriptions list has to raise: otherwise a bazqux outage is
    logged as a completed download of 0 posts.
    """

    def setUp(self) -> None:
        self.provider: BazquxProvider = BazquxProvider(_config())
        self.user: Dict[str, Any] = {"sid": "alice", "token": "t0ken"}

    def test_raises_on_a_broken_response(self) -> None:
        with patch(
            "rsstag.providers.bazqux.client.HTTPSConnection",
            return_value=_connection_returning(b"not json"),
        ):
            with self.assertRaises(RuntimeError):
                list(self.provider.download(self.user))


class TestBazquxListSubscriptions(unittest.TestCase):
    """The picker on /provider/bazqux/feeds keeps its forgiving behaviour."""

    def setUp(self) -> None:
        self.provider: BazquxProvider = BazquxProvider(_config())
        self.user: Dict[str, Any] = {"sid": "alice", "token": "t0ken"}

    def test_groups_subscriptions_by_category(self) -> None:
        with patch(
            "rsstag.providers.bazqux.client.HTTPSConnection",
            return_value=_connection_returning(_SUBSCRIPTIONS),
        ):
            data: Dict[str, Any] = self.provider.list_subscriptions(self.user)

        self.assertEqual(
            data["categories"], sorted(["Tech", self.provider.no_category_name])
        )
        self.assertEqual(data["feeds"][0]["category"], "Tech")

    def test_returns_empty_data_on_a_broken_response(self) -> None:
        with patch(
            "rsstag.providers.bazqux.client.HTTPSConnection",
            return_value=_connection_returning(b"not json"),
        ):
            data: Dict[str, Any] = self.provider.list_subscriptions(self.user)

        self.assertEqual(data, {"categories": [], "feeds": []})


if __name__ == "__main__":
    unittest.main()
