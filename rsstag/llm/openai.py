import json
from collections.abc import Sequence
from typing import Any, List, Optional
import logging

from openai import OpenAI

from rsstag.llm.base import LLMResponse, ToolCall, ToolDefinition, parse_arguments


class ROpenAI:
    ALLOWED_MODELS = ["gpt-5-nano", "gpt-5-mini"]
    DEFAULT_TIMEOUT = 300.0  # 5 minutes

    def __init__(self, token: str, model: str = "gpt-5-mini", timeout: float = DEFAULT_TIMEOUT):
        self.token = token
        if model not in self.ALLOWED_MODELS:
            self.model = self.ALLOWED_MODELS[-1]
        else:
            self.model = model
        self.client = OpenAI(api_key=self.token, timeout=timeout)

    def call(
        self,
        user_msgs: List[str],
        system_msgs: Optional[List[str]] = None,
        temperature: float = 0.7,
        reasoning: Optional[dict] = None,
    ) -> str:
        messages = []
        for msg in user_msgs:
            messages.append({"role": "user", "content": msg})

        if system_msgs:
            for msg in system_msgs:
                messages.append({"role": "system", "content": msg})

        call_kwargs = {
            "model": self.model,
            "input": messages,
            # "temperature": temperature,
            "reasoning": reasoning or {"effort": "low"},
        }

        try:
            resp = self.client.responses.create(**call_kwargs)
        except Exception as e:
            logging.error("OpenAI error: %s", e)
            return f"OpenAI error {e}"

        logging.info("OpenAI response: %s", resp)

        return resp.output[1].content[0].text

    def call_with_tools(
        self,
        user_msgs: List[str],
        tools: Sequence[ToolDefinition],
        system_msgs: Optional[List[str]] = None,
        temperature: float = 0.7,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
    ) -> LLMResponse:
        """Call the model with tool definitions; returns content and/or tool calls."""

        messages: list[dict[str, Any]] = []
        if system_msgs:
            for msg in system_msgs:
                messages.append({"role": "system", "content": msg})
        for msg in user_msgs:
            messages.append({"role": "user", "content": msg})

        provider_tools = self._to_provider_tools(tools)

        call_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "tools": provider_tools,
            "temperature": temperature,
        }
        if tool_choice is not None:
            call_kwargs["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            call_kwargs["parallel_tool_calls"] = parallel_tool_calls

        try:
            resp = self.client.chat.completions.create(**call_kwargs)
        except Exception as e:
            logging.error("OpenAI error: %s", e)
            return LLMResponse(content=f"OpenAI error {e}")

        logging.info("OpenAI response: %s", resp)
        return self._from_provider_response(resp)

    @staticmethod
    def _to_provider_tools(tools: Sequence[ToolDefinition]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for tool in tools:
            tool_def: dict[str, Any] = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": dict(tool.parameters),
                },
            }
            if tool.strict is not None:
                tool_def["function"]["strict"] = tool.strict
            result.append(tool_def)
        return result

    @staticmethod
    def _from_provider_response(response: Any) -> LLMResponse:
        first_choice = response.choices[0] if response.choices else None
        message = first_choice.message if first_choice else None
        content = message.content if message else None
        tool_calls: list[ToolCall] = []
        if message and message.tool_calls:
            for tc in message.tool_calls:
                if tc.type == "function":
                    tool_calls.append(
                        ToolCall(
                            id=tc.id,
                            name=tc.function.name,
                            arguments=parse_arguments(tc.function.arguments),
                        )
                    )
        return LLMResponse(content=content, tool_calls=tuple(tool_calls), raw=response)
