"""Tag context chart: common phrases, distinctive words and feed framing."""

import logging
from typing import TYPE_CHECKING, Any, Optional

from jinja2 import Template
from werkzeug.exceptions import BadRequest, InternalServerError, NotFound
from werkzeug.wrappers import Request, Response

from rsstag.web.posts import (
    _get_category_scope,
    _load_scoped_posts,
    _page_scope_labels,
    _serialize_canvas_posts,
)
from rsstag.web.tag_context_data import (
    Sentence,
    SentenceScope,
    feed_titles,
    scan_sentences,
    scope_for_tag,
    tag_sentences,
)
from rsstag.web.tag_context_views import build_feeds, build_phrases, build_words, post_meta

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

LOG: logging.Logger = logging.getLogger(__name__)
VIEWS: tuple[str, ...] = ("phrases", "words", "feeds")
POST_PROJECTION: dict[str, bool] = {
    "_id": False, "pid": True, "url": True, "read": True,
    "content.title": True, "content.content": True, "feed_id": True,
}


class ChartRequest:
    """Validated query parameters and scope of one chart request."""

    def __init__(
        self,
        user: dict[str, Any],
        tag: str,
        view: str,
        feed: Optional[dict[str, Any]],
        category: Optional[dict[str, str]],
        request: Request,
    ) -> None:
        self.user: dict[str, Any] = user
        self.tag: str = tag
        self.view: str = view
        self.feed: Optional[dict[str, Any]] = feed
        self.category: Optional[dict[str, str]] = category
        self.match_topic: bool = request.args.get("topic", "").strip() == "1"
        self.match_sentences: bool = request.args.get("sentences", "").strip() == "1"
        self.only_unread: Optional[bool] = user["settings"].get("only_unread") or None

    @property
    def owner(self) -> str:
        return str(self.user["sid"])

    @property
    def text_filter(self) -> bool:
        return self.match_topic or self.match_sentences


def _resolve_scope(
    app: "RSSTagApplication", user: dict[str, Any], request: Request
) -> tuple[Optional[dict[str, Any]], Optional[dict[str, str]], Optional[Exception]]:
    feed_id: str = request.args.get("feed", "").strip()
    category_id: str = request.args.get("category", "").strip()
    feed: Optional[dict[str, Any]] = (
        app.feeds.get_by_feed_id(user["sid"], feed_id) if feed_id else None
    )
    if feed_id and not feed:
        return None, None, NotFound("Feed not found.")
    category: Optional[dict[str, str]] = _get_category_scope(app, user["sid"], category_id)
    if category_id and not category:
        return None, None, NotFound("Category not found.")
    return feed, category, None


def _parse_request(
    app: "RSSTagApplication", user: dict[str, Any], request: Request
) -> ChartRequest:
    tag: str = request.args.get("tag", "").strip()
    if not tag:
        raise BadRequest("Select a tag to view its context chart.")
    view: str = request.args.get("view", "phrases").strip() or "phrases"
    if view not in VIEWS:
        raise BadRequest(f"Unknown view “{view}”. Use phrases, words or feeds.")
    feed, category, error = _resolve_scope(app, user, request)
    if error:
        raise error
    return ChartRequest(user, tag, view, feed, category, request)


def _load_posts(app: "RSSTagApplication", chart: ChartRequest, tag: str) -> list[dict[str, Any]]:
    """Posts in the page scope; an empty tag loads the whole background scope."""
    return _load_scoped_posts(
        app, chart.user, chart.feed, chart.category, tag,
        chart.text_filter if tag else False, bool(tag), chart.only_unread, POST_PROJECTION,
    )


def _summary(focus: list[Sentence], titles: dict[str, str]) -> dict[str, Any]:
    return {
        "sentences": len(focus),
        "mentions": sum(len(sentence.spans) for sentence in focus),
        "articles": len({sentence.post_id for sentence in focus}),
        "feeds": len(titles),
    }


def _view_data(
    app: "RSSTagApplication",
    chart: ChartRequest,
    posts: list[dict[str, Any]],
    focus: list[Sentence],
    scope: SentenceScope,
) -> dict[str, Any]:
    titles: dict[str, str] = feed_titles(
        app, chart.owner, sorted({sentence.feed_id for sentence in focus if sentence.feed_id})
    )
    data: dict[str, Any] = {"view": chart.view, "tag": chart.tag, "summary": _summary(focus, titles)}
    if chart.view == "phrases":
        data["rows"] = build_phrases(focus, chart.tag)
        return data
    if chart.view == "feeds":
        return {**data, **build_feeds(focus, post_meta(posts, titles))}
    background_posts: list[dict[str, Any]] = _load_posts(app, chart, "")
    background_scope: SentenceScope = SentenceScope(chart.tag, scope.variants, only_unread=scope.only_unread)
    background: list[Sentence] = scan_sentences(app, chart.owner, background_posts, background_scope)
    return {**data, **build_words(focus, background, post_meta(posts, titles))}


def build_chart(app: "RSSTagApplication", chart: ChartRequest) -> dict[str, Any]:
    """Scan tag sentences once and build the data for the requested view."""
    scope: SentenceScope = scope_for_tag(
        app, chart.owner, chart.tag, chart.match_topic, chart.match_sentences,
        bool(chart.only_unread),
    )
    posts: list[dict[str, Any]] = _load_posts(app, chart, chart.tag)
    focus: list[Sentence] = tag_sentences(scan_sentences(app, chart.owner, posts, scope))
    return _view_data(app, chart, posts, focus, scope)


def _render(app: "RSSTagApplication", chart: ChartRequest, data: dict[str, Any]) -> Response:
    page_scope, page_title = _page_scope_labels(chart.feed, chart.category, chart.tag)
    page: Template = app.template_env.get_template("tag-ngram-chart.html")
    return Response(
        page.render(
            tag=chart.tag,
            view=chart.view,
            views=VIEWS,
            data=data,
            data_json=_serialize_canvas_posts(data),
            feed=chart.feed,
            category=chart.category,
            page_scope=page_scope,
            page_title=page_title,
            user_settings=chart.user["settings"],
            provider=chart.user.get("provider", ""),
        ),
        mimetype="text/html",
    )


def on_tag_ngram_chart_get(
    app: "RSSTagApplication", user: dict[str, Any], request: Request
) -> Response:
    """Render the tag context chart for the requested view and scope."""
    try:
        chart: ChartRequest = _parse_request(app, user, request)
    except (BadRequest, NotFound) as exc:
        return app.on_error(user, request, exc)
    try:
        data: dict[str, Any] = build_chart(app, chart)
    except Exception as exc:
        LOG.exception("Unable to build %s chart for tag %s: %s", chart.view, chart.tag, exc)
        return app.on_error(
            user, request, InternalServerError("The tag context chart could not be loaded.")
        )
    return _render(app, chart, data)
