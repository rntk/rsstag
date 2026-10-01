"""Worker task registry."""

from typing import Callable, Dict

from rsstag.workers.outcome import HandlerResult

TaskHandler = Callable[[dict], HandlerResult]


class WorkerRegistry:
    def __init__(self) -> None:
        self._handlers: Dict[str, TaskHandler] = {}

    def register(self, task_type: str, handler: TaskHandler) -> None:
        self._handlers[task_type] = handler

    @property
    def handlers(self) -> Dict[str, TaskHandler]:
        return self._handlers

    def handle(self, task: dict) -> HandlerResult:
        """Run the handler for ``task``; ``None`` means unknown task type."""
        handler = self._handlers.get(task["type"])
        if not handler:
            return None
        return handler(task)
