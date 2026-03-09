from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
from pymongo.errors import BulkWriteError

from rsstag.providers import providers as data_providers
from rsstag.tasks import TASK_GMAIL_SORT, TASK_MARK, TASK_MARK_TELEGRAM
from rsstag.workers.provider_worker import ProviderWorker


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_users() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_tasks() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_providers() -> Dict[str, MagicMock]:
    return {
        data_providers.TELEGRAM: MagicMock(),
        data_providers.GMAIL: MagicMock(),
        "test_provider": MagicMock(),
    }


@pytest.fixture
def record_bulk_write() -> MagicMock:
    return MagicMock()


@pytest.fixture
def worker(
    mock_db: MagicMock,
    mock_users: MagicMock,
    mock_tasks: MagicMock,
    mock_providers: Dict[str, MagicMock],
    record_bulk_write: MagicMock,
) -> ProviderWorker:
    return ProviderWorker(
        db=mock_db,
        config={},
        providers=mock_providers,
        users=mock_users,
        tasks=mock_tasks,
        record_bulk_write=record_bulk_write,
    )


def test_handle_download_no_provider_user(
    worker: ProviderWorker, mock_users: MagicMock
) -> None:
    task: Dict[str, Any] = {
        "user": {"sid": "123", "provider": "test_provider"},
        "data": {"provider": "test_provider"},
    }
    mock_users.get_provider_user.return_value = None

    assert worker.handle_download(task) is True


def test_handle_download_unknown_provider_marks_task_failed(
    worker: ProviderWorker, mock_users: MagicMock, mock_tasks: MagicMock
) -> None:
    task: Dict[str, Any] = {
        "_id": "task-1",
        "user": {"sid": "123"},
        "data": {"provider": "missing_provider"},
    }
    mock_users.get_provider_user.return_value = {"token": "abc"}

    assert worker.handle_download(task) is False

    mock_tasks.mark_task_failed.assert_called_once_with(
        "task-1", "Unknown provider missing_provider"
    )


def test_handle_download_success(
    worker: ProviderWorker,
    mock_users: MagicMock,
    mock_providers: Dict[str, MagicMock],
    mock_db: MagicMock,
    record_bulk_write: MagicMock,
) -> None:
    task: Dict[str, Any] = {"user": {"sid": "123"}, "data": {"provider": "test_provider"}}
    mock_users.get_provider_user.return_value = {"token": "abc"}

    provider = mock_providers["test_provider"]
    provider.download.return_value = [([{"id": 1}], [{"feed_id": "f1"}])]

    mock_db.feeds.find.return_value = [{"feed_id": "f1"}]

    assert worker.handle_download(task) is True

    mock_db.posts.insert_many.assert_called_once_with(
        [{"id": 1, "provider": "test_provider"}], ordered=False
    )
    record_bulk_write.assert_called_once_with("posts", 1)


def test_handle_download_persists_refreshed_gmail_token(
    worker: ProviderWorker,
    mock_users: MagicMock,
    mock_providers: Dict[str, MagicMock],
) -> None:
    task: Dict[str, Any] = {"user": {"sid": "123"}, "data": {"provider": data_providers.GMAIL}}
    provider_user = {
        "token": "new-token",
        "access_token": "new-token",
        "refresh_token": "refresh-1",
        "token_refreshed": True,
    }
    mock_users.get_provider_user.return_value = provider_user

    mock_providers[data_providers.GMAIL].download.return_value = [([], [])]

    assert worker.handle_download(task) is True

    mock_users.update_provider.assert_called_once_with(
        "123",
        data_providers.GMAIL,
        {"token": "new-token", "retoken": False, "refresh_token": "refresh-1"},
    )


def test_handle_gmail_sort_persists_refreshed_token(
    worker: ProviderWorker,
    mock_users: MagicMock,
    mock_providers: Dict[str, MagicMock],
) -> None:
    task: Dict[str, Any] = {"user": {"sid": "123"}, "type": TASK_GMAIL_SORT, "data": {}}
    provider_user = {
        "token": "new-token",
        "access_token": "new-token",
        "refresh_token": "refresh-1",
        "token_refreshed": True,
    }
    mock_users.get_provider_user.return_value = provider_user

    provider = mock_providers[data_providers.GMAIL]
    provider.sort_emails_by_domain.return_value = True

    assert worker.handle_gmail_sort(task) is True

    mock_users.update_provider.assert_called_once_with(
        "123",
        data_providers.GMAIL,
        {"token": "new-token", "retoken": False, "refresh_token": "refresh-1"},
    )


def test_handle_download_duplicate_post_errors_are_ignored(
    worker: ProviderWorker,
    mock_users: MagicMock,
    mock_providers: Dict[str, MagicMock],
    mock_db: MagicMock,
) -> None:
    task: Dict[str, Any] = {"user": {"sid": "123"}, "data": {"provider": "test_provider"}}
    mock_users.get_provider_user.return_value = {"token": "abc"}
    provider = mock_providers["test_provider"]
    provider.download.return_value = [([{"id": 1}], [])]
    mock_db.posts.insert_many.side_effect = BulkWriteError(
        {"writeErrors": [{"code": 11000}]}
    )

    assert worker.handle_download(task) is True


