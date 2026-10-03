import socket
import unittest
from typing import Any, Dict, Optional

from rsstag.anthologies import RssTagAnthologies
from tests.db_utils import DBHelper

MONGO_PORT: int = 8765


def _result(post_ids: list) -> Dict[str, Any]:
    return {
        "themes": [{"id": "t0", "label": "x", "keywords": [], "size": 1, "cluster_ids": ["c0"]}],
        "clusters": {"c0": {"id": "c0"}},
        "unsorted": [],
        "snippets": {f"s{i}": {"id": f"s{i}", "post_id": pid} for i, pid in enumerate(post_ids)},
        "metrics": {"snippets_total": len(post_ids)},
    }


class TestAnthologyStorageOffline(unittest.TestCase):
    def test_invalid_object_id_returns_none_without_db(self) -> None:
        store = RssTagAnthologies(None)  # type: ignore[arg-type]
        self.assertIsNone(store.get_by_id("owner", "not-an-id"))
        self.assertFalse(store.delete("owner", "bad"))
        self.assertFalse(store.set_stage("bad", "units"))

    def test_normalize_scope(self) -> None:
        self.assertEqual(RssTagAnthologies._normalize_scope(None), {"mode": "all"})
        self.assertEqual(
            RssTagAnthologies._normalize_scope({"mode": "feeds", "feed_ids": [1, "", "b"], "provider": " "}),
            {"mode": "feeds", "feed_ids": ["1", "b"]},
        )


class TestAnthologyStorage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        try:
            with socket.create_connection(("127.0.0.1", MONGO_PORT), timeout=1):
                pass
        except OSError as exc:
            raise unittest.SkipTest(f"MongoDB on port {MONGO_PORT} is required: {exc}")

    def setUp(self) -> None:
        self.db_helper = DBHelper(port=MONGO_PORT)
        try:
            self.db_helper.client.admin.command("ping")
        except Exception as exc:
            self.db_helper.close()
            raise unittest.SkipTest(f"MongoDB on port {MONGO_PORT} is required: {exc}")
        self.db = self.db_helper.create_test_db()
        self.store = RssTagAnthologies(self.db)
        self.store.prepare()
        self.owner = "owner"

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()

    def test_create_reuses_same_seed_and_scope(self) -> None:
        first: Optional[str] = self.store.create(self.owner, "tag", "muse", {"mode": "all"})
        second: Optional[str] = self.store.create(self.owner, "tag", "muse", None)
        third: Optional[str] = self.store.create(self.owner, "tag", "muse", {"mode": "feeds", "feed_ids": ["1"]})
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)
        doc = self.store.get_by_id(self.owner, first)
        self.assertEqual(
            (doc["status"], doc["stage"], doc["error"], doc["stale"], doc["result"]),
            ("pending", None, None, False, None),
        )
        self.assertIsInstance(doc["_id"], str)
        self.assertIsNone(self.store.get_by_id("someone-else", first))
        self.assertIsNone(self.store.get_by_id(self.owner, "garbage"))

    def test_stage_status_result_cycle(self) -> None:
        anthology_id = self.store.create(self.owner, "tag", "muse", None)
        self.assertTrue(self.store.update_status(anthology_id, "processing"))
        self.assertTrue(self.store.set_stage(anthology_id, "label"))
        self.assertEqual(self.store.get_by_id(self.owner, anthology_id)["stage"], "label")
        self.assertTrue(self.store.update_status(anthology_id, "failed", error="boom"))
        self.assertEqual(self.store.get_by_id(self.owner, anthology_id)["error"], "boom")
        self.assertTrue(self.store.save_result(anthology_id, _result(["1", "2"])))
        doc = self.store.get_by_id(self.owner, anthology_id)
        self.assertEqual((doc["status"], doc["stage"], doc["error"]), ("done", "done", None))
        self.assertEqual(doc["post_ids"], ["1", "2"])
        self.assertTrue(self.store.reset_for_retry(self.owner, anthology_id))
        doc = self.store.get_by_id(self.owner, anthology_id)
        self.assertEqual((doc["status"], doc["stage"]), ("pending", None))
        self.assertIsNotNone(doc["result"])
        self.assertEqual(self.store.get_pending(self.owner)["_id"], anthology_id)

    def test_list_by_owner_is_light_and_sorted(self) -> None:
        older = self.store.create(self.owner, "tag", "a", None)
        newer = self.store.create(self.owner, "tag", "b", None)
        self.store.save_result(older, _result(["1"]))
        self.store.update_status(newer, "processing")
        items = self.store.list_by_owner(self.owner)
        self.assertEqual([i["_id"] for i in items], [newer, older])
        done = self.store.list_by_owner(self.owner, status="done")
        self.assertEqual(len(done), 1)
        self.assertNotIn("snippets", done[0]["result"])
        self.assertNotIn("clusters", done[0]["result"])
        self.assertIn("metrics", done[0]["result"])
        self.assertIn("themes", done[0]["result"])

    def test_mark_stale_only_done_with_matching_posts(self) -> None:
        done_id = self.store.create(self.owner, "tag", "a", None)
        other_id = self.store.create(self.owner, "tag", "b", None)
        self.store.save_result(done_id, _result(["10", "11"]))
        self.store.save_result(other_id, _result(["12"]))
        self.assertEqual(self.store.mark_stale_for_source_change(self.owner, ["11"]), 1)
        self.assertTrue(self.store.get_by_id(self.owner, done_id)["stale"])
        self.assertFalse(self.store.get_by_id(self.owner, other_id)["stale"])
        self.assertEqual(self.store.mark_stale_for_source_change("x", ["12"]), 0)
        self.assertEqual(self.store.mark_stale_for_source_change(self.owner, []), 0)

    def test_delete(self) -> None:
        anthology_id = self.store.create(self.owner, "tag", "a", None)
        self.assertFalse(self.store.delete("intruder", anthology_id))
        self.assertTrue(self.store.delete(self.owner, anthology_id))
        self.assertIsNone(self.store.get_by_id(self.owner, anthology_id))


if __name__ == "__main__":
    unittest.main()
