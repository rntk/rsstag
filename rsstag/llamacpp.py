import json
from typing import List
import logging
from urllib.parse import urlparse
from http.client import HTTPConnection, HTTPSConnection

class LLamaCPP:
    def __init__(self, host: str):
        u = urlparse(host)
        self.__host = u.netloc
        self.__is_https = u.scheme.lower() == "https"

    def call(self, user_msgs: List[str]) -> str:
        if self.__is_https:
            conn = HTTPSConnection(self.__host)
        else:
            conn = HTTPConnection(self.__host)
        body = json.dumps(
            {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": user_msgs[0]}]
            }
        )
        headers = {'Content-type': 'application/json'}
        conn.request("POST", "/v1/chat/completions", body, headers)
        res = conn.getresponse()
        resp_body = res.read()
        logging.info("server response: %s", resp_body)
        if res.status != 200:
            err_msg = f"{res.status} - {res.reason} - {resp_body}"
            logging.error(err_msg)
            return err_msg
        resp = json.loads(resp_body)

        return resp["choices"][0]["message"]["content"]
