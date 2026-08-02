"""Tests for prompt level caching inside PostSplitter."""

import unittest
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

from rsstag.post_splitter import ParsingError, PostSplitter, build_grouping_text


class _CountingHandler:
    """LLM handler stand-in counting how many calls really happened."""

    def __init__(self) -> None:
        self.calls: List[str] = []

    def call(self, prompts: List[str], temperature: float = 0.0) -> str:
        self.calls.append(prompts[0])
        return "llm response"


class _DictChunkCache:
    def __init__(self) -> None:
        self.storage: Dict[Tuple[str, float], str] = {}
        self.reads: int = 0

    def get(self, prompt: str, temperature: float) -> Optional[str]:
        self.reads += 1
        return self.storage.get((prompt, temperature))

    def set(self, prompt: str, temperature: float, value: str) -> bool:
        self.storage[(prompt, temperature)] = value
        return True


class _Request:
    prompt: str = "chunk prompt"
    temperature: float = 0.0


class _Session:
    def __init__(self) -> None:
        self.responses: List[Any] = []

    def is_complete(self) -> bool:
        return bool(self.responses)

    def pending_requests(self) -> Tuple[_Request, ...]:
        return (_Request(),)

    def submit_responses(self, responses: List[Any]) -> None:
        self.responses = responses

    def result(self) -> str:
        return self.responses[0].content


class _Pipeline:
    def start(self, text: str) -> _Session:
        return _Session()


def _patch_pipeline(transform_result: Any):
    return patch.multiple(
        "rsstag.post_splitter",
        SparseRegexSentenceSplitter=lambda *args, **kwargs: object(),
        OverlapChunker=lambda *args, **kwargs: object(),
        # Pass the caching callable through so the session drives it directly.
        TracingLLMCallable=lambda inner, tracer: inner,
        TopicRangeLLM=lambda *args, **kwargs: object(),
        HTMLParserTagStripCleaner=lambda *args, **kwargs: object(),
        MappingOffsetRestorer=lambda *args, **kwargs: object(),
        BracketMarker=lambda *args, **kwargs: object(),
        OptimizingMarker=lambda *args, **kwargs: object(),
        TopicRangeParser=lambda *args, **kwargs: object(),
        LLMRepairingGapHandler=lambda *args, **kwargs: object(),
        AdjacentSameTopicJoiner=lambda *args, **kwargs: object(),
        build_pipeline=lambda **kwargs: _Pipeline(),
    )


_VALID_RESULT: Dict[str, Any] = {"sentences": [{"number": 1}], "groups": {"Topic": [1]}}


class PostSplitterChunkCacheTestCase(unittest.TestCase):
    def test_repeated_prompt_is_served_from_cache(self) -> None:
        handler = _CountingHandler()
        cache = _DictChunkCache()
        splitter = PostSplitter(handler, chunk_cache=cache)

        with _patch_pipeline(_VALID_RESULT), patch.object(
            PostSplitter, "_transform_result", return_value=_VALID_RESULT
        ):
            splitter.generate_grouped_data("text one")
            splitter.generate_grouped_data("text two")

        self.assertEqual(len(handler.calls), 1)
        self.assertEqual(cache.storage[("chunk prompt", 0.0)], "llm response")

    def test_failed_pipeline_does_not_cache_responses(self) -> None:
        handler = _CountingHandler()
        cache = _DictChunkCache()
        splitter = PostSplitter(handler, chunk_cache=cache)
        long_topic: str = "x" * (PostSplitter.MAX_TOPIC_LENGTH + 1)

        with _patch_pipeline(None), patch.object(
            PostSplitter,
            "_transform_result",
            return_value={"sentences": [], "groups": {long_topic: [1]}},
        ):
            with self.assertRaises(ParsingError):
                splitter.generate_grouped_data("text")

        self.assertEqual(cache.storage, {})
        self.assertEqual(len(handler.calls), PostSplitter.MAX_PIPELINE_RETRIES)

    def test_retries_bypass_the_cache(self) -> None:
        handler = _CountingHandler()
        cache = _DictChunkCache()
        cache.storage[("chunk prompt", 0.0)] = "stale bad response"
        splitter = PostSplitter(handler, chunk_cache=cache)
        long_topic: str = "x" * (PostSplitter.MAX_TOPIC_LENGTH + 1)

        with _patch_pipeline(None), patch.object(
            PostSplitter,
            "_transform_result",
            return_value={"sentences": [], "groups": {long_topic: [1]}},
        ):
            with self.assertRaises(ParsingError):
                splitter.generate_grouped_data("text")

        # First attempt used the cached answer, the two retries asked the LLM.
        self.assertEqual(len(handler.calls), PostSplitter.MAX_PIPELINE_RETRIES - 1)

    def test_works_without_a_cache(self) -> None:
        handler = _CountingHandler()
        splitter = PostSplitter(handler)

        with _patch_pipeline(_VALID_RESULT), patch.object(
            PostSplitter, "_transform_result", return_value=_VALID_RESULT
        ):
            result = splitter.generate_grouped_data("text one")
            splitter.generate_grouped_data("text two")

        self.assertEqual(result, _VALID_RESULT)
        self.assertEqual(len(handler.calls), 2)

    def test_build_grouping_text_matches_pipeline_input(self) -> None:
        self.assertEqual(build_grouping_text("body", "title"), "title. body")
        self.assertEqual(build_grouping_text("body"), "body")


if __name__ == "__main__":
    unittest.main()
