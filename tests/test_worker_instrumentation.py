import sys
import types
import unittest
from unittest.mock import patch

from rsstag.observability.worker_instrumentation import instrument_tasks


class _FakeCounter:
    def add(self, amount: int, attributes: dict | None = None) -> None:
        del amount, attributes


class _FakeMeter:
    def create_counter(self, name: str, description: str = "") -> _FakeCounter:
        del name, description
        return _FakeCounter()


class _FakeMetricsModule:
    @staticmethod
    def get_meter(name: str) -> _FakeMeter:
        del name
        return _FakeMeter()


class _FakeTraceModule:
    pass


class _InstrumentedTasks:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, bool]] = []

    def add_task(self, data: dict, manual: bool = True) -> bool:
        self.calls.append((data, manual))
        return True

    def get_task(self, users, *args, **kwargs):
        del users, args, kwargs
        return None

    def finish_task(self, task, *args, **kwargs):
        del task, args, kwargs
        return None


class TestWorkerInstrumentation(unittest.TestCase):
    def _fake_modules(self) -> dict[str, types.ModuleType]:
        opentelemetry_module = types.ModuleType("opentelemetry")
        opentelemetry_module.metrics = _FakeMetricsModule()
        opentelemetry_module.trace = _FakeTraceModule()

        propagate_module = types.ModuleType("opentelemetry.propagate")

        def _inject(carrier: dict) -> None:
            carrier["traceparent"] = "00-test"

        def _extract(carrier: dict) -> dict:
            return carrier

        propagate_module.inject = _inject
        propagate_module.extract = _extract

        return {
            "opentelemetry": opentelemetry_module,
            "opentelemetry.propagate": propagate_module,
        }

    def test_instrumented_add_task_accepts_current_signature(self) -> None:
        tasks = _InstrumentedTasks()

        with patch.dict(sys.modules, self._fake_modules()):
            instrument_tasks(tasks)

        result: bool = tasks.add_task({"type": 24, "user": "u1", "data": []})

        self.assertTrue(result)
        self.assertEqual(len(tasks.calls), 1)
        payload, manual = tasks.calls[0]
        self.assertTrue(manual)
        self.assertEqual(payload["type"], 24)
        self.assertEqual(payload["user"], "u1")
        self.assertIn("_trace_context", payload)
        self.assertEqual(payload["_trace_context"]["traceparent"], "00-test")


if __name__ == "__main__":
    unittest.main()
