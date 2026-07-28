import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from rsstag.tasks import RssTagTasks, TASK_DOWNLOAD


class TestTasksQueueCleanup(unittest.TestCase):
    def test_completed_background_task_does_not_enqueue_a_successor(self) -> None:
        db: MagicMock = MagicMock()
        tasks: RssTagTasks = RssTagTasks(db)
        tasks._state = MagicMock()
        task: Dict[str, Any] = {
            "_id": "task-1",
            "type": TASK_DOWNLOAD,
            "user": {"sid": "user-1"},
            "manual": False,
            "data": {},
        }

        self.assertTrue(tasks.finish_task(task))

        tasks._state.complete.assert_called_once_with("task-1")
        tasks._state.enqueue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
