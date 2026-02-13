"""RSSTag worker package."""

from typing import Any

__all__ = ["RSSTagWorkerDispatcher", "ExternalWorkerRunner", "worker"]


def __getattr__(name: str) -> Any:
    if name in {"RSSTagWorkerDispatcher", "worker"}:
        from rsstag.workers.dispatcher import RSSTagWorkerDispatcher, worker

        mapping = {
            "RSSTagWorkerDispatcher": RSSTagWorkerDispatcher,
            "worker": worker,
        }
        return mapping[name]
    if name == "ExternalWorkerRunner":
        from rsstag.workers.external_worker import ExternalWorkerRunner

        return ExternalWorkerRunner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
