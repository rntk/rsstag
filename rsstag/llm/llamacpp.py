import json
from typing import List, Union, Optional, Dict, Any
import logging
import re
from urllib.parse import urlparse
from http.client import HTTPConnection, HTTPSConnection


class LLamaCPP:
    ALLOWED_MODELS = ["default"]
    DEFAULT_TIMEOUT = 600  # 10 minutes

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
        # logging.info("server response: %s", resp_body)
        if res.status != 200:
            err_msg = f"{res.status} - {res.reason} - {resp_body}"
            logging.error(err_msg)
            # Raise exception for 400 status (request too large)
            if res.status == 400:
                raise ValueError(f"Request too large (400): {err_msg}")
            return err_msg
        resp = json.loads(resp_body)

        content = resp["choices"][0]["message"]["content"]
        # Remove <think></think> tags and their content
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        return content

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
