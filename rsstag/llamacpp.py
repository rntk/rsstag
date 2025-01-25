import json
from typing import List, Union, Optional
import logging
from urllib.parse import urlparse
from http.client import HTTPConnection, HTTPSConnection

class LLamaCPP:
    def __init__(self, host: str):
        u = urlparse(host)
        self.__host = u.netloc
        self.__is_https = u.scheme.lower() == "https"

    def call(self, user_msgs: List[str], temperature: float=0.0) -> str:
        conn = self.get_connection()
        body = json.dumps(
            {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": user_msgs[0]}],
                "temperature": temperature,
                "cache_prompt": True
            }
        )
        headers = {'Content-type': 'application/json'}
        conn.request("POST", "/v1/chat/completions", body, headers)
        res = conn.getresponse()
        resp_body = res.read()
        #logging.info("server response: %s", resp_body)
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

    def embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        conn = self.get_connection()
        body = json.dumps(
            {
                #"model":"GPT-4",
                "model":"text-embedding-3-small",
                "encoding_format": "float",
                "input": texts
            }
        )
        headers = {
            'Content-type': 'application/json',
            'Authorization': 'Bearer '
        }
        conn.request("POST", "/v1/embeddings", body, headers)
        res = conn.getresponse()
        resp_body = res.read()
        #logging.info("server response: %s", resp_body)
        if res.status != 200:
            err_msg = f"{res.status} - {res.reason} - {resp_body}"
            logging.error(err_msg)
            return None
        resp = json.loads(resp_body)
        embeds = []
        for emb in resp["data"]:
            embeds.append(emb["embedding"])

        return embeds
