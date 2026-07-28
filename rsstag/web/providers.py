import logging
import asyncio
import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from werkzeug.wrappers import Request, Response
from werkzeug.utils import redirect

import rsstag.providers.providers as data_providers
from rsstag.providers.bazqux import BazquxProvider
from rsstag.providers.telegram import TelegramProvider
from rsstag.providers.x import XProvider
from rsstag.tasks import TASK_DOWNLOAD

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication


_TLG_LOAD_MODES = ("unread", "limit", "unread_or_limit")
_TLG_MAX_SINGLE_FEED_POSTS = 10000


def _empty_selection() -> Dict[str, object]:
    return {
        "channels": [],
        "feeds": [],
        "categories": [],
        "telegram_load_mode": "unread_or_limit",
        "telegram_load_limit": 100,
    }


def _parse_tlg_limit(value: str, default: int = 100) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    if n < 1:
        return default
    if n > 100000:
        return 100000
    return n


def _get_selection(request: Request) -> Dict[str, object]:
    mode = request.form.get("tlg_load_mode", "unread_or_limit")
    if mode not in _TLG_LOAD_MODES:
        mode = "unread_or_limit"
    limit_n = _parse_tlg_limit(request.form.get("tlg_load_limit", ""))
    return {
        "channels": request.form.getlist("channels"),
        "feeds": request.form.getlist("feeds"),
        "categories": request.form.getlist("categories"),
        "telegram_load_mode": mode,
        "telegram_load_limit": limit_n,
    }


def _telegram_limit_from_selection(selection: Dict[str, object]) -> int:
    mode = selection.get("telegram_load_mode", "unread_or_limit")
    n = int(selection.get("telegram_load_limit", 100) or 100)
    if mode == "unread":
        return 0
    if mode == "limit":
        return n
    return -n


def _json_response(payload: Dict[str, object], status: int = 200) -> Response:
    return Response(json.dumps(payload), mimetype="application/json", status=status)


def _parse_single_feed_request(
    request: Request,
) -> Tuple[Optional[str], Optional[int], str]:
    try:
        data: Any = json.loads(request.data or b"{}")
    except (TypeError, ValueError) as exc:
        logging.warning("Invalid single-feed refresh request: %s", exc)
        return None, None, "Invalid request body"

    if not isinstance(data, dict):
        return None, None, "Invalid request body"

    feed_id: str = str(data.get("feed_id", "")).strip()
    posts_count_value: object = data.get("posts_count")
    if not feed_id:
        return None, None, "Feed is required"
    if isinstance(posts_count_value, bool):
        return None, None, "Post count must be a whole number"

    try:
        posts_count: int = int(posts_count_value)
    except (TypeError, ValueError):
        return None, None, "Post count must be a whole number"

    if str(posts_count_value).strip() != str(posts_count):
        return None, None, "Post count must be a whole number"
    if posts_count < 1 or posts_count > _TLG_MAX_SINGLE_FEED_POSTS:
        return (
            None,
            None,
            f"Post count must be between 1 and {_TLG_MAX_SINGLE_FEED_POSTS}",
        )

    return feed_id, posts_count, ""


def _single_feed_selection(feed_id: str, posts_count: int) -> Dict[str, object]:
    return {
        "channels": [feed_id],
        "feeds": [],
        "categories": [],
        "telegram_load_mode": "limit",
        "telegram_load_limit": posts_count,
        "telegram_limit": posts_count,
    }


