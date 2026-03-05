from typing import Dict, List, Tuple

from werkzeug.wrappers import Request, Response

from rsstag.tasks import (
    TASK_POST_GROUPING,
    SCOPE_MODE_ALL,
    SCOPE_MODE_POSTS,
    SCOPE_MODE_FEEDS,
    SCOPE_MODE_CATEGORIES,
    SCOPE_MODE_PROVIDER,
)

SUPPORTED_SCOPED_TASKS = {
    TASK_POST_GROUPING: "Group posts",
}

SCOPE_POST_IDS = SCOPE_MODE_POSTS
SCOPE_FEED_IDS = SCOPE_MODE_FEEDS
SCOPE_CATEGORY_IDS = SCOPE_MODE_CATEGORIES
SCOPE_PROVIDER = SCOPE_MODE_PROVIDER
SUPPORTED_SCOPES = (SCOPE_POST_IDS, SCOPE_FEED_IDS, SCOPE_CATEGORY_IDS, SCOPE_PROVIDER)
SUPPORTED_TASK_SCOPES = {
    TASK_POST_GROUPING: set(SUPPORTED_SCOPES),
}


def _split_csv(raw: str) -> List[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.replace("\n", ",").split(",") if item.strip()]


def _build_filters_data(app, user: dict) -> Tuple[List[Dict], List[str]]:
    feeds: List[Dict] = []
    categories = set()

    for feed in app.feeds.get_all(
        user["sid"], projection={"feed_id": True, "title": True, "category_id": True}
    ):
        category_id = feed.get("category_id")
        if category_id:
            categories.add(category_id)
        feeds.append(
            {
                "feed_id": feed.get("feed_id", ""),
                "title": feed.get("title", ""),
                "category_id": category_id or "",
            }
        )

    feeds.sort(key=lambda item: (item["category_id"], item["title"], item["feed_id"]))
    return feeds, sorted(categories)


def _render_page(app, user: dict, *, errors=None, success_message: str = "", form_data=None, status: int = 200) -> Response:
    feeds, categories = _build_filters_data(app, user)
    page = app.template_env.get_template("metadata.html")

    providers = [p.strip() for p in app.config["settings"].get("providers", "").split(",") if p.strip()]

    initial_form = {
        "task_type": str(TASK_POST_GROUPING),
        "scope_type": SCOPE_PROVIDER,
        "post_ids": "",
        "feed_ids": [],
        "category_ids": [],
        "provider": user.get("provider", ""),
    }
    if form_data:
        initial_form.update(form_data)

    return Response(
        page.render(
            user_settings=user["settings"],
            provider=user.get("provider", ""),
            support=app.config["settings"]["support"],
            version=app.config["settings"]["version"],
            supported_tasks=SUPPORTED_SCOPED_TASKS,
            feeds=feeds,
            categories=categories,
            providers=providers,
            errors=errors or [],
            success_message=success_message,
            form_data=initial_form,
            scope_values={
                "post_ids": SCOPE_POST_IDS,
                "feed_ids": SCOPE_FEED_IDS,
                "category_ids": SCOPE_CATEGORY_IDS,
                "provider": SCOPE_PROVIDER,
            },
        ),
        mimetype="text/html",
        status=status,
    )


def on_metadata_get(app, user: dict, _: Request) -> Response:
    return _render_page(app, user)


def on_metadata_post(app, user: dict, request: Request) -> Response:
    task_type_raw = request.form.get("task_type", "")
    scope_type = request.form.get("scope_type", "")
    post_ids_raw = request.form.get("post_ids", "")
    selected_feed_ids = request.form.getlist("feed_ids")
    selected_category_ids = request.form.getlist("category_ids")
    selected_provider = request.form.get("provider", "")

    form_data = {
        "task_type": task_type_raw,
        "scope_type": scope_type,
        "post_ids": post_ids_raw,
        "feed_ids": selected_feed_ids,
        "category_ids": selected_category_ids,
        "provider": selected_provider,
    }

    errors: List[str] = []
    try:
        task_type = int(task_type_raw)
    except (TypeError, ValueError):
        task_type = None
        errors.append("Invalid task type selected.")

    if task_type not in SUPPORTED_SCOPED_TASKS:
        errors.append("Unsupported task for scoped metadata processing.")

    if scope_type not in SUPPORTED_SCOPES:
        errors.append("Invalid scope type selected.")

    if task_type in SUPPORTED_TASK_SCOPES and scope_type in SUPPORTED_SCOPES:
        if scope_type not in SUPPORTED_TASK_SCOPES[task_type]:
            errors.append("Unsupported task and scope combination selected.")

    query: Dict = {"owner": user["sid"]}
    if scope_type == SCOPE_POST_IDS:
        post_ids = _split_csv(post_ids_raw)
        if not post_ids:
            errors.append("Post IDs scope selected, but no post IDs were provided.")
        else:
            query["pid"] = {"$in": post_ids}
    elif scope_type == SCOPE_FEED_IDS:
        if not selected_feed_ids:
            errors.append("Feed IDs scope selected, but no feed IDs were provided.")
        else:
            query["feed_id"] = {"$in": selected_feed_ids}
    elif scope_type == SCOPE_CATEGORY_IDS:
        if not selected_category_ids:
            errors.append("Category IDs scope selected, but no category IDs were provided.")
        else:
            query["category_id"] = {"$in": selected_category_ids}
    elif scope_type == SCOPE_PROVIDER:
        if not selected_provider:
            errors.append("Provider scope selected, but provider is empty.")
        elif selected_provider != user.get("provider", ""):
            errors.append("Provider scope must match your current active provider.")

    if errors:
        return _render_page(app, user, errors=errors, form_data=form_data, status=400)

    posts = list(app.posts.find(user["sid"], query=query, projection={"pid": True}))
    if not posts:
        return _render_page(
            app,
            user,
            errors=["No posts found for selected scope."],
            form_data=form_data,
            status=400,
        )

    pids = [post["pid"] for post in posts if post.get("pid")]
    if not pids:
        return _render_page(
            app,
            user,
            errors=["Selected scope did not yield valid post identifiers."],
            form_data=form_data,
            status=400,
        )

    app.post_grouping.delete_by_post_ids(user["sid"], pids)
    app.posts.delete_grouping(user["sid"], pids)

    scope = {
        "mode": SCOPE_MODE_ALL,
        "post_ids": [],
        "feed_ids": [],
        "category_ids": [],
        "provider": "",
    }
    if scope_type == SCOPE_POST_IDS:
        scope["mode"] = SCOPE_MODE_POSTS
        scope["post_ids"] = pids
    elif scope_type == SCOPE_FEED_IDS:
        scope["mode"] = SCOPE_MODE_FEEDS
        scope["feed_ids"] = selected_feed_ids
    elif scope_type == SCOPE_CATEGORY_IDS:
        scope["mode"] = SCOPE_MODE_CATEGORIES
        scope["category_ids"] = selected_category_ids
    elif scope_type == SCOPE_PROVIDER:
        scope["mode"] = SCOPE_MODE_PROVIDER
        scope["provider"] = selected_provider

    app.tasks.add_task(
        {
            "user": user["sid"],
            "type": task_type,
            "data": [],
            "host": app.config["settings"]["host_name"],
            "provider": user.get("provider", ""),
            "scope": scope,
        }
    )

    return _render_page(
        app,
        user,
        success_message=f"Reprocessing queued for {len(pids)} post(s).",
        form_data=form_data,
    )
