from typing import Dict
from unittest.mock import MagicMock

import pytest

from rsstag.workers.provider_worker import ProviderWorker


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_users() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_providers() -> Dict[str, MagicMock]:
    return {"test_provider": MagicMock()}


@pytest.fixture
def record_bulk_write() -> MagicMock:
    return MagicMock()


@pytest.fixture
def worker(
    mock_db: MagicMock,
    mock_users: MagicMock,
    mock_providers: Dict[str, MagicMock],
    record_bulk_write: MagicMock,
) -> ProviderWorker:
    return ProviderWorker(
        db=mock_db,
        config={"gmail": {"client_id": "id", "client_secret": "secret"}},
        providers=mock_providers,
        users=mock_users,
        tasks=MagicMock(),
        record_bulk_write=record_bulk_write,
    )


def test_handle_download_deduplicates_by_pid(
    worker: ProviderWorker,
    mock_db: MagicMock,
    mock_users: MagicMock,
    mock_providers: Dict[str, MagicMock],
    record_bulk_write: MagicMock,
) -> None:
    # Task setup
    task: Dict[str, object] = {
        "user": {"sid": "user123"},
        "data": {"provider": "test_provider"},
    }
    mock_users.get_provider_user.return_value = {"token": "abc"}

    # Telegram message IDs may repeat across feeds; only PID is globally stable.
    p1: Dict[str, str] = {
        "id": "msg1",
        "pid": "telegram:feed-1:msg1",
        "content": "original",
    }
    p1_dup: Dict[str, str] = {
        "id": "msg1",
        "pid": "telegram:feed-1:msg1",
        "content": "duplicate",
    }
    p2: Dict[str, str] = {
        "id": "msg1",
        "pid": "telegram:feed-2:msg1",
        "content": "new",
    }

    provider: MagicMock = mock_providers["test_provider"]
    provider.download.return_value = [([p1, p1_dup, p2], [])]

    mock_db.posts.find.return_value = [{"pid": "telegram:feed-1:msg1"}]

    # Execute
    assert worker.handle_download(task) is True

    # Verify DB query
    mock_db.posts.find.assert_called_once()
    query: Dict[str, object] = mock_db.posts.find.call_args[0][0]
    assert query["owner"] == "user123"
    assert set(query["pid"]["$in"]) == {
        "telegram:feed-1:msg1",
        "telegram:feed-2:msg1",
    }
    assert "provider" not in query

    # The same raw ID from a different feed must still be inserted.
    mock_db.posts.insert_many.assert_called_once()
    inserted_posts: list[Dict[str, str]] = mock_db.posts.insert_many.call_args[0][0]
    assert len(inserted_posts) == 1
    assert inserted_posts[0]["pid"] == "telegram:feed-2:msg1"
    assert inserted_posts[0]["provider"] == "test_provider"

    record_bulk_write.assert_called_with("posts", 1)
