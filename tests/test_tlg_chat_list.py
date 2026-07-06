"""Tests for TelegramProvider.__get_all_chat_ids snapshot behavior."""

from typing import Any, Dict, List, Optional

from rsstag.providers.telegram import TelegramProvider
from telegram.client import Result


def _make_provider() -> TelegramProvider:
    config: Dict[str, Any] = {"settings": {"no_category_name": "NotCategorized"}}
    return TelegramProvider(config, None)


class _FakeRepeater:
    """Answers load_chats with a terminal 404 and get_chats from a script.

    ``responses`` maps requested limit -> chat_ids list to return, emulating
    TDLib snapshots at different limits.
    """

    def __init__(self, responses: Dict[int, List[int]]):
        self.responses = responses
        self.requested_limits: List[int] = []

    def __call__(self, query: Dict[str, Any]) -> Result:
        if query["@type"] == "loadChats":
            return Result(None, {"@type": "error", "code": 404, "message": "done"})
        assert query["@type"] == "getChats"
        limit = query["limit"]
        self.requested_limits.append(limit)
        chat_ids: Optional[List[int]] = self.responses.get(limit)
        if chat_ids is None:
            return Result(None, {"@type": "error", "code": 400, "message": "bad"})
        return Result({"@type": "chats", "chat_ids": chat_ids}, None)


def _patch(provider: TelegramProvider, repeater: _FakeRepeater) -> None:
    provider._TelegramProvider__requests_repeater = repeater  # type: ignore[attr-defined]


def _get_all_chat_ids(provider: TelegramProvider, **kwargs: Any) -> List[int]:
    return provider._TelegramProvider__get_all_chat_ids(**kwargs)  # type: ignore[attr-defined]


def test_snapshot_below_limit_returned_once() -> None:
    provider = _make_provider()
    repeater = _FakeRepeater({1000: [1, 2, 3]})
    _patch(provider, repeater)
    assert _get_all_chat_ids(provider) == [1, 2, 3]
    assert repeater.requested_limits == [1000]


def test_snapshot_filling_limit_retries_with_larger_limit() -> None:
    provider = _make_provider()
    full_page = list(range(1, 5))
    all_chats = list(range(1, 7))
    repeater = _FakeRepeater({4: full_page, 8: all_chats})
    _patch(provider, repeater)
    assert _get_all_chat_ids(provider, initial_limit=4) == all_chats
    assert repeater.requested_limits == [4, 8]


def test_duplicate_ids_are_removed_preserving_order() -> None:
    provider = _make_provider()
    repeater = _FakeRepeater({1000: [5, 3, 5, 7, 3]})
    _patch(provider, repeater)
    assert _get_all_chat_ids(provider) == [5, 3, 7]


def test_error_response_returns_empty_list() -> None:
    provider = _make_provider()
    repeater = _FakeRepeater({})
    _patch(provider, repeater)
    assert _get_all_chat_ids(provider) == []
