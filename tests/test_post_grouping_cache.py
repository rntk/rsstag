"""Tests for the post grouping deduplication cache."""

import gzip
import socket
import time
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from rsstag.grouping_cache import (
    KIND_CHUNK,
    KIND_DOCUMENT,
    NAMESPACE_CHUNK_SYNC,
    PostGroupingCache,
    model_identity,
)
from rsstag.workers.llm_worker import _PostGroupingWorker
from rsstag.workers.outcome import Completed, TaskOutcome
from tests.db_utils import DBHelper

MONGO_PORT = 8765


def _result(text: str = "Sentence one.") -> Dict[str, Any]:
    return {
        "sentences": [{"number": 1, "start": 0, "end": len(text), "text": text, "read": False}],
        "groups": {"Topic": [1]},
    }


class MongoCacheTestCase(unittest.TestCase):
    """Shared Mongo bootstrap for the cache tests."""

    db_helper: DBHelper

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        try:
            with socket.create_connection(("127.0.0.1", MONGO_PORT), timeout=1):
                pass
        except OSError as exc:
            raise unittest.SkipTest(
                f"MongoDB on port {MONGO_PORT} is required for cache tests: {exc}"
            )

    def setUp(self) -> None:
        self.db_helper = DBHelper(port=MONGO_PORT)
        try:
            self.db_helper.client.admin.command("ping")
        except Exception as exc:
            self.db_helper.close()
            raise unittest.SkipTest(
                f"MongoDB on port {MONGO_PORT} is required for cache tests: {exc}"
            )
        self.db = self.db_helper.create_test_db()

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()


