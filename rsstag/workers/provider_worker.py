"""Worker handlers for provider-related tasks."""

import logging
import traceback
from typing import Any, Callable, Dict

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

    def _save_refreshed_gmail_token(self, task: Dict[str, Any], provider_user: Dict[str, Any], provider_name: str) -> None:
        if provider_name != data_providers.GMAIL:
            return
        if not provider_user.get("token_refreshed"):
            return

        update_data = {
            "token": provider_user.get("token") or provider_user.get("access_token"),
            "retoken": False,
        }
        refresh_token = provider_user.get("refresh_token")
        if refresh_token:
            update_data["refresh_token"] = refresh_token

        self._users.update_provider(task["user"]["sid"], provider_name, update_data)

    def handle_download(self, task: Dict[str, Any]) -> bool:
        logging.info("Start downloading for user")
        provider_name = task["data"].get("provider") or task["user"].get("provider")
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
        finally:
            self._save_refreshed_gmail_token(task, provider_user, provider_name)

        return success

    def handle_mark(self, task: Dict[str, Any]) -> bool:
        provider_name = task["data"].get("provider") or task["user"].get("provider")
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
        self._save_refreshed_gmail_token(task, provider_user, provider_name)
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
        self._save_refreshed_gmail_token(task, provider_user, data_providers.GMAIL)
        return sorted_emails