def test_handle_download_non_duplicate_bulk_write_error_fails(
    worker: ProviderWorker,
    mock_users: MagicMock,
    mock_providers: Dict[str, MagicMock],
    mock_db: MagicMock,
) -> None:
    task: Dict[str, Any] = {"user": {"sid": "123"}, "data": {"provider": "test_provider"}}
    mock_users.get_provider_user.return_value = {"token": "abc"}
    provider = mock_providers["test_provider"]
    provider.download.return_value = [([{"id": 1}], [])]
    mock_db.posts.insert_many.side_effect = BulkWriteError(
        {"writeErrors": [{"code": 999}]}
    )

    assert worker.handle_download(task) is False


def test_handle_mark_success(
    worker: ProviderWorker, mock_users: MagicMock, mock_providers: Dict[str, MagicMock]
) -> None:
    task: Dict[str, Any] = {
        "user": {"sid": "123"},
        "data": {"provider": "test_provider", "mark": "read"},
    }
    mock_users.get_provider_user.return_value = {"token": "abc"}

    provider = mock_providers["test_provider"]
    provider.mark.return_value = True

    assert worker.handle_mark(task) is True
    provider.mark.assert_called_once_with(task["data"], {"token": "abc"})


def test_handle_mark_unknown_provider_marks_task_failed(
    worker: ProviderWorker, mock_users: MagicMock, mock_tasks: MagicMock
) -> None:
    task: Dict[str, Any] = {
        "_id": "task-2",
        "type": TASK_MARK,
        "user": {"sid": "123"},
        "data": {"provider": "missing_provider", "mark": "read"},
    }
    mock_users.get_provider_user.return_value = {"token": "abc"}

    assert worker.handle_mark(task) is False

    mock_tasks.mark_task_failed.assert_called_once_with(
        "task-2", "Unknown provider missing_provider"
    )


def test_handle_mark_none_freezes_tasks(
    worker: ProviderWorker,
    mock_users: MagicMock,
    mock_providers: Dict[str, MagicMock],
    mock_tasks: MagicMock,
) -> None:
    task: Dict[str, Any] = {
        "user": {"sid": "123"},
        "type": TASK_MARK,
        "data": {"provider": "test_provider", "mark": "read"},
    }
    mock_users.get_provider_user.return_value = {"token": "abc"}
    mock_providers["test_provider"].mark.return_value = None

    assert worker.handle_mark(task) is False

    mock_tasks.freeze_tasks.assert_called_once_with(task["user"], TASK_MARK)
    mock_users.update_provider.assert_called_once_with(
        "123", "test_provider", {"retoken": True}
    )


def test_handle_mark_telegram_success(
    worker: ProviderWorker, mock_users: MagicMock, mock_providers: Dict[str, MagicMock]
) -> None:
    task: Dict[str, Any] = {"user": {"sid": "123"}, "data": {"mark": "read"}}
    mock_users.get_provider_user.return_value = {"token": "abc"}

    provider = mock_providers[data_providers.TELEGRAM]
    provider.mark_all.return_value = True

    assert worker.handle_mark_telegram(task) is True
    provider.mark_all.assert_called_once_with(task["data"], {"token": "abc"})


def test_handle_mark_telegram_none_freezes_tasks(
    worker: ProviderWorker,
    mock_users: MagicMock,
    mock_providers: Dict[str, MagicMock],
    mock_tasks: MagicMock,
) -> None:
    task: Dict[str, Any] = {
        "user": {"sid": "123"},
        "type": TASK_MARK_TELEGRAM,
        "data": {},
    }
    mock_users.get_provider_user.return_value = {"token": "abc"}
    mock_providers[data_providers.TELEGRAM].mark_all.return_value = None

    assert worker.handle_mark_telegram(task) is False

    mock_tasks.freeze_tasks.assert_called_once_with(task["user"], TASK_MARK_TELEGRAM)
    mock_users.update_provider.assert_called_once_with(
        "123", data_providers.TELEGRAM, {"retoken": True}
    )


def test_handle_gmail_sort_success(
    worker: ProviderWorker, mock_users: MagicMock, mock_providers: Dict[str, MagicMock]
) -> None:
    task: Dict[str, Any] = {"user": {"sid": "123"}, "data": {}}
    mock_users.get_provider_user.return_value = {"token": "abc"}

    provider = mock_providers[data_providers.GMAIL]
    provider.sort_emails_by_domain.return_value = True

    assert worker.handle_gmail_sort(task) is True
    provider.sort_emails_by_domain.assert_called_once_with({"token": "abc"})


def test_handle_gmail_sort_unknown_provider_marks_task_failed(
    worker: ProviderWorker, mock_tasks: MagicMock
) -> None:
    task: Dict[str, Any] = {"_id": "task-3", "user": {"sid": "123"}, "data": {}}
    worker._providers.pop(data_providers.GMAIL)

    assert worker.handle_gmail_sort(task) is False

    mock_tasks.mark_task_failed.assert_called_once_with(
        "task-3", "Unknown provider gmail"
    )


def test_handle_gmail_sort_none_freezes_tasks(
    worker: ProviderWorker,
    mock_users: MagicMock,
    mock_providers: Dict[str, MagicMock],
    mock_tasks: MagicMock,
) -> None:
    task: Dict[str, Any] = {"user": {"sid": "123"}, "type": TASK_GMAIL_SORT, "data": {}}
    mock_users.get_provider_user.return_value = {"token": "abc"}

    provider = mock_providers[data_providers.GMAIL]
    provider.sort_emails_by_domain.return_value = None

    assert worker.handle_gmail_sort(task) is False
    mock_tasks.freeze_tasks.assert_called_once_with(task["user"], TASK_GMAIL_SORT)
    mock_users.update_provider.assert_called_once_with(
        "123", data_providers.GMAIL, {"retoken": True}
    )
