"""Post splitting and LLM interaction logic"""

import logging
import re
import unicodedata
from dataclasses import replace
from typing import Optional, Dict, Any, List, Protocol, Tuple

# Import txt_splitt components
from txt_splitt import Tracer, TracingLLMCallable
from txt_splitt.errors import SplitterError
from txt_splitt.html_cleaners import HTMLParserTagStripCleaner
from txt_splitt.protocols import LLMResponse
from txt_splitt.sentences import (
    AdjacentSameTopicJoiner,
    BatchPipeline,
    BracketMarker,
    LLMRepairingGapHandler,
    MappingOffsetRestorer,
    OptimizingMarker,
    OverlapChunker,
    PreparedDocument,
    RepairingGapHandler,
    SparseRegexSentenceSplitter,
    TopicRangeLLM,
    TopicRangeParser,
    build_pipeline,
)
from txt_splitt.sentences.llm import _build_topic_ranges_prompt
from txt_splitt.sentences.types import PreparedChunk
from txt_splitt.sentences.text_optimizers import normalize_for_llm


class PostSplitterError(Exception):
    """Base exception for PostSplitter errors"""

    pass


class LLMGenerationError(PostSplitterError):
    """Raised when LLM call fails or returns empty/invalid response"""

    pass


class ParsingError(PostSplitterError):
    """Raised when LLM response cannot be parsed correctly"""

    pass


class EmptyGroupingContentError(PostSplitterError):
    """Raised when a prepared request contains no text to classify."""


def _create_html_cleaner() -> HTMLParserTagStripCleaner:
    return HTMLParserTagStripCleaner(strip_tags={"style", "script"})


def _create_sentence_splitter() -> SparseRegexSentenceSplitter:
    return SparseRegexSentenceSplitter(anchor_every_words=5, html_aware=True)


def _has_normalized_content(text: str) -> bool:
    """Ignore punctuation and invisible characters, preserving words and symbols."""
    return any(
        unicodedata.category(char)[0] in {"L", "N", "S"}
        for char in normalize_for_llm(text)
    )


def _has_tagged_content(tagged_text: str) -> bool:
    """Check normalized text without counting sentence markers as content."""
    text: str = re.sub(r"\{\d+\}", "", tagged_text)
    return _has_normalized_content(text)


def _has_grouping_content(text: str) -> bool:
    """Check the same cleaned sentences that the pipeline will mark.

    Keep the original text intact so stored sentence offsets stay valid.
    """
    cleaner: HTMLParserTagStripCleaner = _create_html_cleaner()
    cleaned_text: str = cleaner.clean(text)[0]
    splitter: SparseRegexSentenceSplitter = _create_sentence_splitter()
    return any(
        _has_normalized_content(sentence.text)
        for sentence in splitter.split(cleaned_text)
    )


def _provider_failure(error: BaseException) -> Optional[LLMGenerationError]:
    """Return the provider failure that txt_splitt wrapped into ``error``, if any."""
    current: Optional[BaseException] = error
    while current is not None:
        if isinstance(current, LLMGenerationError):
            return current
        current = current.__cause__
    return None


def build_grouping_text(content: str, title: str = "") -> str:
    """Build the exact text the pipeline consumes.

    Cache keys hash this string, so every caller that needs the key must use
    this helper instead of re-implementing the concatenation.
    """
    if title and _has_grouping_content(title):
        return title + ". " + content
    return content


class ChunkCache(Protocol):
    """Prompt level cache used to skip repeated LLM calls."""

    def get(self, prompt: str, temperature: float) -> Optional[str]: ...

    def set(self, prompt: str, temperature: float, value: str) -> bool: ...


class CachingLLMCallable:
    """Serve repeated prompts from a cache, buffering writes until validation.

    Responses are only committed once the pipeline attempt produced a valid
    result: caching a malformed answer would make every retry replay it and
    lock the post into permanent failure. For the same reason reads are
    disabled on retries, so a retry really re-asks the LLM.
    """

    def __init__(self, inner: Any, cache: Optional[ChunkCache]) -> None:
        self._inner = inner
        self._cache = cache
        self._pending: List[Tuple[str, float, str]] = []
        self._read_enabled: bool = True
        self.hits: int = 0
        self.misses: int = 0

    def start_attempt(self, read_enabled: bool) -> None:
        self._pending = []
        self._read_enabled = read_enabled

    def call(self, prompt: str, temperature: float) -> str:
        if self._cache is not None and self._read_enabled:
            cached: Optional[str] = self._cache.get(prompt, temperature)
            if cached:
                self.hits += 1
                return cached

        response: str = self._inner.call(prompt, temperature)
        self.misses += 1
        if self._cache is not None and response:
            self._pending.append((prompt, temperature, response))
        return response

    def commit(self) -> None:
        if self._cache is None:
            self._pending = []
            return
        for prompt, temperature, response in self._pending:
            self._cache.set(prompt, temperature, response)
        self._pending = []


