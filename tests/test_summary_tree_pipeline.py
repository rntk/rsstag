"""Summary tree store, pipeline and queue integration."""

import gzip
import json
import socket
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from rsstag.summary_tree.pipeline import SummaryTreePipeline
from rsstag.summary_tree.sources import SourcePost
from rsstag.summary_trees import STATUS_DONE, STATUS_FAILED, STATUS_PENDING, RssTagSummaryTrees
from tests.db_utils import DBHelper

MONGO_PORT: int = 8765


class FakeRouter:
    """Answers summary prompts per post title and merges by a keyword rule."""

    def __init__(self) -> None:
        self.prompts: List[str] = []

    def call(self, _settings: Any, prompts: List[str], **_kwargs: Any) -> str:
        prompt: str = prompts[0]
        self.prompts.append(prompt)
        data: Dict[str, Any] = json.loads('{"focus":' + prompt.split('\n{"focus":', 1)[1])
        answers: List[Dict[str, Any]] = []
        for node in data["nodes"]:
            if "Unrelated" in node["title"]:
                segments: List[Dict[str, Any]] = []
            elif "evidence" in node:
                segments = [{"text": node["title"] + " says things.", "from": ["1"]}]
            else:
                segments = [{"text": "Posts report prices and harvest.", "from": [
                    child["claims"][0]["cite"] for child in node["children"] if child["claims"]
                ]}]
            answers.append({"id": node["id"], "segments": segments})
        return json.dumps({"summaries": answers})


def _post(pid: str, title: str, text: str = "body", tags: List[str] = None) -> Dict[str, Any]:
    return {
        "owner": "u", "pid": pid, "feed_id": "f1", "unix_date": 100, "url": f"http://x/{pid}",
        "read": False, "tags": tags or ["apple"], "lemmas": gzip.compress(b"apple"),
        "content": {"title": title, "content": gzip.compress(f"<p>{text}</p>".encode())},
    }


class TestPipelineOffline(unittest.TestCase):
    """Runs without MongoDB: the store and post loading are patched."""

    def test_builds_grounded_tree(self) -> None:
        posts: List[SourcePost] = [
            SourcePost("1", "Prices rise", "t", "f", "", 1), SourcePost("2", "Prices fall", "t", "f", "", 2),
            SourcePost("3", "Harvest", "t", "f", "", 3), SourcePost("4", "Unrelated", "t", "f", "", 4),
        ]
        with patch("rsstag.summary_tree.pipeline.RssTagSummaryTrees") as store_cls, patch(
            "rsstag.summary_tree.pipeline.load_posts", return_value=posts
        ), patch("rsstag.summary_tree.pipeline.SummaryLLM._cached", return_value=None), patch(
            "rsstag.summary_tree.pipeline.SummaryLLM._store"
        ), patch("rsstag.summary_tree.pipeline.prepare_cache"):
            store = store_cls.return_value
            store.set_stage.return_value = store.set_progress.return_value = True
            store.save_result.return_value = True
            ok: bool = SummaryTreePipeline(MagicMock(), FakeRouter(), "u").run(
                {"_id": "t1", "run_id": "r", "filters": {"entity": "apple"}, "options": {"limit": 10}}
            )
        self.assertTrue(ok)
        result: Dict[str, Any] = store.save_result.call_args.args[3]
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["metrics"]["skipped"], 1)
        root: Dict[str, Any] = result["nodes"][result["root_id"]]
        self.assertEqual(root["statements"][0]["sources"], ["1", "2", "3"])
        self.assertTrue(all(source["kind"] == "claim" for source in root["segments"][0]["sources"]))
        store.save_partial.assert_called()

    def test_no_entity_fails(self) -> None:
        with patch("rsstag.summary_tree.pipeline.RssTagSummaryTrees") as store_cls:
            ok = SummaryTreePipeline(MagicMock(), FakeRouter(), "u").run(
                {"_id": "t1", "run_id": "r", "filters": {}}
            )
        self.assertFalse(ok)
        self.assertIn("entity", store_cls.return_value.fail.call_args.args[3])

    def test_superseded_run_stops_quietly(self) -> None:
        with patch("rsstag.summary_tree.pipeline.RssTagSummaryTrees") as store_cls, patch(
            "rsstag.summary_tree.pipeline.prepare_cache"
        ):
            store_cls.return_value.set_stage.return_value = False
            ok = SummaryTreePipeline(MagicMock(), FakeRouter(), "u").run(
                {"_id": "t1", "run_id": "r", "filters": {"entity": "apple"}}
            )
        self.assertFalse(ok)
        store_cls.return_value.fail.assert_not_called()


class TestSummaryTreeWithDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            with socket.create_connection(("127.0.0.1", MONGO_PORT), timeout=1):
                pass
        except OSError as exc:
            raise unittest.SkipTest(f"MongoDB on port {MONGO_PORT} is required: {exc}")

    def setUp(self) -> None:
        self.helper: DBHelper = DBHelper(port=MONGO_PORT)
        self.db = self.helper.create_test_db()
        self.store: RssTagSummaryTrees = RssTagSummaryTrees(self.db)
        self.store.prepare()

    def tearDown(self) -> None:
        self.helper.drop_test_db(self.db)
        self.helper.close()

    def test_create_is_idempotent_per_filters(self) -> None:
        first = self.store.create("u", {"entity": "apple", "tags": ["b", "a"]})
        second = self.store.create("u", {"tags": ["a", "b"], "entity": "apple"})
        other = self.store.create("u", {"entity": "apple"})
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertEqual(self.store.find("u", {"entity": "apple"})["_id"], other)

    def test_end_to_end_build(self) -> None:
        self.helper.init_db_from_dict(self.db, {"posts": [
            _post("1", "Prices rise"), _post("2", "Prices fall"), _post("3", "Harvest"),
            _post("4", "Elsewhere", tags=["pear"]),
        ]})
        tree_id = self.store.create("u", {"entity": "apple"})
        doc = self.store.claim_next("u")
        self.assertEqual(str(doc["_id"]), tree_id)
        self.assertIsNone(self.store.claim_next("u"))
        self.assertTrue(SummaryTreePipeline(self.db, FakeRouter(), "u").run(doc))
        saved = self.store.get_by_id("u", tree_id)
        self.assertEqual(saved["status"], STATUS_DONE)
        self.assertEqual(saved["post_ids"], ["1", "2", "3"])
        self.assertEqual(saved["result"]["metrics"]["topics"], 1)

    def test_failure_and_retry(self) -> None:
        tree_id = self.store.create("u", {"entity": "missing"})
        doc = self.store.claim_next("u")
        self.assertFalse(SummaryTreePipeline(self.db, FakeRouter(), "u").run(doc))
        self.assertEqual(self.store.get_by_id("u", tree_id)["status"], STATUS_FAILED)
        self.assertTrue(self.store.reset_for_retry("u", tree_id))
        self.assertEqual(self.store.get_by_id("u", tree_id)["status"], STATUS_PENDING)

    def test_stale_run_cannot_write(self) -> None:
        tree_id = self.store.create("u", {"entity": "apple"})
        doc = self.store.claim_next("u")
        self.store.delete("u", tree_id)
        self.assertFalse(self.store.set_progress(tree_id, "u", doc["run_id"], 1))


if __name__ == "__main__":
    unittest.main()
