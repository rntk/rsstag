import io
import json
import logging
from typing import Optional, Sequence

from openai import OpenAI


class LlmBatchProvider:
    name = "base"

    def __init__(self, model: str):
        self.model = model

    def create_batch(
        self,
        requests: Sequence[dict],
        endpoint: str,
        completion_window: str = "24h",
        metadata: Optional[dict] = None,
    ) -> dict:
        raise NotImplementedError

    def get_batch(self, batch_id: str):
        raise NotImplementedError

    def get_file_content(self, file_id: str) -> str:
        raise NotImplementedError


class OpenAIBatchProvider(LlmBatchProvider):
    name = "openai"

    def __init__(self, token: str, model: str):
        super().__init__(model)
        self._client = OpenAI(api_key=token)

    def create_batch(
        self,
        requests: Sequence[dict],
        endpoint: str,
        completion_window: str = "24h",
        metadata: Optional[dict] = None,
    ) -> dict:
        jsonl = "\n".join(json.dumps(req, ensure_ascii=False) for req in requests)
        file_obj = io.BytesIO(jsonl.encode("utf-8"))
        file_obj.name = "batch.jsonl"
        file_resp = self._client.files.create(file=file_obj, purpose="batch")
        logging.info("Uploaded batch file: %s", file_resp.id)
        batch = self._client.batches.create(
            input_file_id=file_resp.id,
            endpoint=endpoint,
            completion_window=completion_window,
            metadata=metadata,
        )
        logging.info("Created batch: %s status=%s", batch.id, batch.status)
        return {
            "batch": batch,
            "input_file_id": file_resp.id,
        }

    def get_batch(self, batch_id: str):
        return self._client.batches.retrieve(batch_id)

    def get_file_content(self, file_id: str) -> str:
        if not file_id:
            return ""
        file_response = self._client.files.content(file_id)
        return file_response.text
