import pytest
from unittest.mock import MagicMock, call
from pymongo.errors import BulkWriteError

from rsstag.workers.provider_worker import ProviderWorker
from rsstag.providers import providers as data_providers

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_users():
    return MagicMock()

@pytest.fixture
def mock_tasks():
    return MagicMock()

@pytest.fixture
def mock_providers():
    return {
        data_providers.TELEGRAM: MagicMock(),
        data_providers.GMAIL: MagicMock(),
        "test_provider": MagicMock()
    }

@pytest.fixture
def record_bulk_write():
    return MagicMock()

@pytest.fixture
def worker(mock_db, mock_users, mock_tasks, mock_providers, record_bulk_write):
    return ProviderWorker(
        db=mock_db,
        config={},
        providers=mock_providers,
        users=mock_users,
        tasks=mock_tasks,
        record_bulk_write=record_bulk_write
    )

def test_handle_download_no_provider_user(worker, mock_users):
    task = {"user": {"sid": "123", "provider": "test_provider"}, "data": {"provider": "test_provider"}}
    mock_users.get_provider_user.return_value = None

    assert worker.handle_download(task) is True

def test_handle_download_success(worker, mock_users, mock_providers, mock_db, record_bulk_write):
    task = {"user": {"sid": "123"}, "data": {"provider": "test_provider"}}
    mock_users.get_provider_user.return_value = {"token": "abc"}

    provider = mock_providers["test_provider"]
    provider.download.return_value = [
        ([{"id": 1}], [{"feed_id": "f1"}])
    ]

    mock_db.feeds.find.return_value = [{"feed_id": "f1"}]

    assert worker.handle_download(task) is True

    mock_db.posts.insert_many.assert_called_once_with([{"id": 1, "provider": "test_provider"}], ordered=False)
    record_bulk_write.assert_called_with("posts", 1)

def test_handle_mark_success(worker, mock_users, mock_providers):
    task = {"user": {"sid": "123"}, "data": {"provider": "test_provider", "mark": "read"}}
    mock_users.get_provider_user.return_value = {"token": "abc"}

    provider = mock_providers["test_provider"]
    provider.mark.return_value = True

    assert worker.handle_mark(task) is True
    provider.mark.assert_called_once_with(task["data"], {"token": "abc"})

def test_handle_mark_telegram_success(worker, mock_users, mock_providers):
    task = {"user": {"sid": "123"}, "data": {"mark": "read"}}
    mock_users.get_provider_user.return_value = {"token": "abc"}

    provider = mock_providers[data_providers.TELEGRAM]
    provider.mark_all.return_value = True

    assert worker.handle_mark_telegram(task) is True
    provider.mark_all.assert_called_once_with(task["data"], {"token": "abc"})

def test_handle_gmail_sort_success(worker, mock_users, mock_providers):
    task = {"user": {"sid": "123"}, "data": {}}
    mock_users.get_provider_user.return_value = {"token": "abc"}

    provider = mock_providers[data_providers.GMAIL]
    provider.sort_emails_by_domain.return_value = True

    assert worker.handle_gmail_sort(task) is True
    provider.sort_emails_by_domain.assert_called_once_with({"token": "abc"})

def test_handle_gmail_sort_none_freezes_tasks(worker, mock_users, mock_providers, mock_tasks):
    task = {"user": {"sid": "123"}, "type": 10, "data": {}}
    mock_users.get_provider_user.return_value = {"token": "abc"}

    provider = mock_providers[data_providers.GMAIL]
    provider.sort_emails_by_domain.return_value = None

    assert worker.handle_gmail_sort(task) is False
    mock_tasks.freeze_tasks.assert_called_once_with(task["user"], task["type"])
    mock_users.update_provider.assert_called_once_with("123", data_providers.GMAIL, {"retoken": True})
