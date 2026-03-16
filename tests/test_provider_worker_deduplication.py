import pytest
from unittest.mock import MagicMock
from rsstag.workers.provider_worker import ProviderWorker

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_users():
    return MagicMock()

@pytest.fixture
def mock_providers():
    return {"test_provider": MagicMock()}

@pytest.fixture
def record_bulk_write():
    return MagicMock()

@pytest.fixture
def worker(mock_db, mock_users, mock_providers, record_bulk_write):
    return ProviderWorker(
        db=mock_db,
        config={"gmail": {"client_id": "id", "client_secret": "secret"}},
        providers=mock_providers,
        users=mock_users,
        tasks=MagicMock(),
        record_bulk_write=record_bulk_write
    )

def test_handle_download_deduplicates_by_id_robustly(
    worker, mock_db, mock_users, mock_providers, record_bulk_write
):
    # Task setup
    task = {"user": {"sid": "user123"}, "data": {"provider": "test_provider"}}
    mock_users.get_provider_user.return_value = {"token": "abc"}
    
    # Provider returns 3 posts, two have same ID (local duplicate), one is already in DB
    p1 = {"id": "msg1", "content": "original"}
    p1_dup = {"id": "msg1", "content": "duplicate"}
    p2 = {"id": "msg2", "content": "new"}
    
    provider = mock_providers["test_provider"]
    provider.download.return_value = [([p1, p1_dup, p2], [])]
    
    # DB already has msg1 (even without provider field)
    mock_db.posts.find.return_value = [{"id": "msg1"}]
    
    # Execute
    assert worker.handle_download(task) is True
    
    # Verify DB query
    mock_db.posts.find.assert_called_once()
    query = mock_db.posts.find.call_args[0][0]
    assert query["owner"] == "user123"
    assert "id" in query
    assert "$in" in query["id"]
    assert set(query["id"]["$in"]) == {"msg1", "msg2"}
    # Verify provider is NOT in query for robustness
    assert "provider" not in query

    # Verify insertion: only p2 should be inserted
    mock_db.posts.insert_many.assert_called_once()
    inserted_posts = mock_db.posts.insert_many.call_args[0][0]
    assert len(inserted_posts) == 1
    assert inserted_posts[0]["id"] == "msg2"
    assert inserted_posts[0]["provider"] == "test_provider"
    
    record_bulk_write.assert_called_with("posts", 1)
