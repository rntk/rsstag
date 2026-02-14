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

import rsstag.providers.providers as data_providers
from rsstag.providers.bazqux import BazquxProvider
from rsstag.providers.gmail import GmailProvider
from rsstag.providers.telegram import TelegramProvider
from rsstag.providers.textfile import TextFileProvider
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
from rsstag.workers_db import RssTagWorkers


class RSSTagWorkerDispatcher:
    """Rsstag workers handler"""

    def __init__(self, config_path, log_file=None):
        self._config = load_config(config_path)
        self._workers_pool = []
        target_log = log_file
        if not target_log:
            target_log = self._config["settings"].get("worker_log_file", self._config["settings"]["log_file"])
        logging.basicConfig(
            filename=target_log,
            filemode="a",
            level=getattr(logging, self._config["settings"]["log_level"].upper()),
        )
        cl = MongoClient(
            self._config["settings"]["db_host"],
            int(self._config["settings"]["db_port"]),
            username=self._config["settings"]["db_login"] if self._config["settings"]["db_login"] else None,
            password=self._config["settings"]["db_password"] if self._config["settings"]["db_password"] else None,
        )
        db = cl[self._config["settings"]["db_name"]]
        self._workers_db = RssTagWorkers(db)

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


def _build_registry(tag_worker: TagWorker, llm_worker: LLMWorker) -> WorkerRegistry:
    registry = WorkerRegistry()
    registry.register(TASK_TAGS, tag_worker.handle_tags)
    registry.register(TASK_LETTERS, tag_worker.handle_letters)
    registry.register(TASK_NER, tag_worker.handle_ner)
    registry.register(TASK_TAGS_SENTIMENT, tag_worker.handle_tags_sentiment)
    registry.register(TASK_CLUSTERING, tag_worker.handle_clustering)
    registry.register(TASK_W2V, tag_worker.handle_w2v)
    registry.register(TASK_FASTTEXT, tag_worker.handle_fasttext)
    registry.register(TASK_TAGS_GROUP, tag_worker.handle_tags_groups)
    registry.register(TASK_BIGRAMS_RANK, tag_worker.make_bi_grams_rank)
    registry.register(TASK_TAGS_RANK, tag_worker.make_tags_rank)
    registry.register(TASK_CLEAN_BIGRAMS, tag_worker.make_clean_bigrams)
    registry.register(TASK_POST_GROUPING, llm_worker.handle_post_grouping)
    registry.register(TASK_TAG_CLASSIFICATION, llm_worker.handle_tags_classification)
    registry.register(TASK_POST_GROUPING_BATCH, llm_worker.make_post_grouping_batch)
    registry.register(
        TASK_TAG_CLASSIFICATION_BATCH, llm_worker.make_tags_classification_batch
    )
    registry.register(TASK_DELETE_FEEDS, tag_worker.handle_delete_feeds)
    return registry


def worker(config: Dict[str, Any]) -> None:
    import os

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

    tag_worker = TagWorker(db, config)
    llm_worker = LLMWorker(db, config)
    registry = _build_registry(tag_worker, llm_worker)

    providers = {
        data_providers.BAZQUX: BazquxProvider(config),
        data_providers.TELEGRAM: TelegramProvider(config, db),
        data_providers.TEXT_FILE: TextFileProvider(config),
        data_providers.GMAIL: GmailProvider(config),
    }
    users = RssTagUsers(db)
    tasks = RssTagTasks(db)
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
                if task["type"] == TASK_DOWNLOAD:
                    logging.info("Start downloading for user")
                    if tag_worker.clear_user_data(task["user"]):
                        provider_name = task["data"].get("provider") or task["user"].get(
                            "provider"
                        )
                        provider_user = users.get_provider_user(task["user"], provider_name)
                        if not provider_user:
                            logging.warning(
                                "No provider credentials for %s on user %s",
                                provider_name,
                                task["user"]["sid"],
                            )
                            task_done = True
                        else:
                            provider = providers[provider_name]
                            posts_n = 0
                            selection = None
                            if task.get("data"):
                                selection = task["data"].get("selection")
                            try:
                                for posts, feeds in provider.download(
                                    provider_user, selection
                                ):
                                    posts_n += len(posts)
                                    f_ids = [f["feed_id"] for f in feeds]
                                    c = db.feeds.find(
                                        {
                                            "owner": task["user"]["sid"],
                                            "feed_id": {"$in": f_ids},
                                        },
                                        projection={"feed_id": True, "_id": False},
                                    )
                                    skip_ids = {fc["feed_id"] for fc in c}
                                    n_feeds = []
                                    for fee in feeds:
                                        if fee["feed_id"] in skip_ids:
                                            continue
                                        n_feeds.append(fee)
                                    if posts:
                                        db.posts.insert_many(posts)
                                    if n_feeds:
                                        db.feeds.insert_many(n_feeds)
                                task_done = True
                            except Exception as e:
                                task_done = False
                                logging.error(
                                    "Can`t save in db for user %s. Info: %s. %s",
                                    task["user"]["sid"],
                                    e,
                                    traceback.format_exc(),
                                )
                            logging.info("Saved posts: %s.", posts_n)

                elif task["type"] == TASK_MARK:
                    provider_name = task["data"].get("provider") or task["user"].get(
                        "provider"
                    )
                    provider_user = users.get_provider_user(task["user"], provider_name)
                    if not provider_user:
                        logging.warning(
                            "No provider credentials for %s on user %s",
                            provider_name,
                            task["user"]["sid"],
                        )
                        task_done = True
                    else:
                        provider = providers[provider_name]
                        marked = provider.mark(task["data"], provider_user)
                        if marked is None:
                            tasks.freeze_tasks(task["user"], task["type"])
                            users.update_provider(
                                task["user"]["sid"], provider_name, {"retoken": True}
                            )
                            task_done = False
                        else:
                            task_done = marked
                elif task["type"] == TASK_MARK_TELEGRAM:
                    provider = providers[data_providers.TELEGRAM]
                    provider_user = users.get_provider_user(
                        task["user"], data_providers.TELEGRAM
                    )
                    if not provider_user:
                        logging.warning(
                            "No provider credentials for telegram on user %s",
                            task["user"]["sid"],
                        )
                        task_done = True
                    else:
                        marked = provider.mark_all(task["data"], provider_user)
                        if marked is None:
                            tasks.freeze_tasks(task["user"], task["type"])
                            users.update_provider(
                                task["user"]["sid"],
                                data_providers.TELEGRAM,
                                {"retoken": True},
                            )
                            task_done = False
                        else:
                            task_done = marked
                elif task["type"] == TASK_GMAIL_SORT:
                    provider = providers[data_providers.GMAIL]
                    provider_user = users.get_provider_user(
                        task["user"], data_providers.GMAIL
                    )
                    if not provider_user:
                        logging.warning(
                            "No provider credentials for gmail on user %s",
                            task["user"]["sid"],
                        )
                        task_done = True
                    else:
                        sorted_emails = provider.sort_emails_by_domain(provider_user)
                        if sorted_emails is None:
                            tasks.freeze_tasks(task["user"], task["type"])
                            users.update_provider(
                                task["user"]["sid"],
                                data_providers.GMAIL,
                                {"retoken": True},
                            )
                            task_done = False
                        else:
                            task_done = sorted_emails
                else:
                    task_done = registry.handle(task)
                    if task_done is None:
                        logging.warning("Unknown task type %s", task["type"])
                        task_done = False

                if task_done:
                    tasks.finish_task(task)
                    if task["type"] == TASK_CLUSTERING:
                        users.update_by_sid(task["user"]["sid"], {"in_queue": False})
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