class LLMHandlerAdapter:
    """Adapter to make rsstag LLM handler compatible with txt_splitt LLMCallable protocol."""

    def __init__(self, handler: Any) -> None:
        self._handler = handler

    def call(self, prompt: str, temperature: float) -> str:
        """Call the underlying LLM handler."""
        content_match: Optional[re.Match[str]] = re.search(
            r"<content>(.*?)</content>", prompt, flags=re.DOTALL
        )
        if content_match is not None and not _has_tagged_content(content_match.group(1)):
            raise EmptyGroupingContentError("Grouping request has no content")
        gap_match: Optional[re.Match[str]] = re.search(
            r"<GAP>(.*?)</GAP>", prompt, flags=re.DOTALL
        )
        if (
            content_match is None
            and gap_match is not None
            and not _has_tagged_content(gap_match.group(1))
        ):
            # Gap repair offers two neighboring topics. Attach filler to the
            # previous topic without spending a provider call or dropping the post.
            return "PREVIOUS"
        # rsstag handlers might not support temperature or have different signature
        # We assume .call(prompt, temperature=...) compatibility based on previous usage
        # Previous usage: self._llm_handler.call([prompt], temperature=temperature)
        # Note: rsstag handler apparently expects a list of prompts?
        try:
            response: str = self._handler.call([prompt], temperature=temperature)
        except Exception as e:
            raise LLMGenerationError(f"LLM call failed: {e}") from e
        # Legacy provider wrappers return failures as strings rather than raise.
        # Do not let those become parse errors charged against the post.
        if not response or response.startswith(
            ("Cerebras error ", "OpenAI error ", "Anthropic error ", "GroqCom error ", "LLamaCPP error ")
        ) or re.match(r"^[45]\d{2} - ", response):
            raise LLMGenerationError("LLM call failed or returned an empty response")
        return response


