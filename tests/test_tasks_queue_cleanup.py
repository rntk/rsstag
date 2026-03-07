import unittest

from rsstag.tasks import RssTagTasks, TASK_POST_GROUPING, TASK_TAGS


class _TasksForFinalizeTest(RssTagTasks):
    def __init__(self) -> None:
        self._tasks_after = {TASK_TAGS: [999]}
        self.called_with: tuple[str, int] | None = None

    def add_next_tasks(self, user: str, task_type: int):
        self.called_with = (user, task_type)
        return False


class TestTasksQueueCleanup(unittest.TestCase):
    def test_auto_task_without_successors_can_be_deleted(self) -> None:
        tasks = _TasksForFinalizeTest()

        result = tasks._can_finalize_completed_task(
            {"user": "user-1", "type": TASK_POST_GROUPING, "manual": False}
        )

        self.assertTrue(result)
        self.assertIsNone(tasks.called_with)

    def test_auto_task_with_successors_requires_successful_chaining(self) -> None:
        tasks = _TasksForFinalizeTest()

        result = tasks._can_finalize_completed_task(
            {"user": "user-1", "type": TASK_TAGS, "manual": False}
        )

        self.assertFalse(result)
        self.assertEqual(tasks.called_with, ("user-1", TASK_TAGS))


if __name__ == "__main__":
    unittest.main()
