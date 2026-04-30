from collections.abc import Sequence
from typing import Any, List, Optional
import logging

import anthropic

from rsstag.llm.base import LLMResponse, ToolCall, ToolDefinition, parse_arguments


class Anthropic:
    ALLOWED_MODELS = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]
    DEFAULT_TIMEOUT = 300.0  # 5 minutes
    DEFAULT_MAX_TOKENS = 4096

    def __init__(self, token: str, model: str = "claude-3-5-haiku-20241022", timeout: float = DEFAULT_TIMEOUT):
        self.__token = token
        if model not in self.ALLOWED_MODELS:
            self.__model = self.ALLOWED_MODELS[0]
        else:
            self.__model = model
        self.__client = anthropic.Anthropic(
            api_key=token,
            timeout=timeout,
        )

    def call(self, user_msgs: List[str]) -> str:
        messages = []
        for msg in user_msgs:
            messages.append({"role": "user", "content": msg})

        try:
            resp = self.__client.messages.create(
                model=self.__model,
                max_tokens=self.DEFAULT_MAX_TOKENS,
                messages=messages,
            )
        except Exception as e:
            logging.error("Anthropic error: %s", e)
            return f"Anthropic error {e}"

        logging.info("Anthropic response: %s", resp)

        return resp.content[0].text

    def call_with_tools(
        self,
        user_msgs: List[str],
        tools: Sequence[ToolDefinition],
        system_msgs: Optional[List[str]] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResponse:
        """Call the model with tool definitions; returns content and/or tool calls."""

        raw_messages: list[dict[str, Any]] = [
            {"role": "user", "content": msg} for msg in user_msgs
        ]
        messages = self._merge_consecutive_roles(raw_messages)

        call_kwargs: dict[str, Any] = {
            "model": self.__model,
            "max_tokens": max_tokens,
            "messages": messages,
            "tools": self._to_provider_tools(tools),
        }
        if system_msgs:
            call_kwargs["system"] = "\n\n".join(system_msgs)

        try:
            resp = self.__client.messages.create(**call_kwargs)
        except Exception as e:
            logging.error("Anthropic error: %s", e)
            return LLMResponse(content=f"Anthropic error {e}")

        logging.info("Anthropic response: %s", resp)
        return self._from_provider_response(resp)

    @staticmethod
    def _to_provider_tools(tools: Sequence[ToolDefinition]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for tool in tools:
            tool_def: dict[str, Any] = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": dict(tool.parameters),
            }
            result.append(tool_def)
        return result

    @staticmethod
    def _merge_consecutive_roles(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge consecutive messages with the same role (Anthropic requirement)."""
        merged: list[dict[str, Any]] = []
        for msg in messages:
            if merged and merged[-1]["role"] == msg["role"]:
                prev_content = merged[-1]["content"]
                if isinstance(prev_content, list):
                    prev_content.extend(
                        msg["content"] if isinstance(msg["content"], list) else [{"type": "text", "text": msg["content"]}]
                    )
                else:
                    merged[-1]["content"] = prev_content + "\n" + msg["content"]
            else:
                merged.append(dict(msg))
        return merged

    @staticmethod
    def _from_provider_response(response: Any) -> LLMResponse:
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in getattr(response, "content", []):
            block_type = getattr(block, "type", None)
            if block_type == "thinking":
                thinking = getattr(block, "thinking", None)
                if thinking:
                    reasoning_parts.append(thinking)
            elif block_type == "text":
                text = getattr(block, "text", None)
                if text:
                    content_parts.append(text)
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=getattr(block, "id", None) or "",
                        name=getattr(block, "name", ""),
                        arguments=parse_arguments(getattr(block, "input", {})),
                    )
                )
        return LLMResponse(
            content="\n".join(content_parts) if content_parts else None,
            reasoning="\n\n".join(reasoning_parts) if reasoning_parts else None,
            tool_calls=tuple(tool_calls),
            raw=response,
        )

    def call_citation(self, user_prompt: str, docs: list[str]) -> str:
        messages = []
        for i, msg in enumerate(docs):
            messages.append(
                {
                    "type": "document",
                    "source": {
                        "type": "text",
                        "media_type": "text/plain",
                        "data": msg,
                    },
                    "title": f"Document {i}",
                    "context": msg,
                    "citations": {"enabled": True},
                }
            )
        messages.append(
            {
                "type": "text",
                "text": user_prompt,
            }
        )

        try:
            resp = self.__client.messages.create(
                model=self.__model,
                messages=[{"role": "user", "content": messages}],
            )
        except Exception as e:
            logging.error("Anthropic error: %s", e)
            return f"Anthropic error {e}"

        logging.info("OpenAI response: %s", resp)
        """
{
    "content": [
        {
            "type": "text",
            "text": "According to the document, "
        },
        {
            "type": "text",
            "text": "the grass is green",
            "citations": [{
                "type": "char_location",
                "cited_text": "The grass is green.",
                "document_index": 0,
                "document_title": "Example Document",
                "start_char_index": 0,
                "end_char_index": 20
            }]
        },
        {
            "type": "text",
            "text": " and "
        },
        {
            "type": "text",
            "text": "the sky is blue",
            "citations": [{
                "type": "char_location",
                "cited_text": "The sky is blue.",
                "document_index": 0,
                "document_title": "Example Document",
                "start_char_index": 20,
                "end_char_index": 36
            }]
        }
    ]
}
        """

        response = []
        for item in resp.content:
            if item.type == "text":
                response.append(item.text)
                if item.citations:
                    for citation in item.citations:
                        response.append(
                            "<citation>" + citation.cited_text + "</citation>"
                        )

        return "\n".join(response)
