"""Anthology generation agent."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from typing import Any, Optional

from rsstag.anthologies import RssTagAnthologies, RssTagAnthologyRuns
from rsstag.llm.anthology_tools import AnthologyToolExecutor, get_anthology_tools
from rsstag.llm.base import ToolCall


class AnthologyAgent:
    """Generate a scoped anthology by iterating over LLM tool calls."""

    def __init__(
        self,
        db: Any,
        llm_router: Any,
        owner: str,
        settings: Optional[dict[str, Any]] = None,
    ) -> None:
        self._db: Any = db
        self._llm_router: Any = llm_router
        self._owner: str = owner
        self._settings: dict[str, Any] = settings or {}
        self._anthologies = RssTagAnthologies(db)
        self._anthology_runs = RssTagAnthologyRuns(db)
        self._log = logging.getLogger("anthology_agent")

    def run(self, anthology_id: str) -> bool:
        """Generate an anthology result and persist run logs."""

        anthology = self._anthologies.get_by_id(self._owner, anthology_id)
        if not anthology:
            self._log.error("Anthology %s not found for owner %s", anthology_id, self._owner)
            return False

        run_id = self._anthology_runs.create(anthology_id, self._owner)
        if not run_id:
            self._log.error("Failed to create anthology run for %s", anthology_id)
            self._anthologies.update_status(anthology_id, "failed")
            return False

        seed_tag = str(anthology.get("seed_value", "")).strip() or "anthology"
        scope = anthology.get("scope") if isinstance(anthology.get("scope"), dict) else {"mode": "all"}
        executor = AnthologyToolExecutor(self._db, self._owner, seed_tag, scope)
        tools = get_anthology_tools(include_tag_co_occurrences=True)
        messages = self._build_initial_messages(seed_tag, scope, executor)
        max_iterations = self._get_max_iterations()
        default_provider = str(self._settings.get("realtime_llm", "llamacpp")).strip() or "llamacpp"

        try:
            for turn_number in range(1, max_iterations + 1):
                response = self._llm_router.call_with_tools(
                    self._settings,
                    user_msgs=[],
                    tools=tools,
                    provider_key="anthology_llm",
                    default=default_provider,
                    messages=messages,
                    parallel_tool_calls=False,
                )
                assistant_content = str(response.content or "").strip()
                turn_messages: list[dict[str, Any]] = []
                if assistant_content:
                    turn_messages.append({"role": "assistant", "content": assistant_content})

                if response.tool_calls:
                    tool_results: list[dict[str, Any]] = []
                    assistant_turn_content = assistant_content or self._summarize_tool_calls(response.tool_calls)
                    assistant_message = self._build_assistant_tool_call_message(
                        assistant_turn_content,
                        response.tool_calls,
                    )
                    messages.append(assistant_message)
                    if not turn_messages:
                        turn_messages.append(dict(assistant_message))

                    for tool_call in response.tool_calls:
                        tool_output = executor.execute(
                            tool_call.name,
                            dict(tool_call.arguments),
                        )
                        tool_message = {
                            "role": "tool",
                            "tool_call_id": tool_call.id or tool_call.name,
                            "name": tool_call.name,
                            "content": tool_output,
                        }
                        messages.append(tool_message)
                        tool_results.append(
                            {
                                "id": tool_call.id or tool_call.name,
                                "name": tool_call.name,
                                "content": tool_output,
                            }
                        )

                    self._anthology_runs.append_turn(
                        run_id,
                        {
                            "turn": turn_number,
                            "messages": turn_messages,
                            "reasoning": response.reasoning,
                            "tool_calls": [
                                {
                                    "id": call.id,
                                    "name": call.name,
                                    "arguments": dict(call.arguments),
                                }
                                for call in response.tool_calls
                            ],
                            "tool_results": tool_results,
                        },
                    )
                    continue

                messages.append({"role": "assistant", "content": assistant_content})
                result = self._normalize_result(
                    self._parse_json_response(assistant_content),
                    seed_tag,
                    executor,
                )
                saved = self._anthologies.update_result(
                    anthology_id,
                    result,
                    run_id,
                    executor.build_source_snapshot(result),
                )
                self._anthology_runs.append_turn(
                    run_id,
                    {
                        "turn": turn_number,
                        "messages": turn_messages,
                        "reasoning": response.reasoning,
                        "tool_calls": [],
                        "tool_results": [],
                    },
                )
                if not saved:
                    raise RuntimeError("Failed to save anthology result")

                self._anthology_runs.finish(run_id, "done")
                return True

            raise RuntimeError(f"Anthology generation exceeded {max_iterations} iterations")
        except Exception as exc:
            self._log.error("Anthology generation failed for %s: %s", anthology_id, exc)
            self._anthology_runs.append_turn(
                run_id,
                {
                    "turn": max_iterations + 1,
                    "messages": [{"role": "system", "content": f"Anthology generation failed: {exc}"}],
                    "tool_calls": [],
                    "tool_results": [],
                },
            )
            self._anthology_runs.finish(run_id, "failed", str(exc))
            self._anthologies.update_status(anthology_id, "failed")
            return False

    def _build_initial_messages(
        self,
        seed_tag: str,
        scope: dict[str, Any],
        executor: AnthologyToolExecutor,
    ) -> list[dict[str, Any]]:
        topic_seed = executor.search_related_topics(seed_tag, limit=10).get("topics", [])
        topic_lines = [
            f"- {topic['topic_path']} ({topic['sentence_count']} sentences)"
            for topic in topic_seed
        ]
        if not topic_lines:
            topic_lines = ["- No grouped topics found in scope yet."]

        system_prompt = (
            "You are building an anthology from grouped topic snippets.\n"
            "Use tools to inspect scoped topics before answering.\n"
            "Relevance discipline:\n"
            "- The seed tag is matched by lexical search, so candidates may be"
            " homographs or unrelated stems (e.g. seed 'muse' may surface 'museum'"
            " or 'music'). Treat every candidate as a hypothesis, not a confirmed"
            " match.\n"
            "- Before keeping a topic, call get_topic_details and read the"
            " sentences. Keep the topic only if its sentences are clearly about"
            " the seed concept's intended sense; otherwise drop it.\n"
            "- Prefer fewer high-confidence sources over many loosely related ones."
            " It is acceptable to return an empty sub_anthologies list when nothing"
            " strongly fits.\n"
            "- When sentences mix relevant and irrelevant material, only cite"
            " sentence_indices that are on-topic.\n"
            "Return valid JSON only with this shape:\n"
            "{"
            '"title": string, '
            '"summary": string, '
            '"source_refs": [{"post_id": string, "sentence_indices": [int], "topic_path": string, "tag": string}], '
            '"sub_anthologies": ['
            '{"node_id": string, "title": string, "summary": string, "topic_paths": [string], '
            '"source_refs": [...], "post_ids": [string], "sub_anthologies": []}'
            "]"
            "}\n"
            "Every node must have source_refs or topic_paths that can resolve to source_refs."
        )
        user_prompt = (
            f'Seed tag: "{seed_tag}"\n'
            f"Scope: {json.dumps(scope, sort_keys=True)}\n"
            "Initial grouped topics:\n"
            + "\n".join(topic_lines)
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _normalize_result(
        self,
        raw_result: dict[str, Any],
        seed_tag: str,
        executor: AnthologyToolExecutor,
    ) -> dict[str, Any]:
        title = str(raw_result.get("title", "")).strip() or seed_tag
        summary = str(raw_result.get("summary", "")).strip()
        root_source_refs = self._normalize_source_refs(
            raw_result.get("source_refs", []),
            seed_tag,
            executor,
        )
        sub_anthologies = [
            self._normalize_node(child, seed_tag, executor, index)
            for index, child in enumerate(raw_result.get("sub_anthologies", []), start=1)
            if isinstance(child, dict)
        ]
        if not root_source_refs:
            root_source_refs = self._dedupe_source_refs(
                [
                    source_ref
                    for child in sub_anthologies
                    for source_ref in child.get("source_refs", [])
                ]
            )
        return {
            "title": title,
            "summary": summary,
            "source_refs": root_source_refs,
            "sub_anthologies": sub_anthologies,
        }

    def _normalize_node(
        self,
        raw_node: dict[str, Any],
        seed_tag: str,
        executor: AnthologyToolExecutor,
        position: int,
    ) -> dict[str, Any]:
        title = str(raw_node.get("title", "")).strip() or f"Section {position}"
        topic_paths = [
            str(value).strip()
            for value in raw_node.get("topic_paths", [])
            if str(value).strip()
        ]
        source_refs = self._normalize_source_refs(
            raw_node.get("source_refs", []),
            seed_tag,
            executor,
        )
        if topic_paths:
            for topic_path in topic_paths:
                topic_details = executor.get_topic_details(topic_path, limit=20)
                for match in topic_details.get("matches", []):
                    source_refs.extend(match.get("source_refs", []))
        children = [
            self._normalize_node(child, seed_tag, executor, index)
            for index, child in enumerate(raw_node.get("sub_anthologies", []), start=1)
            if isinstance(child, dict)
        ]
        if not source_refs:
            source_refs = self._dedupe_source_refs(
                [
                    source_ref
                    for child in children
                    for source_ref in child.get("source_refs", [])
                ]
            )
        source_refs = self._dedupe_source_refs(source_refs)
        post_ids = sorted({str(ref["post_id"]) for ref in source_refs if ref.get("post_id")})
        normalized_topic_paths = sorted(
            {
                str(ref["topic_path"]).strip()
                for ref in source_refs
                if str(ref.get("topic_path", "")).strip()
            }
            | set(topic_paths)
        )
        node_id = str(raw_node.get("node_id", "")).strip() or self._slugify(title, position)
        return {
            "node_id": node_id,
            "title": title,
            "summary": str(raw_node.get("summary", "")).strip(),
            "source_refs": source_refs,
            "post_ids": post_ids,
            "topic_paths": normalized_topic_paths,
            "sub_anthologies": children,
        }

    def _normalize_source_refs(
        self,
        raw_refs: Any,
        seed_tag: str,
        executor: AnthologyToolExecutor,
    ) -> list[dict[str, Any]]:
        if not isinstance(raw_refs, list):
            return []
        refs: list[dict[str, Any]] = []
        for raw_ref in raw_refs:
            if not isinstance(raw_ref, dict):
                continue
            post_id = str(raw_ref.get("post_id", "")).strip()
            topic_path = str(raw_ref.get("topic_path", "")).strip()
            sentence_indices = []
            for value in raw_ref.get("sentence_indices", []):
                try:
                    sentence_indices.append(int(value))
                except (TypeError, ValueError):
                    continue
            if not post_id or not topic_path or not sentence_indices:
                continue
            refs.append(
                {
                    "post_id": post_id,
                    "sentence_indices": sorted(set(sentence_indices)),
                    "topic_path": topic_path,
                    "tag": str(raw_ref.get("tag", "")).strip() or seed_tag,
                }
            )
        return self._dedupe_source_refs(refs)

    @staticmethod
    def _dedupe_source_refs(source_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, tuple[int, ...], str, str]] = set()
        normalized: list[dict[str, Any]] = []
        for source_ref in source_refs:
            key = (
                str(source_ref.get("post_id", "")),
                tuple(sorted(int(value) for value in source_ref.get("sentence_indices", []))),
                str(source_ref.get("topic_path", "")),
                str(source_ref.get("tag", "")),
            )
            if not all(key[:3]):
                continue
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                {
                    "post_id": key[0],
                    "sentence_indices": list(key[1]),
                    "topic_path": key[2],
                    "tag": key[3],
                }
            )
        return normalized

    @staticmethod
    def _parse_json_response(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as exc:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end < start:
                raise ValueError("Anthology response did not contain JSON")
            json_text = text[start : end + 1]
            try:
                decoded = json.loads(json_text)
            except json.JSONDecodeError as nested_exc:
                if "Invalid \\escape" not in exc.msg and "Invalid \\escape" not in nested_exc.msg:
                    raise
                decoded = json.loads(AnthologyAgent._escape_invalid_json_escapes(json_text))
        if not isinstance(decoded, dict):
            raise ValueError("Anthology response JSON must be an object")
        return decoded

    @staticmethod
    def _build_assistant_tool_call_message(
        content: str,
        tool_calls: Sequence[ToolCall],
    ) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {
                    "id": tool_call.id or tool_call.name,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": json.dumps(dict(tool_call.arguments), sort_keys=True),
                    },
                }
                for tool_call in tool_calls
            ],
        }

    @staticmethod
    def _escape_invalid_json_escapes(text: str) -> str:
        return re.sub(r'\\([^"\\/bfnrtu])', r"\\\\\1", text)

    @staticmethod
    def _slugify(title: str, position: int) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        return slug or f"section-{position}"

    @staticmethod
    def _summarize_tool_calls(tool_calls: Sequence[ToolCall]) -> str:
        items = [f"{tool_call.name}({json.dumps(dict(tool_call.arguments), sort_keys=True)})" for tool_call in tool_calls]
        return "Requested tools: " + ", ".join(items)

    def _get_max_iterations(self) -> int:
        raw_value = self._settings.get("anthology_max_iterations", 8)
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            value = 8
        return max(2, min(value, 20))
