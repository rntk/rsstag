from typing import List
import logging

import anthropic

class Anthropic:
    def __init__(self, token: str):
        self.__token = token
        '''"claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",'''
        self.__model = "claude-3-opus-20240229"
        self.__client = anthropic.Anthropic(
            api_key=token,
        )

    def call(self, user_msgs: List[str]) -> str:
        messages = []
        for msg in user_msgs:
            messages.append({"role": "user", "content": msg})

        try:
            resp = self.__client.messages.create(
                model=self.__model,
                max_tokens=1024,
                messages=messages,
            )
        except Exception as e:
            logging.error("OpenAI error: %s", e)
            return f"OpenAI error {e}"

        logging.info("OpenAI response: %s", resp)

        return resp.content[0].text
