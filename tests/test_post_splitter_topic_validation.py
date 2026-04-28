import unittest
from typing import Any
from unittest.mock import patch

from rsstag.post_splitter import ParsingError, PostSplitter


class _DummyLLMHandler:
    def call(self, prompts, temperature=0.0):
        return "ok"


class _FakePipeline:
    start_calls = 0

    def __init__(self, **kwargs: Any) -> None:
        pass

    def start(self, text: str) -> "_FakeSession":
        _FakePipeline.start_calls += 1
        return _FakeSession()


class _FakeSession:
    def is_complete(self) -> bool:
        return True

    def result(self) -> object:
        return object()


class _FakeRequest:
    prompt: str = "prompt text"
    temperature: float = 0.0


class _DeferredSession:
    def __init__(self) -> None:
        self.responses: list[Any] = []

    def is_complete(self) -> bool:
        return bool(self.responses)

    def pending_requests(self) -> tuple[_FakeRequest, ...]:
        return (_FakeRequest(),)

    def submit_responses(self, responses: list[Any]) -> None:
        self.responses = responses

    def result(self) -> str:
        return self.responses[0].content


class _DeferredPipeline:
    def __init__(self) -> None:
        self.session = _DeferredSession()

    def start(self, text: str) -> _DeferredSession:
        return self.session


class _FakeLLMCallable:
    def __init__(self) -> None:
        self.prompts: list[tuple[str, float]] = []

    def call(self, prompt: str, temperature: float) -> str:
        self.prompts.append((prompt, temperature))
        return "llm response"


class TestPostSplitterTopicValidation(unittest.TestCase):
    def setUp(self):
        _FakePipeline.start_calls = 0

    def _patch_pipeline_dependencies(self):
        return patch.multiple(
            "rsstag.post_splitter",
            SparseRegexSentenceSplitter=lambda *args, **kwargs: object(),
            OverlapChunker=lambda *args, **kwargs: object(),
            TracingLLMCallable=lambda *args, **kwargs: object(),
            TopicRangeLLM=lambda *args, **kwargs: object(),
            HTMLParserTagStripCleaner=lambda *args, **kwargs: object(),
            MappingOffsetRestorer=lambda *args, **kwargs: object(),
            BracketMarker=lambda *args, **kwargs: object(),
            OptimizingMarker=lambda *args, **kwargs: object(),
            TopicRangeParser=lambda *args, **kwargs: object(),
            LLMRepairingGapHandler=lambda *args, **kwargs: object(),
            AdjacentSameTopicJoiner=lambda *args, **kwargs: object(),
            build_pipeline=lambda **kwargs: _FakePipeline(**kwargs),
        )

    def test_retries_when_topic_name_too_long(self):
        splitter = PostSplitter(_DummyLLMHandler())
        long_topic = "x" * (splitter.MAX_TOPIC_LENGTH + 1)

        with self._patch_pipeline_dependencies(), patch.object(
            PostSplitter,
            "_transform_result",
            side_effect=[
                {"sentences": [], "groups": {long_topic: [1]}},
                {"sentences": [], "groups": {"valid topic": [1]}},
            ],
        ):
            result = splitter.generate_grouped_data("text", "title")

        self.assertEqual(_FakePipeline.start_calls, 2)
        self.assertEqual(result["groups"], {"valid topic": [1]})

    def test_fails_after_max_retries_for_invalid_topics(self):
        splitter = PostSplitter(_DummyLLMHandler())
        long_topic = "x" * (splitter.MAX_TOPIC_LENGTH + 1)

        with self._patch_pipeline_dependencies(), patch.object(
            PostSplitter,
            "_transform_result",
            return_value={"sentences": [], "groups": {long_topic: [1]}},
        ):
            with self.assertRaises(ParsingError) as cm:
                splitter.generate_grouped_data("text", "title")

        self.assertIn("Invalid LLM output", str(cm.exception))
        self.assertIn(long_topic, str(cm.exception))
        self.assertEqual(_FakePipeline.start_calls, splitter.MAX_PIPELINE_RETRIES)

    def test_run_pipeline_session_drives_deferred_requests(self):
        splitter = PostSplitter(_DummyLLMHandler())
        pipeline = _DeferredPipeline()
        llm_callable = _FakeLLMCallable()

        result = splitter._run_pipeline_session(pipeline, "text", llm_callable)

        self.assertEqual(result, "llm response")
        self.assertEqual(llm_callable.prompts, [("prompt text", 0.0)])


if __name__ == "__main__":
    unittest.main()
