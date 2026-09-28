"""File-browser style exploration of a tag's context and related posts."""

import gzip
import json
import logging
import re
from typing import TYPE_CHECKING, Any, Iterable, Iterator
from urllib.parse import quote

from werkzeug.wrappers import Request, Response

from rsstag.snippets import strip_html_markup

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication


LOG: logging.Logger = logging.getLogger(__name__)
DEFAULT_POSTS_ON_PAGE: int = 30
CONTEXT_WINDOW: int = 5


def _decode_lemmas(post: dict[str, Any]) -> list[str]:
    packed: Any = post.get("lemmas")
    if not packed:
        return []
    try:
        return gzip.decompress(packed).decode("utf-8", "replace").split()
    except (OSError, TypeError, ValueError) as exc:
        LOG.warning("Could not decode post lemmas: %s", exc)
        return []


def _only_unread(user: dict[str, Any]) -> bool | None:
    """Treat the setting like the /tag/ page: filter only when it is enabled."""
    return True if user["settings"].get("only_unread") else None


def _posts_on_page(user: dict[str, Any]) -> int:
    """Use the menu's saved page size, falling back for invalid settings."""
    try:
        page_size: int = int(user["settings"].get("posts_on_page", DEFAULT_POSTS_ON_PAGE))
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_POSTS_ON_PAGE
    return page_size if page_size > 0 else DEFAULT_POSTS_ON_PAGE


def _posts_for_tag(
    app: "RSSTagApplication", user: dict[str, Any], tag: str,
    selection: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    projection: dict[str, int] = {"_id": 0, "pid": 1, "read": 1}
    if selection is None or selection["kind"] == "context":
        projection["lemmas"] = 1
    return app.posts.get_by_tags(user["sid"], [tag], _only_unread(user), projection)


def _context_paths(lemmas: list[str], tag: str) -> Iterator[tuple[str, ...]]:
    """Yield word prefixes on either side, sharing keys across directions."""
    for index, word in enumerate(lemmas):
        if word != tag:
            continue
        for direction in (1, -1):
            chain: list[str] = []
            for distance in range(1, CONTEXT_WINDOW + 1):
                offset: int = direction * distance
                position: int = index + offset
                if not 0 <= position < len(lemmas):
                    break
                chain.append(lemmas[position])
                yield tuple(chain)


def _context_nodes(branches: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"name": word, "count": branch["count"],
         "occurrences": branch["occurrences"], "children": _context_nodes(branch["children"])}
        for word, branch in sorted(
            branches.items(), key=lambda item: (-item[1]["count"], item[0])
        )
    ]


def _make_tree(posts: Iterable[dict[str, Any]], tag: str) -> dict[str, Any]:
    """Aggregate every post in one pass, counting each prefix once per post."""
    branches: dict[str, dict[str, Any]] = {}
    total: int = 0
    for post in posts:
        total += 1
        seen: set[tuple[str, ...]] = set()
        for chain in _context_paths(_decode_lemmas(post), tag):
            siblings: dict[str, dict[str, Any]] = branches
            node: dict[str, Any] = {}
            for step in chain:
                node = siblings.setdefault(step, {"count": 0, "occurrences": 0, "children": {}})
                siblings = node["children"]
            node["occurrences"] += 1
            if chain not in seen:
                node["count"] += 1
                seen.add(chain)
    return {"name": tag, "count": total, "context": _context_nodes(branches)}


def _matches_context(lemmas: list[str], tag: str, chain: list[str]) -> bool:
    """Match a merged prefix in either direction from the same tag occurrence."""
    selected: tuple[str, ...] = tuple(chain)
    return any(path == selected for path in _context_paths(lemmas, tag))


