import json
import unittest
from unittest.mock import MagicMock, patch

from rsstag.llm.batch import (
    BatchTaskStatus,
    LlmBatchProvider,
    OpenAIBatchProvider,
    NebiusBatchProvider,
)


class TestBatchTaskStatus(unittest.TestCase):
    def test_enum_values(self) -> None:
        self.assertEqual(BatchTaskStatus.NEW.value, "new")
        self.assertEqual(BatchTaskStatus.SUBMITTED.value, "submitted")
        self.assertEqual(BatchTaskStatus.IN_PROGRESS.value, "in_progress")
        self.assertEqual(BatchTaskStatus.RAW_PENDING.value, "raw_pending")
        self.assertEqual(BatchTaskStatus.COMPLETED.value, "done")
        self.assertEqual(BatchTaskStatus.FAILED.value, "failed")


class TestLlmBatchProvider(unittest.TestCase):
    def setUp(self) -> None:
        self.provider: LlmBatchProvider = LlmBatchProvider("gpt-4")

    def test_normalize_batch_host_none(self) -> None:
        self.assertIsNone(self.provider._normalize_batch_host(None))

    def test_normalize_batch_host_empty_string(self) -> None:
        self.assertIsNone(self.provider._normalize_batch_host(""))

    def test_normalize_batch_host_whitespace_only(self) -> None:
        self.assertIsNone(self.provider._normalize_batch_host("   "))

    def test_normalize_batch_host_strips_whitespace(self) -> None:
        result = self.provider._normalize_batch_host("  https://example.com  ")
        self.assertEqual(result, "https://example.com/")

    def test_normalize_batch_host_adds_trailing_slash(self) -> None:
        result = self.provider._normalize_batch_host("https://example.com")
        self.assertEqual(result, "https://example.com/")

    def test_normalize_batch_host_preserves_existing_trailing_slash(self) -> None:
        result = self.provider._normalize_batch_host("https://example.com/")
        self.assertEqual(result, "https://example.com/")

    @patch("rsstag.llm.batch.OpenAI")
    def test_build_openai_client_with_host(self, mock_openai: MagicMock) -> None:
        self.provider.batch_host = "https://api.example.com/"
        client = self.provider._build_openai_client("token123")
        mock_openai.assert_called_once_with(
            api_key="token123", base_url="https://api.example.com/"
        )
        self.assertIs(client, mock_openai.return_value)

    @patch("rsstag.llm.batch.OpenAI")
    def test_build_openai_client_without_host(self, mock_openai: MagicMock) -> None:
        self.provider.batch_host = None
        client = self.provider._build_openai_client("token123")
        mock_openai.assert_called_once_with(api_key="token123")
        self.assertIs(client, mock_openai.return_value)

    def test_build_request(self) -> None:
        req = self.provider.build_request("req-1", "hello world")
        self.assertEqual(req["custom_id"], "req-1")
        self.assertEqual(req["method"], "POST")
        self.assertEqual(req["url"], "/v1/chat/completions")
        self.assertEqual(req["body"]["model"], "gpt-4")
        self.assertEqual(
            req["body"]["messages"], [{"role": "user", "content": "hello world"}]
        )

    def test_create_batch_raises_when_request_limit_exceeded(self) -> None:
        self.provider.MAX_BATCH_REQUESTS = 2
        requests = [{"custom_id": str(i)} for i in range(3)]
        with self.assertRaises(ValueError) as ctx:
            self.provider.create_batch(requests, "/v1/chat/completions")
        self.assertIn("exceeds maximum request limit", str(ctx.exception))

    def test_create_batch_raises_when_size_limit_exceeded(self) -> None:
        self.provider.MAX_BATCH_SIZE_BYTES = 10
        requests = [{"custom_id": "1", "content": "a" * 100}]
        with self.assertRaises(ValueError) as ctx:
            self.provider.create_batch(requests, "/v1/chat/completions")
        self.assertIn("exceeds maximum size limit", str(ctx.exception))

    def test_create_batch_size_validation_uses_utf8_bytes(self) -> None:
        # "é" is 2 bytes in UTF-8, so the JSONL byte size exceeds the limit
        # while the Python string length does not.
        self.provider.MAX_BATCH_SIZE_BYTES = 20
        requests = [{"custom_id": "1", "content": "éééééééééé"}]
        with self.assertRaises(ValueError) as ctx:
            self.provider.create_batch(requests, "/v1/chat/completions")
        self.assertIn("exceeds maximum size limit", str(ctx.exception))

    def test_create_batch_success(self) -> None:
        mock_client = MagicMock()
        file_resp = MagicMock()
        file_resp.id = "file-123"
        batch_resp = MagicMock()
        batch_resp.id = "batch-456"
        batch_resp.status = "submitted"
        mock_client.files.create.return_value = file_resp
        mock_client.batches.create.return_value = batch_resp
        self.provider._client = mock_client

        requests = [
            {"custom_id": "1", "body": {"model": "gpt-4"}},
            {"custom_id": "2", "body": {"model": "gpt-4"}},
        ]
        result = self.provider.create_batch(
            requests,
            "/v1/chat/completions",
            completion_window="24h",
            metadata={"key": "val"},
        )

        # Verify file upload
        mock_client.files.create.assert_called_once()
        call_kwargs = mock_client.files.create.call_args.kwargs
        uploaded_file = call_kwargs["file"]
        self.assertEqual(uploaded_file.name, "batch.jsonl")
        self.assertEqual(call_kwargs["purpose"], "batch")

        # Verify JSONL content
        uploaded_file.seek(0)
        uploaded_bytes = uploaded_file.read()
        expected_jsonl = "\n".join(
            json.dumps(req, ensure_ascii=False) for req in requests
        )
        self.assertEqual(uploaded_bytes, expected_jsonl.encode("utf-8"))

        # Verify batch creation
        mock_client.batches.create.assert_called_once_with(
            input_file_id="file-123",
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"key": "val"},
        )

        # Verify return value
        self.assertEqual(result["input_file_id"], "file-123")
        self.assertIs(result["batch"], batch_resp)

    def test_get_batch(self) -> None:
        mock_client = MagicMock()
        batch_resp = MagicMock()
        mock_client.batches.retrieve.return_value = batch_resp
        self.provider._client = mock_client

        result = self.provider.get_batch("batch-1")
        self.assertIs(result, batch_resp)
        mock_client.batches.retrieve.assert_called_once_with("batch-1")

    def test_get_file_content(self) -> None:
        mock_client = MagicMock()
        file_resp = MagicMock()
        file_resp.text = "file contents"
        mock_client.files.content.return_value = file_resp
        self.provider._client = mock_client

        result = self.provider.get_file_content("file-1")
        self.assertEqual(result, "file contents")
        mock_client.files.content.assert_called_once_with("file-1")

    def test_get_file_content_empty_id(self) -> None:
        self.provider._client = MagicMock()
        result = self.provider.get_file_content("")
        self.assertEqual(result, "")
        self.provider._client.files.content.assert_not_called()


