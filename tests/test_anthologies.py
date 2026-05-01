import json
import socket
import unittest

from rsstag.anthology_agent import AnthologyAgent
from rsstag.anthologies import RssTagAnthologies, RssTagAnthologyRuns
from rsstag.llm.anthology_tools import AnthologyToolExecutor
from rsstag.llm.base import LLMResponse, ToolCall
from tests.db_utils import DBHelper


class TestAnthologyAgentParsing(unittest.TestCase):
    def test_assistant_tool_call_message_preserves_tool_calls(self) -> None:
        message = AnthologyAgent._build_assistant_tool_call_message(
            "Requested tools",
            (
                ToolCall(
                    id="call-1",
                    name="get_topic_details",
                    arguments={"topic_path": "Muse > Albums"},
                ),
            ),
        )

        self.assertEqual(message["role"], "assistant")
        self.assertEqual(message["tool_calls"][0]["id"], "call-1")
        self.assertEqual(message["tool_calls"][0]["type"], "function")
        self.assertEqual(
            message["tool_calls"][0]["function"]["arguments"],
            '{"topic_path": "Muse > Albums"}',
        )

    def test_parse_json_response_repairs_invalid_escapes(self) -> None:
        parsed = AnthologyAgent._parse_json_response(
            '{"title": "Muse \\_ Archive", "summary": "ok", "sub_anthologies": []}'
        )

        self.assertEqual(parsed["title"], "Muse \\_ Archive")


