from typing import List, Optional
import logging

from openai import OpenAI, Completion

class ROpenAI:
    def __init__(self, token: str):
        self.token = token
        self.model = "gpt-4o-mini"
        self.client = OpenAI(
            api_key=self.token
        )

    def call(self, user_msgs: List[str], system_msgs: Optional[List[str]]=None) -> str:
        messages = []
        for msg in user_msgs:
            messages.append({"role": "user", "content": msg})

        if system_msgs:
            for msg in system_msgs:
                messages.append({"role": "system", "content": msg})
        try:
            resp: Completion  = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
        except Exception as e:
            logging.error("OpenAI error: %s", e)
            return f"OpenAI error {e}"

        logging.info("OpenAI response: %s", resp)

        return resp.choices[0].message.content
