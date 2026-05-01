"""Shared read/unread state mutation helpers."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Iterable, Mapping

from rsstag.tasks import TASK_MARK, TASK_NOT_IN_PROCESSING


class ReadStateService:
    """Apply read/unread updates across grouped sentences and derived counters."""

    def __init__(
        self,
        posts: Any,
        tags: Any,
        bi_grams: Any,
        letters: Any,
        tasks: Any,
        post_grouping: Any,
    ) -> None:
        self._posts: Any = posts
        self._tags: Any = tags
        self._bi_grams: Any = bi_grams
        self._letters: Any = letters
        self._tasks: Any = tasks
        self._post_grouping: Any = post_grouping
        self._log = logging.getLogger("read_state")

    def mark_sentences(
        self,
        owner: str,
        provider: str,
        selections: Iterable[Mapping[str, Any]],
        readed: bool,
    ) -> dict[str, Any]:
        """Mark grouped sentences read/unread and roll post state up when needed."""

        by_post: dict[str, list[int]] = defaultdict(list)
        for selection in selections:
            post_id = str(selection.get("post_id", "")).strip()
            if not post_id:
                continue
            sentence_indices = self._normalize_indices(selection.get("sentence_indices", []))
            if sentence_indices:
                by_post[post_id].extend(sentence_indices)

        changed_posts: list[str] = []
        skipped_posts: list[str] = []
        for post_id, sentence_indices in by_post.items():
            all_read = self._post_grouping.update_snippets_read_status(
                owner,
                post_id,
                sorted(set(sentence_indices)),
                readed,
            )
            if all_read is None:
                skipped_posts.append(post_id)
                continue

            post = self._posts.get_by_pid(
                owner,
                post_id,
                {"pid": True, "read": True, "id": True, "tags": True, "bi_grams": True},
            )
            if not post:
                skipped_posts.append(post_id)
                continue

            should_change_post = False
            if not readed:
                should_change_post = bool(post.get("read"))
            elif all_read and not post.get("read"):
                should_change_post = True

            if not should_change_post:
                continue

            task_payload = [
                {
                    "user": owner,
                    "id": post["id"],
                    "status": readed,
                    "processing": TASK_NOT_IN_PROCESSING,
                    "type": TASK_MARK,
                    "provider": provider,
                }
            ]
            if not self._tasks.add_task(
                {"type": TASK_MARK, "user": owner, "data": task_payload}
            ):
                self._log.warning(
                    "Failed to enqueue mark task for owner=%s post_id=%s",
                    owner,
                    post_id,
                )
                return {"ok": False, "error": "Failed to queue mark task"}

            changed = self._posts.change_status(owner, [post_id], readed)
            tags, bi_grams, letters = self._collect_counters(post)
            if changed and tags:
                changed = self._tags.change_unread(owner, tags, readed)
            if changed and bi_grams:
                changed = self._bi_grams.change_unread(owner, bi_grams, readed)
            if changed and letters:
                self._letters.change_unread(owner, letters, readed)

            if not changed:
                return {"ok": False, "error": "Database error"}
            changed_posts.append(post_id)

        return {"ok": True, "changed_posts": changed_posts, "skipped_posts": skipped_posts}

    @staticmethod
    def _normalize_indices(values: Any) -> list[int]:
        indices: list[int] = []
        if not isinstance(values, list):
            return indices
        for value in values:
            try:
                indices.append(int(value))
            except (TypeError, ValueError):
                continue
        return indices

    @staticmethod
    def _collect_counters(post: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
        tags: dict[str, int] = defaultdict(int)
        bi_grams: dict[str, int] = defaultdict(int)
        letters: dict[str, int] = defaultdict(int)

        for tag in post.get("tags", []):
            if not tag:
                continue
            normalized_tag = str(tag)
            tags[normalized_tag] += 1
            letters[normalized_tag[0]] += 1
        for bi_gram in post.get("bi_grams", []):
            if not bi_gram:
                continue
            bi_grams[str(bi_gram)] += 1

        return dict(tags), dict(bi_grams), dict(letters)
