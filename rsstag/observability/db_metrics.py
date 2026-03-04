"""Helper for recording bulk database write metrics."""

import logging
import threading


def _get_instruments():
    from opentelemetry import metrics
    meter = metrics.get_meter("rsstag.db")
    bulk_writes = meter.create_counter(
        "rsstag.db.bulk_writes",
        description="Number of bulk write operations",
    )
    bulk_doc_count = meter.create_histogram(
        "rsstag.db.bulk_write.doc_count",
        description="Number of documents per bulk write operation",
    )
    return bulk_writes, bulk_doc_count


_instruments = None
_instruments_lock = threading.Lock()


def reset_instruments() -> None:
    """Clear the cached OTel instruments.

    Must be called in forked child processes after reset_for_child_process() so
    that record_bulk_write() picks up the fresh MeterProvider rather than using
    counters tied to the parent's (now orphaned) provider.
    """
    global _instruments
    with _instruments_lock:
        _instruments = None


def record_bulk_write(collection: str, count: int) -> None:
    """Record a bulk write operation for observability.

    Args:
        collection: MongoDB collection name (e.g. 'posts', 'feeds').
        count: Number of documents written.
    """
    global _instruments
    try:
        if _instruments is None:
            with _instruments_lock:
                if _instruments is None:
                    _instruments = _get_instruments()
        bulk_writes, bulk_doc_count = _instruments
        labels = {"collection": collection}
        bulk_writes.add(1, labels)
        bulk_doc_count.record(count, labels)
    except Exception as exc:
        logging.debug("OTel db metric record failed: %s", exc)
