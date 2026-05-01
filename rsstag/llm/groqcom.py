import json
import os
from collections.abc import Sequence
from typing import Any, List, Optional, Union
import logging
from urllib.parse import urlparse
from http.client import HTTPConnection, HTTPSConnection

from rsstag.llm.base import LLMResponse, ToolCall, ToolDefinition, parse_arguments


class GroqCom:
    ALLOWED_MODELS = [
        "llama-3.1-70b-versatile",
        "llama3-70b-8192",
        "mixtral-8x7b-32768",
        "gemma-7b-it",
    ]
    DEFAULT_TIMEOUT = 300  # 5 minutes

    def __init__(
        self,
        host: str,
        max_context_tokens: int = 11000,
        token: Optional[str] = None,
        model: str = "llama-3.1-70b-versatile",
        timeout: int = DEFAULT_TIMEOUT,
    ):
        u = urlparse(host)
        self.__host = u.netloc
        self.__is_https = u.scheme.lower() == "https"
        self.__max_context_tokens = max_context_tokens
        self.__token = token or os.getenv("TOKEN")
        if model not in self.ALLOWED_MODELS:
            self.__model = self.ALLOWED_MODELS[0]
        else:
            self.__model = model
        self.__timeout = timeout

    def estimate_tokens(self, text: str) -> int:
        """Rough estimation: ~4 characters per token on average"""
        return len(text) // 4

    def call(
        self,
        user_msgs: List[str],
        temperature: float = 0.0,
    ) -> str:
        conn = self.get_connection()
        payload = {
            "model": self.__model,
            "messages": [{"role": "user", "content": user_msgs[0]}],
            "temperature": temperature,
        }
        body = json.dumps(payload)
        headers = {"Content-type": "application/json"}
        if self.__token:
            headers["Authorization"] = f"Bearer {self.__token}"
        conn.request("POST", "/openai/v1/chat/completions", body, headers)
        res = conn.getresponse()
        resp_body = res.read()
        if res.status != 200:
            err_msg = f"{res.status} - {res.reason} - {resp_body}"
            logging.error(err_msg)
            return err_msg
        resp = json.loads(resp_body)

        return resp["choices"][0]["message"]["content"]

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

        payload: dict[str, Any] = {
            "model": self.__model,
            "messages": request_messages,
            "temperature": temperature,
            "tools": self._to_provider_tools(tools),
        }
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            payload["parallel_tool_calls"] = parallel_tool_calls

        conn = self.get_connection()
        try:
            body = json.dumps(payload)
            headers: dict[str, str] = {"Content-type": "application/json"}
            if self.__token:
                headers["Authorization"] = f"Bearer {self.__token}"
            conn.request("POST", "/openai/v1/chat/completions", body, headers)
            res = conn.getresponse()
            resp_body = res.read()
            if res.status != 200:
                err_msg = f"{res.status} - {res.reason} - {resp_body}"
                logging.error("GroqCom error: %s", err_msg)
                return LLMResponse(content=err_msg)
            resp = json.loads(resp_body)
        except Exception as e:
            logging.error("GroqCom error: %s", e)
            return LLMResponse(content=f"GroqCom error {e}")
        finally:
            conn.close()

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
        choices = response.get("choices", ()) if isinstance(response, dict) else ()
        first_choice = choices[0] if choices else {}
        message = first_choice.get("message", {}) if isinstance(first_choice, dict) else {}

        content: str | None = message.get("content") or None

        tool_calls: list[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", tc) if isinstance(tc, dict) else tc
            tool_calls.append(
                ToolCall(
                    id=tc.get("id") if isinstance(tc, dict) else None,
                    name=fn.get("name", "") if isinstance(fn, dict) else "",
                    arguments=parse_arguments(fn.get("arguments", "{}") if isinstance(fn, dict) else "{}"),
                )
            )
        return LLMResponse(content=content, tool_calls=tuple(tool_calls), raw=response)

    def get_connection(self) -> Union[HTTPConnection, HTTPSConnection]:
        if self.__is_https:
            return HTTPSConnection(self.__host, timeout=self.__timeout)
        else:
            return HTTPConnection(self.__host, timeout=self.__timeout)
