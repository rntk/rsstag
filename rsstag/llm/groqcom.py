import json
import os
from typing import List, Union, Optional
import logging
from urllib.parse import urlparse
from http.client import HTTPConnection, HTTPSConnection


class GroqCom:
    def __init__(
        self, host: str, max_context_tokens: int = 11000, token: Optional[str] = None
    ):
        u = urlparse(host)
        self.__host = u.netloc
        self.__is_https = u.scheme.lower() == "https"
        self.__max_context_tokens = (
            max_context_tokens  # Leave some buffer from the actual context size
        )
        # Token can be passed in explicitly or read from the environment variable TOKEN
        self.__token = token or os.getenv("TOKEN")

    def estimate_tokens(self, text: str) -> int:
        """Rough estimation: ~4 characters per token on average"""
        return len(text) // 4

    def call(
        self,
        user_msgs: List[str],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> str:
        conn = self.get_connection()
        payload = {
            "model": "openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": user_msgs[0]}],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        body = json.dumps(payload)
        headers = {"Content-type": "application/json"}
        if self.__token:
            headers["Authorization"] = f"Bearer {self.__token}"
        conn.request("POST", "/openai/v1/chat/completions", body, headers)
        # conn.request("POST", "/v1/chat/completions", body, headers)
        res = conn.getresponse()
        resp_body = res.read()
        # logging.info("server response: %s", resp_body)
        if res.status != 200:
            err_msg = f"{res.status} - {res.reason} - {resp_body}"
            logging.error(err_msg)
            return err_msg
        resp = json.loads(resp_body)

        return resp["choices"][0]["message"]["content"]

    def get_connection(self) -> Union[HTTPConnection, HTTPSConnection]:
        if self.__is_https:
            return HTTPSConnection(self.__host)
        else:
            return HTTPConnection(self.__host)
