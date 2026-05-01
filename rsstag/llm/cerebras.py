from collections.abc import Sequence
from typing import Any, List, Optional
import logging
import os
from cerebras.cloud.sdk import Cerebras

from rsstag.llm.base import LLMResponse, ToolCall, ToolDefinition, parse_arguments


class RCerebras:
    ALLOWED_MODELS = ["gpt-oss-120b"]
    DEFAULT_TIMEOUT = 300.0  # 5 minutes

    def __init__(self, token: Optional[str] = None, model: str = "gpt-oss-120b", timeout: float = DEFAULT_TIMEOUT):
        self.__token = token or os.environ.get("CEREBRAS_API_KEY")
        if model not in self.ALLOWED_MODELS:
            self.__model = self.ALLOWED_MODELS[-1]
        else:
            self.__model = model
        self.__client = Cerebras(api_key=self.__token, timeout=timeout)

    def call(
        self,
        user_msgs: List[str],
        system_msgs: Optional[List[str]] = None,
        temperature: float = 0.0,
    ) -> str:
        messages = []
        if system_msgs:
            for msg in system_msgs:
                messages.append({"role": "system", "content": msg})

        for msg in user_msgs:
            messages.append({"role": "user", "content": msg})

        call_kwargs = {
            "model": self.__model,
            "messages": messages,
            "temperature": temperature,
        }

        try:
            resp = self.__client.chat.completions.create(**call_kwargs)
        except Exception as e:
            logging.error("Cerebras error: %s", e)
            return f"Cerebras error {e}"

        logging.info("Cerebras response: %s", resp)

        return resp.choices[0].message.content

    def call_with_tools(
        self,
        user_msgs: List[str],
        tools: Sequence[ToolDefinition],
        system_msgs: Optional[List[str]] = None,
        messages: Optional[Sequence[dict[str, Any]]] = None,
        temperature: float = 0.0,
        tool_choice: Optional[str] = None,
        parallel_tool_calls: bool | None = None,
    ) -> LLMResponse:
        """Call the model with tool definitions; returns content and/or tool calls."""

        request_messages = self._build_messages(user_msgs, system_msgs, messages)

        call_kwargs: dict[str, Any] = {
            "model": self.__model,
            "messages": request_messages,
            "temperature": temperature,
            "tools": self._to_provider_tools(tools),
        }
        if tool_choice is not None:
            call_kwargs["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            call_kwargs["parallel_tool_calls"] = parallel_tool_calls

        try:
            resp = self.__client.chat.completions.create(**call_kwargs)
        except Exception as e:
            logging.error("Cerebras error: %s", e)
            return LLMResponse(content=f"Cerebras error {e}")

        logging.info("Cerebras response: %s", resp)
        return self._from_provider_response(resp)

    @staticmethod
    def _build_messages(
        user_msgs: List[str],
        system_msgs: Optional[List[str]],
        messages: Optional[Sequence[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        if messages:
            return [dict(message) for message in messages]
        request_messages: list[dict[str, Any]] = []
        if system_msgs:
            for msg in system_msgs:
                request_messages.append({"role": "system", "content": msg})
        for msg in user_msgs:
            request_messages.append({"role": "user", "content": msg})
        return request_messages

    @staticmethod
    def _to_provider_tools(tools: Sequence[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": dict(tool.parameters),
                },
            }
            for tool in tools
        ]

    @staticmethod
    def _from_provider_response(response: Any) -> LLMResponse:
        choices = getattr(response, "choices", None) or []
        first_choice = choices[0] if choices else None
        message = getattr(first_choice, "message", None) if first_choice else None
        content: str | None = getattr(message, "content", None)

        tool_calls: list[ToolCall] = []
        for tc in getattr(message, "tool_calls", None) or []:
            if getattr(tc, "type", None) == "function":
                tool_calls.append(
                    ToolCall(
                        id=getattr(tc, "id", None),
                        name=tc.function.name,
                        arguments=parse_arguments(tc.function.arguments),
                    )
                )
        return LLMResponse(content=content, tool_calls=tuple(tool_calls), raw=response)
