import unittest

from rsstag.workers_db import RssTagWorkers
from tests.db_utils import DBHelper


class TestRssTagWorkers(unittest.TestCase):
    def setUp(self) -> None:
        self.db_helper: DBHelper = DBHelper(port=8765)
        self.db = self.db_helper.create_test_db()
        self.workers: RssTagWorkers = RssTagWorkers(self.db)

    def tearDown(self) -> None:
        self.db_helper.drop_test_db(self.db)
        self.db_helper.close()

    def test_add_kill_command_rejects_invalid_worker_id(self) -> None:
        with self.assertRaises(ValueError):
            self.workers.add_kill_command(0)

        with self.assertRaises(ValueError):
            self.workers.add_kill_command(-1)

        with self.assertRaises(ValueError):
            self.workers.add_kill_command(True)

    def test_is_known_worker(self) -> None:
        self.assertFalse(self.workers.is_known_worker(11111))

        worker_id: int = 11111
        self.workers.update_heartbeat(worker_id)

        self.assertTrue(self.workers.is_known_worker(worker_id))

    def test_delete_worker(self) -> None:
        worker_id: int = 22222
        self.workers.update_heartbeat(worker_id)

        deleted: bool = self.workers.delete_worker(worker_id)
        self.assertTrue(deleted)
        self.assertFalse(self.workers.is_known_worker(worker_id))

    def test_delete_worker_rejects_invalid_worker_id(self) -> None:
        with self.assertRaises(ValueError):
            self.workers.delete_worker(0)

        with self.assertRaises(ValueError):
            self.workers.delete_worker(-10)

        with self.assertRaises(ValueError):
            self.workers.delete_worker(True)


if __name__ == "__main__":
    unittest.main()
