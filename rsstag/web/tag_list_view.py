"""Query params shared by the tag list pages: topics filter, sort mode, noise."""

from dataclasses import dataclass, replace
from typing import Any, Optional
from urllib.parse import urlencode

from werkzeug.wrappers import Request

from rsstag.tag_rank import DEFAULT_SORT_MODE, normalize_sort_mode

_TRUTHY_ARGS: frozenset[str] = frozenset({"1", "true", "yes", "on"})
_SORT_LABELS: tuple[tuple[str, str], ...] = (
    ("count", "Count"),
    ("informative", "Informative"),
    ("hot", "Hot"),
)


@dataclass(frozen=True)
class TagListView:
    """List-view query params shared by the tag list pages."""

    topics: bool = False
    sort: str = DEFAULT_SORT_MODE
    hide_noise: bool = False


def _flag_arg(request: Optional[Request], name: str) -> bool:
    if request is None:
        return False
    return request.args.get(name, "").strip().casefold() in _TRUTHY_ARGS


def topic_filter_enabled(request: Optional[Request]) -> bool:
    """Return whether the optional topic-backed tag filter was requested."""
    return _flag_arg(request, "topics")


def read_list_view(request: Optional[Request]) -> TagListView:
    """Read ``?topics=``, ``?sort=`` and ``?hide_noise=`` from the request."""
    sort_arg: Optional[str] = request.args.get("sort") if request is not None else None
    return TagListView(
        topics=_flag_arg(request, "topics"),
        sort=normalize_sort_mode(sort_arg),
        hide_noise=_flag_arg(request, "hide_noise"),
    )


def list_view_query(view: TagListView) -> str:
    """Encode the non-default list-view params as a query string."""
    params: list[tuple[str, str]] = []
    if view.topics:
        params.append(("topics", "1"))
    if view.sort != DEFAULT_SORT_MODE:
        params.append(("sort", view.sort))
    if view.hide_noise:
        params.append(("hide_noise", "1"))
    return urlencode(params)


def append_list_view(url: str, view: TagListView) -> str:
    """Keep the list-view params on a generated link."""
    query: str = list_view_query(view)
    if not query:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{query}"


def preserve_list_view_in_pages(
    pages_map: dict[str, list[dict]], view: TagListView
) -> None:
    """Apply the list-view params to all pagination links in a page map."""
    for page_links in pages_map.values():
        for page_link in page_links:
            page_link["url"] = append_list_view(page_link["url"], view)


def build_sort_switcher(
    base_url: str, view: TagListView, show_noise_toggle: bool = True
) -> dict[str, Any]:
    """Links for the Count / Informative / Hot switcher and the generic toggle."""
    modes: list[dict[str, Any]] = [
        {
            "mode": mode,
            "label": label,
            "active": view.sort == mode,
            "url": append_list_view(base_url, replace(view, sort=mode)),
        }
        for mode, label in _SORT_LABELS
    ]
    noise: Optional[dict[str, Any]] = None
    if show_noise_toggle:
        noise = {
            "active": view.hide_noise,
            "url": append_list_view(
                base_url, replace(view, hide_noise=not view.hide_noise)
            ),
        }
    return {"modes": modes, "noise": noise}


def secondary_list_view(request: Optional[Request]) -> TagListView:
    """List view for tag pages without the topic filter (sentiment, groups...)."""
    return replace(read_list_view(request), topics=False)


def tag_hint(doc: dict[str, Any]) -> str:
    """Short tooltip with the tag's rank values, empty when unranked."""
    rank: Any = doc.get("rank")
    if not isinstance(rank, dict):
        return ""
    parts: list[str] = []
    for key in ("score", "hot"):
        value: Any = rank.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            parts.append(f"{key}: {value:.2f}")
    if rank.get("noise") is True:
        parts.append("generic")
    return ", ".join(parts)
