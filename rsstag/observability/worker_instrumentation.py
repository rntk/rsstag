"""OTel instrumentation for RssTagTasks and WorkerRegistry."""

import logging
import time
from typing import Any

from rsstag.tasks import (
    TASK_ALL,
    TASK_NOOP,
    TASK_DOWNLOAD,
    TASK_MARK,
    TASK_TAGS,
    TASK_WORDS,
    TASK_LETTERS,
    TASK_NER,
    TASK_CLUSTERING,
    TASK_W2V,
    TASK_D2V,
    TASK_TAGS_SENTIMENT,
    TASK_TAGS_GROUP,
    TASK_TAGS_COORDS,
    TASK_BIGRAMS_RANK,
    TASK_TAGS_RANK,
    TASK_FASTTEXT,
    TASK_CLEAN_BIGRAMS,
    TASK_MARK_TELEGRAM,
    TASK_GMAIL_SORT,
    TASK_POST_GROUPING,
    TASK_TAG_CLASSIFICATION,
    TASK_POST_GROUPING_BATCH,
    TASK_TAG_CLASSIFICATION_BATCH,
    TASK_DELETE_FEEDS,
)

TASK_TYPE_NAMES = {
    TASK_ALL: "all",
    TASK_NOOP: "noop",
    TASK_DOWNLOAD: "download",
    TASK_MARK: "mark",
    TASK_TAGS: "tags",
    TASK_WORDS: "words",
    TASK_LETTERS: "letters",
    TASK_NER: "ner",
    TASK_CLUSTERING: "clustering",
    TASK_W2V: "w2v",
    TASK_D2V: "d2v",
    TASK_TAGS_SENTIMENT: "tags_sentiment",
    TASK_TAGS_GROUP: "tags_group",
    TASK_TAGS_COORDS: "tags_coords",
    TASK_BIGRAMS_RANK: "bigrams_rank",
    TASK_TAGS_RANK: "tags_rank",
    TASK_FASTTEXT: "fasttext",
    TASK_CLEAN_BIGRAMS: "clean_bigrams",
    TASK_MARK_TELEGRAM: "mark_telegram",
    TASK_GMAIL_SORT: "gmail_sort",
    TASK_POST_GROUPING: "post_grouping",
    TASK_TAG_CLASSIFICATION: "tag_classification",
    TASK_POST_GROUPING_BATCH: "post_grouping_batch",
    TASK_TAG_CLASSIFICATION_BATCH: "tag_classification_batch",
    TASK_DELETE_FEEDS: "delete_feeds",
}


def _task_type_label(task_type: Any) -> str:
    return TASK_TYPE_NAMES.get(task_type, str(task_type))


