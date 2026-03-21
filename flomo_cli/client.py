"""Flomo API client.

Responsibilities:
- MD5 request signing
- HTTP transport via httpx (with retry + rate limiting)
- Response code checking and exception mapping
- All Flomo API endpoint methods
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from . import __version__
from .constants import (
    API_BASE,
    API_KEY,
    APP_VERSION,
    MAX_PAGE_SIZE,
    PLATFORM,
    SIGN_SECRET,
    TIMEZONE,
)
from .exceptions import (
    FlomoApiError,
    NotAuthenticatedError,
    NotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)

_TZ_UTC8 = timezone(timedelta(hours=8))


# ─── Signing ──────────────────────────────────────────────────────────────


def _generate_sign(params: dict[str, Any]) -> str:
    """Compute Flomo request signature.

    Algorithm (reversed from front-end JS):
    1. Sort params by key (ksort)
    2. Skip None and empty-string values (but keep integer 0)
    3. Build key=value& string; lists use key[]=item format
    4. Append SIGN_SECRET, then MD5-hash the whole string
    """
    parts: list[str] = []
    for key in sorted(params.keys()):
        value = params[key]
        if value is None or value == "":
            continue
        if isinstance(value, list):
            for item in sorted(str(v) for v in value if v is not None):
                parts.append(f"{key}[]={item}")
        else:
            parts.append(f"{key}={value}")
    raw = "&".join(parts) + SIGN_SECRET
    return hashlib.md5(raw.encode()).hexdigest()


# ─── Response handling ────────────────────────────────────────────────────


def _handle_response(response: httpx.Response) -> Any:
    """Check HTTP status and Flomo response code; raise on errors."""
    try:
        body = response.json()
    except Exception as exc:
        response.raise_for_status()
        raise FlomoApiError(f"Invalid JSON response: {response.text}") from exc

    code = body.get("code", -1)
    message = body.get("message", "")

    if code == 0:
        return body.get("data", body)

    if code == -10:
        raise NotAuthenticatedError(
            f"Token 已过期，请重新登录: flomo login（{message}）", code=code
        )
    if code == -20:
        raise NotAuthenticatedError(
            f"需要验证密码，请重新登录: flomo login（{message}）", code=code
        )
    if response.status_code == 404 or (code == -1 and "没有找到" in message):
        raise NotFoundError(message or "资源不存在", code=code)

    raise FlomoApiError(message or f"API 错误（code={code}）", code=code)


# ─── Client ───────────────────────────────────────────────────────────────


class FlomoClient:
    """Authenticated Flomo API client.

    Usage::

        with FlomoClient(token) as client:
            memos = client.list_memos()
    """

    def __init__(self, token: str) -> None:
        self._token = token
        self._http = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": f"flomo-cli/{__version__}",
                "platform": "web",
                "device-model": "web",
                "device-id": "flomo-cli",
            },
        )

    def __enter__(self) -> FlomoClient:
        return self

    def __exit__(self, *_: object) -> None:
        self._http.close()

    # ─── Internal helpers ──────────────────────────────────────────────

    @property
    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def _base_params(self) -> dict[str, str]:
        return {
            "timestamp": str(int(time.time())),
            "api_key": API_KEY,
            "app_version": APP_VERSION,
            "platform": PLATFORM,
            "webp": "1",
        }

    def _signed(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of params with 'sign' added."""
        p = dict(params)
        p["sign"] = _generate_sign(p)
        return p

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        _retry: int = 3,
    ) -> Any:
        url = f"{API_BASE}/{path}"
        last_exc: Exception | None = None
        for attempt in range(_retry):
            if attempt:
                wait = 2**attempt
                logger.debug("Retry %d/%d after %ds", attempt, _retry, wait)
                time.sleep(wait)
            try:
                resp = self._http.request(
                    method,
                    url,
                    params=query,
                    json=body,
                    headers=self._auth_headers,
                )
                logger.debug("%s %s → %d", method, url, resp.status_code)
                return _handle_response(resp)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                logger.warning("Network error (attempt %d): %s", attempt + 1, exc)
                continue
            except (FlomoApiError, ValidationError, NotFoundError, NotAuthenticatedError):
                raise  # never retry API-level errors

        raise FlomoApiError(f"请求失败，已重试 {_retry} 次: {last_exc}") from last_exc

    def _get(self, path: str, extra: dict[str, Any] | None = None) -> Any:
        """GET with signing params in query string."""
        params = self._base_params()
        if extra:
            params.update(extra)
        return self._request("GET", path, query=self._signed(params))

    def _put(self, path: str, data: dict[str, Any] | None = None) -> Any:
        """PUT with signing params merged into JSON body."""
        params = self._base_params()
        if data:
            params.update(data)
        return self._request("PUT", path, body=self._signed(params))

    def _post(self, path: str, data: dict[str, Any] | None = None) -> Any:
        """POST with signing params merged into JSON body."""
        params = self._base_params()
        if data:
            params.update(data)
        return self._request("POST", path, body=self._signed(params))

    def _delete(self, path: str) -> Any:
        """DELETE with signing params in query string."""
        return self._request("DELETE", path, query=self._signed(self._base_params()))

    # ─── Auth ──────────────────────────────────────────────────────────

    @classmethod
    def login(cls, email: str, password: str) -> dict[str, Any]:
        """Login without an existing token; returns user data including access_token."""
        params: dict[str, Any] = {
            "email": email,
            "password": password,
            "wechat_union_id": "",
            "wechat_oa_open_id": "",
            "timestamp": str(int(time.time())),
            "api_key": API_KEY,
            "app_version": APP_VERSION,
            "platform": PLATFORM,
            "webp": "1",
        }
        params["sign"] = _generate_sign(params)
        resp = httpx.post(
            f"{API_BASE}/user/login_by_email",
            json=params,
            timeout=30.0,
            headers={"User-Agent": f"flomo-cli/{__version__}"},
        )
        return _handle_response(resp)

    def get_me(self) -> dict[str, Any]:
        """Return current user profile."""
        return self._get("user/me")

    # ─── Memo read ─────────────────────────────────────────────────────

    @staticmethod
    def _exclude_deleted(memos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter out soft-deleted memos (deleted_at is not None/empty)."""
        return [m for m in memos if not m.get("deleted_at")]

    def list_memos(
        self,
        *,
        limit: int = MAX_PAGE_SIZE,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch recent memos sorted newest-first (by updated_at desc).

        Uses the ``memo/latest_updated_desc`` endpoint which natively returns
        memos in descending update order.  The API always returns up to 200
        items; ``limit`` truncates client-side when a smaller page is needed.
        """
        result = self._get("memo/latest_updated_desc")
        memos = result if isinstance(result, list) else (
            result.get("data", []) if isinstance(result, dict) else []
        )
        if not include_deleted:
            memos = self._exclude_deleted(memos)
        return memos[:limit] if limit < len(memos) else memos

    def list_memos_ascending(
        self,
        *,
        limit: int = MAX_PAGE_SIZE,
        latest_updated_at: int = 0,
        latest_slug: str = "",
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch one page of memos in ascending update order (for full sync).

        Uses the ``memo/updated/`` cursor-based incremental sync endpoint.
        Pagination ends when an empty list is returned.
        """
        extra: dict[str, Any] = {
            "limit": str(limit),
            "latest_updated_at": str(latest_updated_at),
            "tz": TIMEZONE,
        }
        if latest_slug:
            extra["latest_slug"] = latest_slug
        result = self._get("memo/updated/", extra)
        if isinstance(result, list):
            memos = result
        else:
            memos = result.get("data", []) if isinstance(result, dict) else []
        if not include_deleted:
            memos = self._exclude_deleted(memos)
        return memos

    def list_all_memos(
        self, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """Fetch every memo by paginating until the API returns an empty list."""
        all_memos: list[dict[str, Any]] = []
        latest_updated_at = 0
        latest_slug = ""

        while True:
            page = self.list_memos_ascending(
                limit=MAX_PAGE_SIZE,
                latest_updated_at=latest_updated_at,
                latest_slug=latest_slug,
                include_deleted=True,
            )
            if not page:
                break
            all_memos.extend(page)
            last = page[-1]
            latest_slug = last.get("slug", "")
            updated_at_str = last.get("updated_at", "")
            try:
                dt = datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=_TZ_UTC8
                )
                latest_updated_at = int(dt.timestamp())
            except ValueError:
                break

        if not include_deleted:
            all_memos = self._exclude_deleted(all_memos)
        return all_memos

    def get_memo(self, slug: str) -> dict[str, Any]:
        """Return a single memo by slug."""
        return self._get(f"memo/{slug}")

    def get_related_memos(self, slug: str) -> list[dict[str, Any]]:
        """Return memos semantically related to the given slug."""
        result = self._get(f"memo/{slug}/recommended", {"type": "1"})
        if isinstance(result, list):
            return result
        return result.get("data", []) if isinstance(result, dict) else []

    def get_daily_review(self) -> list[dict[str, Any]]:
        """Return today's daily-review memos.

        The ``memo/notify_of_today/`` endpoint returns a list of slugs.
        We fetch each memo individually, silently skipping any that have
        been deleted (404).
        """
        slugs = self._get("memo/notify_of_today/")
        if not isinstance(slugs, list):
            return []
        memos: list[dict[str, Any]] = []
        for slug in slugs:
            try:
                memos.append(self.get_memo(slug))
            except NotFoundError:
                logger.debug("Daily review slug %s not found, skipping", slug)
                continue
        return memos

    # ─── Memo write ────────────────────────────────────────────────────

    def create_memo(
        self,
        content: str,
        *,
        source: str = "web",
        created_at: str | None = None,
    ) -> dict[str, Any]:
        """Create a new memo. content should be HTML (wrap plain text in <p>)."""
        data: dict[str, Any] = {
            "content": content,
            "source": source,
            "tz": TIMEZONE,
        }
        if created_at:
            data["created_at"] = created_at
        return self._put("memo", data)

    def update_memo(
        self,
        slug: str,
        content: str,
        *,
        source: str = "web",
        pin: int | None = None,
    ) -> dict[str, Any]:
        """Update an existing memo."""
        data: dict[str, Any] = {
            "content": content,
            "source": source,
            "tz": TIMEZONE,
        }
        if pin is not None:
            data["pin"] = str(pin)
        return self._put(f"memo/{slug}", data)

    def delete_memo(self, slug: str) -> Any:
        """Soft-delete a memo (moves to trash)."""
        return self._delete(f"memo/{slug}")

    # ─── Tags ──────────────────────────────────────────────────────────

    def get_tag_tree(self) -> Any:
        """Return the tag tree structure."""
        return self._get("tag/tree")

    def rename_tag(self, old_tag: str, new_tag: str) -> dict[str, Any]:
        """Rename a tag across all memos (server-side atomic operation).

        Returns ``{"updated_num": N}`` where *N* is the number of memos
        whose content was rewritten by the server.
        """
        return self._post("tag/rename", {"old_tag": old_tag, "new_tag": new_tag})