def _topic_memberships(
    app: "RSSTagApplication", user: dict[str, Any], posts: list[dict[str, Any]],
) -> dict[tuple[str, ...], dict[str, set[int]]]:
    """Index each topic prefix by post and its addressable sentences."""
    pids: set[str] = {str(post["pid"]) for post in posts}
    memberships: dict[tuple[str, ...], dict[str, set[int]]] = {}
    if not pids:
        return memberships
    documents: list[dict[str, Any]] = app.post_grouping.get_by_post_ids(
        user["sid"], list(pids), projection={"_id": 0, "post_ids": 1, "groups": 1, "sentences": 1},
    )
    for doc in documents:
        post_ids: list[Any] = doc.get("post_ids") or []
        # The worker groups one post at a time; sentence numbers belong to it.
        if len(post_ids) != 1 or str(post_ids[0]) not in pids:
            continue
        pid: str = str(post_ids[0])
        available: set[int] = {
            sentence["number"] for sentence in doc.get("sentences", [])
            if isinstance(sentence.get("number"), int) and sentence.get("text")
            and (not _only_unread(user) or not sentence.get("read", False))
        }
        groups: Any = doc.get("groups") or {}
        if not isinstance(groups, dict):
            continue
        for path, indices in groups.items():
            if not isinstance(path, str) or not isinstance(indices, list):
                continue
            chain: tuple[str, ...] = tuple(part.strip() for part in path.split(">") if part.strip())
            numbers: set[int] = {number for number in indices if isinstance(number, int)} & available
            if not numbers:
                continue
            for depth in range(1, len(chain) + 1):
                memberships.setdefault(chain[:depth], {}).setdefault(pid, set()).update(numbers)
    return memberships


def _topic_nodes(
    memberships: dict[tuple[str, ...], dict[str, set[int]]],
) -> list[dict[str, Any]]:
    branches: dict[str, dict[str, Any]] = {}
    for chain, posts in memberships.items():
        siblings: dict[str, dict[str, Any]] = branches
        node: dict[str, Any] = {}
        for part in chain:
            node = siblings.setdefault(part, {"count": 0, "occurrences": 0, "children": {}})
            siblings = node["children"]
        node["count"] = len(posts)
    return _context_nodes(branches)


