import unittest
from unittest.mock import patch

from rsstag.post_splitter import ParsingError, PostSplitter


class _DummyLLMHandler:
    def call(self, prompts, temperature=0.0):
        return "ok"


class _FakePipeline:
    run_calls = 0

    def __init__(self, **kwargs):
        pass

    def run(self, text):
        _FakePipeline.run_calls += 1
        return object()


class TestPostSplitterTopicValidation(unittest.TestCase):
    def setUp(self):
        _FakePipeline.run_calls = 0

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
            Pipeline=_FakePipeline,
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

        self.assertEqual(_FakePipeline.run_calls, 2)
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
        self.assertEqual(_FakePipeline.run_calls, splitter.MAX_PIPELINE_RETRIES)


if __name__ == "__main__":
    unittest.main()
