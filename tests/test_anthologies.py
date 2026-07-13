import json
import socket
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

try:
    from rsstag.anthology_agent import AnthologyAgent
except ImportError:
    AnthologyAgent = None  # type: ignore[misc,assignment]
from rsstag.anthologies import RssTagAnthologies, RssTagAnthologyRuns
from rsstag.llm.anthology_tools import AnthologyToolExecutor
from rsstag.llm.base import LLMResponse, ToolCall
from tests.db_utils import DBHelper


class TestAnthologyAgentParsing(unittest.TestCase):
    def _build_orchestration_agent(
        self,
        router: object,
        max_iterations: int,
    ) -> AnthologyAgent:
        agent: AnthologyAgent = AnthologyAgent(
            None,
            router,
            "owner",
            settings={"anthology_max_iterations": max_iterations},
        )
        agent._anthologies = MagicMock()
        agent._anthologies.get_by_id.return_value = {
            "seed_value": "muse",
            "scope": {"mode": "all"},
        }
        agent._anthology_runs = MagicMock()
        agent._anthology_runs.create.return_value = "run-1"
        agent._finalize_result = MagicMock(return_value=True)  # type: ignore[method-assign]
        return agent

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

    def test_normalize_result_keeps_only_claims_with_verified_refs(self) -> None:
        executor: MagicMock = MagicMock()

        def validate_source_ref(
            post_id: str,
            topic_path: str,
            sentence_indices: list[int],
            tag: str,
        ) -> dict[str, Any] | None:
            if post_id != "valid-post":
                return None
            return {
                "post_id": post_id,
                "topic_path": topic_path,
                "sentence_indices": sentence_indices,
                "tag": tag,
                "title": "Verified source",
            }

        executor.validate_source_ref.side_effect = validate_source_ref
        executor.build_coverage.return_value = {"documents_cited": 1}
        agent: AnthologyAgent = AnthologyAgent(None, object(), "owner")
        raw_result: dict[str, Any] = {
            "title": "Report",
            "summary": "Grounded report.",
            "findings": [
                {
                    "title": "Finding",
                    "status": "consensus",
                    "claims": [
                        {
                            "text": "Supported claim.",
                            "source_refs": [
                                {
                                    "post_id": "valid-post",
                                    "topic_path": "Topic",
                                    "sentence_indices": [1],
                                }
                            ],
                        },
                        {
                            "text": "Unsupported claim.",
                            "source_refs": [
                                {
                                    "post_id": "invented-post",
                                    "topic_path": "Topic",
                                    "sentence_indices": [99],
                                }
                            ],
                        },
                    ],
                }
            ],
        }

        result: dict[str, Any] = agent._normalize_result(
            raw_result, "tag", executor
        )

        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(len(result["findings"][0]["claims"]), 1)
        self.assertEqual(result["findings"][0]["status"], "single_source")
        self.assertEqual(result["source_refs"][0]["post_id"], "valid-post")

    def test_max_iterations_uses_larger_bounded_default(self) -> None:
        default_agent: AnthologyAgent = AnthologyAgent(None, object(), "owner")
        low_agent: AnthologyAgent = AnthologyAgent(
            None, object(), "owner", {"anthology_max_iterations": 1}
        )
        high_agent: AnthologyAgent = AnthologyAgent(
            None, object(), "owner", {"anthology_max_iterations": 1000}
        )

        self.assertEqual(default_agent._get_max_iterations(), 12)
        self.assertEqual(low_agent._get_max_iterations(), 3)
        self.assertEqual(high_agent._get_max_iterations(), 32)

    @patch("rsstag.anthology_agent.AnthologyToolExecutor")
    def test_run_reserves_final_tool_free_synthesis_turn(
        self,
        executor_class: MagicMock,
    ) -> None:
        class BudgetRouter:
            def __init__(self) -> None:
                self.tools_by_call: list[tuple[object, ...]] = []
                self.parallel_by_call: list[bool] = []

            def call_with_tools(
                self, *_args: object, **kwargs: object
            ) -> LLMResponse:
                tools: tuple[object, ...] = tuple(kwargs.get("tools", ()))
                self.tools_by_call.append(tools)
                self.parallel_by_call.append(
                    bool(kwargs.get("parallel_tool_calls", False))
                )
                if tools:
                    call_number: int = len(self.tools_by_call)
                    return LLMResponse(
                        tool_calls=(
                            ToolCall(
                                id=f"call-{call_number}",
                                name="search_related_topics",
                                arguments={"query": f"query-{call_number}"},
                            ),
                        )
                    )
                return LLMResponse(content="{}")

        router = BudgetRouter()
        agent: AnthologyAgent = self._build_orchestration_agent(router, 3)
        agent._fetch_topic_seed = MagicMock(return_value=[])  # type: ignore[method-assign]
        executor_class.return_value.execute.return_value = "{}"

        completed: bool = agent.run("anthology-1")

        self.assertTrue(completed)
        self.assertEqual(len(router.tools_by_call), 3)
        self.assertTrue(router.tools_by_call[0])
        self.assertEqual(router.tools_by_call[-1], ())
        self.assertTrue(all(router.parallel_by_call))
        final_turn: dict[str, Any] = agent._anthology_runs.append_turn.call_args_list[
            -1
        ].args[1]
        self.assertTrue(final_turn["forced_final"])

    @patch("rsstag.anthology_agent.AnthologyToolExecutor")
    def test_run_stops_repeated_tool_call_loop_early(
        self,
        executor_class: MagicMock,
    ) -> None:
        class RepeatingRouter:
            def __init__(self) -> None:
                self.calls: int = 0

            def call_with_tools(
                self, *_args: object, **kwargs: object
            ) -> LLMResponse:
                self.calls += 1
                if kwargs.get("tools"):
                    return LLMResponse(
                        tool_calls=(
                            ToolCall(
                                id=f"call-{self.calls}",
                                name="get_corpus_overview",
                                arguments={"limit": 8},
                            ),
                        )
                    )
                return LLMResponse(content="{}")

        router = RepeatingRouter()
        agent: AnthologyAgent = self._build_orchestration_agent(router, 12)
        agent._fetch_topic_seed = MagicMock(return_value=[])  # type: ignore[method-assign]
        executor_class.return_value.execute.return_value = '{"documents": []}'

        completed: bool = agent.run("anthology-1")

        self.assertTrue(completed)
        self.assertEqual(router.calls, 4)
        executor_class.return_value.execute.assert_called_once()
        tool_turns: list[dict[str, Any]] = [
            call.args[1]
            for call in agent._anthology_runs.append_turn.call_args_list[:-1]
        ]
        self.assertFalse(tool_turns[0]["tool_results"][0]["cached"])
        self.assertTrue(tool_turns[1]["tool_results"][0]["cached"])
        self.assertTrue(tool_turns[2]["tool_results"][0]["cached"])

    @patch("rsstag.anthology_agent.AnthologyToolExecutor")
    def test_final_synthesis_retries_empty_response_with_compact_evidence(
        self,
        executor_class: MagicMock,
    ) -> None:
        class EmptyOnceRouter:
            def __init__(self) -> None:
                self.calls: int = 0
                self.final_messages: list[list[dict[str, Any]]] = []

            def call_with_tools(
                self, *_args: object, **kwargs: object
            ) -> LLMResponse:
                self.calls += 1
                if kwargs.get("tools"):
                    return LLMResponse(
                        tool_calls=(
                            ToolCall(
                                id=f"call-{self.calls}",
                                name="search_related_topics",
                                arguments={"query": f"query-{self.calls}"},
                            ),
                        )
                    )
                messages: list[dict[str, Any]] = list(kwargs.get("messages", []))
                self.final_messages.append(messages)
                if len(self.final_messages) == 1:
                    return LLMResponse()
                return LLMResponse(content="{}")

        router = EmptyOnceRouter()
        agent: AnthologyAgent = self._build_orchestration_agent(router, 3)
        agent._fetch_topic_seed = MagicMock(return_value=[])  # type: ignore[method-assign]
        executor_class.return_value.execute.side_effect = [
            '{"topics":[{"topic_path":"Muse > Albums"}]}',
            '{"topics":[{"topic_path":"Muse > Tours"}]}',
        ]

        completed: bool = agent.run("anthology-1")

        self.assertTrue(completed)
        self.assertEqual(router.calls, 4)
        self.assertEqual(len(router.final_messages), 2)
        first_final_messages: list[dict[str, Any]] = router.final_messages[0]
        self.assertFalse(
            any(message.get("role") == "tool" for message in first_final_messages)
        )
        evidence_messages: list[dict[str, Any]] = [
            message
            for message in first_final_messages
            if "<evidence>" in str(message.get("content", ""))
        ]
        self.assertEqual(len(evidence_messages), 1)
        self.assertIn("Muse > Albums", evidence_messages[0]["content"])
        final_turn: dict[str, Any] = agent._anthology_runs.append_turn.call_args_list[
            -1
        ].args[1]
        self.assertEqual(final_turn["synthesis_attempts"], 2)

    def test_synthesis_messages_deduplicate_tool_results(self) -> None:
        conversation: list[dict[str, Any]] = [
            {"role": "system", "content": "schema"},
            {"role": "user", "content": "seed"},
            {"role": "assistant", "content": "tool request"},
            {"role": "tool", "content": "large repeated result"},
        ]
        tool_cache: dict[str, str] = {
            'get_topic_details:{"topic_path":"Muse"}': '{"matches":[1]}'
        }

        messages: list[dict[str, Any]] = AnthologyAgent._build_synthesis_messages(
            conversation,
            tool_cache,
        )

        self.assertEqual([message["role"] for message in messages], [
            "system",
            "user",
            "user",
            "system",
        ])
        self.assertNotIn("large repeated result", json.dumps(messages))
        self.assertEqual(json.dumps(messages).count("get_topic_details"), 1)


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
        overview_payload: dict[str, Any] = json.loads(
            executor.execute("get_corpus_overview", {"limit": 10})
        )

        self.assertTrue(search_payload["topics"])
        self.assertEqual(detail_payload["topic_path"], "Muse > Tours")
        self.assertEqual(detail_payload["matches"][0]["source_refs"][0]["post_id"], "post-2")
        self.assertEqual(posts_payload["posts"][0]["post_id"], "post-2")
        self.assertIn(
            "albums",
            {row["tag"] for row in co_tag_payload["co_occurrences"]},
        )
        self.assertEqual(overview_payload["documents_in_scope"], 2)
        self.assertEqual(len(overview_payload["documents"]), 2)

    def test_source_refs_are_clipped_to_scoped_topic_sentences(self) -> None:
        executor = AnthologyToolExecutor(
            self.db, self.owner, "muse", {"mode": "feeds", "feed_ids": ["feed-1"]}
        )

        verified: dict[str, Any] | None = executor.validate_source_ref(
            "post-1", "Muse > Albums", [0, 1, 999], "muse"
        )
        wrong_topic: dict[str, Any] | None = executor.validate_source_ref(
            "post-1", "Muse > Tours", [0], "muse"
        )
        outside_scope: dict[str, Any] | None = AnthologyToolExecutor(
            self.db, self.owner, "muse", {"mode": "feeds", "feed_ids": ["other-feed"]}
        ).validate_source_ref("post-1", "Muse > Albums", [0], "muse")

        self.assertIsNotNone(verified)
        self.assertEqual(verified["sentence_indices"], [0])
        self.assertEqual(verified["title"], "Muse Album News")
        self.assertEqual(verified["published_at"], 1700000000)
        self.assertIsNone(wrong_topic)
        self.assertIsNone(outside_scope)

    def test_agent_normalizes_claim_report_and_drops_unsupported_claims(self) -> None:
        executor = AnthologyToolExecutor(self.db, self.owner, "muse", {"mode": "all"})
        agent = AnthologyAgent(self.db, object(), self.owner)
        raw_result: dict[str, Any] = {
            "title": "Muse report",
            "summary": "Sources describe album and tour announcements.",
            "findings": [
                {
                    "title": "Announcements",
                    "status": "disputed",
                    "claims": [
                        {
                            "text": "Muse released a new album.",
                            "kind": "fact",
                            "stance": "supports",
                            "source_refs": [
                                {
                                    "post_id": "post-1",
                                    "topic_path": "Muse > Albums",
                                    "sentence_indices": [0, 999],
                                }
                            ],
                        },
                        {
                            "text": "Muse announced a world tour.",
                            "kind": "fact",
                            "stance": "disputes",
                            "source_refs": [
                                {
                                    "post_id": "post-2",
                                    "topic_path": "Muse > Tours",
                                    "sentence_indices": [0],
                                }
                            ],
                        },
                        {
                            "text": "This unsupported claim must disappear.",
                            "source_refs": [
                                {
                                    "post_id": "invented-post",
                                    "topic_path": "Invented topic",
                                    "sentence_indices": [42],
                                }
                            ],
                        },
                    ],
                }
            ],
            "timeline": [
                {
                    "date": "2023-11",
                    "date_kind": "publication",
                    "title": "Tour announcement",
                    "source_refs": [
                        {
                            "post_id": "post-2",
                            "topic_path": "Muse > Tours",
                            "sentence_indices": [0],
                        }
                    ],
                }
            ],
            "limitations": ["Only grouped sentences were inspected."],
            "sub_anthologies": [],
        }

        result: dict[str, Any] = agent._normalize_result(raw_result, "muse", executor)

        self.assertEqual(result["report_version"], "evidence-report-v1")
        self.assertEqual(result["findings"][0]["status"], "disputed")
        self.assertEqual(len(result["findings"][0]["claims"]), 2)
        self.assertEqual(
            result["findings"][0]["claims"][0]["source_refs"][0][
                "sentence_indices"
            ],
            [0],
        )
        self.assertEqual(len(result["timeline"]), 1)
        self.assertEqual(result["coverage"]["documents_in_scope"], 2)
        self.assertEqual(result["coverage"]["documents_cited"], 2)
        self.assertEqual(len(result["source_refs"]), 2)

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