class PostSplitter:
    """Handles text splitting using txt_splitt pipeline"""

    MAX_TOPIC_LENGTH = 500
    MAX_PIPELINE_RETRIES = 3

    def __init__(
        self,
        llm_handler: Optional[Any] = None,
        chunk_cache: Optional[ChunkCache] = None,
    ) -> None:
        self._log = logging.getLogger("post_splitter")
        self._llm_handler = llm_handler
        self._chunk_cache = chunk_cache

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
        text: str = build_grouping_text(content, title)

        if not _has_grouping_content(text):
            self._log.info("Skipping post grouping: no content after cleaning and splitting")
            return None

        if not self._llm_handler:
            self._log.error("LLM handler not configured")
            raise LLMGenerationError("LLM handler not configured")

        # Create adapter once and retry whole pipeline execution on invalid topic output.
        llm_adapter = CachingLLMCallable(
            LLMHandlerAdapter(self._llm_handler), self._chunk_cache
        )
        base_tracer = tracer
        last_error: Optional[Exception] = None

        for attempt in range(1, self.MAX_PIPELINE_RETRIES + 1):
            attempt_tracer = base_tracer if attempt == 1 and base_tracer is not None else Tracer()
            # Only the first attempt may reuse cached answers: a retry means the
            # previous response was unusable, so it must reach the LLM again.
            llm_adapter.start_attempt(read_enabled=attempt == 1)

            try:
                # Initialize the pipeline components
                # We use settings similar to the reference split_text.py
                splitter: SparseRegexSentenceSplitter = _create_sentence_splitter()

                # Using OverlapChunker as in example
                chunker = OverlapChunker(max_chars=84000)

                # Set up tracing
                llm_callable = TracingLLMCallable(llm_adapter, attempt_tracer)

                topic_range_llm = TopicRangeLLM(
                    client=llm_callable,
                    temperature=0.0,
                    chunker=chunker,
                )

                html_cleaner: HTMLParserTagStripCleaner = _create_html_cleaner()
                offset_restorer = MappingOffsetRestorer()

                # Create the pipeline
                pipeline = build_pipeline(
                    splitter=splitter,
                    marker=OptimizingMarker(BracketMarker()),
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

                result = self._run_pipeline_session(pipeline, text, llm_callable)
                transformed = self._transform_result(result)
                self._validate_topic_lengths(transformed.get("groups", {}))
                llm_adapter.commit()
                self._log.info(
                    "Pipeline trace for attempt %s:\n%s",
                    attempt,
                    attempt_tracer.format(),
                )
                return transformed

            except EmptyGroupingContentError:
                self._log.warning("Skipping post grouping: prepared request has no content")
                return None
            except LLMGenerationError:
                # Infrastructure failures use the queue's delayed retry path.
                raise
            except Exception as e:
                provider_error: Optional[LLMGenerationError] = _provider_failure(e)
                if provider_error is not None:
                    raise provider_error
                last_error = e
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

        # txt_splitt errors mean this post's text or LLM output is unusable;
        # report them as ParsingError so the worker charges the post, not the scan.
        if isinstance(last_error, (ParsingError, SplitterError)):
            raise ParsingError(
                f"Invalid LLM output after {self.MAX_PIPELINE_RETRIES} attempts: {last_error}"
            ) from last_error

        raise PostSplitterError(
            f"Pipeline execution failed after {self.MAX_PIPELINE_RETRIES} attempts: {last_error}"
        ) from last_error

    def _run_pipeline_session(
        self, pipeline: Any, text: str, llm_callable: TracingLLMCallable
    ) -> Any:
        """Drive txt_splitt pipelines that emit deferred LLM request batches."""
        if not hasattr(pipeline, "start"):
            return pipeline.run(text)

        session: Any = pipeline.start(text)
        while not session.is_complete():
            requests: tuple[Any, ...] = session.pending_requests()
            if not requests:
                raise PostSplitterError(
                    "Pipeline session is incomplete but has no pending requests"
                )

            responses: List[LLMResponse] = []
            for request in requests:
                response: str = llm_callable.call(
                    request.prompt,
                    temperature=request.temperature,
                )
                responses.append(LLMResponse(content=response))
            session.submit_responses(responses)

        return session.result()

    def _create_batch_pipeline(self) -> BatchPipeline:
        """Create a BatchPipeline configured the same as the regular pipeline."""
        html_cleaner: HTMLParserTagStripCleaner = _create_html_cleaner()
        offset_restorer = MappingOffsetRestorer()
        return BatchPipeline(
            splitter=_create_sentence_splitter(),
            marker=OptimizingMarker(BracketMarker()),
            parser=TopicRangeParser(),
            gap_handler=RepairingGapHandler(),
            chunker=OverlapChunker(max_chars=84000),
            joiner=AdjacentSameTopicJoiner(),
            html_cleaner=html_cleaner,
            offset_restorer=offset_restorer,
        )

    def prepare_for_batch(
        self, content: str, title: str = "", is_html: bool = True
    ) -> Optional[PreparedDocument]:
        """Prepare text for external batch LLM processing.

        Returns a PreparedDocument whose .chunks contain tagged_text for LLM prompts,
        omitting content-free chunks, or None if no usable content remains.
        """
        text: str = build_grouping_text(content, title)

        if not text.strip():
            return None

        batch_pipeline: BatchPipeline = self._create_batch_pipeline()
        prepared: PreparedDocument = batch_pipeline.prepare(text)
        chunks: Tuple[PreparedChunk, ...] = tuple(
            chunk for chunk in prepared.chunks if _has_tagged_content(chunk.tagged_text)
        )
        if not prepared.sentences or not chunks:
            self._log.info("Skipping batch grouping: no content after cleaning and splitting")
            return None
        # Preserve sentence indices and offsets for finalization and chunk IDs
        # for matching provider responses. Only omit content-free requests.
        return replace(prepared, chunks=chunks)

    def build_batch_prompt(self, tagged_text: str) -> str:
        """Build the LLM prompt for a single prepared chunk's tagged text."""
        if not _has_tagged_content(tagged_text):
            raise EmptyGroupingContentError("Batch grouping request has no content")
        return _build_topic_ranges_prompt(tagged_text)

    def finalize_batch(
        self, prepared: PreparedDocument, merged_response: str
    ) -> Optional[Dict[str, Any]]:
        """Finalize batch LLM results for a prepared document.

        Args:
            prepared: The PreparedDocument from prepare_for_batch().
            merged_response: LLM responses for all chunks joined with newlines.

        Returns:
            rsstag-format dict with "sentences" and "groups", or None on error.
        """
        try:
            batch_pipeline = self._create_batch_pipeline()
            result = batch_pipeline.finalize(prepared, merged_response)
            transformed = self._transform_result(result)
            self._validate_topic_lengths(transformed.get("groups", {}))
            return transformed
        except Exception as e:
            self._log.error("BatchPipeline.finalize failed: %s", e)
            return None

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
