"""Management page for the post grouping deduplication cache."""

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from werkzeug.wrappers import Request, Response
from werkzeug.utils import redirect

from rsstag.grouping_cache import KIND_CHUNK, KIND_DOCUMENT, SORTABLE_FIELDS

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

ENTRIES_ON_PAGE: int = 50
CACHE_PAGE_URL: str = "/post-grouping-cache"


def _read_kind(request: Request) -> str:
    kind: str = str(request.args.get("kind", "")).strip()
    return kind if kind in (KIND_DOCUMENT, KIND_CHUNK) else ""


def _read_int(source: Any, name: str, default: int) -> int:
    try:
        return int(str(source.get(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _read_float(source: Any, name: str, default: float) -> float:
    try:
        return float(str(source.get(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _back_url(kind: str, sort_by: str, descending: bool) -> str:
    return (
        f"{CACHE_PAGE_URL}?kind={kind}&sort={sort_by}"
        f"&order={'desc' if descending else 'asc'}"
    )


def on_post_grouping_cache_get(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    """Show cache entries with their hit statistics."""
    kind: str = _read_kind(request)
    sort_by: str = str(request.args.get("sort", "hits")).strip()
    if sort_by not in SORTABLE_FIELDS:
        sort_by = "hits"
    descending: bool = str(request.args.get("order", "asc")).strip() == "desc"
    page_number: int = max(1, _read_int(request.args, "page", 1))

    owner: str = user["sid"]
    cache = app.post_grouping_cache
    total: int = cache.count_entries(owner, kind)
    entries: List[Dict[str, Any]] = cache.find_entries(
        owner,
        kind=kind,
        sort_by=sort_by,
        descending=descending,
        skip=(page_number - 1) * ENTRIES_ON_PAGE,
        limit=ENTRIES_ON_PAGE,
    )

    page = app.template_env.get_template("post-grouping-cache.html")
    return Response(
        page.render(
            entries=entries,
            summary=cache.summary(owner),
            total=total,
            page_number=page_number,
            pages_count=app.get_page_count(total, ENTRIES_ON_PAGE),
            kind=kind,
            sort_by=sort_by,
            order="desc" if descending else "asc",
            sortable_fields=SORTABLE_FIELDS,
            user_settings=user["settings"],
            provider=user.get("provider", ""),
        ),
        mimetype="text/html",
    )


def on_post_grouping_cache_delete_post(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    """Delete the entries checked on the page."""
    keys: List[str] = [key for key in request.form.getlist("keys") if key]
    try:
        deleted: int = app.post_grouping_cache.delete_keys(user["sid"], keys)
        logging.info(
            "Deleted %d post grouping cache entries for %s", deleted, user["sid"]
        )
    except Exception as e:
        logging.error(
            "Can`t delete post grouping cache entries for %s. Info: %s", user["sid"], e
        )

    return redirect(
        _back_url(
            _read_kind(request),
            str(request.form.get("sort", "hits")),
            str(request.form.get("order", "asc")) == "desc",
        )
    )


def on_post_grouping_cache_purge_post(
    app: "RSSTagApplication", user: dict, request: Request
) -> Response:
    """Drop low value entries in bulk."""
    max_hits: int = max(0, _read_int(request.form, "max_hits", 0))
    older_than_days: float = max(0.0, _read_float(request.form, "older_than_days", 0.0))
    kind: str = str(request.form.get("kind", "")).strip()
    if kind not in (KIND_DOCUMENT, KIND_CHUNK):
        kind = ""

    try:
        deleted: int = app.post_grouping_cache.purge(
            user["sid"],
            max_hits=max_hits,
            older_than_days=older_than_days,
            kind=kind,
        )
        logging.info(
            "Purged %d post grouping cache entries for %s", deleted, user["sid"]
        )
    except Exception as e:
        logging.error(
            "Can`t purge post grouping cache for %s. Info: %s", user["sid"], e
        )

    return redirect(CACHE_PAGE_URL)