def instrument_tasks(tasks_instance: Any) -> None:
    """Monkey-patch RssTagTasks to emit enqueue/claim/complete metrics and inject trace context."""
    if getattr(tasks_instance, "_otel_instrumented", False):
        return
    try:
        from opentelemetry import metrics, trace
        from opentelemetry.propagate import inject, extract

        meter = metrics.get_meter("rsstag.tasks")
        enqueued_counter = meter.create_counter(
            "rsstag.task.enqueued",
            description="Tasks added to the queue",
        )
        claimed_counter = meter.create_counter(
            "rsstag.task.claimed",
            description="Tasks claimed from the queue",
        )
        completed_counter = meter.create_counter(
            "rsstag.task.completed",
            description="Tasks marked as finished",
        )
    except Exception as exc:
        logging.warning("OTel task metrics init failed: %s", exc)
        return

    _orig_add_task = tasks_instance.add_task
    _orig_get_task = tasks_instance.get_task
    _orig_finish_task = tasks_instance.finish_task

    def _add_task(*args, **kwargs):
        manual = kwargs.pop("manual", True)
        task_data = None

        if args and isinstance(args[0], dict):
            task_data = dict(args[0])
            if len(args) > 1:
                manual = args[1]
        else:
            # Backward-compatible path for older call sites that may still use
            # add_task(task_type, user, data=None, manual=True).
            task_type = args[0] if len(args) > 0 else kwargs.pop("task_type", None)
            user = args[1] if len(args) > 1 else kwargs.pop("user", None)
            payload = args[2] if len(args) > 2 else kwargs.pop("data", None)
            if len(args) > 3:
                manual = args[3]

            task_data = dict(payload) if isinstance(payload, dict) else {}
            if task_type is not None:
                task_data["type"] = task_type
            if user is not None:
                task_data["user"] = user
            task_data.update(kwargs)

        # Inject current trace context into the task document so workers can link spans.
        carrier: dict = {}
        try:
            inject(carrier)
        except Exception:
            pass
        if carrier:
            task_data["_trace_context"] = carrier

        result = _orig_add_task(task_data, manual=manual)

        try:
            enqueued_counter.add(
                1, {"task_type": _task_type_label(task_data.get("type"))}
            )
        except Exception:
            pass
        return result

    def _get_task(users, *args, **kwargs):
        task = _orig_get_task(users, *args, **kwargs)
        try:
            if task and task.get("type") is not None:
                claimed_counter.add(1, {"task_type": _task_type_label(task["type"])})
        except Exception:
            pass
        return task

    def _finish_task(task, *args, **kwargs):
        try:
            if task and task.get("type") is not None:
                completed_counter.add(1, {"task_type": _task_type_label(task["type"])})
        except Exception:
            pass
        return _orig_finish_task(task, *args, **kwargs)

    tasks_instance.add_task = _add_task
    tasks_instance.get_task = _get_task
    tasks_instance.finish_task = _finish_task
    tasks_instance._otel_instrumented = True


def instrument_registry(registry: Any) -> None:
    """Wrap WorkerRegistry.handle() to create spans and emit duration/failure metrics."""
    if getattr(registry, "_otel_instrumented", False):
        return
    try:
        from opentelemetry import metrics, trace
        from opentelemetry.propagate import extract
        from opentelemetry.trace import StatusCode, NonRecordingSpan, SpanContext

        meter = metrics.get_meter("rsstag.tasks")
        tracer = trace.get_tracer("rsstag.tasks")
        duration_histogram = meter.create_histogram(
            "rsstag.task.duration",
            unit="s",
            description="Task execution duration in seconds",
        )
        failed_counter = meter.create_counter(
            "rsstag.task.failed",
            description="Tasks that failed during execution",
        )
    except Exception as exc:
        logging.warning("OTel registry instrumentation init failed: %s", exc)
        return

    _orig_handle = registry.handle

    def _handle(task: dict):
        task_type = task.get("type")
        label = _task_type_label(task_type)

        # Extract propagated trace context from the task document
        carrier = {}
        try:
            data = task.get("data")
            if isinstance(data, dict):
                carrier = data.get("_trace_context") or {}
        except Exception:
            pass

        ctx = extract(carrier) if carrier else None

        span_kwargs = {}
        if ctx is not None:
            span_kwargs["context"] = ctx

        start = time.perf_counter()
        with tracer.start_as_current_span(
            f"task.{label}",
            kind=trace.SpanKind.CONSUMER,
            **span_kwargs,
        ) as span:
            span.set_attribute("rsstag.task.type", label)
            try:
                result = _orig_handle(task)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                failed_counter.add(1, {"task_type": label})
                elapsed = time.perf_counter() - start
                duration_histogram.record(elapsed, {"task_type": label})
                raise
            elapsed = time.perf_counter() - start
            duration_histogram.record(elapsed, {"task_type": label})
            if result is False:
                failed_counter.add(1, {"task_type": label})
                span.set_status(StatusCode.ERROR, "task returned False")
            else:
                span.set_status(StatusCode.OK)
            return result

    registry.handle = _handle
    registry._otel_instrumented = True
