"""Worker task registry."""

from typing import Callable, Dict, Optional


class WorkerRegistry:
    def __init__(self):
        self._handlers: Dict[str, Callable[[dict], bool]] = {}

    def register(self, task_type: str, handler: Callable[[dict], bool]) -> None:
        self._handlers[task_type] = handler

    def handle(self, task: dict) -> Optional[bool]:
        handler = self._handlers.get(task["type"])
        if not handler:
            return None
        return handler(task)
