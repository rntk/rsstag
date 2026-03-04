"""Observable gauges for application-level business metrics."""

import logging
import time
from typing import Any

from rsstag.observability.worker_instrumentation import TASK_TYPE_NAMES

# Minimum seconds between MongoDB queries inside metric-scrape callbacks.
# The OTel SDK calls these callbacks on every metric export cycle (default 60s),
# but guard explicitly so a misconfigured short interval doesn't overload the DB.
_CACHE_TTL = 60.0


def register_business_metrics(db: Any) -> None:
    """Register observable gauges backed by MongoDB queries.

    Args:
        db: PyMongo database handle.
    """
    try:
        from opentelemetry import metrics

        meter = metrics.get_meter("rsstag.business")

        # --- Task queue depth per task type ---
        _queue_cache: dict = {"ts": 0.0, "data": []}

        def _observe_task_queue_depth(options):
            try:
                now = time.monotonic()
                if now - _queue_cache["ts"] >= _CACHE_TTL:
                    pipeline = [
                        {"$match": {"processing": 0}},
                        {"$group": {"_id": "$type", "count": {"$sum": 1}}},
                    ]
                    _queue_cache["data"] = list(db.tasks.aggregate(pipeline))
                    _queue_cache["ts"] = now
                for row in _queue_cache["data"]:
                    task_type = row["_id"]
                    label = TASK_TYPE_NAMES.get(task_type, str(task_type))
                    options.observe(int(row["count"]), {"task_type": label})
            except Exception as exc:
                logging.debug("OTel task_queue_depth observation failed: %s", exc)

        meter.create_observable_gauge(
            "rsstag.task_queue.depth",
            callbacks=[_observe_task_queue_depth],
            description="Number of pending tasks per type",
        )

        # --- Active users in the last hour ---
        _users_cache: dict = {"ts": 0.0, "count": 0}

        def _observe_active_users(options):
            try:
                now = time.monotonic()
                if now - _users_cache["ts"] >= _CACHE_TTL:
                    cutoff = time.time() - 3600
                    _users_cache["count"] = db.users.count_documents({"last_visit": {"$gte": cutoff}})
                    _users_cache["ts"] = now
                options.observe(int(_users_cache["count"]))
            except Exception as exc:
                logging.debug("OTel active_users observation failed: %s", exc)

        meter.create_observable_gauge(
            "rsstag.users.active",
            callbacks=[_observe_active_users],
            description="Users active in the last hour",
        )

    except Exception as exc:
        logging.warning("OTel business metrics registration failed: %s", exc)
