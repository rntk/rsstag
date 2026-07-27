import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from rsstag.read_state import ReadStateService
from rsstag.tasks import TASK_MARK, TASK_MARK_TELEGRAM, TASK_NOT_IN_PROCESSING


class TestReadStateServiceNormalizeIndices(unittest.TestCase):
    def test_empty_list(self):
        result = ReadStateService._normalize_indices([])
        self.assertEqual(result, [])

    def test_single_int(self):
        result = ReadStateService._normalize_indices([1, 2, 3])
        self.assertEqual(result, [1, 2, 3])

    def test_string_numbers(self):
        result = ReadStateService._normalize_indices(["1", "2", "3"])
        self.assertEqual(result, [1, 2, 3])

    def test_mixed_types(self):
        result = ReadStateService._normalize_indices([1, "2", 3.0])
        self.assertEqual(result, [1, 2, 3])

    def test_invalid_values_skipped(self):
        result = ReadStateService._normalize_indices([1, "abc", None, "3"])
        self.assertEqual(result, [1, 3])

    def test_non_list_input(self):
        result = ReadStateService._normalize_indices("not a list")
        self.assertEqual(result, [])

    def test_none_input(self):
        result = ReadStateService._normalize_indices(None)
        self.assertEqual(result, [])

    def test_negative_numbers(self):
        result = ReadStateService._normalize_indices([-1, -5])
        self.assertEqual(result, [-1, -5])

    def test_float_string(self):
        # Float strings cannot be converted directly by int(), so they are skipped
        result = ReadStateService._normalize_indices(["1.5"])
        self.assertEqual(result, [])


class TestReadStateServiceCollectCounters(unittest.TestCase):
    def test_empty_post(self):
        result = ReadStateService._collect_counters({})
        self.assertEqual(result, ({}, {}, {}))

    def test_post_with_tags(self):
        post = {"tags": ["apple", "banana"]}
        tags, bi_grams, letters = ReadStateService._collect_counters(post)
        self.assertEqual(tags, {"apple": 1, "banana": 1})
        self.assertEqual(letters, {"a": 1, "b": 1})

    def test_post_with_duplicate_tags(self):
        post = {"tags": ["apple", "apple"]}
        tags, bi_grams, letters = ReadStateService._collect_counters(post)
        self.assertEqual(tags, {"apple": 2})
        self.assertEqual(letters, {"a": 2})

    def test_post_with_bi_grams(self):
        post = {"tags": [], "bi_grams": ["apple banana", "banana cherry"]}
        tags, bi_grams, letters = ReadStateService._collect_counters(post)
        self.assertEqual(bi_grams, {"apple banana": 1, "banana cherry": 1})

    def test_post_with_mixed_content(self):
        post = {"tags": ["apple"], "bi_grams": ["apple banana"]}
        tags, bi_grams, letters = ReadStateService._collect_counters(post)
        self.assertEqual(tags, {"apple": 1})
        self.assertEqual(bi_grams, {"apple banana": 1})
        self.assertEqual(letters, {"a": 1})

    def test_empty_string_tags_skipped(self):
        post = {"tags": ["apple", "", "banana"]}
        tags, _, _ = ReadStateService._collect_counters(post)
        self.assertEqual(tags, {"apple": 1, "banana": 1})

    def test_empty_string_bi_grams_skipped(self):
        post = {"bi_grams": ["a b", "", "c d"]}
        _, bi_grams, _ = ReadStateService._collect_counters(post)
        self.assertEqual(bi_grams, {"a b": 1, "c d": 1})

    def test_tag_to_string_conversion(self):
        post = {"tags": [123, "abc"]}
        tags, _, _ = ReadStateService._collect_counters(post)
        self.assertEqual(tags, {"123": 1, "abc": 1})


