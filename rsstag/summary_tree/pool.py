"""Worker pool that aborts in-flight LLM work when the coordinator fails."""

import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Iterator

from rsstag.summary_tree.llm import SummaryLLM

_log: logging.Logger = logging.getLogger("summary_tree.pool")


@contextmanager
def worker_pool(workers: int, llm: SummaryLLM) -> Iterator[ThreadPoolExecutor]:
    """Join workers on success; on any error cancel queued work without waiting.

    Running workers stop at their next LLM attempt via ``llm.cancel()``; their
    results are discarded, so the failing run returns without a request cycle.
    """
    pool: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=max(1, workers))
    try:
        yield pool
    except BaseException:
        _log.info("Summary tree run aborted; cancelling outstanding LLM work")
        llm.cancel()
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown(wait=True)
