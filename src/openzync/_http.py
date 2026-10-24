"""Async HTTP transport with retry, auth, and error mapping.

Wraps ``httpx.AsyncClient`` with:
- Bearer token authentication
- Exponential backoff retry for 429/5xx responses, honoring ``Retry-After``
- Structured error mapping via ``_errors.raise_on_error``
- Transport failures (connect/DNS/protocol/timeout) mapped onto
  ``_errors.TransportError`` — they never reach the API, so there is no
  response to map
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from openzync._errors import (
    AuthorizationError,
    OpenZyncError,
    RequestTimeoutError,
    TransportError,
    raise_on_error,
)
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
"""Default per-request timeout in seconds (connect, read, pool)."""

MAX_RETRY_AFTER: float = 60.0
"""Upper bound in seconds on a server-sent ``Retry-After`` delay.

A hostile or misconfigured server could otherwise stall the worker with
an absurd delay (``Retry-After: 999999999`` or an HTTP-date in year
9999). Legitimate small delays pass through untouched.
"""

WRITE_TIMEOUT: float = 300.0
"""Write budget in seconds for request bodies.

Reads stay at ``DEFAULT_TIMEOUT`` while writes get the longer of
``WRITE_TIMEOUT`` and the caller-supplied ``timeout``. Multipart memory
ingestion uploads blobs — a 30s write budget aborts large uploads
before the server has finished receiving them.
"""

# httpx encodes ``data`` as ``application/x-www-form-urlencoded`` unless
# ``files`` is truthy — an empty list/dict silently downgrades a multipart
# call.  ``_EMPTY_FILES`` is truthy yet iterates to zero parts, forcing
# genuine multipart encoding with no file parts (a valid ``data``-only form).
_EMPTY_FILES = iter(())


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Parse a ``Retry-After`` header into a non-negative delay in seconds.

    Supports both forms defined by RFC 7231 §7.1.3: delay-seconds
    (``Retry-After: 120``) and HTTP-date (``Retry-After: Wed, 21 Oct
    2015 07:28:00 GMT``), the latter resolved against the current UTC
    clock.

    Args:
        response: Response that may carry the header.

    Returns:
        Delay in seconds (``0.0`` when the server says "retry now"), or
        ``None`` when the header is absent or unparseable — the caller
        falls back to exponential backoff, the documented default.
    """
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None

    # delay-seconds form (1*DIGIT). str.isdigit() also rejects "nan" and
    # "inf", which float() would happily accept and asyncio.sleep() would
    # then reject at sleep time. isascii() keeps unicode digit-lookalikes
    # ("²".isdigit() is True but float("²") raises) on the parse path.
    if value.isascii() and value.isdigit():
        return min(float(value), MAX_RETRY_AFTER)

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if retry_at.tzinfo is None:
        # HTTP-date is defined as GMT (RFC 7231 §7.1.1.1); treat a
        # zone-less date as UTC rather than guessing local time.
        retry_at = retry_at.replace(tzinfo=UTC)
    return min(
        max(0.0, (retry_at - datetime.now(UTC)).total_seconds()), MAX_RETRY_AFTER
    )


def _attempts_phrase(attempts: int) -> str:
    """Format an attempt count for error messages (``"1 attempt"``)."""
    return f"{attempts} attempt" if attempts == 1 else f"{attempts} attempts"


