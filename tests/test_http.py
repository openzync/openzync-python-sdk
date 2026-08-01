"""Tests for the low-level HTTP transport layer."""

from __future__ import annotations

import httpx
import pytest
import respx
from httpx import Response

from openzync._errors import OpenZyncError
from openzync._http import AsyncHTTPTransport


TEST_API_KEY = "oz_test_" + "a" * 64
TEST_BASE_URL = "https://api.openzync.test"


@pytest.fixture
async def transport():
    t = AsyncHTTPTransport(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
    yield t
    await t.close()


class TestAsyncHTTPTransport:
    """Tests for ``AsyncHTTPTransport``."""

    @pytest.mark.asyncio
    async def test_request_204_returns_none(self, transport):
        """204 No Content returns None."""
        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            mock.get("/v1/no-content").respond(status_code=204)

            result = await transport.request("GET", "/v1/no-content")
            assert result is None

    @pytest.mark.asyncio
    async def test_request_non_json_error_body(self, transport):
        """Error response with non-JSON body is handled gracefully."""
        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            mock.get("/v1/error").respond(
                status_code=500,
                text="Internal Server Error",
                headers={"Content-Type": "text/plain"},
            )

            with pytest.raises(OpenZyncError):
                await transport.request("GET", "/v1/error")

    @pytest.mark.asyncio
    async def test_request_non_json_success_body(self, transport):
        """Success response with non-JSON body returns _raw wrapper."""
        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            mock.get("/v1/raw").respond(
                status_code=200,
                text="plain text",
                headers={"Content-Type": "text/plain"},
            )

            result = await transport.request("GET", "/v1/raw")
            assert result == {"_raw": "plain text"}

    @pytest.mark.asyncio
    async def test_request_timeout_triggers_retry(self, transport):
        """504 triggers retry, then raises GraphTimeoutError after exhaustion."""
        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            route = mock.get("/v1/timeout")
            route.respond(status_code=504)

            with pytest.raises(OpenZyncError):
                await transport.request("GET", "/v1/timeout")

    @pytest.mark.asyncio
    async def test_request_retry_exhaustion(self, transport):
        """All retries exhausted raises OpenZyncError."""
        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            route = mock.get("/v1/exhaust")
            route.side_effect = [
                Response(503),
                Response(503),
                Response(503),
                Response(503),  # 4th attempt = beyond max_retries=3
            ]

            with pytest.raises(OpenZyncError):
                await transport.request("GET", "/v1/exhaust")

    @pytest.mark.asyncio
    async def test_request_stream(self, transport):
        """request_stream returns raw httpx.Response."""
        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            mock.get("/v1/stream").respond(
                status_code=200,
                text="streamed content",
            )

            response = await transport.request_stream("GET", "/v1/stream")
            assert isinstance(response, Response)
            assert response.status_code == 200
            assert await response.aread() == b"streamed content"

    @pytest.mark.asyncio
    async def test_request_multipart_success(self, transport):
        """request_multipart sends files and returns JSON."""
        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            mock.post("/v1/upload").respond(
                status_code=202,
                json={"status": "accepted"},
            )

            result = await transport.request_multipart(
                "POST",
                "/v1/upload",
                data={"key": "value"},
                files=[("file", ("test.txt", b"hello", "text/plain"))],
            )
            assert result == {"status": "accepted"}

    @pytest.mark.asyncio
    async def test_request_multipart_204(self, transport):
        """request_multipart with 204 returns None."""
        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            mock.post("/v1/upload").respond(status_code=204)

            result = await transport.request_multipart("POST", "/v1/upload")
            assert result is None

    @pytest.mark.asyncio
    async def test_request_multipart_non_json_body(self, transport):
        """request_multipart with non-JSON error body."""
        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            mock.post("/v1/upload").respond(
                status_code=500,
                text="server error",
            )

            with pytest.raises(OpenZyncError):
                await transport.request_multipart("POST", "/v1/upload")

    @pytest.mark.asyncio
    async def test_request_multipart_retry_on_503(self, transport):
        """request_multipart retries on 503."""
        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            route = mock.post("/v1/upload")
            route.side_effect = [
                Response(503),
                Response(202, json={"status": "ok"}),
            ]

            result = await transport.request_multipart("POST", "/v1/upload")
            assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_build_url_normalizes_path(self, transport):
        """_build_url ensures path starts with /."""
        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            mock.get("https://api.openzync.test/v1/items").respond(json={"ok": True})

            # Path without leading /
            result = await transport.request("GET", "v1/items")
            assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_resolve_project_id_caches(self, transport):
        """resolve_project_id caches result after first call."""
        call_count = 0

        def handler(_):
            nonlocal call_count
            call_count += 1
            return Response(200, json={"project_id": "p1"})

        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            mock.get("/v1/api-key/project-id").side_effect = handler

            pid1 = await transport.resolve_project_id()
            pid2 = await transport.resolve_project_id()
            assert pid1 == "p1"
            assert pid2 == "p1"
            assert call_count == 1  # Only one HTTP call

    @pytest.mark.asyncio
    async def test_request_timeout_exception(self, transport):
        """TimeoutException triggers retry and eventually 504 OpenZyncError."""
        original = transport._client.request
        call_count: list[int] = [0]

        async def timeout_request(*args: object, **kwargs: object) -> object:
            call_count[0] += 1
            raise httpx.TimeoutException("Connection timed out")

        transport._client.request = timeout_request  # type: ignore[method-assign]
        try:
            with pytest.raises(OpenZyncError, match="timed out after 3 retries"):
                await transport.request("GET", "/v1/timeout")
            assert call_count[0] == 4  # max_retries + 1
        finally:
            transport._client.request = original

    @pytest.mark.asyncio
    async def test_request_timeout_then_succeeds(self, transport):
        """TimeoutException on first attempt, succeeds on retry."""
        original = transport._client.request
        call_count: list[int] = [0]

        async def flaky_request(*args: object, **kwargs: object) -> object:
            call_count[0] += 1
            if call_count[0] == 1:
                raise httpx.TimeoutException("timed out")
            return httpx.Response(200, json={"status": "ok"})

        transport._client.request = flaky_request  # type: ignore[method-assign]
        try:
            result = await transport.request("GET", "/v1/flaky")
            assert result == {"status": "ok"}
            assert call_count[0] == 2
        finally:
            transport._client.request = original

    @pytest.mark.asyncio
    async def test_request_multipart_timeout_exception(self, transport):
        """Multipart TimeoutException triggers retry and eventually 504."""
        original = transport._client.request
        call_count: list[int] = [0]

        async def timeout_request(*args: object, **kwargs: object) -> object:
            call_count[0] += 1
            raise httpx.TimeoutException("timed out")

        transport._client.request = timeout_request  # type: ignore[method-assign]
        try:
            with pytest.raises(OpenZyncError, match="timed out after 3 retries"):
                await transport.request_multipart("POST", "/v1/upload")
            assert call_count[0] == 4
        finally:
            transport._client.request = original

    @pytest.mark.asyncio
    async def test_request_multipart_non_json_success(self, transport):
        """Multipart with non-JSON success returns _raw wrapper."""
        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            mock.post("/v1/upload").respond(
                status_code=201,
                text="plain ok",
                headers={"Content-Type": "text/plain"},
            )

            result = await transport.request_multipart("POST", "/v1/upload")
            assert result == {"_raw": "plain ok"}

    @pytest.mark.asyncio
    async def test_resolve_project_id_raises_value_error(self, transport):
        """resolve_project_id raises ValueError if no project_id in response."""
        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            mock.get("/v1/api-key/project-id").respond(
                status_code=200, json={"not_project_id": "nope"}
            )

            with pytest.raises(ValueError, match="Could not determine project_id"):
                await transport.resolve_project_id()
