"""Worker dispatcher and process loop."""

import logging
import signal
import time
import traceback
from multiprocessing import Process
from random import randint
from types import FrameType
from typing import Any, Dict, Optional

from pymongo import MongoClient
from pymongo.errors import BulkWriteError

import rsstag.providers.providers as data_providers
from rsstag.providers.bazqux import BazquxProvider
from rsstag.providers.gmail import GmailProvider
from rsstag.providers.telegram import TelegramProvider
from rsstag.providers.textfile import TextFileProvider
from rsstag.providers.x import XProvider
from rsstag.tasks import (
    TASK_BIGRAMS_RANK,
    TASK_CLEAN_BIGRAMS,
    TASK_CLUSTERING,
    TASK_DELETE_FEEDS,
    TASK_DOWNLOAD,
    TASK_FASTTEXT,
    TASK_GMAIL_SORT,
    TASK_LETTERS,
    TASK_MARK,
    TASK_MARK_TELEGRAM,
    TASK_NER,
    TASK_NOOP,
    TASK_POST_GROUPING,
    TASK_POST_GROUPING_BATCH,
    TASK_POST_GROUPING_CLEANUP,
    TASK_SNIPPET_CLUSTERING,
    TASK_TAGS,
    TASK_TAGS_GROUP,
    TASK_TAGS_RANK,
    TASK_TAGS_SENTIMENT,
    TASK_TAG_CLASSIFICATION,
    TASK_TAG_CLASSIFICATION_BATCH,
    TASK_W2V,
)
from rsstag.tasks import RssTagTasks
from rsstag.users import RssTagUsers
from rsstag.utils import load_config
from rsstag.workers.llm_worker import LLMWorker
from rsstag.workers.registry import WorkerRegistry
from rsstag.workers.tag_worker import TagWorker
from rsstag.workers.provider_worker import ProviderWorker
from rsstag.workers_db import RssTagWorkers


class RSSTagWorkerDispatcher:
    """Rsstag workers handler"""

    def __init__(self, config_path, log_file=None):
        self._config = load_config(config_path)
        if not self._config or "settings" not in self._config:
            raise ValueError(f"Unable to load worker config from: {config_path}")
        self._workers_pool = []
        target_log = log_file
        if not target_log:
            target_log = self._config["settings"].get("worker_log_file", self._config["settings"]["log_file"])
        logging.basicConfig(
            filename=target_log,
            filemode="a",
            level=getattr(logging, self._config["settings"]["log_level"].upper()),
            force=True,
        )
        cl = MongoClient(
            self._config["settings"]["db_host"],
            int(self._config["settings"]["db_port"]),
            username=self._config["settings"]["db_login"] if self._config["settings"]["db_login"] else None,
            password=self._config["settings"]["db_password"] if self._config["settings"]["db_password"] else None,
        )
        db = cl[self._config["settings"]["db_name"]]
        self._client = cl
        self._db = db
        self._workers_db = RssTagWorkers(db)

    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    @property
    def workers_db(self) -> RssTagWorkers:
        return self._workers_db

    @property
    def db(self) -> Any:
        return self._db

    def start(self):
        """Start worker"""
        for _ in range(int(self._config["settings"]["workers_count"])):
            self._workers_pool.append(Process(target=worker, args=(self._config,)))
            self._workers_pool[-1].start()

        # Monitor loop for commands
        while True:
            time.sleep(5)
            
            cmd = self._workers_db.get_next_command()
            if not cmd:
                continue
            
            if cmd["command"] == "spawn":
                p = Process(target=worker, args=(self._config,))
                p.start()
                self._workers_pool.append(p)
                logging.info(f"Spawned new worker: {p.pid}")
            elif cmd["command"] == "kill":
                worker_id = cmd.get("worker_id")
                if not isinstance(worker_id, int) or isinstance(worker_id, bool) or worker_id <= 0:
                    logging.warning("Rejected kill command with invalid worker_id: %r", worker_id)
                    continue

                managed_worker = self._get_worker_from_pool(worker_id)
                if managed_worker is None:
                    logging.warning("Rejected kill command for unknown worker: %s", worker_id)
                    continue

                try:
                    managed_worker.terminate()
                    managed_worker.join(timeout=5)
                except OSError:
                    logging.warning("Failed to terminate worker %s", worker_id)
                    continue

                self._workers_db.set_worker_status(worker_id, "killed")
                logging.info("Killed managed worker: %s", worker_id)
            
            # Clean up finished workers
            self._workers_pool = [w for w in self._workers_pool if w.is_alive()]

    def _get_worker_from_pool(self, worker_id: int) -> Optional[Process]:
        """Return a managed worker process by PID."""
        for worker_process in self._workers_pool:
            if worker_process.pid == worker_id:
                return worker_process
        return None


