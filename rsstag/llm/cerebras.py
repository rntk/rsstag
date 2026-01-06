from typing import List, Optional
import logging
import os
from cerebras.cloud.sdk import Cerebras


class RCerebras:
    ALLOWED_MODELS = ["gpt-oss-120b"]

    def __init__(self, token: Optional[str] = None, model: str = "gpt-oss-120b"):
        self.__token = token or os.environ.get("CEREBRAS_API_KEY")
        if model not in self.ALLOWED_MODELS:
            self.__model = self.ALLOWED_MODELS[-1]
        else:
            self.__model = model
        self.__client = Cerebras(api_key=self.__token)

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
