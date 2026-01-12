import io
import json
import logging
from enum import Enum
from typing import Optional, Sequence

from openai import OpenAI


class BatchTaskStatus(Enum):
    """Enum for batch task status values"""

    NEW = "new"
    SUBMITTED = "submitted"
    IN_PROGRESS = "in_progress"
    RAW_PENDING = "raw_pending"
    COMPLETED = "done"
    FAILED = "failed"


class LlmBatchProvider:
    name = "base"

    # Batch API limits
    MAX_BATCH_REQUESTS = 50000
    MAX_BATCH_SIZE_BYTES = 200 * 1024 * 1024  # 200 MB

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
        # Validate batch size limits
        if len(requests) > self.MAX_BATCH_REQUESTS:
            raise ValueError(
                f"Batch exceeds maximum request limit of {self.MAX_BATCH_REQUESTS} "
                f"(got {len(requests)} requests)"
            )

        # Create JSONL content and validate size
        jsonl = "\n".join(json.dumps(req, ensure_ascii=False) for req in requests)
        jsonl_bytes = jsonl.encode("utf-8")

        if len(jsonl_bytes) > self.MAX_BATCH_SIZE_BYTES:
            raise ValueError(
                f"Batch file exceeds maximum size limit of {self.MAX_BATCH_SIZE_BYTES} bytes "
                f"(got {len(jsonl_bytes)} bytes)"
            )

        file_obj = io.BytesIO(jsonl_bytes)
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
