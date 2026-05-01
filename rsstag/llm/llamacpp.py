import json
from collections.abc import Sequence
from typing import Any, Dict, List, Optional, Union
import logging
import re
from urllib.parse import urlparse
from http.client import HTTPConnection, HTTPSConnection

from rsstag.llm.base import LLMResponse, ToolCall, ToolDefinition, parse_arguments


class LLamaCPP:
    ALLOWED_MODELS = ["default"]
    DEFAULT_TIMEOUT = 2400  # 40 minutes

    def __init__(self, host: str, model: str = "default", timeout: int = DEFAULT_TIMEOUT):
        u = urlparse(host)
        self.__host = u.netloc
        self.__is_https = u.scheme.lower() == "https"
        self.__model = model
        self.__timeout = timeout

    def call(
        self,
        user_msgs: List[str],
        temperature: float = 0.0,
    ) -> str:
        conn = self.get_connection()
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": user_msgs[0]}],
            "temperature": temperature,
            "cache_prompt": True,
        }
        body = json.dumps(payload)
        headers = {"Content-type": "application/json"}
        conn.request("POST", "/v1/chat/completions", body, headers)
        res = conn.getresponse()
        resp_body = res.read()
        if res.status != 200:
            err_msg = f"{res.status} - {res.reason} - {resp_body}"
            logging.error(err_msg)
            if res.status == 400:
                raise ValueError(f"Request too large (400): {err_msg}")
            return err_msg
        resp = json.loads(resp_body)

        content = resp["choices"][0]["message"]["content"]
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        return content

    def call_with_tools(
        self,
        user_msgs: List[str],
        tools: Sequence[ToolDefinition],
        system_msgs: Optional[List[str]] = None,
        messages: Optional[Sequence[dict[str, Any]]] = None,
        temperature: float = 0.0,
        tool_choice: Optional[str] = None,
    ) -> LLMResponse:
        """Call the model with tool definitions; returns content and/or tool calls."""

        request_messages = self._build_messages(user_msgs, system_msgs, messages)

        payload: dict[str, Any] = {
            "model": self.__model,
            "messages": request_messages,
            "temperature": temperature,
            "cache_prompt": True,
            "tools": self._to_provider_tools(tools),
        }
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

        conn = self.get_connection()
        try:
            body = json.dumps(payload)
            headers = {"Content-type": "application/json"}
            conn.request("POST", "/v1/chat/completions", body, headers)
            res = conn.getresponse()
            resp_body = res.read()
            if res.status != 200:
                err_msg = f"{res.status} - {res.reason} - {resp_body}"
                logging.error("LLamaCPP error: %s", err_msg)
                return LLMResponse(content=err_msg)
            resp = json.loads(resp_body)
        except Exception as e:
            logging.error("LLamaCPP error: %s", e)
            return LLMResponse(content=f"LLamaCPP error {e}")
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

        raw_content: str = message.get("content") or ""
        content = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip() or None

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

    def embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        conn = self.get_connection()
        body = json.dumps(
            {
                # "model":"GPT-4",
                "model": "text-embedding-3-small",
                "encoding_format": "float",
                "input": texts,
            }
        )
        headers = {"Content-type": "application/json", "Authorization": "Bearer "}
        conn.request("POST", "/v1/embeddings", body, headers)
        res = conn.getresponse()
        resp_body = res.read()
        # logging.info("server response: %s", resp_body)
        if res.status != 200:
            err_msg = f"{res.status} - {res.reason} - {resp_body}"
            logging.error(err_msg)
            return None
        resp = json.loads(resp_body)
        embeds = []
        for emb in resp["data"]:
            embeds.append(emb["embedding"])

        return embeds

    def rerank(
        self, query: str, documents: List[str], top_n: int = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Reranks documents according to their relevance to the query.

        Args:
            query: The query string to rank documents against
            documents: List of document strings to rank
            top_n: Optional number of top documents to return (default returns all documents)

        Returns:
            List of dictionaries containing:
                - document: The original document text
                - index: Original index of the document in the input list
                - relevance_score: A float indicating relevance (higher is more relevant)
            Sorted by relevance_score in descending order, or None if the API call fails.
        """
        conn = self.get_connection()
        request_body = {"query": query, "documents": documents}

        if top_n is not None:
            request_body["top_n"] = top_n

        body = json.dumps(request_body)
        headers = {"Content-type": "application/json", "Authorization": "Bearer "}

        conn.request("POST", "/v1/rerank", body, headers)
        res = conn.getresponse()
        resp_body = res.read()

        if res.status != 200:
            err_msg = f"{res.status} - {res.reason} - {resp_body}"
            logging.error(err_msg)

            return None

        resp = json.loads(resp_body)

        return resp.get("results", [])