def _transport_error(
    exc: httpx.TransportError,
    attempts: int,
    url: str,
) -> OpenZyncError:
    """Map a transport-level failure onto the SDK's error taxonomy.

    Every ``httpx.TransportError`` — connect refused, DNS failure, read
    error, remote protocol error, pool timeout — means the API never
    produced an HTTP response, so none of them can be mapped through
    ``raise_on_error``.  They are mapped here instead, so callers can
    catch them as ``OpenZyncError`` and tell "the backend refused the
    connection" apart from "the backend answered 502".

    Args:
        exc: The httpx transport error that aborted the request.
        attempts: Number of attempts made (1-based).
        url: The request URL — carries no credential (the API key travels
            in a header), so it is safe to include as error context.

    Returns:
        ``RequestTimeoutError`` for timeouts (a distinct, useful case
        within the transport family), ``TransportError`` for every other
        transport failure.
    """
    detail = {"url": url, "error_type": type(exc).__name__}
    if isinstance(exc, httpx.TimeoutException):
        return RequestTimeoutError(
            message=f"Request timed out after {_attempts_phrase(attempts)}: {exc}",
            detail=detail,
            status_code=504,
        )
    return TransportError(
        message=(
            f"Transport error after {_attempts_phrase(attempts)}: "
            f"{type(exc).__name__}: {exc}"
        ),
        detail=detail,
        status_code=503,
    )


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
        timeout: Per-request timeout in seconds for connect, read, and
            pool operations.  Writes use a longer budget (see
            ``WRITE_TIMEOUT``) so blob uploads are not cut off.
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
        self._timeout = timeout
        self._project_id: str | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client = self._build_client()

    def _build_client(self) -> httpx.AsyncClient:
        """Build the underlying async HTTP client."""
        # browser-like UA + HTTP/2 + Accept header to reduce
        # Cloudflare JS challenge likelihood from datacenter IPs.
        # SDK identity moved to X-SDK-Version header.
        return httpx.AsyncClient(
            base_url=self._base_url,
            # connect/read/pool stay at ``timeout``; writes get the longer
            # blob-upload budget, never below the caller's read timeout.
            timeout=httpx.Timeout(
                self._timeout, write=max(self._timeout, WRITE_TIMEOUT)
            ),
            http2=True,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (compatible; OpenZyncSDK; "
                    f"+https://openzync.tech; {_sdk_version})"
                ),
                "X-SDK-Version": _sdk_version,
            },
        )

    async def _ensure_bound_loop(self) -> None:
        """Rebuild the client when the running loop changed since creation.

        Sync ``list_iter`` drives each page in a fresh ``asyncio.run()``
        loop while reusing one transport — the pooled keep-alive
        connection stays bound to the dead loop and page 2 dies with
        ``RuntimeError: Event loop is closed``. Rebuilding on loop
        change keeps the transport usable across loops.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._loop is None:
            self._loop = loop
            return
        if self._loop is not loop:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = self._build_client()
            self._loop = loop

    async def close(self) -> None:
        """Close the underlying HTTP client connection pool."""
        await self._client.aclose()
        self._loop = None

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
        429/5xx, timeouts and transport failures (connection refused, DNS
        or protocol errors) with exponential backoff (jittered, and
        honoring the server's ``Retry-After`` header when present).
        ``POST`` is only
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
            TransportError: When the request never reached the API (connection
                refused, DNS failure, protocol error) — no HTTP response
                exists to map.  Retried like a timeout on retryable methods.
            RequestTimeoutError: When the request timed out (a
                ``TransportError`` subclass).
        """
        url = self._build_url(path)
        await self._ensure_bound_loop()
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
            except httpx.TransportError as exc:
                # TimeoutException is a TransportError subclass, so this
                # single branch covers timeouts, connect failures, DNS
                # failures and protocol errors alike — none of which carry
                # an HTTP response to map through raise_on_error.
                logger.warning(
                    "http.transport_error",
                    extra={
                        "url": url,
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                    },
                )
                if can_retry and attempt < self._max_retries:
                    await self._wait(attempt)
                    continue
                raise _transport_error(exc, attempt + 1, url) from exc

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
                await self._wait(attempt, response)
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
            message=f"Request failed after {_attempts_phrase(self._max_retries + 1)}",
            status_code=500,
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
            TransportError: When the request never reached the API (connection
                refused, DNS failure, protocol error) — no HTTP response
                exists to map.  Retried like a timeout on retryable methods.
            RequestTimeoutError: When the request timed out (a
                ``TransportError`` subclass).
        """
        url = self._build_url(path)
        await self._ensure_bound_loop()
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
            except httpx.TransportError as exc:
                logger.warning(
                    "http.multipart_transport_error",
                    extra={
                        "url": url,
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                    },
                )
                if can_retry and attempt < self._max_retries:
                    await self._wait(attempt)
                    continue
                raise _transport_error(exc, attempt + 1, url) from exc

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
                await self._wait(attempt, response)
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
            message=f"Request failed after {_attempts_phrase(self._max_retries + 1)}",
            status_code=500,
        )

    def _build_url(self, path: str) -> str:
        """Ensure path starts with ``/`` and return full URL."""
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self._base_url}{path}"

    async def _wait(self, attempt: int, response: httpx.Response | None = None) -> None:
        """Sleep before the next retry.

        Honors the server's ``Retry-After`` header (seconds or HTTP-date
        form) when the retried response carries one. Otherwise exponential
        backoff with ±50% jitter, so concurrent clients don't retry in
        lockstep (thundering herd).

        Args:
            attempt: Zero-based retry index (0 = first retry).
            response: The response being retried, if any — timeouts have
                no response to read a header from.
        """
        retry_after = _parse_retry_after(response) if response is not None else None
        if retry_after is not None:
            await asyncio.sleep(retry_after)
            return
        delay = BASE_DELAY * (2**attempt) * random.uniform(0.5, 1.5)
        await asyncio.sleep(delay)

    async def resolve_project_id(self) -> str:
        """Resolve the project_id from the API key via the backend.

        Cached in memory for the lifetime of the client — the resolve
        endpoint is called at most once.  Subsequent calls return the
        cached value.

        Returns:
            The project UUID string scoped to this API key.

        Raises:
            AuthorizationError: If the API key is authenticated but not
                scoped to a project (e.g. org-wide keys that were created
                before project scoping).
            AuthenticationError: If the key is revoked or invalid.
        """
        if self._project_id is not None:
            return self._project_id

        data = await self.request("GET", "/v1/api-key/project-id")
        pid: str | None = data.get("project_id")
        if pid is None:
            # ⚠️ BREAKING: was ValueError — the key authenticated fine but
            # lacks project scope, i.e. an authorization failure.
            raise AuthorizationError(
                "Could not determine project_id from API key. "
                "Ensure your API key is scoped to a project."
            )
        self._project_id = pid
        return pid
