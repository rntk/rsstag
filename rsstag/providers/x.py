import asyncio
import base64
import gzip
import html
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlencode

import aiohttp

from rsstag.providers.pid import generate_post_pid
from rsstag.providers.providers import X
from rsstag.tasks import POST_NOT_IN_PROCESSING
from rsstag.web.routes import RSSTagRoutes


class XProviderError(Exception):
    """Raised when X API errors should be surfaced to the user."""

    def __init__(self, message: str, user_message: Optional[str] = None, retoken: bool = False) -> None:
        super().__init__(message)
        self.user_message = user_message or message
        self.retoken = retoken


class XProvider:
    """X.com provider backed by the official OAuth 2.0 and REST APIs."""

    def __init__(self, config: dict):
        self._config = config
        self._provider_config = config.get(X, {})
        self._api_base = self._provider_config.get("api_base", "https://api.x.com")
        self._auth_base = self._provider_config.get("auth_base", "https://x.com")
        self._timeline_category = "X"
        self._default_max_results = int(self._provider_config.get("max_results", 50))
        self._timeout = aiohttp.ClientTimeout(total=60)

    def get_authorization_url(self, redirect_uri: str, state: str, code_challenge: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self._provider_config.get("client_id", ""),
            "redirect_uri": redirect_uri,
            "scope": "tweet.read users.read follows.read offline.access",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self._auth_base}/i/oauth2/authorize?{urlencode(params)}"

    def get_headers(self, user: dict) -> dict:
        token = user.get("access_token") or user.get("token")
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def _get_client_auth_headers(self) -> Dict[str, str]:
        client_id = self._provider_config.get("client_id", "")
        client_secret = self._provider_config.get("client_secret", "")
        headers: Dict[str, str] = {}
        if client_id and client_secret:
            credentials = f"{client_id}:{client_secret}".encode("utf-8")
            headers["Authorization"] = (
                f"Basic {base64.b64encode(credentials).decode('ascii')}"
            )
        return headers

    async def refresh_access_token(self, user: dict) -> Optional[str]:
        refresh_token = user.get("refresh_token")
        client_id = self._provider_config.get("client_id", "")
        if not refresh_token or not client_id:
            logging.error("Missing X refresh token or client id for user %s", user.get("sid"))
            return None

        payload = {
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "client_id": client_id,
        }
        client_secret = self._provider_config.get("client_secret", "")
        if client_secret:
            payload["client_secret"] = client_secret

        token_url = f"{self._api_base}/2/oauth2/token"
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            try:
                async with session.post(
                    token_url,
                    data=payload,
                    headers=self._get_client_auth_headers(),
                ) as resp:
                    if resp.status != 200:
                        logging.error("Failed to refresh X token: %s", await resp.text())
                        return None
                    token_data = await resp.json()
            except aiohttp.ClientError as exc:
                logging.error("Error refreshing X token: %s", exc)
                return None

        access_token = token_data.get("access_token")
        if not access_token:
            logging.error("No access token returned while refreshing X token")
            return None

        user["token"] = access_token
        user["access_token"] = access_token
        user["token_refreshed"] = True
        if token_data.get("refresh_token"):
            user["refresh_token"] = token_data["refresh_token"]
        if token_data.get("expires_in"):
            user["token_expires_at"] = int(time.time()) + int(token_data["expires_in"])
        return access_token

    async def make_authenticated_request(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        user: dict,
        max_retries: int = 4,
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        headers = dict(kwargs.pop("headers", {}))
        headers.update(self.get_headers(user))

        for retry_count in range(max_retries + 1):
            response: Optional[aiohttp.ClientResponse] = None
            try:
                response = await session.request(method.upper(), url, headers=headers, **kwargs)
            except aiohttp.ClientError as exc:
                logging.error("X request failed for %s: %s", url, exc)
                if retry_count >= max_retries:
                    raise XProviderError(
                        f"X request failed for {url}: {exc}",
                        "X request failed. Please try again later.",
                    ) from exc
                await asyncio.sleep(min(2 ** retry_count, 15))
                continue

            if response.status == 429:
                if retry_count >= max_retries:
                    error_text = await response.text()
                    response.release()
                    raise XProviderError(
                        f"X rate limit reached for {url}: {error_text}",
                        "X rate limit reached. Please try again later.",
                    )
                retry_after = response.headers.get("Retry-After")
                reset_at = response.headers.get("x-rate-limit-reset")
                wait_time = 2 ** (retry_count + 1)
                if retry_after:
                    try:
                        wait_time = max(wait_time, int(retry_after))
                    except ValueError:
                        pass
                elif reset_at:
                    try:
                        wait_time = max(wait_time, int(reset_at) - int(time.time()))
                    except ValueError:
                        pass
                response.release()
                await asyncio.sleep(max(wait_time, 1))
                continue

            if response.status == 401:
                response.release()
                new_token = await self.refresh_access_token(user)
                if not new_token:
                    raise XProviderError(
                        f"X authentication expired for {url}",
                        "X authentication expired. Reconnect X.",
                        retoken=True,
                    )
                headers.update(self.get_headers(user))
                continue

            return response

        raise XProviderError(
            f"Unable to complete X request for {url}",
            "Unable to complete X request. Please try again later.",
        )

    async def _get_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
        user: dict,
        params: Optional[dict] = None,
    ) -> dict:
        resp = await self.make_authenticated_request(
            session, "GET", url, user, params=params or {}
        )
        if resp.status != 200:
            error_text = await resp.text()
            logging.error("Unexpected X API status %s for %s: %s", resp.status, url, error_text)
            if resp.status in (401, 403):
                raise XProviderError(
                    f"X access denied for {url}: {error_text}",
                    "X API access denied. Check app permissions or reconnect X.",
                    retoken=resp.status == 401,
                )
            raise XProviderError(
                f"Unexpected X API status {resp.status} for {url}: {error_text}",
                "X request failed. Please try again later.",
            )
        try:
            return await resp.json()
        except aiohttp.ContentTypeError as exc:
            logging.error("Invalid X API JSON for %s: %s", url, exc)
            raise XProviderError(
                f"Invalid X API JSON for {url}: {exc}",
                "X returned an unexpected response. Please try again later.",
            ) from exc

    async def get_me(self, session: aiohttp.ClientSession, user: dict) -> Optional[dict]:
        data = await self._get_json(
            session,
            f"{self._api_base}/2/users/me",
            user,
            params={"user.fields": "username,name,profile_image_url"},
        )
        return data.get("data")

    async def list_following(self, user: dict) -> List[dict]:
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            owner_id = user.get("x_user_id")
            if not owner_id:
                me = await self.get_me(session, user)
                if not me:
                    return []
                owner_id = me.get("id")
                if owner_id:
                    user["provider_updates"] = {
                        **user.get("provider_updates", {}),
                        "x_user_id": owner_id,
                        "x_username": me.get("username", ""),
                        "login": me.get("username", ""),
                    }

            params = {
                "max_results": min(self._default_max_results, 1000),
                "user.fields": "username,name,profile_image_url",
            }
            feeds: List[dict] = []
            pagination_token = ""
            while True:
                if pagination_token:
                    params["pagination_token"] = pagination_token
                data = await self._get_json(
                    session,
                    f"{self._api_base}/2/users/{owner_id}/following",
                    user,
                    params=params,
                )
                if not data:
                    break
                for item in data.get("data", []):
                    feeds.append(
                        {
                            "id": str(item.get("id", "")),
                            "title": f"@{item.get('username', item.get('name', 'unknown'))}",
                            "category": "Following",
                        }
                    )
                meta = data.get("meta", {})
                pagination_token = meta.get("next_token", "")
                if not pagination_token:
                    break
            return feeds

    async def _lookup_users(
        self, session: aiohttp.ClientSession, user: dict, user_ids: List[str]
    ) -> Dict[str, dict]:
        if not user_ids:
            return {}
        users_by_id: Dict[str, dict] = {}
        chunk_size = 100
        for index in range(0, len(user_ids), chunk_size):
            chunk = user_ids[index : index + chunk_size]
            data = await self._get_json(
                session,
                f"{self._api_base}/2/users",
                user,
                params={
                    "ids": ",".join(chunk),
                    "user.fields": "username,name,profile_image_url",
                },
            )
            users_by_id.update(
                {
                    str(item.get("id")): item
                    for item in data.get("data", [])
                    if item.get("id")
                }
            )
        return users_by_id

    def _make_feed(self, user: dict, feed_id: str, origin_feed_id: str, title: str, routes: RSSTagRoutes) -> dict:
        return {
            "createdAt": datetime.now(timezone.utc),
            "title": title,
            "owner": user["sid"],
            "category_id": self._timeline_category,
            "feed_id": feed_id,
            "origin_feed_id": origin_feed_id,
            "category_title": self._timeline_category,
            "category_local_url": routes.get_url_by_endpoint(
                endpoint="on_category_get",
                params={"quoted_category": self._timeline_category},
            ),
            "local_url": routes.get_url_by_endpoint(
                endpoint="on_feed_get",
                params={"quoted_feed": feed_id},
            ),
            "favicon": "",
        }

    def _make_post(
        self,
        user: dict,
        feed_id: str,
        post: dict,
        author_by_id: Dict[str, dict],
    ) -> dict:
        author_id = str(post.get("author_id", ""))
        author = author_by_id.get(author_id, {})
        username = author.get("username", "")
        entities = post.get("entities", {}) or {}
        attachments: List[str] = []
        text_parts = [html.escape(post.get("text", ""))]

        for url_item in entities.get("urls", []) or []:
            expanded = url_item.get("expanded_url") or url_item.get("url")
            if expanded:
                attachments.append(expanded)
                display_url = html.escape(expanded)
                text_parts.append(f'<p><a href="{display_url}">{display_url}</a></p>')

        url = f"https://x.com/i/web/status/{post['id']}"
        if username:
            url = f"https://x.com/{username}/status/{post['id']}"

        created_at = post.get("created_at")
        unix_date = time.time()
        date_str = datetime.now(timezone.utc).strftime("%x")
        if created_at:
            try:
                created_dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
            except ValueError:
                created_dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            unix_date = created_dt.timestamp()
            date_str = created_dt.strftime("%x")

        return {
            "content": {
                "title": "",
                "content": gzip.compress("".join(text_parts).encode("utf-8", "replace")),
                "format": "html",
            },
            "feed_id": feed_id,
            "category_id": self._timeline_category,
            "id": str(post["id"]),
            "url": url,
            "date": date_str,
            "unix_date": unix_date,
            "read": False,
            "favorite": False,
            "attachments": attachments,
            "tags": [],
            "bi_grams": [],
            "pid": generate_post_pid(X, feed_id, str(post["id"])),
            "owner": user["sid"],
            "processing": POST_NOT_IN_PROCESSING,
        }

    def _normalize_fetch_mode(self, user: dict) -> str:
        fetch_mode = str(user.get("x_fetch_mode", user.get("fetch_mode", "unread"))).lower()
        if fetch_mode not in {"recent", "unread"}:
            return "unread"
        return fetch_mode

    def _selected_following_ids(self, user: dict, selection: Optional[dict]) -> List[str]:
        if selection and selection.get("feeds") is not None:
            return [str(feed_id) for feed_id in selection.get("feeds", []) if feed_id]
        return [str(feed_id) for feed_id in user.get("x_selected_feeds", []) if feed_id]

    def _home_enabled(self, user: dict, selection: Optional[dict]) -> bool:
        if selection and selection.get("channels") is not None:
            return "home" in selection.get("channels", [])
        return bool(user.get("x_home_enabled", True))

    async def _fetch_timeline_page(
        self,
        session: aiohttp.ClientSession,
        url: str,
        user: dict,
        params: dict,
    ) -> Optional[dict]:
        tweet_fields = "created_at,author_id,entities,referenced_tweets"
        expansions = "author_id,attachments.media_keys"
        media_fields = "preview_image_url,url"
        merged_params = {
            "tweet.fields": tweet_fields,
            "expansions": expansions,
            "user.fields": "username,name",
            "media.fields": media_fields,
            **params,
        }
        return await self._get_json(session, url, user, params=merged_params)

    async def _download_home(
        self,
        session: aiohttp.ClientSession,
        user: dict,
        routes: RSSTagRoutes,
        feeds: Dict[str, dict],
        posts: List[dict],
    ) -> None:
        owner_id = user.get("x_user_id")
        if not owner_id:
            me = await self.get_me(session, user)
            if not me:
                return
            owner_id = me.get("id")
            user["provider_updates"] = {
                **user.get("provider_updates", {}),
                "x_user_id": owner_id,
                "x_username": me.get("username", ""),
                "login": me.get("username", ""),
            }

        max_results = int(user.get("x_max_results_per_sync", self._default_max_results))
        max_results = max(5, min(max_results, 100))
        params: Dict[str, Any] = {"max_results": max_results}
        if self._normalize_fetch_mode(user) == "unread" and user.get("x_home_since_id"):
            params["since_id"] = str(user["x_home_since_id"])
        exclude_values = [
            value
            for value, enabled in (
                ("replies", bool(user.get("x_exclude_replies"))),
                ("retweets", bool(user.get("x_exclude_reposts"))),
            )
            if enabled
        ]
        if exclude_values:
            params["exclude"] = ",".join(exclude_values)
        data = await self._fetch_timeline_page(
            session,
            f"{self._api_base}/2/users/{owner_id}/timelines/reverse_chronological",
            user,
            params,
        )
        if not data:
            return

        feed_id = "x-home"
        feeds[feed_id] = self._make_feed(user, feed_id, "home", "X Home", routes)
        includes = data.get("includes", {})
        users_by_id = {
            str(item.get("id")): item
            for item in includes.get("users", [])
            if item.get("id")
        }
        newest_id = user.get("x_home_since_id", "")
        for post in data.get("data", []) or []:
            posts.append(self._make_post(user, feed_id, post, users_by_id))
            post_id = str(post.get("id", ""))
            if post_id and (not newest_id or int(post_id) > int(newest_id)):
                newest_id = post_id
        if self._normalize_fetch_mode(user) == "unread" and newest_id:
            user["provider_updates"] = {
                **user.get("provider_updates", {}),
                "x_home_since_id": newest_id,
            }

    async def _download_following(
        self,
        session: aiohttp.ClientSession,
        user: dict,
        selected_feed_ids: List[str],
        routes: RSSTagRoutes,
        feeds: Dict[str, dict],
        posts: List[dict],
    ) -> None:
        if not selected_feed_ids:
            return
        max_results = int(user.get("x_max_results_per_sync", self._default_max_results))
        max_results = max(5, min(max_results, 100))
        users_by_id = await self._lookup_users(session, user, selected_feed_ids)
        follow_since_ids = dict(user.get("x_follow_since_ids", {}))
        unread_mode = self._normalize_fetch_mode(user) == "unread"

        for followed_id in selected_feed_ids:
            feed_id = f"x-user-{followed_id}"
            account = users_by_id.get(followed_id, {})
            username = account.get("username", followed_id)
            title = f"@{username}"
            feeds[feed_id] = self._make_feed(user, feed_id, followed_id, title, routes)
            params: Dict[str, Any] = {
                "max_results": max_results,
                "exclude": ",".join(
                    [
                        value
                        for value, enabled in (
                            ("replies", bool(user.get("x_exclude_replies"))),
                            ("retweets", bool(user.get("x_exclude_reposts"))),
                        )
                        if enabled
                    ]
                ),
            }
            if not params["exclude"]:
                params.pop("exclude")
            if unread_mode and follow_since_ids.get(followed_id):
                params["since_id"] = str(follow_since_ids[followed_id])
            data = await self._fetch_timeline_page(
                session,
                f"{self._api_base}/2/users/{followed_id}/tweets",
                user,
                params,
            )
            if not data:
                continue
            includes = data.get("includes", {})
            author_by_id = {
                str(item.get("id")): item
                for item in includes.get("users", [])
                if item.get("id")
            }
            if followed_id not in author_by_id and account:
                author_by_id[followed_id] = account

            newest_id = follow_since_ids.get(followed_id, "")
            for post in data.get("data", []) or []:
                posts.append(self._make_post(user, feed_id, post, author_by_id))
                post_id = str(post.get("id", ""))
                if post_id and (not newest_id or int(post_id) > int(newest_id)):
                    newest_id = post_id
            if unread_mode and newest_id:
                follow_since_ids[followed_id] = newest_id

        if unread_mode:
            user["provider_updates"] = {
                **user.get("provider_updates", {}),
                "x_follow_since_ids": follow_since_ids,
            }

    def download(
        self, user: dict, selection: Optional[dict] = None
    ) -> Iterator[Tuple[List, List]]:
        posts: List[dict] = []
        feeds: Dict[str, dict] = {}
        user["token_refreshed"] = False

        async def main() -> None:
            routes = RSSTagRoutes(self._config["settings"]["host_name"])
            selected_feed_ids = self._selected_following_ids(user, selection)
            home_enabled = self._home_enabled(user, selection)
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                if home_enabled:
                    await self._download_home(session, user, routes, feeds, posts)
                await self._download_following(
                    session,
                    user,
                    selected_feed_ids,
                    routes,
                    feeds,
                    posts,
                )

        asyncio.run(main())
        yield posts, list(feeds.values())
