"""Web tests for the snippet-cluster anthology explorer."""

import copy
import json
import time
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import patch

from bson import ObjectId

from rsstag.tasks import TASK_ANTHOLOGY
from rsstag.web.anthologies import (
    _annotate_read_counts,
    _parse_create_payload,
    _resolve_target_snippet_ids,
    _serialize_summary,
    _source_refs,
)
from tests.web_test_utils import MongoWebTestCase


def build_result() -> Dict[str, Any]:
    """Two themes, two clusters, one unsorted snippet over two posts."""

    def snippet(sid: str, post_id: str, indices: List[int], date: float) -> Dict[str, Any]:
        return {
            "id": sid,
            "post_id": post_id,
            "sentence_indices": indices,
            "topic_path": "Consoles > Hardware",
            "title": f"Title {post_id}",
            "feed_id": "test-feed-1",
            "date": date,
            "preview": "preview",
        }

    def cluster(cid: str, label: str, snippet_ids: List[str]) -> Dict[str, Any]:
        return {
            "id": cid,
            "label": label,
            "kind": "release",
            "score": 4,
            "intruder_ok": True,
            "keywords": ["console"],
            "cohesion": 0.42,
            "snippet_ids": snippet_ids,
            "start_snippet_id": snippet_ids[0],
            "date_min": 1700000000.0,
            "date_max": 1700000001.0,
            "feed_ids": ["test-feed-1"],
        }

    return {
        "themes": [
            {"id": "t0", "label": "Launch", "keywords": ["launch"], "size": 2, "cluster_ids": ["c1"]},
            {"id": "t1", "label": "Prices", "keywords": ["price"], "size": 1, "cluster_ids": ["c2"]},
        ],
        "clusters": {
            "c1": cluster("c1", "Launch date", ["s1", "s2"]),
            "c2": cluster("c2", "Price cut", ["s3"]),
        },
        "unsorted": ["s4"],
        "snippets": {
            "s1": snippet("s1", "test-post-1", [0, 1], 1700000000.0),
            "s2": snippet("s2", "test-post-1", [2], 1700000000.0),
            "s3": snippet("s3", "test-post-2", [0, 1], 1700000001.0),
            "s4": snippet("s4", "test-post-2", [2], 1700000001.0),
        },
        "metrics": {"snippets_total": 4, "coverage": 0.75, "llm_calls": 3},
    }


def sentences(read: Optional[set] = None) -> List[Dict[str, Any]]:
    read = read or set()
    return [{"number": i, "text": f"Console sentence {i}", "read": i in read} for i in range(3)]


