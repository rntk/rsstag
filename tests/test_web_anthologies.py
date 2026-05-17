import json
import unittest
from unittest.mock import MagicMock

from bson import ObjectId

from rsstag.tasks import TASK_ANTHOLOGY
from rsstag.web.anthologies import (
    _collect_source_refs,
    _find_node_by_id,
    _parse_create_payload,
    _render_markdown,
    _resolve_read_target,
    _resolve_sentences_target,
    _serialize_anthology,
)
from tests.web_test_utils import MongoWebTestCase


class TestWebAnthologies(MongoWebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.owner = "anthologywebuser"
        _user_data, self.sid = self.seed_test_user(self.owner, "pass")
        self.minimal_data = self.seed_minimal_data(self.sid)
        self.client = self.get_authenticated_client(self.sid)

        # Replace simple letters doc with structured one for read-state rollups.
        self.test_db.letters.delete_many({"owner": self.sid})
        self.test_db.letters.insert_one(
            {
                "owner": self.sid,
                "letters": {
                    "t": {
                        "letter": "t",
                        "local_url": "/group/tag/startwith/t/1",
                        "unread_count": 2,
                    }
                },
            }
        )
        self.test_db.posts.update_many(
            {"owner": self.sid},
            {"$set": {"bi_grams": ["test phrase"], "read": False}},
        )
        self.test_db.bi_grams.update_one(
            {"owner": self.sid, "tag": "test phrase"},
            {"$set": {"unread_count": 2}},
        )
        self.app.post_grouping.save_grouped_posts(
            self.sid,
            ["test-post-1"],
            sentences=[
                {"number": 0, "text": "Muse article opening", "read": False},
                {"number": 1, "text": "Anthology source detail", "read": False},
            ],
            groups={"Muse > Albums": [0, 1]},
        )

    def _seed_anthology(
        self,
        seed_value: str = "testtag",
        status: str = "pending",
        result: dict | None = None,
    ) -> str:
        """Create an anthology via the app layer and return its id."""
        anthology_id = self.app.anthologies.create(
            self.sid, "tag", seed_value, {"mode": "all"}
        )
        assert anthology_id is not None
        if status != "pending" or result is not None:
            update: dict = {"$set": {"status": status}}
            if result is not None:
                update["$set"]["result"] = result
            self.test_db.anthologies.update_one(
                {"_id": self.app.anthologies._to_object_id(anthology_id)},
                update,
            )
        return anthology_id

    def _seed_run(self, anthology_id: str, status: str = "done") -> str:
        run_id = self.app.anthology_runs.create(anthology_id, self.sid)
        assert run_id is not None
        if status != "processing":
            self.app.anthology_runs.finish(run_id, status)
        return run_id

    # ------------------------------------------------------------------
    # on_anthologies_get
    # ------------------------------------------------------------------
    def test_on_anthologies_get_returns_200(self) -> None:
        response = self.client.get("/anthologies")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Anthologies", body)

    def test_on_anthologies_get_lists_user_anthologies(self) -> None:
        self._seed_anthology(seed_value="python")
        response = self.client.get("/anthologies")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("python", body)

    def test_on_anthologies_get_respects_status_filter(self) -> None:
        self._seed_anthology(seed_value="done-tag", status="done")
        self._seed_anthology(seed_value="pending-tag", status="pending")
        response = self.client.get("/anthologies?status=done")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("done-tag", body)
        self.assertNotIn("pending-tag", body)

    # ------------------------------------------------------------------
    # on_anthologies_detail_get
    # ------------------------------------------------------------------
    def test_on_anthologies_detail_get_returns_200(self) -> None:
        anthology_id = self._seed_anthology(seed_value="rust")
        response = self.client.get(f"/anthologies/{anthology_id}")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("rust", body)

    def test_on_anthologies_detail_get_missing_returns_404(self) -> None:
        response = self.client.get("/anthologies/nonexistent-id")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"Anthology not found", response.data)

    def test_on_anthologies_detail_get_renders_hierarchy_and_run(self) -> None:
        anthology_id = self._seed_anthology(seed_value="testtag", status="done")
        run_id = self._seed_run(anthology_id, status="done")
        self.app.anthologies.update_result(
            anthology_id,
            {
                "title": "testtag anthology",
                "summary": "Anthology summary",
                "source_refs": [{"post_id": "test-post-1", "title": "Test Post 1"}],
                "sub_anthologies": [
                    {
                        "title": "Child chapter",
                        "summary": "Nested summary",
                        "source_refs": [],
                        "sub_anthologies": [],
                    }
                ],
            },
            run_id,
            {"post_grouping_updated_at": 1700000000, "post_grouping_doc_ids": ["test-post-1"]},
        )
        response = self.client.get(f"/anthologies/{anthology_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Hierarchy", response.data)
        self.assertIn(b"Agent run", response.data)
        self.assertIn(b"Child chapter", response.data)
        self.assertIn(f"/api/anthologies/{anthology_id}".encode("utf-8"), response.data)
        self.assertIn(b"Retry", response.data)
        self.assertIn(b"Export", response.data)

    # ------------------------------------------------------------------
    # on_anthologies_api_list_get
    # ------------------------------------------------------------------
    def test_on_anthologies_api_list_get_returns_200(self) -> None:
        self._seed_anthology(seed_value="golang")
        response = self.client.get("/api/anthologies")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("data", data)
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["seed_value"], "golang")

    def test_on_anthologies_api_list_get_empty_list(self) -> None:
        response = self.client.get("/api/anthologies")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["data"], [])

    def test_on_anthologies_api_list_get_status_filter(self) -> None:
        self._seed_anthology(seed_value="done-tag", status="done")
        self._seed_anthology(seed_value="pending-tag", status="pending")
        response = self.client.get("/api/anthologies?status=done")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["seed_value"], "done-tag")

    # ------------------------------------------------------------------
    # on_anthologies_api_create_post
    # ------------------------------------------------------------------
    def test_on_anthologies_api_create_post_creates_anthology(self) -> None:
        response = self.client.post(
            "/api/anthologies",
            data={"seed_type": "tag", "seed_value": "nodejs", "scope_mode": "all"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("anthology_id", data["data"])
        self.assertEqual(data["data"]["status"], "pending")
        self.assertEqual(data["data"]["anthology"]["seed_value"], "nodejs")

        task = self.test_db.tasks.find_one({"user": self.sid, "type": TASK_ANTHOLOGY})
        self.assertIsNotNone(task)

    def test_on_anthologies_api_create_post_json_payload(self) -> None:
        response = self.client.post(
            "/api/anthologies",
            data=json.dumps(
                {"seed_type": "tag", "seed_value": "docker", "scope": {"mode": "all"}}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["data"]["anthology"]["seed_value"], "docker")

    def test_on_anthologies_api_create_post_deduplicates_existing(self) -> None:
        first = self.client.post(
            "/api/anthologies",
            data={"seed_type": "tag", "seed_value": "duplicate", "scope_mode": "all"},
        )
        self.assertEqual(first.status_code, 200)
        first_id = first.get_json()["data"]["anthology_id"]

        second = self.client.post(
            "/api/anthologies",
            data={"seed_type": "tag", "seed_value": "duplicate", "scope_mode": "all"},
        )
        self.assertEqual(second.status_code, 200)
        second_id = second.get_json()["data"]["anthology_id"]
        self.assertEqual(first_id, second_id)

    def test_on_anthologies_api_create_post_rejects_non_tag_seed_type(self) -> None:
        response = self.client.post(
            "/api/anthologies",
            data={"seed_type": "feed", "seed_value": "feed-1"},
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)
        self.assertIn("Only tag anthologies are supported", data["error"])

    def test_on_anthologies_api_create_post_rejects_empty_seed_value(self) -> None:
        response = self.client.post(
            "/api/anthologies",
            data={"seed_type": "tag", "seed_value": ""},
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("seed_value is required", data["error"])

    # ------------------------------------------------------------------
    # on_anthologies_api_detail_get
    # ------------------------------------------------------------------
    def test_on_anthologies_api_detail_get_returns_200(self) -> None:
        anthology_id = self._seed_anthology(
            seed_value="elixir",
            status="done",
            result={
                "title": "Elixir",
                "summary": "Elixir language coverage.",
                "source_refs": [],
                "sub_anthologies": [],
            },
        )
        response = self.client.get(f"/api/anthologies/{anthology_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["data"]["seed_value"], "elixir")
        self.assertEqual(data["data"]["result"]["title"], "Elixir")

    def test_on_anthologies_api_detail_get_missing_returns_404(self) -> None:
        response = self.client.get("/api/anthologies/nonexistent-id")
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertIn("Anthology not found", data["error"])

    def test_on_anthologies_api_detail_get_includes_latest_run(self) -> None:
        anthology_id = self._seed_anthology(seed_value="kotlin", status="done")
        run_id = self._seed_run(anthology_id, status="done")
        self.app.anthologies.update_result(
            anthology_id,
            {"title": "Kotlin", "summary": "s", "source_refs": [], "sub_anthologies": []},
            run_id,
        )
        response = self.client.get(f"/api/anthologies/{anthology_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["data"]["latest_run"]["_id"], run_id)

    # ------------------------------------------------------------------
    # on_anthologies_api_run_get
    # ------------------------------------------------------------------
    def test_on_anthologies_api_run_get_returns_404_when_no_run(self) -> None:
        anthology_id = self._seed_anthology(seed_value="haskell")
        response = self.client.get(f"/api/anthologies/{anthology_id}/run")
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertIn("Run not found", data["error"])

    def test_on_anthologies_api_run_get_returns_run_when_exists(self) -> None:
        anthology_id = self._seed_anthology(seed_value="kotlin")
        self._seed_run(anthology_id, status="done")
        response = self.client.get(f"/api/anthologies/{anthology_id}/run")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["data"]["status"], "done")

    # ------------------------------------------------------------------
    # on_anthologies_api_retry_post
    # ------------------------------------------------------------------
    def test_on_anthologies_api_retry_post_triggers_retry(self) -> None:
        anthology_id = self._seed_anthology(
            seed_value="clojure",
            status="done",
            result={
                "title": "Clojure",
                "summary": "s",
                "source_refs": [],
                "sub_anthologies": [],
            },
        )
        self._seed_run(anthology_id, status="done")
        response = self.client.post(f"/api/anthologies/{anthology_id}/retry")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["data"]["status"], "pending")

        task = self.test_db.tasks.find_one({"user": self.sid, "type": TASK_ANTHOLOGY})
        self.assertIsNotNone(task)

    def test_on_anthologies_api_retry_post_missing_anthology_returns_404(self) -> None:
        response = self.client.post("/api/anthologies/nonexistent-id/retry")
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertIn("Anthology not found", data["error"])

    def test_on_anthologies_api_retry_post_already_processing_returns_400(self) -> None:
        anthology_id = self._seed_anthology(seed_value="scala", status="processing")
        response = self.client.post(f"/api/anthologies/{anthology_id}/retry")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("already processing", data["error"])

    # ------------------------------------------------------------------
    # on_anthologies_api_read_post
    # ------------------------------------------------------------------
    def test_on_anthologies_api_read_post_marks_sentences_read(self) -> None:
        anthology_id = self._seed_anthology(
            seed_value="muse",
            status="done",
            result={
                "title": "Muse",
                "summary": "s",
                "source_refs": [
                    {
                        "post_id": "test-post-1",
                        "sentence_indices": [0, 1],
                        "topic_path": "Muse > Albums",
                        "tag": "muse",
                    }
                ],
                "sub_anthologies": [
                    {
                        "node_id": "albums",
                        "title": "Albums",
                        "summary": "s",
                        "source_refs": [
                            {
                                "post_id": "test-post-1",
                                "sentence_indices": [0],
                                "topic_path": "Muse > Albums",
                                "tag": "muse",
                            }
                        ],
                        "sub_anthologies": [],
                    }
                ],
            },
        )
        response = self.client.post(
            f"/api/anthologies/{anthology_id}/read",
            data=json.dumps(
                {
                    "readed": True,
                    "target": {"kind": "node", "node_id": "albums"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        grouping = self.test_db.post_grouping.find_one(
            {"owner": self.sid, "post_ids": "test-post-1"}
        )
        self.assertTrue(grouping["sentences"][0]["read"])

    def test_on_anthologies_api_read_post_no_target_returns_400(self) -> None:
        anthology_id = self._seed_anthology(
            seed_value="dart",
            status="done",
            result={
                "title": "Dart",
                "summary": "s",
                "source_refs": [],
                "sub_anthologies": [],
            },
        )
        response = self.client.post(
            f"/api/anthologies/{anthology_id}/read",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("target is required", data["error"])

    def test_on_anthologies_api_read_post_anthology_not_found_returns_404(self) -> None:
        response = self.client.post(
            "/api/anthologies/nonexistent-id/read",
            data=json.dumps({"target": {"kind": "anthology"}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertIn("Anthology not found", data["error"])

    def test_on_anthologies_api_read_post_no_result_returns_400(self) -> None:
        anthology_id = self._seed_anthology(seed_value="swift", status="pending")
        response = self.client.post(
            f"/api/anthologies/{anthology_id}/read",
            data=json.dumps({"target": {"kind": "anthology"}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("Anthology result not ready", data["error"])

    def test_on_anthologies_api_read_post_unresolved_target_returns_400(self) -> None:
        anthology_id = self._seed_anthology(
            seed_value="lua",
            status="done",
            result={
                "title": "Lua",
                "summary": "s",
                "source_refs": [],
                "sub_anthologies": [],
            },
        )
        response = self.client.post(
            f"/api/anthologies/{anthology_id}/read",
            data=json.dumps({"target": {"kind": "node", "node_id": "missing"}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("No source refs resolved for target", data["error"])

    # ------------------------------------------------------------------
    # on_anthologies_api_export_get
    # ------------------------------------------------------------------
    def test_on_anthologies_api_export_get_json(self) -> None:
        anthology_id = self._seed_anthology(
            seed_value="ruby",
            status="done",
            result={
                "title": "Ruby",
                "summary": "Ruby language.",
                "source_refs": [],
                "sub_anthologies": [],
            },
        )
        response = self.client.get(f"/api/anthologies/{anthology_id}/export?format=json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        disposition = response.headers.get("Content-Disposition", "")
        self.assertIn("attachment", disposition)
        data = json.loads(response.data)
        self.assertEqual(data["title"], "Ruby")

    def test_on_anthologies_api_export_get_markdown(self) -> None:
        anthology_id = self._seed_anthology(
            seed_value="csharp",
            status="done",
            result={
                "title": "C#",
                "summary": "C# language.",
                "source_refs": [],
                "sub_anthologies": [],
            },
        )
        response = self.client.get(
            f"/api/anthologies/{anthology_id}/export?format=markdown"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "text/markdown")
        body = response.get_data(as_text=True)
        self.assertIn("C#", body)
        self.assertIn("# C#", body)

    def test_on_anthologies_api_export_get_unsupported_format(self) -> None:
        anthology_id = self._seed_anthology(
            seed_value="php",
            status="done",
            result={
                "title": "PHP",
                "summary": "s",
                "source_refs": [],
                "sub_anthologies": [],
            },
        )
        response = self.client.get(f"/api/anthologies/{anthology_id}/export?format=xml")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("Unsupported export format", data["error"])

    def test_on_anthologies_api_export_get_no_result_returns_400(self) -> None:
        anthology_id = self._seed_anthology(seed_value="swift", status="pending")
        response = self.client.get(f"/api/anthologies/{anthology_id}/export")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("Anthology result not ready", data["error"])

    def test_on_anthologies_api_export_get_missing_anthology_returns_404(self) -> None:
        response = self.client.get("/api/anthologies/nonexistent-id/export")
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertIn("Anthology not found", data["error"])

    # ------------------------------------------------------------------
    # on_anthologies_api_delete
    # ------------------------------------------------------------------
    def test_on_anthologies_api_delete_removes_anthology(self) -> None:
        anthology_id = self._seed_anthology(seed_value="perl")
        response = self.client.delete(f"/api/anthologies/{anthology_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["data"], "ok")
        doc = self.test_db.anthologies.find_one(
            {"_id": self.app.anthologies._to_object_id(anthology_id)}
        )
        self.assertIsNone(doc)

    def test_on_anthologies_api_delete_missing_returns_404(self) -> None:
        response = self.client.delete("/api/anthologies/nonexistent-id")
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertIn("Anthology not found", data["error"])

    def test_on_anthologies_api_delete_removes_runs(self) -> None:
        anthology_id = self._seed_anthology(seed_value="perl")
        self._seed_run(anthology_id, status="done")
        response = self.client.delete(f"/api/anthologies/{anthology_id}")
        self.assertEqual(response.status_code, 200)
        runs = list(
            self.test_db.anthology_runs.find(
                {"anthology_id": self.app.anthologies._to_object_id(anthology_id)}
            )
        )
        self.assertEqual(len(runs), 0)


class TestWebAnthologiesUnit(unittest.TestCase):
    """Pure unit tests for helper functions in rsstag/web/anthologies.py."""

    def test_serialize_anthology_with_result_title(self) -> None:
        item: dict = {
            "_id": "id1",
            "seed_type": "tag",
            "seed_value": "python",
            "scope": {"mode": "all"},
            "status": "done",
            "stale": False,
            "created_at": 1,
            "updated_at": 2,
            "current_run_id": None,
            "result": {"title": "Python Language"},
        }
        serialized = _serialize_anthology(item)
        self.assertEqual(serialized["title"], "Python Language")
        self.assertEqual(serialized["seed_value"], "python")

    def test_serialize_anthology_fallback_to_seed_value(self) -> None:
        item: dict = {
            "_id": "id1",
            "seed_type": "tag",
            "seed_value": "rust",
            "scope": {"mode": "all"},
            "status": "pending",
            "stale": False,
            "created_at": 1,
            "updated_at": 2,
            "current_run_id": None,
            "result": None,
        }
        serialized = _serialize_anthology(item)
        self.assertEqual(serialized["title"], "rust")

    def test_parse_create_payload_from_json(self) -> None:
        request = MagicMock()
        request.get_json.return_value = {
            "seed_type": "tag",
            "seed_value": "go",
            "scope": {"mode": "all"},
        }
        request.form = {}
        payload = _parse_create_payload(request)
        self.assertEqual(payload["seed_type"], "tag")
        self.assertEqual(payload["seed_value"], "go")

    def test_parse_create_payload_from_form(self) -> None:
        request = MagicMock()
        request.get_json.return_value = None
        request.form = {
            "seed_type": "tag",
            "seed_value": "java",
            "scope_mode": "unread",
        }
        payload = _parse_create_payload(request)
        self.assertEqual(payload["seed_type"], "tag")
        self.assertEqual(payload["seed_value"], "java")
        self.assertEqual(payload["scope"]["mode"], "unread")

    def test_render_markdown(self) -> None:
        node: dict = {
            "title": "Root",
            "summary": "Root summary.",
            "sub_anthologies": [
                {
                    "title": "Child",
                    "summary": "Child summary.",
                    "sub_anthologies": [],
                }
            ],
        }
        md = _render_markdown(node)
        self.assertIn("# Root", md)
        self.assertIn("## Child", md)
        self.assertIn("Root summary.", md)

    def test_collect_source_refs(self) -> None:
        node: dict = {
            "source_refs": [{"post_id": "p1"}],
            "sub_anthologies": [
                {"source_refs": [{"post_id": "p2"}], "sub_anthologies": []}
            ],
        }
        refs = _collect_source_refs(node)
        self.assertEqual(len(refs), 2)
        self.assertEqual(refs[0]["post_id"], "p1")
        self.assertEqual(refs[1]["post_id"], "p2")

    def test_find_node_by_id(self) -> None:
        node: dict = {
            "node_id": "root",
            "sub_anthologies": [
                {"node_id": "child1", "sub_anthologies": []},
                {"node_id": "child2", "sub_anthologies": []},
            ],
        }
        self.assertIsNone(_find_node_by_id(node, "missing"))
        self.assertEqual(_find_node_by_id(node, "root")["node_id"], "root")
        self.assertEqual(_find_node_by_id(node, "child2")["node_id"], "child2")

    def test_resolve_read_target_unknown_kind(self) -> None:
        result: dict = {"source_refs": [{"post_id": "p1"}], "sub_anthologies": []}
        target = {"kind": "unknown"}
        self.assertEqual(_resolve_read_target(result, target), [])

    def test_resolve_read_target_anthology_kind(self) -> None:
        result: dict = {"source_refs": [{"post_id": "p1"}], "sub_anthologies": []}
        target = {"kind": "anthology"}
        refs = _resolve_read_target(result, target)
        self.assertEqual(len(refs), 1)

    def test_resolve_sentences_target(self) -> None:
        result: dict = {
            "source_refs": [
                {
                    "post_id": "p1",
                    "sentence_indices": [0, 1, 2],
                    "topic_path": "A > B",
                    "tag": "t1",
                }
            ],
            "sub_anthologies": [],
        }
        target = {"post_id": "p1", "sentence_indices": [1, 2]}
        refs = _resolve_sentences_target(result, target)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["sentence_indices"], [1, 2])


if __name__ == "__main__":
    unittest.main()
