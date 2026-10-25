"""Tests for ``resolve_project_id`` TTL + invalidation.

- ``resolve_project_id`` re-resolves after 60s (TTL expiry, not stale cache).
- A 401 invalidates the cached project_id (next call re-resolves).
"""

from __future__ import annotations

import time

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


class TestResolveProjectIdTtl:
    """TTL expiry and auth-driven invalidation of the cached project_id."""

    @pytest.mark.asyncio
    async def test_reresolves_after_ttl(self, transport, monkeypatch):
        """Cache older than 60s is distrusted — next call hits the API."""
        now = [1_000.0]
        monkeypatch.setattr(time, "monotonic", lambda: now[0])
        call_count = 0

        def handler(_):
            nonlocal call_count
            call_count += 1
            return Response(200, json={"project_id": f"p{call_count}"})

        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            mock.get("/v1/api-key/project-id").side_effect = handler

            assert await transport.resolve_project_id() == "p1"
            now[0] += 30.0  # within TTL — served from cache
            assert await transport.resolve_project_id() == "p1"
            assert call_count == 1
            now[0] += 31.0  # 61s total — TTL expired, re-resolve
            assert await transport.resolve_project_id() == "p2"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_401_invalidates_cache(self, transport):
        """A 401 drops the cached project_id; the next resolve re-fetches."""
        calls = {"project": 0}

        def project_handler(_):
            calls["project"] += 1
            return Response(200, json={"project_id": f"p{calls['project']}"})

        with respx.mock(base_url=TEST_BASE_URL, assert_all_mocked=True) as mock:
            mock.get("/v1/api-key/project-id").side_effect = project_handler
            mock.get("/v1/other").respond(status_code=401, json={"detail": "revoked"})

            assert await transport.resolve_project_id() == "p1"
            assert calls["project"] == 1

            with pytest.raises(OpenZyncError):
                await transport.request("GET", "/v1/other")

            # Cache was invalidated by the 401 — re-resolve hits the API.
            assert await transport.resolve_project_id() == "p2"
            assert calls["project"] == 2