def on_provider_feed_download_post(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    """Queue a bounded refresh for one Telegram feed owned by the user."""
    parsed_request: Tuple[Optional[str], Optional[int], str] = (
        _parse_single_feed_request(request)
    )
    feed_id, posts_count, error = parsed_request
    if feed_id is None or posts_count is None:
        return _json_response({"status": "error", "message": error}, status=400)

    feed: Optional[dict] = app.feeds.get_by_feed_id(user["sid"], feed_id)
    if feed is None:
        return _json_response(
            {"status": "error", "message": "Feed was not found"}, status=404
        )
    if feed.get("provider") != data_providers.TELEGRAM:
        return _json_response(
            {
                "status": "error",
                "message": "Single-feed refresh is available only for Telegram",
            },
            status=400,
        )
    if not app.users.is_provider_connected(user, data_providers.TELEGRAM):
        return _json_response(
            {"status": "error", "message": "Telegram provider is not connected"},
            status=400,
        )

    try:
        app.users.reset_in_queue_if_legacy(user["sid"], user)
        if app.users.get_in_queue(user).get(data_providers.TELEGRAM, False):
            return _json_response(
                {
                    "status": "error",
                    "message": "A Telegram download is already in progress",
                },
                status=409,
            )

        added: bool = app.tasks.add_task(
            {
                "type": TASK_DOWNLOAD,
                "user": user["sid"],
                "host": request.environ.get(
                    "HTTP_HOST", app.config["settings"]["host_name"]
                ),
                "provider": data_providers.TELEGRAM,
                "selection": _single_feed_selection(feed_id, posts_count),
            },
            manual=False,
        )
        if not added:
            logging.error(
                "Can`t queue Telegram feed refresh for user %s, feed %s",
                user["sid"],
                feed_id,
            )
            return _json_response(
                {"status": "error", "message": "Can`t start feed refresh"},
                status=500,
            )

        updated: Optional[bool] = app.users.update_by_sid(
            user["sid"],
            {
                f"in_queue.{data_providers.TELEGRAM}": True,
                "message": f"Refreshing {feed.get('title', 'Telegram feed')}",
            },
        )
        if not updated:
            logging.error(
                "Can`t update queue status for user %s after queueing feed %s",
                user["sid"],
                feed_id,
            )
    except Exception as exc:
        logging.exception(
            "Can`t queue Telegram feed refresh for user %s, feed %s: %s",
            user["sid"],
            feed_id,
            exc,
        )
        return _json_response(
            {"status": "error", "message": "Can`t start feed refresh"}, status=500
        )

    logging.info(
        "Queued refresh of %d posts for Telegram feed %s, user %s",
        posts_count,
        feed_id,
        user["sid"],
    )
    return _json_response(
        {"status": "success", "message": "Telegram feed refresh started"}
    )


def on_provider_feeds_get_post(
    app, user: dict, request: Request, provider: Optional[str] = None
) -> Response:
    provider = provider
    if provider not in (data_providers.TELEGRAM, data_providers.BAZQUX, data_providers.X):
        return redirect(app.routes.get_url_by_endpoint(endpoint="on_root_get"))

    provider_user = app.users.get_provider_user(user, provider)
    if not provider_user:
        return redirect(
            app.routes.get_url_by_endpoint(
                endpoint="on_provider_detail_get", params={"provider": provider}
            )
        )

    action = request.form.get("action")
    selection = (
        _get_selection(request) if request.method == "POST" else _empty_selection()
    )
    if request.method != "POST" and provider == data_providers.X:
        selection = {
            "channels": ["home"] if provider_user.get("x_home_enabled", True) else [],
            "feeds": [
                str(feed_id)
                for feed_id in provider_user.get("x_selected_feeds", [])
                if feed_id
            ],
            "categories": [],
        }
    error = None
    channels = []
    categories = []
    feeds = []

    if request.method == "POST" and action == "download":
        if not (selection["channels"] or selection["feeds"] or selection["categories"]):
            error = "Select at least one channel, feed, or category."
        else:
            if provider == data_providers.X:
                app.users.update_provider(
                    user["sid"],
                    provider,
                    {
                        "x_home_enabled": "home" in selection["channels"],
                        "x_selected_feeds": selection["feeds"],
                    },
                )
            if provider == data_providers.TELEGRAM:
                selection["telegram_limit"] = _telegram_limit_from_selection(
                    selection
                )
            app.users.reset_in_queue_if_legacy(user["sid"], user)
            if not app.users.get_in_queue(user).get(provider, False):
                added = app.tasks.add_task(
                    {
                        "type": TASK_DOWNLOAD,
                        "user": user["sid"],
                        "host": request.environ["HTTP_HOST"],
                        "provider": provider,
                        "selection": selection,
                    }
                )
                if added:
                    updated = app.users.update_by_sid(
                        user["sid"],
                        {
                            f"in_queue.{provider}": True,
                            "message": "Downloading selected sources, please wait",
                        },
                    )
                    if not updated:
                        logging.error(
                            "Cant update data of user %s while create download task",
                            user["sid"],
                        )
            else:
                app.users.update_by_sid(
                    user["sid"], {"message": "You already in queue, please wait"}
                )
            return redirect(app.routes.get_url_by_endpoint(endpoint="on_root_get"))

    if request.method == "POST" and action != "refresh":
        action = "refresh"

    if action == "refresh":
        logging.info(
            "Refreshing channel list for provider: %s, user: %s",
            provider,
            user.get("sid"),
        )
        try:
            if provider == data_providers.TELEGRAM:
                telegram = TelegramProvider(app.config, app.db)
                channels = telegram.list_channels(provider_user)
                logging.info(
                    "Successfully refreshed %d channels for telegram", len(channels)
                )
            elif provider == data_providers.BAZQUX:
                bazqux = BazquxProvider(app.config)
                data = bazqux.list_subscriptions(provider_user)
                categories = data["categories"]
                feeds = data["feeds"]
            elif provider == data_providers.X:
                x_provider = XProvider(app.config)
                feeds = asyncio.run(x_provider.list_following(provider_user))
                if provider_user.get("provider_updates"):
                    app.users.update_provider(
                        user["sid"], provider, provider_user["provider_updates"]
                    )
        except Exception as exc:
            logging.error("Failed to refresh provider list: %s", exc)
            error = "Failed to refresh the list. Please try again later."

    page = app.template_env.get_template("provider-feeds.html")
    return Response(
        page.render(
            provider=provider,
            channels=channels,
            categories=categories,
            feeds=feeds,
            selected=selection,
            error=error,
            selection_url=app.routes.get_url_by_endpoint(
                endpoint="on_provider_feeds_get_post",
                params={"provider": provider},
            ),
            data_sources_url=app.routes.get_url_by_endpoint(
                endpoint="on_data_sources_get"
            ),
            user_settings=user["settings"],
            support=app.config["settings"]["support"],
            version=app.config["settings"]["version"],
        ),
        mimetype="text/html",
    )
