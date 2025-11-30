from typing import List, Optional
import logging

from openai import OpenAI, Completion

class ROpenAI:
    def __init__(self, token: str):
        self.token = token
        self.model = "gpt-5-mini"
        self.client = OpenAI(
            api_key=self.token
        )

    def call(self, user_msgs: List[str], system_msgs: Optional[List[str]]=None, temperature: float=0.7, reasoning: Optional[dict]=None) -> str:
        messages = []
        for msg in user_msgs:
            messages.append({"role": "user", "content": msg})

        if system_msgs:
            for msg in system_msgs:
                messages.append({"role": "system", "content": msg})
        try:
            resp: Completion  = self.client.responses.create(
                model=self.model,
                input=messages,
                temperature=temperature,
                reasoning=reasoning or {"effort": "low"}
            )
        except Exception as e:
            logging.error("OpenAI error: %s", e)
            return f"OpenAI error {e}"

        logging.info("OpenAI response: %s", resp)

        return resp.output[1].content[0].text