def _build_registry(tag_worker: TagWorker, llm_worker: LLMWorker, provider_worker: ProviderWorker) -> WorkerRegistry:
    registry = WorkerRegistry()
    registry.register(TASK_DOWNLOAD, provider_worker.handle_download)
    registry.register(TASK_MARK, provider_worker.handle_mark)
    registry.register(TASK_MARK_TELEGRAM, provider_worker.handle_mark_telegram)
    registry.register(TASK_GMAIL_SORT, provider_worker.handle_gmail_sort)
    registry.register(TASK_TAGS, tag_worker.handle_tags)
    registry.register(TASK_LETTERS, tag_worker.handle_letters)
    registry.register(TASK_NER, tag_worker.handle_ner)
    registry.register(TASK_TAGS_SENTIMENT, tag_worker.handle_tags_sentiment)
    registry.register(TASK_CLUSTERING, tag_worker.handle_clustering)
    registry.register(TASK_SNIPPET_CLUSTERING, tag_worker.handle_snippet_clustering)
    registry.register(TASK_W2V, tag_worker.handle_w2v)
    registry.register(TASK_FASTTEXT, tag_worker.handle_fasttext)
    registry.register(TASK_TAGS_GROUP, tag_worker.handle_tags_groups)
    registry.register(TASK_BIGRAMS_RANK, tag_worker.make_bi_grams_rank)
    registry.register(TASK_TAGS_RANK, tag_worker.make_tags_rank)
    registry.register(TASK_CLEAN_BIGRAMS, tag_worker.make_clean_bigrams)
    registry.register(TASK_POST_GROUPING, llm_worker.handle_post_grouping)
    registry.register(TASK_TAG_CLASSIFICATION, llm_worker.handle_tags_classification)
    registry.register(TASK_POST_GROUPING_BATCH, llm_worker.make_post_grouping_batch)
    registry.register(TASK_POST_GROUPING_CLEANUP, llm_worker.handle_post_grouping_cleanup)
    registry.register(
        TASK_TAG_CLASSIFICATION_BATCH, llm_worker.make_tags_classification_batch
    )
    registry.register(TASK_DELETE_FEEDS, tag_worker.handle_delete_feeds)
    return registry


def worker(config: Dict[str, Any]) -> None:
    import os

    # Observability: reset the parent's _initialized flag so this child process
    # gets its own providers. Skip auto_instrument to avoid double-patching
    # libraries already monkey-patched by the parent before fork.
    record_bulk_write = lambda *a, **kw: None  # noqa: E731  # default no-op
    try:
        from rsstag.observability import init_observability, reset_for_child_process
        from rsstag.observability.db_metrics import record_bulk_write, reset_instruments
        from rsstag.observability.worker_instrumentation import (
            instrument_registry,
            instrument_tasks,
        )
        from rsstag.observability.llm_instrumentation import instrument_llm_router
        from rsstag.observability.business_metrics import register_business_metrics
        reset_for_child_process()
        reset_instruments()
        init_observability("rsstag-worker-child", auto_instrument=False)
        _obs_available = True
    except ImportError:
        _obs_available = False

    cl = MongoClient(
        config["settings"]["db_host"],
        int(config["settings"]["db_port"]),
        username=config["settings"]["db_login"]
        if config["settings"]["db_login"]
        else None,
        password=config["settings"]["db_password"]
        if config["settings"]["db_password"]
        else None,
    )

    db = cl[config["settings"]["db_name"]]
    workers_db = RssTagWorkers(db)
    worker_id = os.getpid()

    # Initialize heartbeat
    workers_db.update_heartbeat(worker_id)

    stop_requested: bool = False

    def _request_stop(signum: int, frame: Optional[FrameType]) -> None:
        nonlocal stop_requested
        stop_requested = True
        logging.info("Worker %s received signal %s, stopping", worker_id, signum)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    providers = {
        data_providers.BAZQUX: BazquxProvider(config),
        data_providers.TELEGRAM: TelegramProvider(config, db),
        data_providers.TEXT_FILE: TextFileProvider(config),
        data_providers.GMAIL: GmailProvider(config),
        data_providers.X: XProvider(config),
    }
    users = RssTagUsers(db)
    tasks = RssTagTasks(db)

    tag_worker = TagWorker(db, config)
    llm_worker = LLMWorker(db, config)
    provider_worker = ProviderWorker(db, config, providers, users, tasks, record_bulk_write)
    registry = _build_registry(tag_worker, llm_worker, provider_worker)
    if _obs_available:
        instrument_registry(registry)
        instrument_llm_router(llm_worker._llm)

    if _obs_available:
        instrument_tasks(tasks)
        register_business_metrics(db)
    last_heartbeat = time.time()
    try:
        while not stop_requested:
            try:
                # Update heartbeat every 10 seconds
                if time.time() - last_heartbeat > 10:
                    workers_db.update_heartbeat(worker_id)
                    last_heartbeat = time.time()

                task = tasks.get_task(users)
                task_done = False
                if task["type"] == TASK_NOOP:
                    time.sleep(randint(3, 8))
                    continue
                is_scope_valid, scope_error = tasks.validate_task_scope(
                    task["type"], task.get("scope")
                )
                if not is_scope_valid:
                    logging.warning(
                        "Rejecting invalid task+scope combination. task_id=%s type=%s user=%s error=%s",
                        task.get("_id"),
                        task.get("type"),
                        task.get("user", {}).get("sid"),
                        scope_error,
                    )
                    tasks.mark_task_failed(task.get("_id"), scope_error)
                    task_done = True
                else:
                    task_done = registry.handle(task)
                    if task_done is None:
                        logging.warning("Unknown task type %s", task["type"])
                        task_done = False

                if task_done:
                    tasks.finish_task(task)
                    if task["type"] == TASK_CLUSTERING:
                        users.update_by_sid(task["user"]["sid"], {"in_queue": False})
                else:
                    time.sleep(randint(3, 8))
            except Exception as e:
                logging.error(
                    "worker got exception: {}. {}".format(e, traceback.format_exc())
                )
                time.sleep(randint(3, 8))
    finally:
        try:
            workers_db.delete_worker(worker_id)
            logging.info("Worker %s heartbeat deleted on shutdown", worker_id)
        except Exception as e:
            logging.warning("Failed to delete worker %s heartbeat: %s", worker_id, e)
        cl.close()
