import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from rsstag.web.system import _format_duration, _worker_view


class TestWorkersView(unittest.TestCase):
    def test_format_duration(self) -> None:
        self.assertEqual(_format_duration(5), "5s")
        self.assertEqual(_format_duration(125), "2m")
        self.assertEqual(_format_duration(3725), "1h 2m")
        self.assertEqual(_format_duration(90000), "1d 1h")
        self.assertEqual(_format_duration(-3), "0s")

    def test_worker_view_with_task(self) -> None:
        app: MagicMock = MagicMock()
        app.tasks.get_task_title.return_value = "Tags"
        worker: Dict[str, Any] = {"worker_id": 1, "last_task_at": 1000.0, "last_task_type": 3, "tasks_processed": 4}
        view: Dict[str, Any] = _worker_view(app, worker, 1120.0)
        self.assertEqual(view["idle_for"], "2m")
        self.assertEqual(view["last_task_title"], "Tags")
        self.assertEqual(view["tasks_processed"], 4)

    def test_worker_view_without_task(self) -> None:
        worker: Dict[str, Any] = {"worker_id": 1, "started_at": 1000.0}
        view: Dict[str, Any] = _worker_view(MagicMock(), worker, 1030.0)
        self.assertEqual(view["idle_for"], "30s (no tasks yet)")
        self.assertEqual(view["tasks_processed"], 0)

    def test_worker_view_legacy_record(self) -> None:
        view: Dict[str, Any] = _worker_view(MagicMock(), {"worker_id": 1}, 1030.0)
        self.assertEqual(view["idle_for"], "N/A")


if __name__ == "__main__":
    unittest.main()
