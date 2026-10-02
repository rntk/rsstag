"""Empty grouping content must never reach an LLM provider."""

import unittest
from dataclasses import replace
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch

from rsstag.post_splitter import (
    EmptyGroupingContentError,
    LLMHandlerAdapter,
    PostSplitter,
    build_grouping_text,
)
from txt_splitt.sentences import PreparedDocument
from txt_splitt.sentences.gap_handlers import _build_gap_prompt
from txt_splitt.sentences.types import PreparedChunk


class TestPostSplitterEmptyContent(unittest.TestCase):
    def test_empty_documents_are_skipped_in_regular_and_batch_paths(self) -> None:
        contents: List[str] = [
            "",
            " \t\n\u00a0",
            '<div><img src="image.jpg"><br></div>',
            "<!-- hidden text -->",
            "<script>hidden text</script><style>hidden text</style>",
            "<script>unclosed hidden text",
            "<p>&nbsp;&#160;&amp;nbsp;&#x200b;</p>",
            "\u200b\u200d\ufeff",
            "... !!!",
        ]
        for content in contents:
            for title in ("", " \t", "<span></span>", "... !!!"):
                with self.subTest(content=content, title=title):
                    handler: Mock = Mock()
                    splitter: PostSplitter = PostSplitter(handler)
                    self.assertIsNone(splitter.generate_grouped_data(content, title))
                    self.assertIsNone(splitter.prepare_for_batch(content, title))
                    handler.call.assert_not_called()

    def test_title_only_document_still_reaches_llm(self) -> None:
        handler: Mock = Mock()
        handler.call.return_value = "Technology>Testing: 0"
        splitter: PostSplitter = PostSplitter(handler)
        result: Optional[Dict[str, Any]] = splitter.generate_grouped_data(
            '<img src="image.jpg">', "Useful title"
        )
        self.assertIsNotNone(result)
        handler.call.assert_called_once()
        self.assertIn("Useful title", handler.call.call_args.args[0][0])
        self.assertIsNotNone(splitter.prepare_for_batch("", "Useful title"))

    def test_cleaning_preserves_original_offsets(self) -> None:
        content: str = "  <p>Useful body text.</p>  "
        handler: Mock = Mock()
        handler.call.return_value = "Technology>Testing: 0"
        splitter: PostSplitter = PostSplitter(handler)
        result: Optional[Dict[str, Any]] = splitter.generate_grouped_data(content)
        self.assertIsNotNone(result)
        assert result is not None
        sentence: Dict[str, Any] = result["sentences"][0]
        self.assertIn("Useful body text.", content[sentence["start"]:sentence["end"]])

    def test_request_boundary_rejects_empty_and_marker_only_content(self) -> None:
        contents: List[str] = [
            "", " \n\t", "{0} &nbsp;\n{1} \u200b", "{0} ... !!!", "{0} 。！？"
        ]
        for content in contents:
            with self.subTest(content=content):
                handler: Mock = Mock()
                adapter: LLMHandlerAdapter = LLMHandlerAdapter(handler)
                with self.assertRaises(EmptyGroupingContentError):
                    adapter.call(
                        f"Instructions\n<content>\n{content}\n</content>\nTrailing instructions",
                        0.0,
                    )
                handler.call.assert_not_called()
                with self.assertRaises(EmptyGroupingContentError):
                    PostSplitter().build_batch_prompt(content)

    def test_junk_titles_do_not_change_body_or_cache_text(self) -> None:
        content: str = "Useful body text."
        for title in (" \t", "<span></span>", "... !!!", "<script>hidden</script>"):
            with self.subTest(title=title):
                self.assertEqual(build_grouping_text(content, title), content)
        self.assertEqual(build_grouping_text(content, "Useful title"), "Useful title. " + content)

    def test_symbols_numbers_and_non_latin_text_remain_content(self) -> None:
        splitter: PostSplitter = PostSplitter()
        for content in ("😀", "42", "中文", "Привет", "こんにちは", "∑"):
            with self.subTest(content=content):
                prepared: Optional[PreparedDocument] = splitter.prepare_for_batch(content)
                self.assertIsNotNone(prepared)
                assert prepared is not None
                self.assertIn(content, splitter.build_batch_prompt(prepared.chunks[0].tagged_text))

    def test_empty_gap_is_repaired_without_provider_call(self) -> None:
        handler: Mock = Mock()
        adapter: LLMHandlerAdapter = LLMHandlerAdapter(handler)
        for text in ("", "... !!!", "&nbsp;\u200b"):
            with self.subTest(text=text):
                prompt: str = _build_gap_prompt(
                    sentence_text=text,
                    prev_label=("Technology",),
                    prev_context=["Useful previous text."],
                    next_label=("Science",),
                    next_context=["Useful next text."],
                )
                self.assertEqual(adapter.call(prompt, 0.0), "PREVIOUS")
        handler.call.assert_not_called()

    def test_nonempty_gap_reaches_provider(self) -> None:
        handler: Mock = Mock()
        handler.call.return_value = "NEXT"
        prompt: str = _build_gap_prompt(
            sentence_text="Useful gap text.",
            prev_label=("Technology",), prev_context=[],
            next_label=("Science",), next_context=[],
        )
        self.assertEqual(LLMHandlerAdapter(handler).call(prompt, 0.0), "NEXT")
        handler.call.assert_called_once_with([prompt], temperature=0.0)

    def test_batch_filters_empty_chunks_and_preserves_finalization_state(self) -> None:
        splitter: PostSplitter = PostSplitter()
        prepared: Optional[PreparedDocument] = splitter.prepare_for_batch("Useful body text.")
        assert prepared is not None
        good_chunk: PreparedChunk = replace(prepared.chunks[0], chunk_id=7)
        empty_chunk: PreparedChunk = replace(good_chunk, chunk_id=6, tagged_text="{0} ... !!!")
        mixed: PreparedDocument = replace(prepared, chunks=(empty_chunk, good_chunk))
        pipeline: Mock = Mock()
        pipeline.prepare.return_value = mixed
        with patch.object(splitter, "_create_batch_pipeline", return_value=pipeline):
            result: Optional[PreparedDocument] = splitter.prepare_for_batch("Useful body text.")
        assert result is not None
        self.assertEqual(result.chunks, (good_chunk,))
        self.assertIs(result.sentences, mixed.sentences)
        self.assertIs(result.offset_mapping, mixed.offset_mapping)
        self.assertEqual(result.original_text, mixed.original_text)
        splitter.build_batch_prompt(result.chunks[0].tagged_text)
        self.assertEqual(
            splitter.finalize_batch(result, "Technology>Testing: 0"),
            splitter.finalize_batch(prepared, "Technology>Testing: 0"),
        )
        pipeline.prepare.return_value = replace(prepared, chunks=(empty_chunk,))
        with patch.object(splitter, "_create_batch_pipeline", return_value=pipeline):
            self.assertIsNone(splitter.prepare_for_batch("Useful body text."))

    def test_empty_request_does_not_retry_or_read_provider(self) -> None:
        handler: Mock = Mock()
        splitter: PostSplitter = PostSplitter(handler)
        with patch.object(
            splitter, "_run_pipeline_session", side_effect=EmptyGroupingContentError
        ) as run_pipeline:
            self.assertIsNone(splitter.generate_grouped_data("Useful body text."))
        run_pipeline.assert_called_once()
        handler.call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
