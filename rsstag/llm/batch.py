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
    # Endpoint used when submitting a batch (e.g. "/v1/chat/completions")
    batch_endpoint = "/v1/chat/completions"

    # Batch API limits
    MAX_BATCH_REQUESTS = 50000
    MAX_BATCH_SIZE_BYTES = 200 * 1024 * 1024  # 200 MB

    def __init__(self, model: str, batch_host: Optional[str] = None):
        self.model = model
        self.batch_host = self._normalize_batch_host(batch_host)
        self._client = None

    def _normalize_batch_host(self, host: Optional[str]) -> Optional[str]:
        if not host:
            return None
        normalized: str = host.strip()
        if not normalized:
            return None
        return normalized.rstrip("/") + "/"

    def _build_openai_client(self, token: str) -> OpenAI:
        if self.batch_host:
            return OpenAI(api_key=token, base_url=self.batch_host)
        return OpenAI(api_key=token)

    def build_request(self, custom_id: str, prompt: str) -> dict:
        """Build a single JSONL batch request dict for this provider."""
        return {
            "custom_id": custom_id,
            "method": "POST",
            "url": self.batch_endpoint,
            "body": {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            },
        }

    def create_batch(
        self,
        requests: Sequence[dict],
        endpoint: str,
        completion_window: str = "24h",
        metadata: Optional[dict] = None,
    ) -> dict:
        if len(requests) > self.MAX_BATCH_REQUESTS:
            raise ValueError(
                f"Batch exceeds maximum request limit of {self.MAX_BATCH_REQUESTS} "
                f"(got {len(requests)} requests)"
            )

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
        logging.info("%s: uploaded batch file: %s", self.name, file_resp.id)
        batch = self._client.batches.create(
            input_file_id=file_resp.id,
            endpoint=endpoint,
            completion_window=completion_window,
            metadata=metadata,
        )
        logging.info("%s: created batch: %s status=%s", self.name, batch.id, batch.status)
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


class OpenAIBatchProvider(LlmBatchProvider):
    name = "openai"
    batch_endpoint = "/v1/responses"

    def __init__(self, token: str, model: str, batch_host: Optional[str] = None):
        super().__init__(model, batch_host=batch_host)
        self._client = self._build_openai_client(token)

    def build_request(self, custom_id: str, prompt: str) -> dict:
        """OpenAI Responses API uses 'input' instead of 'messages'."""
        return {
            "custom_id": custom_id,
            "method": "POST",
            "url": self.batch_endpoint,
            "body": {
                "model": self.model,
                "input": [{"role": "user", "content": prompt}],
            },
        }


class NebiusBatchProvider(LlmBatchProvider):
    """Batch provider for Nebius AI (OpenAI-compatible chat completions API).

    Uses /v1/chat/completions endpoint with standard 'messages' body format.
    Base URL: https://api.tokenfactory.nebius.com/v1/
    """

    name = "nebius"
    batch_endpoint = "/v1/chat/completions"
    # Nebius limits: up to 5,000,000 requests, max 10 GB file
    MAX_BATCH_REQUESTS = 5_000_000
    MAX_BATCH_SIZE_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB

    NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

    def __init__(self, token: str, model: str, batch_host: Optional[str] = None):
        super().__init__(model, batch_host=batch_host or self.NEBIUS_BASE_URL)
        self._client = self._build_openai_client(token)
