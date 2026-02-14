"""Worker management database operations."""
import time
from typing import Any, Dict, List, Optional


class RssTagWorkers:
    """Worker heartbeat and command management"""

    def __init__(self, db: Any) -> None:
        self._db: Any = db

    def prepare(self) -> None:
        """Prepare indexes"""
        self._db.worker_heartbeats.create_index("worker_id", unique=True)
        self._db.worker_commands.create_index("timestamp")

    def update_heartbeat(self, worker_id: int, status: str = "running") -> None:
        """Update worker heartbeat"""
        self._db.worker_heartbeats.update_one(
            {"worker_id": worker_id},
            {"$set": {"last_heartbeat": time.time(), "status": status}},
            upsert=True
        )

    def get_all_workers(self) -> List[Dict[str, Any]]:
        """Get all workers"""
        return list(self._db.worker_heartbeats.find({}, {"_id": 0}))

    def add_spawn_command(self) -> None:
        """Add command to spawn new worker"""
        self._db.worker_commands.insert_one({"command": "spawn", "timestamp": time.time()})

    def add_kill_command(self, worker_id: int) -> None:
        """Add command to kill worker"""
        if not isinstance(worker_id, int) or isinstance(worker_id, bool) or worker_id <= 0:
            raise ValueError("worker_id must be a positive integer")
        self._db.worker_commands.insert_one({
            "command": "kill",
            "worker_id": worker_id,
            "timestamp": time.time()
        })

    def is_known_worker(self, worker_id: int) -> bool:
        """Check if worker id exists in heartbeat records."""
        if not isinstance(worker_id, int) or isinstance(worker_id, bool) or worker_id <= 0:
            return False
        return self._db.worker_heartbeats.count_documents(
            {"worker_id": worker_id},
            limit=1,
        ) > 0

    def get_next_command(self) -> Optional[Dict[str, Any]]:
        """Get and remove next command"""
        return self._db.worker_commands.find_one_and_delete({})

    def set_worker_status(self, worker_id: int, status: str) -> None:
        """Update worker status"""
        self._db.worker_heartbeats.update_one(
            {"worker_id": worker_id},
            {"$set": {"status": status}}
        )

    def delete_worker(self, worker_id: int) -> bool:
        """Delete a worker heartbeat record by worker id."""
        if not isinstance(worker_id, int) or isinstance(worker_id, bool) or worker_id <= 0:
            raise ValueError("worker_id must be a positive integer")
        deleted = self._db.worker_heartbeats.delete_one({"worker_id": worker_id})
        return bool(getattr(deleted, "deleted_count", 0))
