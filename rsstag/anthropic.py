from typing import List
import logging

import anthropic

class Anthropic:
    def __init__(self, token: str):
        self.__token = token
        '''"claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",'''
        self.__model = "claude-3-5-haiku-20241022"
        self.__client = anthropic.Anthropic(
            api_key=token,
        )

    def call(self, user_msgs: List[str], max_tokens: int = 1024) -> str:
        messages = []
        for msg in user_msgs:
            messages.append({"role": "user", "content": msg})

        try:
            resp = self.__client.messages.create(
                model=self.__model,
                max_tokens=max_tokens,
                messages=messages,
            )
        except Exception as e:
            logging.error("OpenAI error: %s", e)
            return f"OpenAI error {e}"

        logging.info("OpenAI response: %s", resp)

        return resp.content[0].text

    def call_citation(self, user_prompt: str, docs: list[str]) -> str:
        messages = []
        for i, msg in enumerate(docs):
            messages.append({
                "type": "document",
                "source": {
                    "type": "text",
                    "media_type": "text/plain",
                    "data": msg,
                },
                "title": f"Document {i}",
                "context": msg,
                "citations": {"enabled": True},
            })
        messages.append({
            "type": "text",
            "text": user_prompt,
        })

        try:
            resp = self.__client.messages.create(
                model=self.__model,
                max_tokens=1024,
                messages=[{"role": "user", "content": messages}],
            )
        except Exception as e:
            logging.error("OpenAI error: %s", e)
            return f"OpenAI error {e}"

        logging.info("OpenAI response: %s", resp)
        '''
{
    "content": [
        {
            "type": "text",
            "text": "According to the document, "
        },
        {
            "type": "text",
            "text": "the grass is green",
            "citations": [{
                "type": "char_location",
                "cited_text": "The grass is green.",
                "document_index": 0,
                "document_title": "Example Document",
                "start_char_index": 0,
                "end_char_index": 20
            }]
        },
        {
            "type": "text",
            "text": " and "
        },
        {
            "type": "text",
            "text": "the sky is blue",
            "citations": [{
                "type": "char_location",
                "cited_text": "The sky is blue.",
                "document_index": 0,
                "document_title": "Example Document",
                "start_char_index": 20,
                "end_char_index": 36
            }]
        }
    ]
}
        '''

        response = []
        for item in resp.content:
            if item.type == "text":
                response.append(item.text)
                if item.citations:
                    for citation in item.citations:
                        response.append("<citation>" + citation.cited_text + "</citation>")

        return "\n".join(response)