class TestWebAnthologies(MongoWebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.owner = "anthologywebuser"
        _user_data, self.sid = self.seed_test_user(self.owner, "pass")
        self.seed_minimal_data(self.sid)
        self.client = self.get_authenticated_client(self.sid)
        self.test_db.letters.delete_many({"owner": self.sid})
        self.test_db.letters.insert_one(
            {
                "owner": self.sid,
                "letters": {"t": {"letter": "t", "local_url": "/group/tag/startwith/t/1", "unread_count": 2}},
            }
        )
        for pid in ("test-post-1", "test-post-2"):
            self.test_db.posts.update_one({"owner": self.sid, "pid": pid}, {"$set": {"read": False, "id": pid}})
        self.app.post_grouping.save_grouped_posts(self.sid, ["test-post-1"], sentences(), {})
        self.app.post_grouping.save_grouped_posts(self.sid, ["test-post-2"], sentences({0}), {})

    def _seed(
        self,
        seed_value: str = "testtag",
        status: str = "done",
        result: Optional[Dict[str, Any]] = None,
        **extra: Any,
    ) -> str:
        now: float = time.time()
        doc: Dict[str, Any] = {
            "owner": self.sid,
            "seed_type": "tag",
            "seed_value": seed_value,
            "scope": {"mode": "all"},
            "scope_hash": seed_value,
            "status": status,
            "stage": "done" if status == "done" else None,
            "error": None,
            "stale": False,
            "created_at": now,
            "updated_at": now,
            "result": result,
        }
        doc.update(extra)
        return str(self.test_db.anthologies.insert_one(doc).inserted_id)

    def _seed_done(self) -> str:
        return self._seed(result=build_result())

    def _get_json(self, url: str) -> tuple[int, Dict[str, Any]]:
        response = self.client.get(url)
        return response.status_code, json.loads(response.get_data(as_text=True))

    def _post_json(self, url: str, payload: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        return response.status_code, json.loads(response.get_data(as_text=True))

    # -- pages ---------------------------------------------------------------
    def test_list_page_renders_items_and_feeds(self) -> None:
        self._seed(seed_value="python", status="processing", stage="merge")
        response = self.client.get("/anthologies")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("python", body)
        self.assertIn("test-feed-1", body)
        self.assertIn("/static/js/anthologies-list.js", body)

    def test_list_page_status_filter(self) -> None:
        self._seed(seed_value="done-tag", status="done")
        self._seed(seed_value="pending-tag", status="pending")
        body = self.client.get("/anthologies?status=done").get_data(as_text=True)
        self.assertIn("done-tag", body)
        self.assertNotIn("pending-tag", body)

    def test_detail_page_renders_and_escapes(self) -> None:
        anthology_id = self._seed(seed_value="<script>x</script>", result=build_result())
        response = self.client.get(f"/anthologies/{anthology_id}")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("<script>x</script>", body)
        self.assertIn("&lt;script&gt;x&lt;/script&gt;", body)
        self.assertIn("anthology-detail-data", body)
        self.assertIn("/static/js/anthology-detail.js", body)

    def test_detail_page_404(self) -> None:
        self.assertEqual(self.client.get("/anthologies/not-an-id").status_code, 404)
        self.assertEqual(self.client.get(f"/anthologies/{ObjectId()}").status_code, 404)

    # -- list / create -------------------------------------------------------
    def test_api_list(self) -> None:
        anthology_id = self._seed_done()
        status, payload = self._get_json("/api/anthologies")
        self.assertEqual(status, 200)
        item = payload["data"][0]
        self.assertEqual(item["id"], anthology_id)
        self.assertEqual(item["themes_count"], 2)
        self.assertEqual(item["metrics"]["snippets_total"], 4)
        self.assertNotIn("result", item)

    def test_api_create_enqueues_task(self) -> None:
        status, payload = self._post_json(
            "/api/anthologies",
            {"seed_type": "tag", "seed_value": "newtag", "scope": {"mode": "posts", "post_ids": ["test-post-1"]}},
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["data"]["anthology_id"])
        self.assertEqual(payload["data"]["status"], "pending")
        task = self.test_db.tasks.find_one({"user": self.sid, "type": TASK_ANTHOLOGY})
        self.assertIsNotNone(task)

    def test_api_create_validation(self) -> None:
        status, payload = self._post_json("/api/anthologies", {"seed_type": "tag", "seed_value": " "})
        self.assertEqual(status, 400)
        self.assertIn("seed_value", payload["error"])
        status, _ = self._post_json("/api/anthologies", {"seed_type": "feed", "seed_value": "x"})
        self.assertEqual(status, 400)

    # -- detail / clusters ---------------------------------------------------
    def test_api_detail_read_counts_without_snippets(self) -> None:
        anthology_id = self._seed_done()
        status, payload = self._get_json(f"/api/anthologies/{anthology_id}")
        self.assertEqual(status, 200)
        result = payload["data"]["result"]
        self.assertNotIn("snippets", result)
        self.assertEqual(result["clusters"]["c1"]["read"], {"unread": 3, "total": 3})
        self.assertEqual(result["clusters"]["c2"]["read"], {"unread": 1, "total": 2})
        self.assertEqual(result["themes"][1]["read"], {"unread": 1, "total": 2})
        self.assertEqual(result["unsorted_read"], {"unread": 1, "total": 1})
        self.assertEqual(result["total_read"], {"unread": 5, "total": 6})
        self.assertIn("test-feed-1", payload["data"]["feed_titles"])

    def test_api_detail_pending_has_no_result(self) -> None:
        anthology_id = self._seed(status="pending")
        status, payload = self._get_json(f"/api/anthologies/{anthology_id}")
        self.assertEqual(status, 200)
        self.assertIsNone(payload["data"]["result"])
        self.assertEqual(payload["data"]["status"], "pending")

    def test_api_detail_404_and_other_owner(self) -> None:
        other_id = str(
            self.test_db.anthologies.insert_one({"owner": "someone-else", "seed_value": "x", "status": "done"}).inserted_id
        )
        self.assertEqual(self.client.get(f"/api/anthologies/{other_id}").status_code, 404)
        self.assertEqual(self.client.get("/api/anthologies/bad-id").status_code, 404)

    def test_api_cluster_returns_snippets_with_sentences(self) -> None:
        anthology_id = self._seed_done()
        status, payload = self._get_json(f"/api/anthologies/{anthology_id}/clusters/c2")
        self.assertEqual(status, 200)
        data = payload["data"]
        self.assertEqual(data["cluster"]["id"], "c2")
        snippet = data["snippets"][0]
        self.assertEqual(snippet["id"], "s3")
        self.assertEqual([s["number"] for s in snippet["sentences"]], [0, 1])
        self.assertEqual([s["read"] for s in snippet["sentences"]], [True, False])
        self.assertFalse(snippet["read"])

    def test_api_cluster_order_and_unsorted(self) -> None:
        anthology_id = self._seed_done()
        _, payload = self._get_json(f"/api/anthologies/{anthology_id}/clusters/c1")
        self.assertEqual([s["id"] for s in payload["data"]["snippets"]], ["s1", "s2"])
        status, payload = self._get_json(f"/api/anthologies/{anthology_id}/clusters/unsorted")
        self.assertEqual(status, 200)
        self.assertIsNone(payload["data"]["cluster"])
        self.assertEqual([s["id"] for s in payload["data"]["snippets"]], ["s4"])

    def test_api_cluster_errors(self) -> None:
        anthology_id = self._seed_done()
        self.assertEqual(self.client.get(f"/api/anthologies/{anthology_id}/clusters/nope").status_code, 404)
        self.assertEqual(self.client.get(f"/api/anthologies/{ObjectId()}/clusters/c1").status_code, 404)
        pending_id = self._seed(seed_value="pending", status="pending")
        self.assertEqual(self.client.get(f"/api/anthologies/{pending_id}/clusters/c1").status_code, 409)

    # -- read state ----------------------------------------------------------
    def test_api_read_cluster_marks_sentences(self) -> None:
        anthology_id = self._seed_done()
        status, payload = self._post_json(
            f"/api/anthologies/{anthology_id}/read", {"target": {"kind": "cluster", "id": "c2"}, "readed": True}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["result"]["clusters"]["c2"]["read"], {"unread": 0, "total": 2})
        doc = self.test_db.post_grouping.find_one({"owner": self.sid, "post_ids": "test-post-2"})
        self.assertEqual([s["read"] for s in doc["sentences"]], [True, True, False])

    def test_api_read_snippet_unread_and_theme_and_unsorted(self) -> None:
        anthology_id = self._seed_done()
        url = f"/api/anthologies/{anthology_id}/read"
        _, payload = self._post_json(url, {"target": {"kind": "theme", "id": "t0"}, "readed": True})
        self.assertEqual(payload["data"]["result"]["themes"][0]["read"]["unread"], 0)
        _, payload = self._post_json(url, {"target": {"kind": "snippet", "id": "s2"}, "readed": False})
        self.assertEqual(payload["data"]["result"]["clusters"]["c1"]["read"], {"unread": 1, "total": 3})
        _, payload = self._post_json(url, {"target": {"kind": "unsorted", "id": "unsorted"}, "readed": True})
        self.assertEqual(payload["data"]["result"]["unsorted_read"]["unread"], 0)

    def test_api_read_errors(self) -> None:
        anthology_id = self._seed_done()
        url = f"/api/anthologies/{anthology_id}/read"
        self.assertEqual(self._post_json(url, {"target": {"kind": "bogus"}})[0], 400)
        self.assertEqual(self._post_json(url, {"target": {"kind": "cluster", "id": "zz"}})[0], 400)
        self.assertEqual(self._post_json(f"/api/anthologies/{ObjectId()}/read", {"target": {"kind": "cluster", "id": "c1"}})[0], 404)
        pending_id = self._seed(seed_value="pending", status="pending")
        self.assertEqual(self._post_json(f"/api/anthologies/{pending_id}/read", {"target": {"kind": "cluster", "id": "c1"}})[0], 409)

    # -- retry / delete ------------------------------------------------------
    def test_api_retry_failed(self) -> None:
        anthology_id = self._seed(status="failed", error="boom")
        status, payload = self._post_json(f"/api/anthologies/{anthology_id}/retry", {})
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["status"], "pending")
        self.assertIsNotNone(self.test_db.tasks.find_one({"user": self.sid, "type": TASK_ANTHOLOGY}))

    def test_api_retry_rejects_processing_and_missing(self) -> None:
        anthology_id = self._seed(status="processing")
        self.assertEqual(self._post_json(f"/api/anthologies/{anthology_id}/retry", {})[0], 400)
        self.assertEqual(self._post_json(f"/api/anthologies/{ObjectId()}/retry", {})[0], 404)

    def test_api_retry_stuck_processing(self) -> None:
        anthology_id: str = self._seed(status="processing", updated_at=time.time() - 7200)
        status: int
        payload: Dict[str, Any]
        status, payload = self._get_json(f"/api/anthologies/{anthology_id}")
        self.assertTrue(payload["data"]["stuck"])
        status, payload = self._post_json(f"/api/anthologies/{anthology_id}/retry", {})
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["status"], "pending")
        self.assertIsNone(payload["data"]["stage"])
        self.assertFalse(payload["data"]["stuck"])

    def test_api_create_reports_queue_failure(self) -> None:
        status: int
        payload: Dict[str, Any]
        with patch.object(self.app.tasks, "add_task", return_value=False):
            status, payload = self._post_json("/api/anthologies", {"seed_value": "queue-failure"})
        self.assertEqual(status, 500)
        self.assertIn("Failed to queue", payload["error"])

    def test_api_retry_reports_queue_failure(self) -> None:
        anthology_id: str = self._seed(status="failed")
        status: int
        payload: Dict[str, Any]
        with patch.object(self.app.tasks, "add_task", return_value=False):
            status, payload = self._post_json(f"/api/anthologies/{anthology_id}/retry", {})
        self.assertEqual(status, 500)
        self.assertIn("Failed to queue", payload["error"])

    def test_api_delete(self) -> None:
        anthology_id = self._seed_done()
        self.assertEqual(self.client.delete(f"/api/anthologies/{anthology_id}").status_code, 200)
        self.assertIsNone(self.test_db.anthologies.find_one({"_id": ObjectId(anthology_id)}))
        self.assertEqual(self.client.delete(f"/api/anthologies/{anthology_id}").status_code, 404)


