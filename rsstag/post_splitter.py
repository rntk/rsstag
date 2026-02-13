"""Post splitting and LLM interaction logic"""

import logging
from typing import Optional, Dict, Any, List

# Import txt_splitt components
from txt_splitt import (
    AdjacentSameTopicJoiner,
    BracketMarker,
    SparseRegexSentenceSplitter,
    HTMLParserTagStripCleaner,
    LLMRepairingGapHandler,
    MappingOffsetRestorer,
    NormalizingSplitter,
    Pipeline,
    OverlapChunker,
    TopicRangeLLM,
    TopicRangeParser,
    Tracer,
    TracingLLMCallable,
)


class PostSplitterError(Exception):
    """Base exception for PostSplitter errors"""

    pass


class LLMGenerationError(PostSplitterError):
    """Raised when LLM call fails or returns empty/invalid response"""

    pass


class ParsingError(PostSplitterError):
    """Raised when LLM response cannot be parsed correctly"""

    pass


class LLMHandlerAdapter:
    """Adapter to make rsstag LLM handler compatible with txt_splitt LLMCallable protocol."""

    def __init__(self, handler: Any) -> None:
        self._handler = handler

    def call(self, prompt: str, temperature: float) -> str:
        """Call the underlying LLM handler."""
        # rsstag handlers might not support temperature or have different signature
        # We assume .call(prompt, temperature=...) compatibility based on previous usage
        # Previous usage: self._llm_handler.call([prompt], temperature=temperature)
        # Note: rsstag handler apparently expects a list of prompts?
        try:
            return self._handler.call([prompt], temperature=temperature)
        except Exception as e:
            raise LLMGenerationError(f"LLM call failed: {e}") from e


class PostSplitter:
    """Handles text splitting using txt_splitt pipeline"""

    MAX_TOPIC_LENGTH = 500
    MAX_PIPELINE_RETRIES = 3

    def __init__(self, llm_handler: Optional[Any] = None) -> None:
        self._log = logging.getLogger("post_splitter")
        self._llm_handler = llm_handler

    def generate_grouped_data(
        self,
        content: str,
        title: str = "",
        is_html: bool = True,
        tracer: Optional[Tracer] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate grouped data from raw text content and title

        Raises:
            PostSplitterError: If splitting or grouping fails
        """
        if title:
            text = title + ". " + content
        else:
            text = content

        if not text.strip():
            return None

        if not self._llm_handler:
            self._log.error("LLM handler not configured")
            raise LLMGenerationError("LLM handler not configured")

        # Create adapter once and retry whole pipeline execution on invalid topic output.
        llm_adapter = LLMHandlerAdapter(self._llm_handler)
        base_tracer = tracer
        last_error: Optional[Exception] = None
        saw_validation_error = False

        for attempt in range(1, self.MAX_PIPELINE_RETRIES + 1):
            attempt_tracer = base_tracer if attempt == 1 and base_tracer is not None else Tracer()

            try:
                # Initialize the pipeline components
                # We use settings similar to the reference split_text.py
                splitter = SparseRegexSentenceSplitter(
                    anchor_every_words=5, html_aware=True
                )

                # Using OverlapChunker as in example
                chunker = OverlapChunker(max_chars=84000)

                # Set up tracing
                llm_callable = TracingLLMCallable(llm_adapter, attempt_tracer)

                topic_range_llm = TopicRangeLLM(
                    client=llm_callable,
                    temperature=0.0,
                    chunker=chunker,
                )

                html_cleaner = HTMLParserTagStripCleaner()
                offset_restorer = MappingOffsetRestorer()

                # Create the pipeline
                pipeline = Pipeline(
                    splitter=splitter,
                    marker=BracketMarker(),
                    llm=topic_range_llm,
                    parser=TopicRangeParser(),
                    gap_handler=LLMRepairingGapHandler(
                        llm_callable, temperature=0.0, tracer=attempt_tracer
                    ),
                    joiner=AdjacentSameTopicJoiner(),
                    html_cleaner=html_cleaner,
                    offset_restorer=offset_restorer,
                    tracer=attempt_tracer,
                )

                # Run the pipeline
                result = pipeline.run(text)
                transformed = self._transform_result(result)
                self._validate_topic_lengths(transformed.get("groups", {}))
                self._log.info(
                    "Pipeline trace for attempt %s:\n%s",
                    attempt,
                    attempt_tracer.format(),
                )
                return transformed

            except Exception as e:
                last_error = e
                if isinstance(e, ParsingError):
                    saw_validation_error = True
                self._log.warning(
                    "Pipeline attempt %s/%s failed: %s",
                    attempt,
                    self.MAX_PIPELINE_RETRIES,
                    e,
                )
                if attempt_tracer:
                    self._log.info(
                        "Pipeline trace before failure (attempt %s):\n%s",
                        attempt,
                        attempt_tracer.format(),
                    )

        if saw_validation_error and isinstance(last_error, ParsingError):
            raise ParsingError(
                f"Invalid LLM output after {self.MAX_PIPELINE_RETRIES} attempts: {last_error}"
            ) from last_error

        raise PostSplitterError(
            f"Pipeline execution failed after {self.MAX_PIPELINE_RETRIES} attempts: {last_error}"
        ) from last_error

    def _validate_topic_lengths(self, groups: Dict[str, List[int]]) -> None:
        """Validate topic titles produced by the LLM."""
        invalid_topics = [
            topic_name for topic_name in groups if len(topic_name) > self.MAX_TOPIC_LENGTH
        ]
        if invalid_topics:
            raise ParsingError(
                f"Topic names exceed {self.MAX_TOPIC_LENGTH} characters: {invalid_topics!r}"
            )

    def _transform_result(self, result: Any) -> Dict[str, Any]:
        """Convert txt_splitt result to rsstag format.

        rsstag format:
        {
            "sentences": [
                {
                    "number": int, # 1-based index
                    "start": int,
                    "end": int,
                    "read": bool
                }, ...
            ],
            "groups": {
                "Topic Name": [sentence_number, ...],
                ...
            }
        }
        """
        # Transform sentences
        sentences_list = []
        for s in result.sentences:
            sentences_list.append(
                {
                    # Sentences are 0-indexed in txt_splitt result.sentences generally,
                    # but check if .index is available. split_text.py uses s.index.
                    # We map to 1-based index for rsstag "number"
                    "number": s.index + 1,
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "read": False,
                }
            )

        # Transform groups
        groups_dict = {}
        for group in result.groups:
            # Join labels with ' > '
            topic_name = " > ".join(group.label)

            # Collect sentence numbers
            sentence_numbers = []
            for rng in group.ranges:
                # range is inclusive [start, end]
                # Map 0-based indices to 1-based numbers
                # The ranges refer to sentence indices
                for idx in range(rng.start, rng.end + 1):
                    # verify index exists in sentences_list
                    if 0 <= idx < len(sentences_list):
                        # Ensure we match the sentence number
                        sentence_numbers.append(sentences_list[idx]["number"])

            if sentence_numbers:
                if topic_name in groups_dict:
                    groups_dict[topic_name].extend(sentence_numbers)
                else:
                    groups_dict[topic_name] = sentence_numbers

        # Sort and deduplicate numbers in groups
        for topic in groups_dict:
            groups_dict[topic] = sorted(list(set(groups_dict[topic])))

        return {
            "sentences": sentences_list,
            "groups": groups_dict,
        }