class TestRssTagAnthologies(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        try:
            with socket.create_connection(("127.0.0.1", 8765), timeout=1):
                pass
        except OSError as exc:
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for anthology tests: {exc}"
            )

    def setUp(self) -> None:
        self.db_helper = DBHelper(port=8765)
        try:
            self.db_helper.client.admin.command("ping")
        except Exception as exc:
            self.db_helper.close()
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for anthology tests: {exc}"
            )
        self.db = self.db_helper.create_test_db()
        self.anthologies = RssTagAnthologies(self.db)
        self.anthology_runs = RssTagAnthologyRuns(self.db)
        self.anthologies.prepare()
        self.anthology_runs.prepare()
        self.owner = "anthology-owner"
        self._seed_grouped_fixture()

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()

    def _seed_grouped_fixture(self) -> None:
        self.db.posts.insert_many(
            [
                {
                    "owner": self.owner,
                    "pid": "post-1",
                    "feed_id": "feed-1",
                    "tags": ["muse", "music", "albums"],
                    "bi_grams": ["live show"],
                    "read": False,
                    "id": "db-post-1",
                    "content": {"title": "Muse Album News"},
                    "date": 1700000000,
                },
                {
                    "owner": self.owner,
                    "pid": "post-2",
                    "feed_id": "feed-1",
                    "tags": ["muse", "tour", "concert"],
                    "bi_grams": ["world tour"],
                    "read": False,
                    "id": "db-post-2",
                    "content": {"title": "Muse Tour Notes"},
                    "date": 1700000100,
                },
            ]
        )
        self.db.post_grouping.insert_many(
            [
                {
                    "owner": self.owner,
                    "post_ids": ["post-1"],
                    "post_ids_hash": "hash-post-1",
                    "sentences": [
                        {"number": 0, "text": "Muse released a new album.", "read": False},
                        {"number": 1, "text": "Fans discussed the set list.", "read": False},
                    ],
                    "groups": {
                        "Muse > Albums": [0],
                        "Muse > Community": [1],
                    },
                },
                {
                    "owner": self.owner,
                    "post_ids": ["post-2"],
                    "post_ids_hash": "hash-post-2",
                    "sentences": [
                        {"number": 0, "text": "Muse announced a world tour.", "read": False},
                        {"number": 1, "text": "The concert dates sold quickly.", "read": False},
                    ],
                    "groups": {
                        "Muse > Tours": [0, 1],
                    },
                },
            ]
        )

    def test_create_deduplicates_same_seed_and_scope(self) -> None:
        first = self.anthologies.create(self.owner, "tag", "playstation 5", {"mode": "all"})
        second = self.anthologies.create(self.owner, "tag", "playstation 5", {"mode": "all"})

        self.assertIsNotNone(first)
        self.assertEqual(first, second)
        self.assertEqual(self.db.anthologies.count_documents({"owner": self.owner}), 1)

    def test_update_result_marks_document_done(self) -> None:
        anthology_id = self.anthologies.create(self.owner, "tag", "python", {"mode": "all"})
        self.assertIsNotNone(anthology_id)
        run_id = self.anthology_runs.create(anthology_id, self.owner)
        self.assertIsNotNone(run_id)

        updated = self.anthologies.update_result(
            anthology_id,
            {
                "title": "python",
                "summary": "summary",
                "source_refs": [],
                "sub_anthologies": [],
            },
            run_id,
            {"post_grouping_updated_at": None, "post_grouping_doc_ids": []},
        )

        self.assertTrue(updated)
        stored = self.anthologies.get_by_id(self.owner, anthology_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored["status"], "done")
        self.assertEqual(stored["result"]["title"], "python")
        self.assertEqual(stored["current_run_id"], run_id)

    def test_list_by_owner_returns_serialized_documents(self) -> None:
        anthology_id = self.anthologies.create(self.owner, "tag", "rust", {"mode": "all"})
        self.assertIsNotNone(anthology_id)

        docs = list(self.anthologies.list_by_owner(self.owner))

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["_id"], anthology_id)
        self.assertEqual(docs[0]["seed_value"], "rust")

    def test_runs_create_append_finish_and_lookup(self) -> None:
        anthology_id = self.anthologies.create(self.owner, "tag", "golang", {"mode": "all"})
        self.assertIsNotNone(anthology_id)
        run_id = self.anthology_runs.create(anthology_id, self.owner)
        self.assertIsNotNone(run_id)

        appended = self.anthology_runs.append_turn(
            run_id,
            {"turn": 1, "messages": [{"role": "system", "content": "hello"}]},
        )
        finished = self.anthology_runs.finish(run_id, "done")
        latest = self.anthology_runs.get_latest_for_anthology(self.owner, anthology_id)

        self.assertTrue(appended)
        self.assertTrue(finished)
        self.assertIsNotNone(latest)
        self.assertEqual(latest["_id"], run_id)
        self.assertEqual(latest["status"], "done")
        self.assertEqual(len(latest["turns"]), 1)

    def test_tool_executor_returns_topic_details_and_co_occurrences(self) -> None:
        executor = AnthologyToolExecutor(self.db, self.owner, "muse", {"mode": "all"})

        search_payload = json.loads(executor.execute("search_related_topics", {"query": "tour"}))
        detail_payload = json.loads(
            executor.execute("get_topic_details", {"topic_path": "Muse > Tours"})
        )
        posts_payload = json.loads(
            executor.execute("get_posts_for_topic", {"topic_path": "Muse > Tours"})
        )
        co_tag_payload = json.loads(
            executor.execute("get_tag_co_occurrences", {"tag": "muse"})
        )

        self.assertTrue(search_payload["topics"])
        self.assertEqual(detail_payload["topic_path"], "Muse > Tours")
        self.assertEqual(detail_payload["matches"][0]["source_refs"][0]["post_id"], "post-2")
        self.assertEqual(posts_payload["posts"][0]["post_id"], "post-2")
        self.assertIn(
            "albums",
            {row["tag"] for row in co_tag_payload["co_occurrences"]},
        )

    def test_agent_run_generates_anthology_from_tool_calls(self) -> None:
        anthology_id = self.anthologies.create(self.owner, "tag", "muse", {"mode": "all"})
        self.assertIsNotNone(anthology_id)

        class FakeRouter:
            def __init__(self) -> None:
                self.calls: int = 0
                self.message_snapshots: list[list[dict[str, object]]] = []

            def call_with_tools(self, *_args: object, **_kwargs: object) -> LLMResponse:
                self.calls += 1
                self.message_snapshots.append(
                    json.loads(json.dumps(_kwargs.get("messages", [])))
                )
                if self.calls == 1:
                    return LLMResponse(
                        tool_calls=(
                            ToolCall(
                                id="call-1",
                                name="get_topic_details",
                                arguments={"topic_path": "Muse > Albums"},
                            ),
                        )
                    )
                return LLMResponse(
                    content=json.dumps(
                        {
                            "title": "Muse",
                            "summary": "Coverage of albums and tours.",
                            "sub_anthologies": [
                                {
                                    "title": "Albums",
                                    "summary": "Album-related updates.",
                                    "topic_paths": ["Muse > Albums"],
                                    "source_refs": [],
                                }
                            ],
                        }
                    )
                )

        router = FakeRouter()
        agent = AnthologyAgent(self.db, router, self.owner, settings={"realtime_llm": "openai"})

        completed = agent.run(anthology_id)

        self.assertTrue(completed)
        self.assertIn("tool_calls", router.message_snapshots[1][2])
        self.assertEqual(router.message_snapshots[1][2]["role"], "assistant")
        self.assertEqual(router.message_snapshots[1][3]["role"], "tool")
        stored = self.anthologies.get_by_id(self.owner, anthology_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored["status"], "done")
        self.assertEqual(stored["result"]["title"], "Muse")
        self.assertEqual(stored["result"]["sub_anthologies"][0]["node_id"], "albums")
        self.assertTrue(stored["result"]["source_refs"])
        latest_run = self.anthology_runs.get_latest_for_anthology(self.owner, anthology_id)
        self.assertIsNotNone(latest_run)
        self.assertEqual(latest_run["status"], "done")
        self.assertEqual(len(latest_run["turns"]), 2)
