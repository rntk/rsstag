"""Worker handlers for provider-related tasks."""

import logging
import time
import traceback
from typing import Any, Callable, Dict, List

from pymongo.errors import BulkWriteError

from rsstag.providers import providers as data_providers


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

    def handle_download(self, task: Dict[str, Any]) -> bool:
        logging.info("Start downloading for user")
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

        posts_n = 0
        selection = None
        if task.get("data"):
            selection = task["data"].get("selection")
        success = False
        try:
            for posts, feeds in provider.download(provider_user, selection):
                posts_n += len(posts)
                f_ids = [f["feed_id"] for f in feeds]
                c = self._db.feeds.find(
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
                    fee["provider"] = provider_name
                    n_feeds.append(fee)
                if posts:
                    # 1. Local deduplication of incoming posts by 'id'
                    unique_incoming_posts = {}
                    for post in posts:
                        p_id = post.get("id")
                        if p_id and p_id not in unique_incoming_posts:
                            post["provider"] = provider_name
                            unique_incoming_posts[p_id] = post
                    
                    if unique_incoming_posts:
                        p_ids = list(unique_incoming_posts.keys())
                        
                        # 2. Query DB to find existing posts by owner and 'id'
                        # We exclude 'provider' from filter to be more robust
                        # against missing or differently-cased provider fields.
                        existing_posts = self._db.posts.find(
                            {
                                "owner": task["user"]["sid"],
                                "id": {"$in": p_ids},
                            },
                            projection={"id": True, "_id": False},
                        )
                        skip_p_ids = {pc["id"] for pc in existing_posts}

                        n_posts = [
                            post for p_id, post in unique_incoming_posts.items()
                            if p_id not in skip_p_ids
                        ]

                        if n_posts:
                            try:
                                self._db.posts.insert_many(n_posts, ordered=False)
                                self._record_bulk_write("posts", len(n_posts))
                            except BulkWriteError as bulk_err:
                                # Ignore duplicate key errors (code 11000), re-raise others
                                non_dup = [
                                    e for e in bulk_err.details.get("writeErrors", [])
                                    if e.get("code") != 11000
                                ]
                                if non_dup:
                                    raise
                if n_feeds:
                    self._db.feeds.insert_many(n_feeds)
                    self._record_bulk_write("feeds", len(n_feeds))
            success = True
        except Exception as e:
            logging.error(
                "Can`t save in db for user %s. Info: %s. %s",
                task["user"]["sid"],
                e,
                traceback.format_exc(),
            )
            logging.info("Saved posts: %s.", posts_n)
            self._handle_provider_error(task, provider_name, e)
        finally:
            self._save_refreshed_oauth_token(task, provider_user, provider_name)

        if success:
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
