import logging
from typing import Dict, List, Optional

from werkzeug.wrappers import Request, Response
from werkzeug.utils import redirect

import rsstag.providers.providers as data_providers
from rsstag.providers.bazqux import BazquxProvider
from rsstag.providers.telegram import TelegramProvider
from rsstag.tasks import TASK_DOWNLOAD


def _empty_selection() -> Dict[str, List[str]]:
    return {"channels": [], "feeds": [], "categories": []}


def _get_selection(request: Request) -> Dict[str, List[str]]:
    return {
        "channels": request.form.getlist("channels"),
        "feeds": request.form.getlist("feeds"),
        "categories": request.form.getlist("categories"),
    }


def on_provider_feeds_get_post(
    app, user: dict, request: Request, provider: Optional[str] = None
) -> Response:
    provider = provider or user.get("provider")
    if provider not in (data_providers.TELEGRAM, data_providers.BAZQUX):
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
    error = None
    channels = []
    categories = []
    feeds = []

    if request.method == "POST" and action == "download":
        if not (selection["channels"] or selection["feeds"] or selection["categories"]):
            error = "Select at least one channel, feed, or category."
        else:
            if not user["in_queue"]:
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
                            "in_queue": True,
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