class PostGroupingCacheStorageTestCase(MongoCacheTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.cache = PostGroupingCache(self.db)
        self.cache.prepare()

    def test_document_round_trip_counts_hits(self) -> None:
        self.cache.set_document("owner", "model:a", "some text", _result())

        first: Optional[Dict[str, Any]] = self.cache.get_document(
            "owner", "model:a", "some text"
        )
        second: Optional[Dict[str, Any]] = self.cache.get_document(
            "owner", "model:a", "some text"
        )

        self.assertIsNotNone(first)
        self.assertEqual(first["groups"], {"Topic": [1]})
        self.assertIsNotNone(second)
        entry: Dict[str, Any] = self.db.post_grouping_cache.find_one({"owner": "owner"})
        self.assertEqual(entry["hits"], 2)
        self.assertEqual(entry["kind"], KIND_DOCUMENT)
        self.assertIsNotNone(entry["last_hit_at"])

    def test_key_separates_models_owners_and_texts(self) -> None:
        self.cache.set_document("owner", "model:a", "some text", _result())

        self.assertIsNone(self.cache.get_document("owner", "model:b", "some text"))
        self.assertIsNone(self.cache.get_document("other", "model:a", "some text"))
        self.assertIsNone(self.cache.get_document("owner", "model:a", "some text "))

    def test_disabled_cache_neither_reads_nor_writes(self) -> None:
        disabled = PostGroupingCache(self.db, enabled=False)

        self.assertFalse(disabled.set_document("owner", "model:a", "text", _result()))
        self.assertIsNone(disabled.get_document("owner", "model:a", "text"))
        self.assertIsNone(disabled.chunk_cache("owner", "model:a"))
        self.assertEqual(self.db.post_grouping_cache.count_documents({}), 0)

    def test_chunk_cache_view_is_prompt_and_temperature_scoped(self) -> None:
        view = self.cache.chunk_cache("owner", "model:a", NAMESPACE_CHUNK_SYNC)

        self.assertTrue(view.set("prompt", 0.0, "response"))
        self.assertEqual(view.get("prompt", 0.0), "response")
        self.assertIsNone(view.get("prompt", 0.7))
        self.assertEqual(
            self.db.post_grouping_cache.find_one({"owner": "owner"})["kind"], KIND_CHUNK
        )

    def test_summary_reports_kinds_hits_and_unused(self) -> None:
        self.cache.set_document("owner", "model:a", "text one", _result())
        view = self.cache.chunk_cache("owner", "model:a")
        view.set("prompt one", 0.0, "response")
        view.set("prompt two", 0.0, "response")
        view.get("prompt one", 0.0)

        summary: Dict[str, Any] = self.cache.summary("owner")

        self.assertEqual(summary["entries"], 3)
        self.assertEqual(summary["document_entries"], 1)
        self.assertEqual(summary["chunk_entries"], 2)
        self.assertEqual(summary["chunk_hits"], 1)
        self.assertEqual(summary["unused_entries"], 2)
        self.assertGreater(summary["size"], 0)

    def test_find_entries_sorts_by_hits_and_adds_rates(self) -> None:
        view = self.cache.chunk_cache("owner", "model:a")
        view.set("hot", 0.0, "response")
        view.set("cold", 0.0, "response")
        for _ in range(3):
            view.get("hot", 0.0)

        entries: List[Dict[str, Any]] = self.cache.find_entries("owner", sort_by="hits")

        self.assertEqual([entry["hits"] for entry in entries], [0, 3])
        self.assertEqual(entries[1]["hits_per_day"], 3.0)
        self.assertNotIn("value", entries[0])

    def test_hits_per_day_sorting_is_paged_by_the_server(self) -> None:
        view = self.cache.chunk_cache("owner", "model:a")
        view.set("old-popular", 0.0, "old-popular-response")
        view.set("young-popular", 0.0, "young-popular-response")
        self.db.post_grouping_cache.update_one(
            {"value": "old-popular-response"},
            {"$set": {"hits": 20, "created_at": time.time() - 100 * 86400}},
        )
        self.db.post_grouping_cache.update_one(
            {"value": "young-popular-response"},
            {"$set": {"hits": 5, "created_at": time.time() - 1 * 86400}},
        )

        top: List[Dict[str, Any]] = self.cache.find_entries(
            "owner", sort_by="hits_per_day", descending=True, limit=1
        )
        second: List[Dict[str, Any]] = self.cache.find_entries(
            "owner", sort_by="hits_per_day", descending=True, skip=1, limit=1
        )

        # More total hits, but spread over 100 days -- the young entry wins.
        self.assertEqual(top[0]["hits"], 5)
        self.assertEqual(second[0]["hits"], 20)

    def test_delete_keys_removes_only_owner_entries(self) -> None:
        view = self.cache.chunk_cache("owner", "model:a")
        view.set("prompt", 0.0, "response")
        other_view = self.cache.chunk_cache("other", "model:a")
        other_view.set("other prompt", 0.0, "response")
        key: str = self.db.post_grouping_cache.find_one({"owner": "owner"})["key"]

        deleted: int = self.cache.delete_keys("other", [key])

        self.assertEqual(deleted, 0)
        self.assertEqual(self.cache.delete_keys("owner", [key]), 1)
        self.assertEqual(self.db.post_grouping_cache.count_documents({}), 1)

    def test_purge_drops_only_old_low_hit_entries(self) -> None:
        view = self.cache.chunk_cache("owner", "model:a")
        view.set("useless", 0.0, "useless-response")
        view.set("useful", 0.0, "useful-response")
        view.set("fresh", 0.0, "fresh-response")
        view.get("useful", 0.0)
        old: float = time.time() - 10 * 86400
        self.db.post_grouping_cache.update_many(
            {"owner": "owner"}, {"$set": {"created_at": old}}
        )
        self.db.post_grouping_cache.update_one(
            {"owner": "owner", "value": "fresh-response"},
            {"$set": {"created_at": time.time()}},
        )

        deleted: int = self.cache.purge("owner", max_hits=0, older_than_days=7)

        self.assertEqual(deleted, 1)
        self.assertEqual(self.db.post_grouping_cache.count_documents({}), 2)

    def test_clear_removes_single_kind(self) -> None:
        self.cache.set_document("owner", "model:a", "text", _result())
        self.cache.chunk_cache("owner", "model:a").set("prompt", 0.0, "response")

        self.assertEqual(self.cache.clear("owner", kind=KIND_CHUNK), 1)
        self.assertEqual(self.cache.count_entries("owner"), 1)

    def test_oversized_values_are_not_stored(self) -> None:
        huge: str = "x" * (PostGroupingCache.MAX_VALUE_BYTES + 1)

        stored: bool = self.cache.set("owner", NAMESPACE_CHUNK_SYNC, "model:a", "k", huge)

        self.assertFalse(stored)
        self.assertEqual(self.db.post_grouping_cache.count_documents({}), 0)


class _FakeSplitter:
    """Stand-in for PostSplitter counting pipeline runs."""

    calls: List[str] = []

    def __init__(self, llm_handler: Any = None, chunk_cache: Any = None) -> None:
        self.chunk_cache = chunk_cache

    def generate_grouped_data(
        self, content: str, title: str = "", **kwargs: Any
    ) -> Dict[str, Any]:
        _FakeSplitter.calls.append(f"{title}. {content}" if title else content)
        return _result(content)


class PostGroupingWorkerCacheTestCase(MongoCacheTestCase):
    def setUp(self) -> None:
        super().setUp()
        _FakeSplitter.calls = []
        self.llm = MagicMock()
        self.llm.get_handler.return_value = MagicMock(name="handler", model="m1")
        self.worker = _PostGroupingWorker(
            self.db, {}, self.llm, MagicMock(), MagicMock()
        )

    def _post(self, post_id: int, content: str, title: str = "") -> Dict[str, Any]:
        doc: Dict[str, Any] = {
            "owner": "owner",
            "pid": post_id,
            "processing": 123.0,
            "content": {
                "title": title,
                "content": gzip.compress(content.encode("utf-8")),
            },
        }
        doc["_id"] = self.db.posts.insert_one(doc).inserted_id
        return doc

    def _task(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"user": {"sid": "owner", "settings": {}}, "data": posts}

    def test_duplicate_posts_run_the_pipeline_once(self) -> None:
        posts: List[Dict[str, Any]] = [
            self._post(1, "Same body text."),
            self._post(2, "Same body text."),
        ]

        with patch("rsstag.post_splitter.PostSplitter", _FakeSplitter):
            self.assertTrue(self.worker.make_post_grouping(self._task(posts)))

        self.assertEqual(len(_FakeSplitter.calls), 1)
        self.assertEqual(self.db.post_grouping.count_documents({}), 2)
        for post in posts:
            stored: Dict[str, Any] = self.db.posts.find_one({"_id": post["_id"]})
            self.assertEqual(stored["grouping"], 1)

    def test_second_task_with_same_text_makes_no_llm_calls(self) -> None:
        with patch("rsstag.post_splitter.PostSplitter", _FakeSplitter):
            self.worker.make_post_grouping(self._task([self._post(1, "Body text.")]))
            _FakeSplitter.calls = []
            self.worker.make_post_grouping(self._task([self._post(2, "Body text.")]))

        self.assertEqual(_FakeSplitter.calls, [])
        self.assertEqual(
            self.db.post_grouping_cache.find_one({"kind": KIND_DOCUMENT})["hits"], 1
        )

    def test_title_is_part_of_the_cached_text(self) -> None:
        with patch("rsstag.post_splitter.PostSplitter", _FakeSplitter):
            self.worker.make_post_grouping(
                self._task([self._post(1, "Body text.", title="First")])
            )
            self.worker.make_post_grouping(
                self._task([self._post(2, "Body text.", title="Second")])
            )

        self.assertEqual(len(_FakeSplitter.calls), 2)

    def test_cached_result_keeps_sentence_offsets(self) -> None:
        content: str = "Body text with offsets."
        with patch("rsstag.post_splitter.PostSplitter", _FakeSplitter):
            self.worker.make_post_grouping(self._task([self._post(1, content)]))
            self.worker.make_post_grouping(self._task([self._post(2, content)]))

        groupings: List[Dict[str, Any]] = list(self.db.post_grouping.find({}))
        self.assertEqual(len(groupings), 2)
        self.assertEqual(
            groupings[0]["sentences"][0]["end"], groupings[1]["sentences"][0]["end"]
        )
        self.assertEqual(groupings[1]["sentences"][0]["end"], len(content))

    def test_different_model_does_not_reuse_entries(self) -> None:
        with patch("rsstag.post_splitter.PostSplitter", _FakeSplitter):
            self.worker.make_post_grouping(self._task([self._post(1, "Body text.")]))
            self.llm.get_handler.return_value = MagicMock(name="handler", model="m2")
            _FakeSplitter.calls = []
            self.worker.make_post_grouping(self._task([self._post(2, "Body text.")]))

        self.assertEqual(len(_FakeSplitter.calls), 1)

    def test_cache_can_be_disabled_by_config(self) -> None:
        worker = _PostGroupingWorker(
            self.db,
            {"settings": {"post_grouping_cache": "false"}},
            self.llm,
            MagicMock(),
            MagicMock(),
        )

        with patch("rsstag.post_splitter.PostSplitter", _FakeSplitter):
            worker.make_post_grouping(self._task([self._post(1, "Body text.")]))
            worker.make_post_grouping(self._task([self._post(2, "Body text.")]))

        self.assertEqual(len(_FakeSplitter.calls), 2)
        self.assertEqual(self.db.post_grouping_cache.count_documents({}), 0)

    def test_model_identity_uses_name_and_model(self) -> None:
        handler = MagicMock()
        handler.name = "openai"
        handler.model = "gpt-5-mini"

        self.assertEqual(model_identity(handler), "openai:gpt-5-mini")
        self.assertEqual(model_identity(None), "unknown")

    def test_model_identity_reads_private_model_attributes(self) -> None:
        class _PrivateModelHandler:
            """Same shape as the anthropic/groq/cerebras/llamacpp handlers."""

            def __init__(self, model: str) -> None:
                self.__model = model

        self.assertEqual(
            model_identity(_PrivateModelHandler("claude-sonnet-5")),
            "_PrivateModelHandler:claude-sonnet-5",
        )
        self.assertNotEqual(
            model_identity(_PrivateModelHandler("a")),
            model_identity(_PrivateModelHandler("b")),
        )


class PostGroupingCleanupCacheTestCase(MongoCacheTestCase):
    """A cleanup must invalidate what it is going to reprocess."""

    def setUp(self) -> None:
        super().setUp()
        self.worker = _PostGroupingWorker(
            self.db, {}, MagicMock(), MagicMock(), MagicMock()
        )
        self.cache = self.worker._cache

    def _post(self, pid: str, content: str) -> None:
        self.db.posts.insert_one(
            {
                "owner": "owner",
                "pid": pid,
                "feed_id": "feed",
                "content": {"title": "", "content": gzip.compress(content.encode())},
            }
        )

    def _fill_cache(self, text: str) -> None:
        self.cache.set_document("owner", "model:a", text, _result(text))
        view = self.cache.chunk_cache("owner", "model:a")
        view.bind_document(text)
        view.set(f"prompt of {text}", 0.0, "response")

    def test_scoped_cleanup_drops_only_the_selected_posts(self) -> None:
        self._post("1", "first text")
        self._post("2", "second text")
        self._fill_cache("first text")
        self._fill_cache("second text")

        self.worker.make_post_grouping_cleanup(
            {
                "user": {"sid": "owner"},
                "scope": {"mode": "posts", "post_ids": ["1"]},
            }
        )

        remaining: List[Dict[str, Any]] = list(self.db.post_grouping_cache.find({}))
        self.assertEqual(len(remaining), 2)
        self.assertIsNone(self.cache.get_document("owner", "model:a", "first text"))
        self.assertIsNotNone(self.cache.get_document("owner", "model:a", "second text"))

    def test_cleanup_drops_chunks_shared_with_another_document(self) -> None:
        self._post("1", "first text")
        self._post("2", "second text")
        view = self.cache.chunk_cache("owner", "model:a")
        for text in ("first text", "second text"):
            self.cache.set_document("owner", "model:a", text, _result(text))
            view.bind_document(text)
            view.set("shared prompt", 0.0, "response")

        self.worker.make_post_grouping_cleanup(
            {"user": {"sid": "owner"}, "scope": {"mode": "posts", "post_ids": ["2"]}}
        )

        # The shared chunk was reused by post 2, so cleaning post 2 must drop it.
        self.assertIsNone(view.get("shared prompt", 0.0))
        self.assertIsNotNone(self.cache.get_document("owner", "model:a", "first text"))

    def test_unscoped_cleanup_clears_the_whole_cache(self) -> None:
        self._post("1", "first text")
        self._fill_cache("first text")

        self.worker.make_post_grouping_cleanup({"user": {"sid": "owner"}, "scope": {}})

        self.assertEqual(self.db.post_grouping_cache.count_documents({}), 0)


class _Chunk:
    def __init__(self, chunk_id: int, text: str) -> None:
        self.chunk_id = chunk_id
        self.tagged_text = text


class _Prepared:
    def __init__(self, chunks: List[_Chunk]) -> None:
        self.chunks = chunks


class _BatchSplitter:
    """PostSplitter stand-in producing one chunk per sentence of the content."""

    def prepare_for_batch(self, content: str, title: str = "") -> _Prepared:
        parts: List[str] = [part for part in content.split("|") if part]
        return _Prepared([_Chunk(index, part) for index, part in enumerate(parts)])

    def build_batch_prompt(self, tagged_text: str) -> str:
        return f"prompt::{tagged_text}"

    def finalize_batch(self, prepared: _Prepared, merged_response: str) -> Dict[str, Any]:
        return _result(merged_response)


class _BatchProvider:
    name = "openai"
    model = "gpt-5-mini"

    def build_request(self, custom_id: str, prompt: str) -> Dict[str, Any]:
        return {"custom_id": custom_id, "prompt": prompt}


class PostGroupingBatchCacheTestCase(MongoCacheTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.worker = _PostGroupingWorker(
            self.db, {}, MagicMock(), MagicMock(), MagicMock()
        )
        self.provider = _BatchProvider()
        self.splitter = _BatchSplitter()
        self.model_id: str = model_identity(self.provider)
        self.chunk_cache = self.worker._batch_chunk_cache("owner", self.model_id)

    def _post(self, post_id: int, content: str) -> Dict[str, Any]:
        doc: Dict[str, Any] = {
            "owner": "owner",
            "pid": post_id,
            "processing": 123.0,
            "content": {"title": "", "content": gzip.compress(content.encode("utf-8"))},
        }
        doc["_id"] = self.db.posts.insert_one(doc).inserted_id
        return doc

    def test_cached_chunks_are_left_out_of_the_batch(self) -> None:
        self.chunk_cache.set("prompt::one", 0.0, "Topic: 1")
        post: Dict[str, Any] = self._post(1, "one|two")

        requests, item_ids, _, _, cached_posts = (
            self.worker._build_post_grouping_batch_subset(
                "task", [post], self.provider, self.splitter, "owner", self.model_id
            )
        )

        self.assertEqual([request["prompt"] for request in requests], ["prompt::two"])
        self.assertEqual(item_ids, [str(post["_id"])])
        self.assertEqual(cached_posts, [])

    def test_fully_cached_post_needs_no_request(self) -> None:
        self.chunk_cache.set("prompt::one", 0.0, "Topic: 1")
        self.chunk_cache.set("prompt::two", 0.0, "Topic: 2")
        post: Dict[str, Any] = self._post(1, "one|two")

        requests, item_ids, _, _, cached_posts = (
            self.worker._build_post_grouping_batch_subset(
                "task", [post], self.provider, self.splitter, "owner", self.model_id
            )
        )
        finalized = self.worker._finalize_cached_batch_posts(
            "owner", self.model_id, cached_posts, self.splitter
        )

        self.assertEqual(requests, [])
        self.assertEqual(item_ids, [])
        self.assertEqual(finalized, {str(post["_id"])})
        self.assertEqual(self.db.post_grouping.count_documents({}), 1)
        self.assertEqual(
            self.db.posts.find_one({"_id": post["_id"]})["grouping"], 1
        )
        # The finalized result is promoted to a document entry for next time.
        self.assertEqual(
            self.db.post_grouping_cache.count_documents({"kind": KIND_DOCUMENT}), 1
        )

    def test_fully_cached_batch_task_is_marked_done(self) -> None:
        content: str = "one|two"
        _, _, text = self.worker._post_text(self._post(1, content))
        self.worker._cache.set_document("owner", self.model_id, text, _result(content))
        post: Dict[str, Any] = self._post(2, content)
        task: Dict[str, Any] = {
            "_id": "task-id",
            "user": {"sid": "owner", "settings": {}},
            "data": [post],
            "batch": {},
        }
        self.worker._llm = MagicMock()
        self.worker._llm.get_batch_provider.return_value = self.provider

        with patch("rsstag.post_splitter.PostSplitter", lambda *a, **kw: self.splitter):
            outcome: TaskOutcome = self.worker.make_post_grouping_batch(task)

        self.assertIsInstance(outcome, Completed)
        self.assertEqual(task["data"], [])
        state: Dict[str, Any] = (
            self.worker._batch_storage.update_task_batch_state.call_args[0][1]
        )
        self.assertEqual(state["status"], "done")

    def test_batch_and_sync_chunk_entries_do_not_collide(self) -> None:
        self.chunk_cache.set("prompt::one", 0.0, "batch answer")
        sync_cache = self.worker._cache.chunk_cache("owner", self.model_id)

        self.assertIsNone(sync_cache.get("prompt::one", 0.0))


if __name__ == "__main__":
    unittest.main()