class TestOpenAIBatchProvider(unittest.TestCase):
    @patch("rsstag.llm.batch.OpenAI")
    def test_init_sets_client(self, mock_openai: MagicMock) -> None:
        provider = OpenAIBatchProvider("token-abc", "gpt-4o")
        mock_openai.assert_called_once_with(api_key="token-abc")
        self.assertIs(provider._client, mock_openai.return_value)

    @patch("rsstag.llm.batch.OpenAI")
    def test_init_with_batch_host(self, mock_openai: MagicMock) -> None:
        provider = OpenAIBatchProvider(
            "token-abc", "gpt-4o", batch_host="https://custom.openai.com/"
        )
        mock_openai.assert_called_once_with(
            api_key="token-abc", base_url="https://custom.openai.com/"
        )

    @patch("rsstag.llm.batch.OpenAI")
    def test_build_request_uses_input_field(self, mock_openai: MagicMock) -> None:
        provider = OpenAIBatchProvider("token", "gpt-4o")
        req = provider.build_request("req-1", "hello")
        self.assertEqual(req["body"]["input"], [{"role": "user", "content": "hello"}])
        self.assertNotIn("messages", req["body"])


class TestNebiusBatchProvider(unittest.TestCase):
    @patch("rsstag.llm.batch.OpenAI")
    def test_init_forces_default_base_url_when_no_custom_host(
        self, mock_openai: MagicMock
    ) -> None:
        provider = NebiusBatchProvider("token-abc", "llama-3")
        mock_openai.assert_called_once_with(
            api_key="token-abc",
            base_url="https://api.tokenfactory.nebius.com/v1/",
        )
        self.assertIs(provider._client, mock_openai.return_value)

    @patch("rsstag.llm.batch.OpenAI")
    def test_init_uses_custom_host_when_provided(self, mock_openai: MagicMock) -> None:
        provider = NebiusBatchProvider(
            "token-abc", "llama-3", batch_host="https://custom.nebius.com/"
        )
        mock_openai.assert_called_once_with(
            api_key="token-abc", base_url="https://custom.nebius.com/"
        )

    def test_larger_limits_than_base_class(self) -> None:
        self.assertEqual(NebiusBatchProvider.MAX_BATCH_REQUESTS, 5_000_000)
        self.assertEqual(
            NebiusBatchProvider.MAX_BATCH_SIZE_BYTES, 10 * 1024 * 1024 * 1024
        )


if __name__ == "__main__":
    unittest.main()
