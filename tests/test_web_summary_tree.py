"""Web tests for /summary-tree/ pages and the summary tree API."""

import json
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from rsstag.tasks import TASK_SUMMARY_TREE
from rsstag.web.routes import RSSTagRoutes
from rsstag.web.summary_tree import _result_payload, filters_from_args, serialize_summary
from tests.web_test_utils import MongoWebTestCase


def _request(query: str) -> Request:
    return Request(EnvironBuilder(path="/summary-tree/", query_string=query).get_environ())


class TestSummaryTreeHelpers(unittest.TestCase):
    def test_routes_resolve(self) -> None:
        adapter = RSSTagRoutes("localhost").get_werkzeug_routes().bind("localhost")
        self.assertEqual(adapter.match("/summary-tree/")[0], "on_summary_tree_get")
        self.assertEqual(adapter.match("/summary-tree/abc")[0], "on_summary_tree_detail_get")
        self.assertEqual(adapter.match("/api/summary-trees", method="POST")[0], "on_summary_trees_api_create_post")

    def test_filters_from_args(self) -> None:
        user: Dict[str, Any] = {"settings": {"only_unread": True}}
        filters = filters_from_args(_request("tag=apple&tags=a,b&feed=f1&feed=f2"), user)
        self.assertEqual(filters["entity"], "apple")
        self.assertEqual(filters["tags"], ["a", "b"])
        self.assertEqual(filters["feed_ids"], ["f1", "f2"])
        self.assertTrue(filters["only_unread"])
        self.assertEqual(filters_from_args(_request("tag=x&unread=0"), user)["only_unread"], "0")

    def test_serialize_and_feed_titles(self) -> None:
        summary = serialize_summary({"_id": "1", "focus": "apple", "filters": {"entity": "apple"}, "status": "done"})
        self.assertEqual(summary["filters_label"], "apple")
        app = MagicMock()
        app.feeds.get_by_feed_ids.return_value = [{"feed_id": "f1", "title": "Feed"}]
        payload = _result_payload(app, "u", {"root_id": "n1", "nodes": {}, "posts": [{"pid": "p.1", "feed_id": "f1"}]})
        self.assertEqual(payload["posts"]["p.1"]["feed_title"], "Feed")


class TestWebSummaryTree(MongoWebTestCase):
    def setUp(self) -> None:
        super().setUp()
        _user, self.sid = self.seed_test_user("summarytreeuser", "pass")
        self.client = self.get_authenticated_client(self.sid)
        self.test_db.summary_trees.delete_many({})
        self.test_db.tasks.delete_many({})

    def _post_json(self, url: str, payload: Dict[str, Any]) -> tuple:
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        return response.status_code, json.loads(response.get_data(as_text=True))

    def test_create_queues_task_and_reuses_tree(self) -> None:
        status, body = self._post_json("/api/summary-trees", {"filters": {"entity": "apple"}})
        self.assertEqual(status, 200)
        tree_id: str = body["data"]["tree_id"]
        self.assertEqual(self.test_db.tasks.count_documents({"user": self.sid, "type": TASK_SUMMARY_TREE}), 1)
        _status, again = self._post_json("/api/summary-trees", {"filters": {"entity": "apple"}})
        self.assertEqual(again["data"]["tree_id"], tree_id)

    def test_create_requires_entity(self) -> None:
        status, _body = self._post_json("/api/summary-trees", {"filters": {"tags": ["a"]}})
        self.assertEqual(status, 400)

    def test_list_page_and_redirect_to_existing(self) -> None:
        self.assertEqual(self.client.get("/summary-tree/?tag=apple").status_code, 200)
        _status, body = self._post_json(
            "/api/summary-trees", {"filters": {"entity": "apple", "only_unread": False}}
        )
        response = self.client.get("/summary-tree/?tag=apple&unread=0")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith(body["data"]["url"]))
        detail = self.client.get(body["data"]["url"])
        self.assertEqual(detail.status_code, 200)
        self.assertIn("summary-tree-data", detail.get_data(as_text=True))

    def test_delete(self) -> None:
        _status, body = self._post_json("/api/summary-trees", {"filters": {"entity": "apple"}})
        url: str = f"/api/summary-trees/{body['data']['tree_id']}"
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 404)


if __name__ == "__main__":
    unittest.main()
