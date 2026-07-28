"""Worker handlers for provider-related tasks."""

import logging
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple

from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

from rsstag.providers import providers as data_providers
from rsstag.providers.feed_docs import dedup_feed_docs


class ProviderWorker:
    """Handles tasks that interact with external providers like Bazqux, Telegram, etc."""

    def __init__(self, db: Any, config: Dict[str, Any], providers: Dict[str, Any], users: Any, tasks: Any, record_bulk_write: Callable[[str, int], None]):
        self._db = db
        self._config = config
        self._providers = providers
        self._users = users
        self._tasks = tasks
        self._record_bulk_write = record_bulk_write

    def _save_refreshed_oauth_token(self, task: Dict[str, Any], provider_user: Dict[str, Any], provider_name: str) -> None:
        if provider_name not in (data_providers.GMAIL, data_providers.X):
            return
        if not provider_user.get("token_refreshed"):
            return

        update_data = {
            "token": provider_user.get("token") or provider_user.get("access_token"),
            "access_token": provider_user.get("access_token") or provider_user.get("token"),
            "retoken": False,
        }
        refresh_token = provider_user.get("refresh_token")
        if refresh_token:
            update_data["refresh_token"] = refresh_token
        token_expires_at = provider_user.get("token_expires_at")
        if token_expires_at:
            update_data["token_expires_at"] = token_expires_at

        self._users.update_provider(task["user"]["sid"], provider_name, update_data)

    def _save_provider_updates(self, task: Dict[str, Any], provider_user: Dict[str, Any], provider_name: str) -> None:
        provider_updates = provider_user.get("provider_updates")
        if not provider_updates:
            return
        self._users.update_provider(task["user"]["sid"], provider_name, provider_updates)

    def _handle_provider_error(
        self,
        task: Dict[str, Any],
        provider_name: str,
        error: Exception,
    ) -> None:
        error_text = str(error)
        user_message = getattr(error, "user_message", "") or error_text
        retoken = bool(getattr(error, "retoken", False))
        if retoken:
            self._tasks.freeze_tasks(task["user"], task["type"])
            self._users.update_provider(
                task["user"]["sid"], provider_name, {"retoken": True}
            )
        else:
            self._tasks.mark_task_failed(task.get("_id"), error_text)
        self._users.update_by_sid(task["user"]["sid"], {"message": user_message})

    def _prepare_new_posts(
        self,
        owner: str,
        provider_name: str,
        posts: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Return posts not already stored, using the provider-scoped PID."""
        unique_posts: Dict[str, Dict[str, Any]] = {}
        skipped_count: int = 0
        for post in posts:
            pid_value: Any = post.get("pid")
            if not pid_value:
                skipped_count += 1
                logging.warning(
                    "Skipping %s post without pid. feed_id=%s id=%s",
                    provider_name,
                    post.get("feed_id"),
                    post.get("id"),
                )
                continue

            pid: str = str(pid_value)
            if pid in unique_posts:
                skipped_count += 1
                continue
            post["provider"] = provider_name
            unique_posts[pid] = post

        if not unique_posts:
            return [], skipped_count

        existing_posts: Any = self._db.posts.find(
            {
                "owner": owner,
                "pid": {"$in": list(unique_posts)},
            },
            projection={"pid": True, "_id": False},
        )
        existing_pids: set[str] = {
            str(post["pid"]) for post in existing_posts if post.get("pid")
        }
        skipped_count += len(existing_pids)
        new_posts: List[Dict[str, Any]] = [
            post
            for pid, post in unique_posts.items()
            if pid not in existing_pids
        ]
        return new_posts, skipped_count

    def _insert_posts(
        self,
        provider_name: str,
        posts: List[Dict[str, Any]],
    ) -> Tuple[int, int]:
        """Insert posts and report inserted and duplicate-conflict counts."""
        if not posts:
            return 0, 0

        try:
            self._db.posts.insert_many(posts, ordered=False)
        except BulkWriteError as bulk_error:
            details: Dict[str, Any] = bulk_error.details or {}
            write_errors: List[Dict[str, Any]] = details.get("writeErrors", [])
            duplicate_errors: List[Dict[str, Any]] = [
                error for error in write_errors if error.get("code") == 11000
            ]
            non_duplicate_errors: List[Dict[str, Any]] = [
                error for error in write_errors if error.get("code") != 11000
            ]
            write_concern_errors: List[Dict[str, Any]] = details.get(
                "writeConcernErrors", []
            )
            inserted_count: int = int(details.get("nInserted", 0))
            duplicate_count: int = len(duplicate_errors)
            if inserted_count:
                self._record_bulk_write("posts", inserted_count)
            if duplicate_count:
                key_patterns: List[Dict[str, Any]] = [
                    error.get("keyPattern", {}) for error in duplicate_errors
                ]
                logging.warning(
                    "Skipped %d %s posts because of duplicate-key conflicts. "
                    "Index keys: %s",
                    duplicate_count,
                    provider_name,
                    key_patterns,
                )
            if non_duplicate_errors or write_concern_errors:
                raise
            return inserted_count, duplicate_count

        inserted_count = len(posts)
        self._record_bulk_write("posts", inserted_count)
        return inserted_count, 0

    def _store_feeds(
        self,
        owner: str,
        provider_name: str,
        feeds: List[Dict[str, Any]],
        refresh_titles: bool = False,
    ) -> Tuple[int, int]:
        """Insert feeds the owner does not have yet; report (new, known).

        Sources arrive from several paths (posts download, raw conversion, a
        sources-list refresh), so the same feed is offered over and over. The
        ``feed_id`` is the identity: anything already stored for this owner is
        skipped instead of inserted a second time.
        """
        unique_feeds: List[Dict[str, Any]] = dedup_feed_docs(feeds)
        if not unique_feeds:
            return 0, 0

        feed_ids: List[str] = [feed["feed_id"] for feed in unique_feeds]
        existing_feeds: Any = self._db.feeds.find(
            {"owner": owner, "feed_id": {"$in": feed_ids}},
            projection={"feed_id": True, "_id": False},
        )
        existing_feed_ids: set[str] = {feed["feed_id"] for feed in existing_feeds}
        new_feeds: List[Dict[str, Any]] = []
        title_updates: List[UpdateOne] = []
        for feed in unique_feeds:
            if feed["feed_id"] not in existing_feed_ids:
                feed["provider"] = provider_name
                new_feeds.append(feed)
            elif refresh_titles:
                title_updates.append(
                    UpdateOne(
                        {"owner": owner, "feed_id": feed["feed_id"]},
                        {
                            "$set": {
                                "title": feed["title"],
                                "provider": provider_name,
                            }
                        },
                    )
                )

        if new_feeds:
            self._db.feeds.insert_many(new_feeds)
            self._record_bulk_write("feeds", len(new_feeds))
        if title_updates:
            self._db.feeds.bulk_write(title_updates, ordered=False)

        return len(new_feeds), len(unique_feeds) - len(new_feeds)

    def handle_feeds_list(self, task: Dict[str, Any]) -> bool:
        """Refresh the stored list of sources for one provider, without posts.

        Providers opt in by implementing ``list_feeds``; a provider without it
        simply has nothing to refresh. Nothing here is provider specific.
        """
        provider_name: str = task["data"].get("provider")
        owner: str = task["user"]["sid"]
        provider_user: Optional[Dict[str, Any]] = self._users.get_provider_user(
            task["user"], provider_name
        )
        if not provider_user:
            logging.warning(
                "No provider credentials for %s on user %s", provider_name, owner
            )
            return True

        provider: Any = self._providers.get(provider_name)
        if not provider:
            error: str = f"Unknown provider {provider_name}"
            logging.warning(error)
            self._tasks.mark_task_failed(task.get("_id"), error)
            return False
        if not data_providers.supports_feeds_list(provider):
            error = f"Provider {provider_name} can`t list sources"
            logging.warning(error)
            self._tasks.mark_task_failed(task.get("_id"), error)
            return False

        try:
            feeds: List[Dict[str, Any]] = provider.list_feeds(provider_user)
            new_count: int
            known_count: int
            new_count, known_count = self._store_feeds(
                owner, provider_name, feeds, refresh_titles=True
            )
        except Exception as e:
            logging.error(
                "Can`t refresh %s sources list for user %s. Info: %s. %s",
                provider_name,
                owner,
                e,
                traceback.format_exc(),
            )
            self._handle_provider_error(task, provider_name, e)
            # A failed refresh must not keep the provider queue flag raised:
            # otherwise every later download for this provider is rejected.
            self._users.update_by_sid(owner, {f"in_queue.{provider_name}": False})
            return False
        finally:
            self._save_refreshed_oauth_token(task, provider_user, provider_name)

        logging.info(
            "Refreshed %s sources for user %s. New=%d already known=%d",
            provider_name,
            owner,
            new_count,
            known_count,
        )
        self._save_provider_updates(task, provider_user, provider_name)
        self._users.update_by_sid(
            owner,
            {
                "message": f"Sources list updated: {new_count} new, "
                f"{known_count} already known"
            },
        )

        return True

    def handle_download(self, task: Dict[str, Any]) -> bool:
        """Incrementally download new posts/feeds for one connected source.

        Contract: this task is strictly additive. It never deletes posts or
        feeds and never wipes prior data when switching/refreshing a source.
        Incoming posts are deduped against existing rows by their canonical
        ``pid`` (per owner) and feeds by ``feed_id``; only genuinely new
        documents are inserted, so re-running it only fetches and stores the
        diff. Bulk cleanup is the job of the separate (future) prune task, not
        download.
        """
        logging.info("Start downloading for user")
        provider_name: str = task["data"].get("provider")
        provider_user: Optional[Dict[str, Any]] = self._users.get_provider_user(
            task["user"], provider_name
        )
        if not provider_user:
            logging.warning(
                "No provider credentials for %s on user %s",
                provider_name,
                task["user"]["sid"],
            )
            return True

        provider: Any = self._providers.get(provider_name)
        if not provider:
            error: str = f"Unknown provider {provider_name}"
            logging.warning(error)
            self._tasks.mark_task_failed(task.get("_id"), error)
            return False

        received_count: int = 0
        inserted_count: int = 0
        skipped_count: int = 0
        selection: Any = None
        if task.get("data"):
            selection = task["data"].get("selection")
        success: bool = False
        try:
            posts: List[Dict[str, Any]]
            feeds: List[Dict[str, Any]]
            for posts, feeds in provider.download(provider_user, selection):
                received_count += len(posts)
                if posts:
                    new_posts: List[Dict[str, Any]]
                    filtered_count: int
                    new_posts, filtered_count = self._prepare_new_posts(
                        task["user"]["sid"], provider_name, posts
                    )
                    skipped_count += filtered_count
                    batch_inserted: int
                    duplicate_count: int
                    batch_inserted, duplicate_count = self._insert_posts(
                        provider_name, new_posts
                    )
                    inserted_count += batch_inserted
                    skipped_count += duplicate_count
                if feeds:
                    self._store_feeds(task["user"]["sid"], provider_name, feeds)
            success = True
        except Exception as e:
            logging.error(
                "Can`t save in db for user %s. Received=%d inserted=%d "
                "skipped=%d. Info: %s. %s",
                task["user"]["sid"],
                received_count,
                inserted_count,
                skipped_count,
                e,
                traceback.format_exc(),
            )
            self._handle_provider_error(task, provider_name, e)
        finally:
            self._save_refreshed_oauth_token(task, provider_user, provider_name)

        if success:
            logging.info(
                "Completed %s download for user %s. Received=%d inserted=%d "
                "skipped=%d",
                provider_name,
                task["user"]["sid"],
                received_count,
                inserted_count,
                skipped_count,
            )
            self._save_provider_updates(task, provider_user, provider_name)

        return success

    def _ensure_raw_indexes(self) -> None:
        try:
            self._db.raw_posts.create_index(
                [("owner", 1), ("provider", 1), ("external_id", 1)],
                unique=True,
            )
            self._db.raw_posts.create_index(
                [("owner", 1), ("provider", 1), ("stream_id", 1)]
            )
            self._db.raw_download_state.create_index(
                [("owner", 1), ("provider", 1), ("stream_id", 1)],
                unique=True,
            )
        except Exception as e:
            logging.warning(
                "Can`t create raw download indexes. May already exist. Info: %s",
                e,
            )

    def _insert_raw_posts(self, docs: List[Dict[str, Any]]) -> int:
        if not docs:
            return 0
        owner = docs[0]["owner"]
        provider_name = docs[0]["provider"]
        ext_ids = [d["external_id"] for d in docs]
        existing = self._db.raw_posts.find(
            {
                "owner": owner,
                "provider": provider_name,
                "external_id": {"$in": ext_ids},
            },
            projection={"external_id": True, "_id": False},
        )
        skip = {e["external_id"] for e in existing}
        new_docs = [d for d in docs if d["external_id"] not in skip]
        if not new_docs:
            return 0
        try:
            self._db.raw_posts.insert_many(new_docs, ordered=False)
        except BulkWriteError as bulk_err:
            # Concurrent run may have inserted the same id; ignore duplicate
            # key errors (11000), re-raise anything else.
            non_dup = [
                e
                for e in bulk_err.details.get("writeErrors", [])
                if e.get("code") != 11000
            ]
            if non_dup:
                raise
        self._record_bulk_write("raw_posts", len(new_docs))
        return len(new_docs)

    def handle_raw_download(self, task: Dict[str, Any]) -> bool:
        """Incrementally archive untransformed provider data into raw_posts.

        Only the per-chat diff is fetched (provider stops at the stored
        cursor). The cursor is advanced only when the provider reports a chat
        fully caught up, so an interrupted run safely re-scans and dedupes
        instead of skipping un-fetched older history.
        """
        provider_name = task["data"].get("provider")
        provider_user = self._users.get_provider_user(
            task["user"], provider_name
        )
        if not provider_user:
            logging.warning(
                "No provider credentials for %s on user %s",
                provider_name,
                task["user"]["sid"],
            )
            return True

        provider = self._providers.get(provider_name)
        download_raw = getattr(provider, "download_raw", None)
        if provider is None or not callable(download_raw):
            error = f"Provider {provider_name} does not support raw download"
            logging.warning(error)
            self._tasks.mark_task_failed(task.get("_id"), error)
            return False

        owner = task["user"]["sid"]
        self._ensure_raw_indexes()
        cursors: Dict[str, int] = {
            str(doc["stream_id"]): int(doc.get("cursor", 0))
            for doc in self._db.raw_download_state.find(
                {"owner": owner, "provider": provider_name},
                projection={"stream_id": True, "cursor": True, "_id": False},
            )
        }

        saved_n = 0
        success = False
        stream_max: Dict[str, int] = {}
        try:
            for chat, messages, chat_done in download_raw(
                provider_user, cursors
            ):
                stream_id = str(chat["id"])
                running_max = stream_max.get(
                    stream_id, cursors.get(stream_id, 0)
                )
                if messages:
                    docs: List[Dict[str, Any]] = []
                    for message in messages:
                        msg_id = int(message["id"])
                        if msg_id > running_max:
                            running_max = msg_id
                        docs.append(
                            {
                                "owner": owner,
                                "provider": provider_name,
                                "stream_id": stream_id,
                                "external_id": f"{stream_id}:{msg_id}",
                                "msg_id": msg_id,
                                "raw": message,
                                "downloaded_at": time.time(),
                            }
                        )
                    saved_n += self._insert_raw_posts(docs)
                stream_max[stream_id] = running_max
                if chat_done:
                    self._db.raw_download_state.update_one(
                        {
                            "owner": owner,
                            "provider": provider_name,
                            "stream_id": stream_id,
                        },
                        {
                            "$set": {
                                "owner": owner,
                                "provider": provider_name,
                                "stream_id": stream_id,
                                "cursor": stream_max.get(
                                    stream_id, cursors.get(stream_id, 0)
                                ),
                                "raw_chat": chat,
                                "updated_at": time.time(),
                            }
                        },
                        upsert=True,
                    )
            success = True
        except Exception as e:
            logging.error(
                "Raw download failed for user %s. Info: %s. %s",
                owner,
                e,
                traceback.format_exc(),
            )
            logging.info("Raw download saved messages so far: %s", saved_n)
            self._handle_provider_error(task, provider_name, e)

        logging.info(
            "Raw download finished for %s. Saved %d new messages.",
            owner,
            saved_n,
        )
        return success

    def _store_converted_posts(
        self,
        owner: str,
        provider_name: str,
        posts: List[Dict[str, Any]],
        feeds: List[Dict[str, Any]],
    ) -> None:
        if feeds:
            f_ids = [f["feed_id"] for f in feeds]
            existing = self._db.feeds.find(
                {"owner": owner, "feed_id": {"$in": f_ids}},
                projection={"feed_id": True, "_id": False},
            )
            skip = {fc["feed_id"] for fc in existing}
            n_feeds = []
            for fee in feeds:
                if fee["feed_id"] in skip:
                    continue
                fee["provider"] = provider_name
                n_feeds.append(fee)
            if n_feeds:
                self._db.feeds.insert_many(n_feeds)
                self._record_bulk_write("feeds", len(n_feeds))

        if not posts:
            return
        unique: Dict[str, Dict[str, Any]] = {}
        for post in posts:
            pid = post.get("pid")
            if pid and pid not in unique:
                post["provider"] = provider_name
                unique[pid] = post
        if not unique:
            return
        pids = list(unique.keys())
        existing = self._db.posts.find(
            {"owner": owner, "pid": {"$in": pids}},
            projection={"pid": True, "_id": False},
        )
        skip = {pc["pid"] for pc in existing}
        n_posts = [p for pid, p in unique.items() if pid not in skip]
        if not n_posts:
            return
        try:
            self._db.posts.insert_many(n_posts, ordered=False)
            self._record_bulk_write("posts", len(n_posts))
        except BulkWriteError as bulk_err:
            non_dup = [
                e
                for e in bulk_err.details.get("writeErrors", [])
                if e.get("code") != 11000
            ]
            if non_dup:
                raise

    def handle_raw_to_posts(self, task: Dict[str, Any]) -> bool:
        """Incrementally convert archived raw data into the posts collection.

        Only raw_posts docs not yet marked ``posts_converted`` are processed,
        deduped against existing posts by pid, and the source raw docs are
        marked converted afterwards so re-runs only handle new data. Does not
        chain into the tag pipeline (run Build Tags separately).
        """
        provider_name = task["data"].get("provider")
        provider = self._providers.get(provider_name)
        transform = getattr(provider, "raw_messages_to_posts", None)
        if provider is None or not callable(transform):
            error = (
                f"Provider {provider_name} does not support raw->posts "
                f"conversion"
            )
            logging.warning(error)
            self._tasks.mark_task_failed(task.get("_id"), error)
            return False

        owner = task["user"]["sid"]
        self._ensure_raw_indexes()
        chat_by_stream = {
            str(doc["stream_id"]): doc.get("raw_chat", {})
            for doc in self._db.raw_download_state.find(
                {"owner": owner, "provider": provider_name},
                projection={"stream_id": True, "raw_chat": True, "_id": False},
            )
        }

        converted_n = 0
        batch_size = 500
        success = False
        try:
            while True:
                raw_docs = list(
                    self._db.raw_posts.find(
                        {
                            "owner": owner,
                            "provider": provider_name,
                            "posts_converted": {"$exists": False},
                        },
                        projection={"raw": True},
                    ).limit(batch_size)
                )
                if not raw_docs:
                    break
                messages = [
                    d["raw"]
                    for d in raw_docs
                    if isinstance(d.get("raw"), dict)
                ]
                posts, feeds = transform(owner, messages, chat_by_stream)
                self._store_converted_posts(
                    owner, provider_name, posts, feeds
                )
                ids = [d["_id"] for d in raw_docs]
                self._db.raw_posts.update_many(
                    {"_id": {"$in": ids}},
                    {"$set": {"posts_converted": 1}},
                )
                converted_n += len(ids)
                if len(raw_docs) < batch_size:
                    break
            success = True
        except Exception as e:
            logging.error(
                "Raw->posts failed for user %s. Info: %s. %s",
                owner,
                e,
                traceback.format_exc(),
            )
            self._handle_provider_error(task, provider_name, e)

        logging.info(
            "Raw->posts finished for %s. Converted %d raw docs.",
            owner,
            converted_n,
        )
        return success

    def handle_mark(self, task: Dict[str, Any]) -> bool:
        provider_name = task["data"].get("provider")
        provider_user = self._users.get_provider_user(task["user"], provider_name)
        if not provider_user:
            logging.warning(
                "No provider credentials for %s on user %s",
                provider_name,
                task["user"]["sid"],
            )
            return True
        provider = self._providers.get(provider_name)
        if not provider:
            error = f"Unknown provider {provider_name}"
            logging.warning(error)
            self._tasks.mark_task_failed(task.get("_id"), error)
            return False

        marked = provider.mark(task["data"], provider_user)
        if marked is None:
            self._tasks.freeze_tasks(task["user"], task["type"])
            self._users.update_provider(
                task["user"]["sid"], provider_name, {"retoken": True}
            )
            return False
        self._save_refreshed_oauth_token(task, provider_user, provider_name)
        return marked

    def handle_mark_telegram(self, task: Dict[str, Any]) -> bool:
        provider = self._providers.get(data_providers.TELEGRAM)
        if not provider:
            error = "Unknown provider telegram"
            logging.warning(error)
            self._tasks.mark_task_failed(task.get("_id"), error)
            return False

        provider_user = self._users.get_provider_user(
            task["user"], data_providers.TELEGRAM
        )
        if not provider_user:
            logging.warning(
                "No provider credentials for telegram on user %s",
                task["user"]["sid"],
            )
            return True

        marked = provider.mark_all(task["data"], provider_user)
        if marked is None:
            self._tasks.freeze_tasks(task["user"], task["type"])
            self._users.update_provider(
                task["user"]["sid"],
                data_providers.TELEGRAM,
                {"retoken": True},
            )
            return False
        return marked

    def handle_gmail_sort(self, task: Dict[str, Any]) -> bool:
        provider = self._providers.get(data_providers.GMAIL)
        if not provider:
            error = "Unknown provider gmail"
            logging.warning(error)
            self._tasks.mark_task_failed(task.get("_id"), error)
            return False

        provider_user = self._users.get_provider_user(
            task["user"], data_providers.GMAIL
        )
        if not provider_user:
            logging.warning(
                "No provider credentials for gmail on user %s",
                task["user"]["sid"],
            )
            return True

        sorted_emails = provider.sort_emails_by_domain(provider_user)
        if sorted_emails is None:
            self._tasks.freeze_tasks(task["user"], task["type"])
            self._users.update_provider(
                task["user"]["sid"],
                data_providers.GMAIL,
                {"retoken": True},
            )
            return False
        self._save_refreshed_oauth_token(task, provider_user, data_providers.GMAIL)
        return sorted_emails