def _matching_posts(
    app: "RSSTagApplication", user: dict[str, Any], tag: str,
    posts: Iterable[dict[str, Any]], selection: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    if selection["kind"] == "topic":
        candidates: list[dict[str, Any]] = list(posts)
        memberships: dict[tuple[str, ...], dict[str, set[int]]] = _topic_memberships(app, user, candidates)
        selected: dict[str, set[int]] = memberships.get(tuple(selection["chain"]), {})
        for post in candidates:
            numbers: set[int] = selected.get(str(post["pid"]), set())
            if numbers:
                yield {**post, "topic_numbers": numbers}
        return
    for post in posts:
        if selection["kind"] == "root" or _matches_context(_decode_lemmas(post), tag, selection["chain"]):
            yield post


def _validate_selection(selection: Any) -> dict[str, Any]:
    if not isinstance(selection, dict) or selection.get("kind") not in {"root", "context", "topic"}:
        raise ValueError("Invalid explorer selection")
    if selection["kind"] == "context":
        chain: Any = selection.get("chain")
        if not isinstance(chain, list) or not 1 <= len(chain) <= CONTEXT_WINDOW:
            raise ValueError("Invalid context chain")
        if not all(isinstance(word, str) and 0 < len(word) <= 100 for word in chain):
            raise ValueError("Invalid context chain")
    if selection["kind"] == "topic":
        chain: Any = selection.get("chain")
        if not isinstance(chain, list) or not 1 <= len(chain) <= 100:
            raise ValueError("Invalid topic path")
        if not all(isinstance(part, str) and part.strip() == part and 0 < len(part) <= 1000 and ">" not in part for part in chain):
            raise ValueError("Invalid topic path")
    return selection


def _parse_selection(request: Request) -> dict[str, Any]:
    raw: str = request.args.get("selection", '{"kind":"root"}')
    return _validate_selection(json.loads(raw))


def _parse_page(request: Request) -> int:
    raw: str = request.args.get("page", "1")
    if not raw.isdecimal() or not 1 <= int(raw) <= 10000:
        raise ValueError("Invalid page number")
    return int(raw)


def _parse_scope(request: Request) -> str:
    scope: str = request.args.get("scope", "page")
    if scope not in {"page", "all"}:
        raise ValueError("Invalid result scope")
    return scope


def _post_text(post: dict[str, Any]) -> str:
    content: dict[str, Any] = post.get("content") or {}
    packed: Any = content.get("content")
    try:
        raw: str = gzip.decompress(packed).decode("utf-8", "replace") if packed else ""
    except (OSError, TypeError, ValueError) as exc:
        LOG.warning("Could not decode post content: %s", exc)
        raw = ""
    return strip_html_markup(raw)


def _search_terms(tag: str, selection: dict[str, Any]) -> set[str]:
    terms: set[str] = {tag.casefold()}
    if selection["kind"] == "context":
        terms.update(word.casefold() for word in selection["chain"])
    return terms


def _sentence_source(
    pid: str, text: str, grouped: dict[str, list[dict[str, Any]]], only_unread: bool | None,
) -> list[dict[str, Any]]:
    """Prefer addressable sentences, hiding read ones when only unread is on."""
    sentences: list[dict[str, Any]] = grouped.get(pid) or []
    if not sentences:
        return [{"text": part.strip()} for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]
    if only_unread:
        return [sentence for sentence in sentences if not sentence.get("read", False)]
    return sentences


def _excerpts(source: list[dict[str, Any]], terms: set[str], tag: str) -> list[dict[str, Any]]:
    def text_of(sentence: dict[str, Any]) -> str:
        return str(sentence.get("text", "")).casefold()

    selected: list[dict[str, Any]] = [sentence for sentence in source if all(term in text_of(sentence) for term in terms)]
    if not selected:
        selected = [sentence for sentence in source if tag.casefold() in text_of(sentence)]
    return (selected or source)[:2]


def _post_excerpts(
    post: dict[str, Any], source: list[dict[str, Any]], terms: set[str], tag: str,
) -> list[dict[str, Any]]:
    if "topic_numbers" in post:
        return [sentence for sentence in source if sentence.get("number") in post["topic_numbers"]]
    return _excerpts(source, terms, tag)


def _results(
    posts: list[dict[str, Any]], tag: str, selection: dict[str, Any],
    grouped: dict[str, list[dict[str, Any]]], only_unread: bool | None = None,
) -> dict[str, Any]:
    post_items: list[dict[str, Any]] = []
    sentence_items: list[dict[str, Any]] = []
    terms: set[str] = _search_terms(tag, selection)
    for post in posts:
        raw_pid: str | int = post.get("pid", "")
        pid: str = str(raw_pid)
        title: str = str((post.get("content") or {}).get("title") or "Untitled post")
        source: list[dict[str, Any]] = _sentence_source(pid, _post_text(post), grouped, only_unread)
        excerpts: list[dict[str, Any]] = _post_excerpts(post, source, terms, tag)
        post_items.append({"pid": raw_pid, "title": title, "url": f"/posts/{quote(pid, safe='')}", "excerpt": " ".join(str(sentence.get("text", "")) for sentence in excerpts)[:400], "read": bool(post.get("read", False))})
        for sentence in excerpts:
            sentence_items.append({"pid": raw_pid, "title": title, "url": f"/posts/{quote(pid, safe='')}", "text": str(sentence.get("text", ""))[:500], "number": sentence.get("number"), "read": bool(post.get("read", False) or sentence.get("read", False))})
    return {"total": len(posts), "posts": post_items, "sentences": sentence_items}


def _all_results(
    app: "RSSTagApplication", user: dict[str, Any], tag: str,
    matches: Iterable[dict[str, Any]], selection: dict[str, Any],
) -> dict[str, Any]:
    """Return read state of every matching post and addressable excerpt."""
    posts: list[dict[str, Any]] = list(matches)
    grouped: dict[str, list[dict[str, Any]]] = _grouped_sentences(app, user, posts)
    terms: set[str] = _search_terms(tag, selection)
    only_unread: bool | None = _only_unread(user)
    sentence_items: list[dict[str, Any]] = []
    for post in posts:
        source: list[dict[str, Any]] = _sentence_source(str(post["pid"]), "", grouped, only_unread)
        for sentence in _post_excerpts(post, source, terms, tag):
            sentence_items.append({"pid": post["pid"], "number": sentence["number"], "read": bool(post.get("read", False) or sentence.get("read", False))})
    post_items: list[dict[str, Any]] = [{"pid": post["pid"], "read": bool(post.get("read", False))} for post in posts]
    return {"total": len(posts), "posts": post_items, "sentences": sentence_items}


def _load_result_content(
    app: "RSSTagApplication", user: dict[str, Any], posts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Fetch content for displayed posts, retaining the filter's sort order."""
    pids: list[str | int] = [post["pid"] for post in posts if post.get("pid") is not None]
    if not pids:
        return posts
    content_by_pid: dict[str, dict[str, Any]] = {
        str(post["pid"]): {"content": post.get("content") or {}, "read": post.get("read", False)}
        for post in app.posts.get_by_pids(
            user["sid"], pids, projection={"_id": 0, "pid": 1, "content": 1, "read": 1}
        )
    }
    return [
        {**post, **content_by_pid.get(str(post.get("pid", "")), {})}
        for post in posts
    ]


def _grouped_sentences(
    app: "RSSTagApplication", user: dict[str, Any], posts: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Load addressable sentences from single-post grouping documents."""
    pids: list[str] = [str(post["pid"]) for post in posts if post.get("pid") is not None]
    if not pids:
        return {}
    documents: list[dict[str, Any]] = app.post_grouping.get_by_post_ids(
        user["sid"], pids, projection={"_id": 0, "post_ids": 1, "sentences": 1}
    )
    return {
        str(doc["post_ids"][0]): [
            sentence for sentence in doc.get("sentences", [])
            if isinstance(sentence.get("number"), int) and sentence.get("text")
        ]
        for doc in documents if len(doc.get("post_ids") or []) == 1
    }


def _page_results(
    app: "RSSTagApplication", user: dict[str, Any], tag: str,
    matches: Iterable[dict[str, Any]], selection: dict[str, Any], page_number: int,
) -> dict[str, Any]:
    page_size: int = _posts_on_page(user)
    offset: int = (page_number - 1) * page_size
    page_posts: list[dict[str, Any]] = []
    total: int = 0
    for index, post in enumerate(matches):
        total += 1
        if offset <= index < offset + page_size:
            page_posts.append(post)
    visible: list[dict[str, Any]] = _load_result_content(app, user, page_posts)
    only_unread: bool | None = _only_unread(user)
    result: dict[str, Any] = _results(visible, tag, selection, _grouped_sentences(app, user, visible), only_unread)
    result.update(
        total=total, page=page_number, page_size=page_size,
        has_more=total > offset + page_size, only_unread=bool(only_unread),
    )
    return result


def _json_response(app: "RSSTagApplication", user: dict[str, Any], request: Request, tag: str) -> Response:
    try:
        selection: dict[str, Any] = _parse_selection(request)
        page_number: int = _parse_page(request)
        scope: str = _parse_scope(request)
    except (ValueError, TypeError) as exc:
        return Response(json.dumps({"error": str(exc)}), status=400, mimetype="application/json")
    posts: Iterator[dict[str, Any]] = _posts_for_tag(app, user, tag, selection)
    matches: Iterator[dict[str, Any]] = _matching_posts(app, user, tag, posts, selection)
    if scope == "all":
        result: dict[str, Any] = _all_results(app, user, tag, matches, selection)
    else:
        result = _page_results(app, user, tag, matches, selection, page_number)
    return Response(json.dumps(result), mimetype="application/json")


def _html_response(app: "RSSTagApplication", user: dict[str, Any], tag: str) -> Response:
    posts: list[dict[str, Any]] = list(_posts_for_tag(app, user, tag))
    tree: dict[str, Any] = _make_tree(posts, tag)
    tree["topics"] = _topic_nodes(_topic_memberships(app, user, posts))
    page: Any = app.template_env.get_template("tag-explorer.html")
    return Response(page.render(tag=tag, tree=tree, user_settings=user["settings"], provider=user.get("provider", "")), mimetype="text/html")


def on_tag_explorer_get(app: "RSSTagApplication", user: dict[str, Any], request: Request, tag: str) -> Response:
    """Render the explorer or return results for a selected tree node."""
    is_json: bool = request.args.get("format") == "json"
    try:
        if is_json:
            return _json_response(app, user, request, tag)
        return _html_response(app, user, tag)
    except Exception:
        LOG.exception("Failed to load tag explorer for %s", tag)
        if is_json:
            return Response(json.dumps({"error": "Could not load results. Please try again."}), status=500, mimetype="application/json")
        return Response("Could not load tag explorer. Please try again.", status=500, mimetype="text/plain")