class TestAnthologyHelpers(unittest.TestCase):
    def test_resolve_target_snippet_ids(self) -> None:
        result = build_result()
        self.assertEqual(_resolve_target_snippet_ids(result, {"kind": "theme", "id": "t0"}), ["s1", "s2"])
        self.assertEqual(_resolve_target_snippet_ids(result, {"kind": "cluster", "id": "c2"}), ["s3"])
        self.assertEqual(_resolve_target_snippet_ids(result, {"kind": "unsorted"}), ["s4"])
        self.assertEqual(_resolve_target_snippet_ids(result, {"kind": "snippet", "id": "s9"}), [])
        self.assertEqual(_resolve_target_snippet_ids(result, {"kind": "theme", "id": "t9"}), [])

    def test_source_refs_merge_by_post(self) -> None:
        result = build_result()
        refs = _source_refs(["s1", "s2", "s3"], result["snippets"])
        self.assertEqual(
            refs,
            [
                {"post_id": "test-post-1", "sentence_indices": [0, 1, 2]},
                {"post_id": "test-post-2", "sentence_indices": [0, 1]},
            ],
        )

    def test_annotate_read_counts_ignores_missing_sentences(self) -> None:
        result = build_result()
        maps = {"test-post-1": {0: {"number": 0, "read": True}}}
        annotated = _annotate_read_counts(copy.deepcopy(result), maps)
        self.assertEqual(annotated["clusters"]["c1"]["read"], {"unread": 0, "total": 1})
        self.assertEqual(annotated["clusters"]["c2"]["read"], {"unread": 0, "total": 0})
        self.assertNotIn("snippets", annotated)

    def test_serialize_summary(self) -> None:
        summary = _serialize_summary({"_id": "x", "seed_value": "v", "status": "done", "result": build_result()})
        self.assertEqual(summary["themes_count"], 2)
        self.assertTrue(summary["has_result"])
        self.assertFalse(_serialize_summary({"_id": "y"})["has_result"])

    def test_parse_create_payload_form_scope(self) -> None:
        from werkzeug.test import EnvironBuilder
        from werkzeug.wrappers import Request

        builder = EnvironBuilder(method="POST", data={"seed_value": "tag", "feed_id": "f1"})
        payload = _parse_create_payload(Request(builder.get_environ()))
        self.assertEqual(payload["scope"], {"mode": "feeds", "feed_ids": ["f1"]})


if __name__ == "__main__":
    unittest.main()
