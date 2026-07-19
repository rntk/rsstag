import gzip
import hashlib
import unittest
from typing import Any, Mapping, Sequence

from rsstag_lite.grouping import (
    GroupingService,
    html_to_text,
    split_sentences,
    validate_groups,
)
from rsstag_lite.repository import post_ids_hash


class _FakeRepository:
    def __init__(self) -> None:
        self.saved: dict[str, Any] = {}
        self.released: list[tuple[str, str, str]] = []

    def save_grouping(
        self,
        owner: str,
        post_id: str,
        sentences: Sequence[Mapping[str, Any]],
        groups: Mapping[str, Sequence[int]],
        claim_token: str,
    ) -> None:
        self.saved = {
            "owner": owner,
            "post_id": post_id,
            "sentences": list(sentences),
            "groups": dict(groups),
        }

    def release_post(
        self, owner: str, post_id: str, claim_token: str, error: str = ""
    ) -> None:
        self.released.append((owner, post_id, error))


class _FakeGrouper:
    def group(
        self, title: str, sentences: Sequence[Mapping[str, Any]]
    ) -> dict[str, list[int]]:
        return {"News > Telegram": [int(sentence["number"]) for sentence in sentences]}


class TestLiteGrouping(unittest.TestCase):
    def test_html_cleaning_and_sentence_split(self) -> None:
        text: str = html_to_text("<p>Hello world.</p><script>bad()</script><p>Next item!</p>")
        sentences: list[dict[str, Any]] = split_sentences(text)

        self.assertEqual([item["text"] for item in sentences], ["Hello world.", "Next item!"])
        self.assertEqual([item["number"] for item in sentences], [1, 2])

    def test_group_validation_rejects_missing_sentences(self) -> None:
        sentences: list[dict[str, Any]] = split_sentences("One. Two.")

        with self.assertRaisesRegex(ValueError, "omitted"):
            validate_groups({"Only one": [1]}, sentences)

    def test_grouping_service_persists_legacy_shape(self) -> None:
        repository: _FakeRepository = _FakeRepository()
        service: GroupingService = GroupingService(repository, _FakeGrouper())  # type: ignore[arg-type]
        post: dict[str, Any] = {
            "pid": "post-1",
            "grouping_claim": "claim-1",
            "content": {
                "title": "A title",
                "content": gzip.compress(b"First sentence. Second sentence."),
            },
        }

        service.process_post("owner", post)

        self.assertEqual(repository.saved["post_id"], "post-1")
        self.assertEqual(repository.saved["groups"], {"News > Telegram": [1, 2, 3]})
        self.assertEqual(repository.released, [])

    def test_hash_matches_legacy_md5(self) -> None:
        expected: str = hashlib.md5(b"1,2,3", usedforsecurity=False).hexdigest()
        self.assertEqual(post_ids_hash([3, "1", 2]), expected)


if __name__ == "__main__":
    unittest.main()
