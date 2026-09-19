"""Async HTTP transport with retry, auth, and error mapping.

Wraps ``httpx.AsyncClient`` with:
- Bearer token authentication
- Exponential backoff retry for 429/5xx responses
- Structured error mapping via ``_errors.raise_on_error``
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from openzync._errors import OpenZyncError, raise_on_error
from openzync._version import __version__ as _sdk_version

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

RETRYABLE_STATUSES: set[int] = {429, 502, 503, 504}
"""HTTP status codes that trigger automatic retry (idempotent methods only)."""

MAX_RETRIES: int = 3
"""Maximum number of retry attempts before giving up."""

BASE_DELAY: float = 1.0
"""Base delay in seconds for exponential backoff."""

DEFAULT_TIMEOUT: float = 30.0
"""Default per-request timeout in seconds."""

# httpx encodes ``data`` as ``application/x-www-form-urlencoded`` unless
# ``files`` is truthy — an empty list/dict silently downgrades a multipart
# call.  ``_EMPTY_FILES`` is truthy yet iterates to zero parts, forcing
# genuine multipart encoding with no file parts (a valid ``data``-only form).
_EMPTY_FILES = iter(())


def _has_idempotency_key(headers: dict[str, str] | None) -> bool:
    """Check for an ``Idempotency-Key`` header (case-insensitive).

    Args:
        headers: Per-request headers (may be ``None``).

    Returns:
        ``True`` when an idempotency key is present, making POST safe to retry.
    """
    if not headers:
        return False
    return any(k.lower() == "idempotency-key" for k in headers)


class AsyncHTTPTransport:
    """Low-level async HTTP transport with retry, auth, and error mapping.

    Args:
        api_key: The OpenZync API key (sent as ``Authorization: Bearer <key>``).
        base_url: Base URL of the OpenZync API server.
        timeout: Per-request timeout in seconds.
        max_retries: Maximum retry count for retryable statuses.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._project_id: str | None = None

        # browser-like UA + HTTP/2 + Accept header to reduce
        # Cloudflare JS challenge likelihood from datacenter IPs.
        # SDK identity moved to X-SDK-Version header.
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout),
            http2=True,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (compatible; OpenZyncSDK/1.0; "
                    f"+https://openzync.tech; {_sdk_version})"
                ),
                "X-SDK-Version": _sdk_version,
            },
        )

    async def close(self) -> None:
        """Close the underlying HTTP client connection pool."""
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        json_body: dict | list | None = None,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make an HTTP request with retry and error mapping.

        Retry policy: ``GET``/``PUT``/``PATCH``/``DELETE`` retry on
        429/5xx and timeouts with exponential backoff. ``POST`` is only
        retried when an ``Idempotency-Key`` header is present — without it
        the request fails fast (mapped error, no retry) so a non-idempotent
        write is never duplicated.

        Args:
            method: HTTP method (``GET``, ``POST``, ``PATCH``, ``DELETE``).
            path: URL path relative to base URL (e.g. ``/v1/users``).
            json_body: Optional JSON-serializable request body.
            params: Optional query parameters.
            headers: Optional per-request headers (e.g. ``Idempotency-Key``,
                which enables safe retry for ``POST``).

        Returns:
            Parsed JSON response body, or ``None`` for ``DELETE`` with
            ``204 No Content`` (``DELETE`` is the only method typed to
            return ``None``).

        Raises:
            OpenZyncError: Mapped from the API's RFC 7807 error response;
                ``"empty response"`` when a body-expecting method receives
                ``204``/empty 2xx; non-JSON 2xx details the status, a
                200-char content preview, and the URL.
        """
        url = self._build_url(path)
        can_retry = method.upper() != "POST" or _has_idempotency_key(headers)

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    json=json_body,
                    params=params,
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                logger.warning("http.timeout", extra={"url": url, "attempt": attempt})
                if can_retry and attempt < self._max_retries:
                    await self._wait(attempt)
                    continue
                raise OpenZyncError(
                    message=f"Request timed out after {self._max_retries} retries: {exc}",
                    status_code=504,
                ) from exc

            if (
                response.status_code in RETRYABLE_STATUSES
                and attempt < self._max_retries
                and can_retry
            ):
                logger.info(
                    "http.retry",
                    extra={
                        "url": url,
                        "status": response.status_code,
                        "attempt": attempt + 1,
                    },
                )
                await self._wait(attempt)
                continue

            # 204 No Content — only DELETE is typed to return None; any
            # body-expecting method receiving 204 is a contract violation.
            if response.status_code == 204:
                if method.upper() == "DELETE":
                    return None
                raise OpenZyncError(
                    message="empty response",
                    status_code=204,
                )

            if response.is_error:
                try:
                    body = response.json()
                except Exception:
                    body = {"detail": response.text}
                raise_on_error(response.status_code, body)

            # DELETE is typed None — an empty 2xx body means "done".
            if method.upper() == "DELETE" and not response.content:
                return None
            if not response.content:
                raise OpenZyncError(
                    message="empty response",
                    status_code=response.status_code,
                )

            try:
                return response.json()
            except Exception as exc:
                raise OpenZyncError(
                    message=(
                        f"Expected JSON from {url} "
                        f"(status {response.status_code}), "
                        f"got non-JSON body: {response.text[:200]!r}"
                    ),
                    status_code=response.status_code,
                    detail={
                        "url": url,
                        "content_preview": response.text[:200],
                    },
                ) from exc

        # Should not reach here, but safety net:
        raise OpenZyncError(
            message=f"Request failed after {self._max_retries} retries",
            status_code=500,
        )

    async def request_stream(
        self,
        method: str,
        path: str,
        json_body: dict | None = None,
        params: dict[str, str | int] | None = None,
    ) -> httpx.Response:
        """Make a streaming HTTP request (no JSON deserialization).

        Used for endpoints that return non-JSON responses (e.g. raw text).
        """
        url = self._build_url(path)
        return await self._client.request(
            method=method,
            url=url,
            json=json_body,
            params=params,
        )

    async def request_multipart(
        self,
        method: str,
        path: str,
        data: dict[str, str] | None = None,
        files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str | int] | None = None,
    ) -> Any:
        """Make a multipart/form-data HTTP request with optional file uploads.

        Used for endpoints that accept both structured JSON and binary
        file blobs (e.g. memory ingestion).

        Per-request ``headers`` are merged with the client-level headers
        (Authorization, User-Agent, X-SDK-Version stay intact — httpx merges,
        per-request wins on overlap).

        Args:
            method: HTTP method (``"POST"``, ``"PUT"``, etc.).
            path: API path (e.g. ``/v1/projects/{pid}/memory``).
            data: Form fields as a dict of string values.  The JSON
                payload should be passed as ``{"data": json.dumps(...)}``.
            files: List of file fields as ``(field_name, (filename, bytes, mime_type))``
                tuples, matching httpx's ``files`` parameter format.
            headers: Optional per-request headers (e.g. ``Idempotency-Key``).
            params: Optional query parameters.

        Returns:
            Parsed JSON response body, or ``None`` for ``DELETE`` with
            ``204 No Content`` (``DELETE`` is the only method typed to
            return ``None``).

        Raises:
            OpenZyncError: On HTTP errors (mapped from RFC 7807);
                ``"empty response"`` when a body-expecting method receives
                ``204``/empty 2xx; non-JSON 2xx details the status, a
                200-char content preview, and the URL. ``POST`` without an
                ``Idempotency-Key`` header is never retried — it fails fast.
            httpx.TimeoutException: On timeout after retries.
        """
        url = self._build_url(path)
        can_retry = method.upper() != "POST" or _has_idempotency_key(headers)

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    data=data,
                    files=files or _EMPTY_FILES,
                    headers=headers,
                    params=params,
                )
            except httpx.TimeoutException as exc:
                logger.warning(
                    "http.multipart_timeout",
                    extra={"url": url, "attempt": attempt},
                )
                if can_retry and attempt < self._max_retries:
                    await self._wait(attempt)
                    continue
                raise OpenZyncError(
                    message=f"Request timed out after {self._max_retries} retries: {exc}",
                    status_code=504,
                ) from exc

            if (
                response.status_code in RETRYABLE_STATUSES
                and attempt < self._max_retries
                and can_retry
            ):
                logger.info(
                    "http.multipart_retry",
                    extra={
                        "url": url,
                        "status": response.status_code,
                        "attempt": attempt,
                    },
                )
                await self._wait(attempt)
                continue

            # 204 No Content — only DELETE is typed to return None; any
            # body-expecting method receiving 204 is a contract violation.
            if response.status_code == 204:
                if method.upper() == "DELETE":
                    return None
                raise OpenZyncError(
                    message="empty response",
                    status_code=204,
                )

            if response.is_error:
                try:
                    body = response.json()
                except Exception:
                    body = {"detail": response.text}
                raise_on_error(response.status_code, body)

            # DELETE is typed None — an empty 2xx body means "done".
            if method.upper() == "DELETE" and not response.content:
                return None
            if not response.content:
                raise OpenZyncError(
                    message="empty response",
                    status_code=response.status_code,
                )

            try:
                return response.json()
            except Exception as exc:
                raise OpenZyncError(
                    message=(
                        f"Expected JSON from {url} "
                        f"(status {response.status_code}), "
                        f"got non-JSON body: {response.text[:200]!r}"
                    ),
                    status_code=response.status_code,
                    detail={
                        "url": url,
                        "content_preview": response.text[:200],
                    },
                ) from exc

        raise OpenZyncError(
            message=f"Request failed after {self._max_retries} retries",
            status_code=500,
        )

    def _build_url(self, path: str) -> str:
        """Ensure path starts with ``/`` and return full URL."""
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self._base_url}{path}"

    async def _wait(self, attempt: int) -> None:
        """Exponential backoff sleep."""
        delay = BASE_DELAY * (2**attempt)
        await asyncio.sleep(delay)

    async def resolve_project_id(self) -> str:
        """Resolve the project_id from the API key via the backend.

        Cached in memory for the lifetime of the client — the resolve
        endpoint is called at most once.  Subsequent calls return the
        cached value.

        Returns:
            The project UUID string scoped to this API key.

        Raises:
            ValueError: If the API key is not scoped to a project (e.g.
                org-wide keys that were created before project scoping).
            AuthenticationError: If the key is revoked or invalid.
        """
        if self._project_id is not None:
            return self._project_id

        data = await self.request("GET", "/v1/api-key/project-id")
        pid: str | None = data.get("project_id")
        if pid is None:
            raise ValueError(
                "Could not determine project_id from API key. "
                "Ensure your API key is scoped to a project."
            )
        self._project_id = pid
        return pid
