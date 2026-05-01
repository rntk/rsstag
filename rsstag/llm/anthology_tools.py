"""Anthology-specific LLM tools and executor."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from typing import Any, Iterable, Optional

from rsstag.llm.base import ToolDefinition
from rsstag.post_grouping import RssTagPostGrouping
from rsstag.posts import RssTagPosts


def get_anthology_tools(include_tag_co_occurrences: bool = True) -> tuple[ToolDefinition, ...]:
    """Return the tool definitions used by the anthology agent."""

    tools: list[ToolDefinition] = [
        ToolDefinition(
            name="search_related_topics",
            description="Search scoped grouped topics related to a query and return likely matching topic paths.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
        ToolDefinition(
            name="get_topic_details",
            description="Return the supporting sentences and source references for a scoped topic path.",
            parameters={
                "type": "object",
                "properties": {
                    "topic_path": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["topic_path"],
                "additionalProperties": False,
            },
        ),
        ToolDefinition(
            name="get_posts_for_topic",
            description="Return post metadata for posts that contribute to a scoped topic path.",
            parameters={
                "type": "object",
                "properties": {
                    "topic_path": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["topic_path"],
                "additionalProperties": False,
            },
        ),
    ]
    if include_tag_co_occurrences:
        tools.append(
            ToolDefinition(
                name="get_tag_co_occurrences",
                description="Return tags that co-occur most often with the provided tag inside the anthology scope.",
                parameters={
                    "type": "object",
                    "properties": {
                        "tag": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    },
                    "required": ["tag"],
                    "additionalProperties": False,
                },
            )
        )
    return tuple(tools)


class AnthologyToolExecutor:
    """Execute read-only anthology tools inside a scoped corpus."""

    def __init__(self, db: Any, owner: str, seed_tag: str, scope: Optional[dict[str, Any]]) -> None:
        self._db: Any = db
        self._owner: str = owner
        self._seed_tag: str = seed_tag
        self._scope: dict[str, Any] = scope or {"mode": "all"}
        self._posts = RssTagPosts(db)
        self._post_grouping = RssTagPostGrouping(db)
        self._log = logging.getLogger("anthology_tools")
        self._allowed_post_ids: Optional[set[str]] = None
        self._grouping_entries: Optional[list[dict[str, Any]]] = None
        self._grouping_ids_by_post_id: dict[str, str] = {}

    def execute(self, tool_name: str, args: dict[str, Any]) -> str:
        """Execute a named tool and return a JSON string payload."""

        limit = self._normalize_limit(args.get("limit"), default=8)
        if tool_name == "search_related_topics":
            payload = self.search_related_topics(str(args.get("query", "")).strip(), limit)
        elif tool_name == "get_topic_details":
            payload = self.get_topic_details(str(args.get("topic_path", "")).strip(), limit)
        elif tool_name == "get_posts_for_topic":
            payload = self.get_posts_for_topic(str(args.get("topic_path", "")).strip(), limit)
        elif tool_name == "get_tag_co_occurrences":
            tag = str(args.get("tag", "")).strip() or self._seed_tag
            payload = self.get_tag_co_occurrences(tag, limit)
        else:
            raise ValueError(f"Unsupported anthology tool: {tool_name}")
        return json.dumps(payload, ensure_ascii=True)

    def search_related_topics(self, query: str, limit: int) -> dict[str, Any]:
        terms = self._tokenize(query)
        results: list[dict[str, Any]] = []
        for item in self._load_grouping_entries():
            if not terms:
                score = 1
            else:
                score = self._score_topic_match(item, terms)
            if score <= 0:
                continue
            results.append(
                {
                    "topic_path": item["topic_path"],
                    "post_ids": item["post_ids"],
                    "sentence_indices": item["sentence_indices"],
                    "sentence_count": len(item["sentence_indices"]),
                    "preview": item["preview"],
                    "score": score,
                }
            )
        results.sort(key=lambda row: (-int(row["score"]), row["topic_path"]))
        return {"query": query, "topics": results[:limit]}

    def get_topic_details(self, topic_path: str, limit: int) -> dict[str, Any]:
        topic_path = topic_path.strip()
        if not topic_path:
            return {"topic_path": "", "matches": []}
        matches: list[dict[str, Any]] = []
        for item in self._load_grouping_entries():
            if item["topic_path"] != topic_path:
                continue
            matches.append(
                {
                    "topic_path": topic_path,
                    "post_ids": item["post_ids"],
                    "sentences": item["sentences"],
                    "source_refs": item["source_refs"],
                }
            )
        return {"topic_path": topic_path, "matches": matches[:limit]}

    def get_posts_for_topic(self, topic_path: str, limit: int) -> dict[str, Any]:
        topic_path = topic_path.strip()
        if not topic_path:
            return {"topic_path": "", "posts": []}

        post_ids: list[str] = []
        for item in self._load_grouping_entries():
            if item["topic_path"] == topic_path:
                post_ids.extend(item["post_ids"])
        unique_post_ids = list(dict.fromkeys(post_ids))[:limit]
        if not unique_post_ids:
            return {"topic_path": topic_path, "posts": []}

        projection = {"pid": True, "date": True, "unix_date": True, "feed_id": True, "content.title": True}
        posts = list(self._posts.get_by_pids(self._owner, unique_post_ids, projection=projection))
        normalized_posts = [
            {
                "post_id": str(post.get("pid", "")),
                "title": str(post.get("content", {}).get("title", "")).strip(),
                "date": post.get("date") or post.get("unix_date"),
                "feed_id": post.get("feed_id"),
            }
            for post in posts
        ]
        return {"topic_path": topic_path, "posts": normalized_posts}

    def get_tag_co_occurrences(self, tag: str, limit: int) -> dict[str, Any]:
        normalized_tag = tag.strip()
        if not normalized_tag:
            return {"tag": "", "co_occurrences": []}

        query = self._post_grouping._build_scope_post_query(self._owner, self._scope)
        query["tags"] = normalized_tag
        projection = {"pid": True, "tags": True}
        counts: Counter[str] = Counter()
        for post in self._db.posts.find(query, projection=projection):
            post_id = str(post.get("pid", "")).strip()
            if not post_id or not self._is_allowed_post_id(post_id):
                continue
            for other_tag in post.get("tags", []):
                normalized_other = str(other_tag).strip()
                if normalized_other and normalized_other != normalized_tag:
                    counts[normalized_other] += 1
        return {
            "tag": normalized_tag,
            "co_occurrences": [
                {"tag": co_tag, "count": count}
                for co_tag, count in counts.most_common(limit)
            ],
        }

    def build_source_snapshot(self, result: dict[str, Any]) -> dict[str, Any]:
        post_ids: set[str] = set()
        for source_ref in self.iter_source_refs(result):
            post_id = str(source_ref.get("post_id", "")).strip()
            if post_id:
                post_ids.add(post_id)

        doc_ids = [
            self._grouping_ids_by_post_id[post_id]
            for post_id in sorted(post_ids)
            if post_id in self._grouping_ids_by_post_id
        ]
        return {
            "post_grouping_updated_at": None,
            "post_grouping_doc_ids": doc_ids,
        }

    def iter_source_refs(self, node: dict[str, Any]) -> Iterable[dict[str, Any]]:
        source_refs = node.get("source_refs", [])
        if isinstance(source_refs, list):
            for ref in source_refs:
                if isinstance(ref, dict):
                    yield ref
        for child in node.get("sub_anthologies", []):
            if isinstance(child, dict):
                yield from self.iter_source_refs(child)

    def _load_grouping_entries(self) -> list[dict[str, Any]]:
        if self._grouping_entries is not None:
            return self._grouping_entries

        allowed_post_ids = self._get_allowed_post_ids()
        query: dict[str, Any] = {"owner": self._owner}
        if allowed_post_ids is not None:
            if not allowed_post_ids:
                self._grouping_entries = []
                return self._grouping_entries
            query["post_ids"] = {"$in": sorted(allowed_post_ids)}

        entries: list[dict[str, Any]] = []
        projection = {"post_ids": True, "groups": True, "sentences": True}
        for doc in self._db.post_grouping.find(query, projection=projection):
            doc_id = str(doc.get("_id", ""))
            post_ids = [str(value) for value in doc.get("post_ids", []) if value is not None]
            usable_post_ids = [post_id for post_id in post_ids if self._is_allowed_post_id(post_id)]
            if not usable_post_ids:
                continue

            for post_id in usable_post_ids:
                self._grouping_ids_by_post_id[post_id] = doc_id
            sentence_map = {
                int(sentence["number"]): sentence
                for sentence in doc.get("sentences", [])
                if isinstance(sentence, dict) and "number" in sentence
            }
            groups = doc.get("groups", {})
            if not isinstance(groups, dict):
                continue
            for topic_path, raw_indices in groups.items():
                if not isinstance(topic_path, str) or not isinstance(raw_indices, list):
                    continue
                sentence_indices = sorted(
                    {
                        int(index)
                        for index in raw_indices
                        if isinstance(index, int) or (isinstance(index, str) and index.isdigit())
                    }
                )
                sentences = [
                    {
                        "number": index,
                        "text": str(sentence_map.get(index, {}).get("text", "")).strip(),
                        "read": bool(sentence_map.get(index, {}).get("read", False)),
                    }
                    for index in sentence_indices
                ]
                preview = " ".join(sentence["text"] for sentence in sentences if sentence["text"])[:280]
                source_refs = [
                    {
                        "post_id": post_id,
                        "sentence_indices": sentence_indices,
                        "topic_path": topic_path,
                        "tag": self._seed_tag,
                    }
                    for post_id in usable_post_ids
                ]
                entries.append(
                    {
                        "topic_path": topic_path,
                        "post_ids": usable_post_ids,
                        "sentence_indices": sentence_indices,
                        "sentences": sentences,
                        "preview": preview,
                        "source_refs": source_refs,
                    }
                )
        self._grouping_entries = entries
        return self._grouping_entries

    def _get_allowed_post_ids(self) -> Optional[set[str]]:
        if self._allowed_post_ids is not None:
            return self._allowed_post_ids

        query = self._post_grouping._build_scope_post_query(self._owner, self._scope)
        projection = {"pid": True}
        self._allowed_post_ids = {
            str(post.get("pid", "")).strip()
            for post in self._db.posts.find(query, projection=projection)
            if post.get("pid") is not None
        }
        return self._allowed_post_ids

    def _is_allowed_post_id(self, post_id: str) -> bool:
        allowed_post_ids = self._get_allowed_post_ids()
        if allowed_post_ids is None:
            return True
        return post_id in allowed_post_ids

    @staticmethod
    def _normalize_limit(value: Any, default: int) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            normalized = default
        return max(1, min(normalized, 20))

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token for token in re.split(r"[^a-z0-9]+", text.lower()) if token]

    def _score_topic_match(self, item: dict[str, Any], terms: list[str]) -> int:
        haystacks = [item["topic_path"].lower(), item["preview"].lower()]
        score = 0
        for term in terms:
            for haystack in haystacks:
                if term in haystack:
                    score += 2 if haystack == haystacks[0] else 1
                    break
        if self._seed_tag.lower() in item["topic_path"].lower():
            score += 1
        return score
