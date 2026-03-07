import socket
import time
import unittest
from typing import Any, Dict

from rsstag.workers_db import RssTagWorkers
from tests.db_utils import DBHelper


class MongoWorkerLifecycleTestCase(unittest.TestCase):
    db_helper: DBHelper

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        try:
            with socket.create_connection(("127.0.0.1", 8765), timeout=1):
                pass
        except OSError as exc:
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for worker lifecycle tests: {exc}"
            )

    def setUp(self) -> None:
        self.db_helper = DBHelper(port=8765)
        try:
            self.db_helper.client.admin.command("ping")
        except Exception as exc:
            self.db_helper.close()
            raise unittest.SkipTest(
                f"MongoDB on port 8765 is required for worker lifecycle tests: {exc}"
            )
        self.db = self.db_helper.create_test_db()
        self.workers = RssTagWorkers(self.db)

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()


class TestWorkerProcessLifecycle(MongoWorkerLifecycleTestCase):
    def test_update_heartbeat_creates_record(self) -> None:
        self.workers.update_heartbeat(101)

        heartbeat: Dict[str, Any] | None = self.db.worker_heartbeats.find_one(
            {"worker_id": 101}
        )
        self.assertIsNotNone(heartbeat)
        self.assertEqual(heartbeat["status"], "running")
        self.assertIn("last_heartbeat", heartbeat)

    def test_update_heartbeat_refreshes_timestamp(self) -> None:
        self.workers.update_heartbeat(202)
        initial: Dict[str, Any] | None = self.db.worker_heartbeats.find_one(
            {"worker_id": 202}
        )
        self.assertIsNotNone(initial)

        time.sleep(0.02)
        self.workers.update_heartbeat(202)
        updated: Dict[str, Any] | None = self.db.worker_heartbeats.find_one(
            {"worker_id": 202}
        )

        self.assertIsNotNone(updated)
        self.assertGreater(updated["last_heartbeat"], initial["last_heartbeat"])

    def test_add_spawn_command_round_trip_and_consume(self) -> None:
        self.workers.add_spawn_command()

        command: Dict[str, Any] | None = self.workers.get_next_command()

        self.assertIsNotNone(command)
        self.assertEqual(command["command"], "spawn")
        self.assertIsNone(self.workers.get_next_command())

    def test_add_kill_command_round_trip(self) -> None:
        self.workers.add_kill_command(303)

        command: Dict[str, Any] | None = self.workers.get_next_command()

        self.assertIsNotNone(command)
        self.assertEqual(command["command"], "kill")
        self.assertEqual(command["worker_id"], 303)
        self.assertIn("timestamp", command)

    def test_set_worker_status_updates_existing_heartbeat(self) -> None:
        self.workers.update_heartbeat(404)

        self.workers.set_worker_status(404, "killed")

        heartbeat: Dict[str, Any] | None = self.db.worker_heartbeats.find_one(
            {"worker_id": 404}
        )
        self.assertIsNotNone(heartbeat)
        self.assertEqual(heartbeat["status"], "killed")

    def test_get_all_workers_returns_known_heartbeats(self) -> None:
        self.workers.update_heartbeat(501)
        self.workers.update_heartbeat(502, status="idle")

        workers = self.workers.get_all_workers()

        worker_ids = {worker["worker_id"] for worker in workers}
        self.assertEqual(worker_ids, {501, 502})
        self.assertNotIn("_id", workers[0])


if __name__ == "__main__":
    unittest.main()
