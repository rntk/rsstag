import base64
import asyncio
import logging
import re
from typing import Tuple, List, Optional, Iterator
from datetime import datetime
from hashlib import md5
import gzip

import aiohttp

from rsstag.tasks import POST_NOT_IN_PROCESSING
from rsstag.web.routes import RSSTagRoutes


class GmailProvider:
    """Gmail provider"""

    def __init__(self, config: dict):
        self._config = config
        self.no_category_name = "Gmail"
        self._api_host = "www.googleapis.com"
        self._mark_label = config["gmail"].get("mark_label", "rsstag_mark")

    def get_headers(self, user: dict) -> dict:
        """Build Authorization headers from available token fields.
        Supports both 'token' and 'access_token' keys for compatibility with
        different parts of the app or OAuth libraries.
        """
        token = user.get("token") or user.get("access_token")
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    async def get_or_create_label(self, session, user: dict) -> Optional[str]:
        """Get or create the custom label for marking emails. Returns label ID."""
        # First, try to get the label
        list_labels_url = f"https://{self._api_host}/gmail/v1/users/me/labels"
        resp = await self.make_authenticated_request(
            session, "GET", list_labels_url, user
        )

        if not resp or resp.status != 200:
            logging.error(
                f"Failed to list labels: {resp.status if resp else 'No response'}"
            )
            return None

        labels_data = await resp.json()
        labels = labels_data.get("labels", [])

        # Check if our label exists
        for label in labels:
            if label["name"] == self._mark_label:
                logging.info(
                    f"Found existing label: {self._mark_label} with id {label['id']}"
                )
                return label["id"]

        # Label doesn't exist, create it
        create_label_url = f"https://{self._api_host}/gmail/v1/users/me/labels"
        label_payload = {
            "name": self._mark_label,
            "messageListVisibility": "show",
            "labelListVisibility": "labelShow",
        }

        resp = await self.make_authenticated_request(
            session, "POST", create_label_url, user, json=label_payload
        )

        if not resp or resp.status != 200:
            logging.error(
                f"Failed to create label: {await resp.text() if resp else 'No response'}"
            )
            return None

        label_data = await resp.json()
        label_id = label_data.get("id")
        logging.info(f"Created new label: {self._mark_label} with id {label_id}")
        return label_id

    async def refresh_access_token(self, user: dict) -> Optional[str]:
        """Refresh the access token using the refresh token"""
        if "refresh_token" not in user or not user["refresh_token"]:
            logging.error("No refresh token available for user")
            return None

        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": self._config["gmail"]["client_id"],
            "client_secret": self._config["gmail"]["client_secret"],
            "refresh_token": user["refresh_token"],
            "grant_type": "refresh_token",
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(token_url, data=payload) as resp:
                    if resp.status != 200:
                        logging.error(f"Failed to refresh token: {await resp.text()}")
                        return None
                    token_data = await resp.json()
                    access_token = token_data.get("access_token")
                    if access_token:
                        # Keep both keys in sync for compatibility across the app
                        user["token"] = access_token
                        user["access_token"] = access_token
                    return access_token
            except aiohttp.ClientError as e:
                logging.error(f"Error refreshing token: {e}")
                return None

    async def fetch_email_content(self, session, url, headers):
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logging.error(f"Failed to fetch email content: {resp.status}")
                    return None
        except Exception as e:
            logging.error(f"Error fetching email content: {e}")
            return None

    async def make_authenticated_request(
        self, session, method, url, user, max_retries=5, **kwargs
    ):
        """Make an authenticated request with automatic token refresh on 401 and retry on 429

        Args:
            session: aiohttp session
            method: HTTP method (GET, POST)
            url: Request URL
            user: User dict with credentials
            max_retries: Maximum number of retries for 429 errors (default: 5)
            **kwargs: Additional arguments for the request
        """
        headers = self.get_headers(user)
        if "headers" in kwargs:
            kwargs["headers"].update(headers)
        else:
            kwargs["headers"] = headers

        # Retry loop for 429 errors
        for retry_count in range(max_retries + 1):
            # Make the request
            response = None
            if method.upper() == "GET":
                response = await session.get(url, **kwargs)
            elif method.upper() == "POST":
                response = await session.post(url, **kwargs)

            # Handle 429 Too Many Requests
            if response and response.status == 429:
                if retry_count < max_retries:
                    # Calculate exponential backoff with longer delays: 2s, 4s, 8s, 16s, 32s
                    wait_time = 2 ** (retry_count + 1)
                    logging.warning(
                        f"Received 429 Too Many Requests, retrying in {wait_time}s (attempt {retry_count + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logging.error(f"Max retries ({max_retries}) reached for 429 error")
                    return response

            # Handle 401 Unauthorized - try to refresh the token
            if response and response.status == 401:
                logging.info("Received 401, attempting to refresh token")
                new_token = await self.refresh_access_token(user)
                if not new_token:
                    logging.error("Failed to refresh token")
                    return response

                # Update user token(s) and headers
                user["token"] = new_token
                user["access_token"] = new_token
                user["token_refreshed"] = True  # Mark that token was refreshed
                headers = self.get_headers(user)
                kwargs["headers"].update(headers)

                # Retry with new token
                if method.upper() == "GET":
                    response = await session.get(url, **kwargs)
                elif method.upper() == "POST":
                    response = await session.post(url, **kwargs)

            # Return response if not 429 or if successful after retry
            return response

        return response

    def download(self, user: dict) -> Iterator[Tuple[List, List]]:
        """Fetch all unread emails"""
        posts = []
        feeds = {}
        user["token_refreshed"] = False  # Track if token was refreshed

        async def main():
            async with aiohttp.ClientSession() as session:
                # 1. Get list of unread message IDs
                list_url = (
                    f"https://{self._api_host}/gmail/v1/users/me/messages?q=is:unread"
                )
                message_ids = []
                while list_url:
                    resp = await self.make_authenticated_request(
                        session, "GET", list_url, user, max_retries=5
                    )
                    if not resp:
                        logging.error("Failed to authenticate Gmail request")
                        break
                    if resp.status != 200:
                        logging.error(f"Failed to list messages: {await resp.text()}")
                        break
                    data = await resp.json()
                    message_ids.extend(data.get("messages", []))
                    next_token = data.get("nextPageToken")
                    if next_token:
                        # Add small delay before fetching next page
                        await asyncio.sleep(0.5)
                    list_url = (
                        f"https://{self._api_host}/gmail/v1/users/me/messages?q=is:unread&pageToken={next_token}"
                        if next_token
                        else None
                    )

                if not message_ids:
                    return

                # 2. Fetch email content for each message ID in batches to avoid rate limiting
                # Process in batches of 10 with a delay between batches
                batch_size = 10
                batch_delay = 0.5  # 0.5 second delay between batches
                emails = []

                logging.info(
                    f"Fetching {len(message_ids)} emails in batches of {batch_size}"
                )
                for i in range(0, len(message_ids), batch_size):
                    batch = message_ids[i : i + batch_size]
                    email_tasks = []
                    for message in batch:
                        email_url = f"https://{self._api_host}/gmail/v1/users/me/messages/{message['id']}"
                        email_tasks.append(
                            self.fetch_email_content_authenticated(
                                session, email_url, user
                            )
                        )

                    batch_emails = await asyncio.gather(*email_tasks)
                    emails.extend(batch_emails)

                    # Add delay between batches (except for the last batch)
                    if i + batch_size < len(message_ids):
                        logging.debug(
                            f"Processed batch {i//batch_size + 1}, waiting {batch_delay}s before next batch"
                        )
                        await asyncio.sleep(batch_delay)

                routes = RSSTagRoutes(self._config["settings"]["host_name"])
                pid = 0
                for mail_data in emails:
                    if not mail_data:
                        continue

                    headers_map = {
                        h["name"].lower(): h["value"]
                        for h in mail_data["payload"]["headers"]
                    }
                    subject = headers_map.get("subject", "")
                    from_ = headers_map.get("from", "")

                    body = self.get_email_body(mail_data["payload"])

                    stream_id = md5(from_.encode("utf-8")).hexdigest()
                    if stream_id not in feeds:
                        feeds[stream_id] = {
                            "createdAt": datetime.utcnow(),
                            "title": from_,
                            "owner": user["sid"],
                            "category_id": self.no_category_name,
                            "feed_id": stream_id,
                            "origin_feed_id": from_,
                            "category_title": self.no_category_name,
                            "category_local_url": routes.get_url_by_endpoint(
                                endpoint="on_category_get",
                                params={"quoted_category": self.no_category_name},
                            ),
                            "local_url": routes.get_url_by_endpoint(
                                endpoint="on_feed_get",
                                params={"quoted_feed": stream_id},
                            ),
                            "favicon": "",
                        }

                    posts.append(
                        {
                            "content": {
                                "title": subject,
                                "content": gzip.compress(
                                    body.encode("utf-8", "replace")
                                ),
                            },
                            "feed_id": stream_id,
                            "category_id": self.no_category_name,
                            "id": mail_data["id"],
                            "url": f"https://mail.google.com/mail/u/0/#inbox/{mail_data['id']}",
                            "date": datetime.fromtimestamp(
                                int(mail_data["internalDate"]) / 1000
                            ).strftime("%x"),
                            "unix_date": float(mail_data["internalDate"]) / 1000,
                            "read": False,
                            "favorite": False,
                            "attachments": [],
                            "tags": [],
                            "bi_grams": [],
                            "pid": pid,
                            "owner": user["sid"],
                            "processing": POST_NOT_IN_PROCESSING,
                        }
                    )
                    pid += 1

        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())

        yield (posts, list(feeds.values()))

    async def fetch_email_content_authenticated(self, session, url, user):
        """Fetch email content with authentication and token refresh"""
        try:
            resp = await self.make_authenticated_request(
                session, "GET", url, user, max_retries=5
            )
            if resp and resp.status == 200:
                return await resp.json()
            else:
                logging.error(
                    f"Failed to fetch email content: {resp.status if resp else 'No response'}"
                )
                return None
        except Exception as e:
            logging.error(f"Error fetching email content: {e}")
            return None

    def get_email_body(self, payload) -> str:
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    return base64.urlsafe_b64decode(part["body"]["data"]).decode(
                        "utf-8"
                    )
                if part["mimeType"] == "text/html":
                    return base64.urlsafe_b64decode(part["body"]["data"]).decode(
                        "utf-8"
                    )
        if "body" in payload and "data" in payload["body"]:
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
        return ""

    def mark(self, data: dict, user: dict) -> Optional[bool]:
        """Mark email by adding/removing custom label"""
        message_id = data["id"]
        should_be_read = data["status"]
        url = f"https://{self._api_host}/gmail/v1/users/me/messages/{message_id}/modify"

        async def main():
            async with aiohttp.ClientSession() as session:
                # Get or create the label
                label_id = await self.get_or_create_label(session, user)
                if not label_id:
                    logging.error("Failed to get or create label")
                    return False

                # Add label if marking as read, remove if marking as unread
                if should_be_read:
                    payload = {"addLabelIds": [label_id]}
                else:
                    payload = {"removeLabelIds": [label_id]}

                resp = await self.make_authenticated_request(
                    session, "POST", url, user, json=payload
                )
                if resp and resp.status == 200:
                    logging.info(
                        f"Successfully {'added' if should_be_read else 'removed'} label {self._mark_label} to/from message {message_id}"
                    )
                    return True
                else:
                    logging.error(
                        f"Failed to mark email: {await resp.text() if resp else 'No response'}"
                    )
                    return False

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(main())

    def get_token(self, login: str, password: str) -> Optional[str]:
        # OAuth 2.0 flow is required for Gmail API.
        # This function is a placeholder.
        logging.warning(
            "get_token is not implemented for GmailProvider. OAuth is required."
        )
        return None

    def is_valid_user(self, user: dict) -> Optional[bool]:
        """Check if user's token is valid"""
        url = f"https://{self._api_host}/gmail/v1/users/me/profile"

        async def main():
            async with aiohttp.ClientSession() as session:
                resp = await self.make_authenticated_request(session, "GET", url, user)
                return resp.status == 200 if resp else False

        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(main())

        # Return whether token was refreshed as part of the validation
        return result

    def refresh_user_token(self, user: dict) -> Optional[str]:
        """Refresh user token synchronously - for use by the application"""

        async def main():
            return await self.refresh_access_token(user)

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(main())

    def sort_emails_by_domain(self, user: dict) -> Optional[bool]:
        """Sort emails by sender domain - create labels for each domain and apply them"""

        async def main():
            async with aiohttp.ClientSession() as session:
                # 1. Get list of all messages in inbox
                list_url = (
                    f"https://{self._api_host}/gmail/v1/users/me/messages?q=in:inbox"
                )
                message_ids = []
                while list_url:
                    resp = await self.make_authenticated_request(
                        session, "GET", list_url, user, max_retries=5
                    )
                    if not resp:
                        logging.error(
                            "Failed to authenticate Gmail request for sorting"
                        )
                        return False
                    if resp.status != 200:
                        logging.error(
                            f"Failed to list messages for sorting: {await resp.text()}"
                        )
                        return False
                    data = await resp.json()
                    message_ids.extend(data.get("messages", []))
                    next_token = data.get("nextPageToken")
                    if next_token:
                        # Add small delay before fetching next page
                        await asyncio.sleep(0.5)
                    list_url = (
                        f"https://{self._api_host}/gmail/v1/users/me/messages?q=in:inbox&pageToken={next_token}"
                        if next_token
                        else None
                    )

                if not message_ids:
                    logging.info("No messages found in inbox for sorting")
                    return True

                # 2. Process emails in batches to get sender domains
                batch_size = 10
                batch_delay = 0.5
                domain_emails = {}

                logging.info(f"Processing {len(message_ids)} emails for domain sorting")
                for i in range(0, len(message_ids), batch_size):
                    batch = message_ids[i : i + batch_size]
                    email_tasks = []
                    for message in batch:
                        email_url = f"https://{self._api_host}/gmail/v1/users/me/messages/{message['id']}"
                        email_tasks.append(
                            self.fetch_email_content_authenticated(
                                session, email_url, user
                            )
                        )

                    batch_emails = await asyncio.gather(*email_tasks)

                    for mail_data in batch_emails:
                        if not mail_data:
                            continue

                        # Extract sender domain from headers
                        headers_map = {
                            h["name"].lower(): h["value"]
                            for h in mail_data["payload"]["headers"]
                        }
                        from_header = headers_map.get("from", "")

                        if from_header:
                            # Extract domain from email address
                            domain = self.extract_domain(from_header)
                            if domain:
                                if domain not in domain_emails:
                                    domain_emails[domain] = []
                                domain_emails[domain].append(mail_data["id"])

                    # Add delay between batches
                    if i + batch_size < len(message_ids):
                        await asyncio.sleep(batch_delay)

                # 3. Create labels for each domain and apply them
                # Optimization: Fetch all labels once
                all_labels_map = await self.get_all_labels_map(session, user)

                for domain, email_ids in domain_emails.items():
                    # Create or get label for this domain
                    label_id = await self.get_or_create_domain_label(
                        session, user, domain, all_labels_map
                    )
                    if not label_id:
                        logging.error(
                            f"Failed to get or create label for domain {domain}"
                        )
                        continue

                    # Apply label to all emails from this domain using batchModify
                    chunk_size = 50
                    for i in range(0, len(email_ids), chunk_size):
                        chunk = email_ids[i : i + chunk_size]
                        await self.batch_apply_label(session, user, chunk, label_id)
                        await asyncio.sleep(0.1)  # Small delay between API calls

                logging.info(f"Successfully sorted {len(domain_emails)} domains")
                return True

        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(main())
        return result

    async def get_all_labels_map(self, session, user: dict) -> dict:
        """Fetch all labels and return a map of name -> id"""
        list_labels_url = f"https://{self._api_host}/gmail/v1/users/me/labels"
        resp = await self.make_authenticated_request(
            session, "GET", list_labels_url, user
        )

        if not resp or resp.status != 200:
            logging.error(
                f"Failed to list labels: {resp.status if resp else 'No response'}"
            )
            return {}

        labels_data = await resp.json()
        return {label["name"]: label["id"] for label in labels_data.get("labels", [])}

    async def get_or_create_domain_label(
        self, session, user: dict, domain: str, labels_map: Optional[dict] = None
    ) -> Optional[str]:
        """Get or create a label for a specific domain"""
        domain_label_name = f"Domain/{domain}"

        # Check if label exists in the provided map
        if labels_map and domain_label_name in labels_map:
            logging.info(
                f"Found existing label for domain {domain} in cache: {labels_map[domain_label_name]}"
            )
            return labels_map[domain_label_name]

        # Label doesn't exist (or map not provided), create it
        create_label_url = f"https://{self._api_host}/gmail/v1/users/me/labels"
        label_payload = {
            "name": domain_label_name,
            "messageListVisibility": "show",
            "labelListVisibility": "labelShow",
        }

        resp = await self.make_authenticated_request(
            session, "POST", create_label_url, user, json=label_payload
        )

        if not resp or resp.status != 200:
            logging.error(
                f"Failed to create label for domain {domain}: {await resp.text() if resp else 'No response'}"
            )
            return None

        label_data = await resp.json()
        label_id = label_data.get("id")
        logging.info(f"Created new label for domain {domain}: {label_id}")

        # Update map if provided
        if labels_map is not None:
            labels_map[domain_label_name] = label_id

        return label_id

    async def batch_apply_label(
        self, session, user: dict, email_ids: List[str], label_id: str
    ) -> bool:
        """Apply a label to multiple emails using batchModify"""
        url = f"https://{self._api_host}/gmail/v1/users/me/messages/batchModify"
        payload = {"ids": email_ids, "addLabelIds": [label_id]}

        resp = await self.make_authenticated_request(
            session, "POST", url, user, json=payload
        )
        if resp and (resp.status == 200 or resp.status == 204):
            logging.debug(
                f"Successfully applied label {label_id} to {len(email_ids)} emails"
            )
            return True
        else:
            logging.error(
                f"Failed to batch apply label: {await resp.text() if resp else 'No response'}"
            )
            return False

    async def apply_label_to_email(
        self, session, user: dict, email_id: str, label_id: str
    ) -> bool:
        """Apply a label to an email"""
        return await self.batch_apply_label(session, user, [email_id], label_id)

    def extract_domain(self, from_header: str) -> Optional[str]:
        """Extract domain from email address in From header"""
        # Look for email address in angle brackets
        email_match = re.search(r"<([^>]+)>", from_header)
        if email_match:
            email = email_match.group(1)
        else:
            # Try to find email address directly
            email_match = re.search(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", from_header
            )
            if email_match:
                email = email_match.group(0)
            else:
                return None

        # Extract domain part
        domain = email.split("@")[-1]
        return domain if domain else None