class TestReadStateServiceMarkSentences(unittest.TestCase):
    """The provider is only told about a post once it has no unread sentence."""

    owner: str = "user-1"
    post_id: str = "pid-1"

    def setUp(self) -> None:
        self.posts: MagicMock = MagicMock()
        self.tags: MagicMock = MagicMock()
        self.bi_grams: MagicMock = MagicMock()
        self.letters: MagicMock = MagicMock()
        self.tasks: MagicMock = MagicMock()
        self.post_grouping: MagicMock = MagicMock()

        self.posts.change_status.return_value = True
        self.tags.change_unread.return_value = True
        self.bi_grams.change_unread.return_value = True
        self.tasks.add_task.return_value = True

        self.service: ReadStateService = ReadStateService(
            self.posts,
            self.tags,
            self.bi_grams,
            self.letters,
            self.tasks,
            self.post_grouping,
        )

    def _set_post(
        self, read: bool = False, provider: Optional[str] = "bazqux"
    ) -> Dict[str, Any]:
        post: Dict[str, Any] = {
            "pid": self.post_id,
            "id": "provider-id-1",
            "read": read,
            "tags": ["tag1"],
            "bi_grams": ["tag1 tag2"],
        }
        if provider is not None:
            post["provider"] = provider
        self.posts.get_by_pid.return_value = post
        return post

    def _mark(
        self, sentence_indices: List[int], readed: bool, provider: str = "bazqux"
    ) -> Dict[str, Any]:
        return self.service.mark_sentences(
            self.owner,
            provider,
            [{"post_id": self.post_id, "sentence_indices": sentence_indices}],
            readed,
        )

    def _queued_tasks(self) -> List[Dict[str, Any]]:
        return [call.args[0] for call in self.tasks.add_task.call_args_list]

    def test_partial_read_does_not_reach_provider(self) -> None:
        """Sentences left unread: grouping is updated, provider is not called."""
        self.post_grouping.update_snippets_read_status.return_value = False
        self._set_post(read=False)

        result: Dict[str, Any] = self._mark([0, 1], True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["changed_posts"], [])
        self.tasks.add_task.assert_not_called()
        self.posts.change_status.assert_not_called()

    def test_partial_read_still_persists_sentences(self) -> None:
        self.post_grouping.update_snippets_read_status.return_value = False
        self._set_post(read=False)

        self._mark([2, 0], True)

        self.post_grouping.update_snippets_read_status.assert_called_once_with(
            self.owner, self.post_id, [0, 2], True
        )

    def test_last_unread_sentence_marks_post_and_queues_task(self) -> None:
        self.post_grouping.update_snippets_read_status.return_value = True
        self._set_post(read=False)

        result: Dict[str, Any] = self._mark([2], True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["changed_posts"], [self.post_id])
        self.posts.change_status.assert_called_once_with(self.owner, [self.post_id], True)

        queued: List[Dict[str, Any]] = self._queued_tasks()
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["type"], TASK_MARK)
        self.assertEqual(queued[0]["user"], self.owner)
        self.assertEqual(
            queued[0]["data"],
            [
                {
                    "user": self.owner,
                    "id": "provider-id-1",
                    "status": True,
                    "processing": TASK_NOT_IN_PROCESSING,
                    "type": TASK_MARK,
                    "provider": "bazqux",
                }
            ],
        )

    def test_no_task_when_post_is_already_read(self) -> None:
        self.post_grouping.update_snippets_read_status.return_value = True
        self._set_post(read=True)

        result: Dict[str, Any] = self._mark([2], True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["changed_posts"], [])
        self.tasks.add_task.assert_not_called()

    def test_unmarking_a_sentence_reopens_the_post(self) -> None:
        self.post_grouping.update_snippets_read_status.return_value = False
        self._set_post(read=True)

        result: Dict[str, Any] = self._mark([0], False)

        self.assertEqual(result["changed_posts"], [self.post_id])
        self.posts.change_status.assert_called_once_with(self.owner, [self.post_id], False)
        self.assertFalse(self._queued_tasks()[0]["data"][0]["status"])

    def test_unmarking_an_already_unread_post_queues_nothing(self) -> None:
        self.post_grouping.update_snippets_read_status.return_value = False
        self._set_post(read=False)

        self._mark([0], False)

        self.tasks.add_task.assert_not_called()

    def test_unmatched_sentence_numbers_skip_the_post(self) -> None:
        """No sentence changed, so the post's read state must not move."""
        self.post_grouping.update_snippets_read_status.return_value = None
        self._set_post(read=True)

        result: Dict[str, Any] = self._mark([99], False)

        self.assertEqual(result["skipped_posts"], [self.post_id])
        self.assertEqual(result["changed_posts"], [])
        self.tasks.add_task.assert_not_called()
        self.posts.change_status.assert_not_called()

    def test_missing_post_is_skipped(self) -> None:
        self.post_grouping.update_snippets_read_status.return_value = True
        self.posts.get_by_pid.return_value = None

        result: Dict[str, Any] = self._mark([0], True)

        self.assertEqual(result["skipped_posts"], [self.post_id])
        self.tasks.add_task.assert_not_called()

    def test_post_provider_wins_over_session_provider(self) -> None:
        self.post_grouping.update_snippets_read_status.return_value = True
        self._set_post(read=False, provider="gmail")

        self._mark([0], True, provider="bazqux")

        self.assertEqual(self._queued_tasks()[0]["data"][0]["provider"], "gmail")

    def test_session_provider_used_when_post_has_none(self) -> None:
        self.post_grouping.update_snippets_read_status.return_value = True
        self._set_post(read=False, provider=None)

        self._mark([0], True, provider="bazqux")

        self.assertEqual(self._queued_tasks()[0]["data"][0]["provider"], "bazqux")

    def test_telegram_sentences_never_queue_a_full_sync(self) -> None:
        """Telegram syncs through the manual TASK_MARK_TELEGRAM task only."""
        self.post_grouping.update_snippets_read_status.return_value = True
        self._set_post(read=False, provider="telegram")

        self._mark([0], True, provider="telegram")

        queued_types: List[int] = [task["type"] for task in self._queued_tasks()]
        self.assertEqual(queued_types, [TASK_MARK])
        self.assertNotIn(TASK_MARK_TELEGRAM, queued_types)

    def test_failed_enqueue_reports_error(self) -> None:
        self.post_grouping.update_snippets_read_status.return_value = True
        self._set_post(read=False)
        self.tasks.add_task.return_value = False

        result: Dict[str, Any] = self._mark([0], True)

        self.assertFalse(result["ok"])
        self.posts.change_status.assert_not_called()


if __name__ == "__main__":
    unittest.main()
