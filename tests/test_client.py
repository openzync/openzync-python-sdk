"""Tests for the OpenZync Python SDK — sync/async client entry points."""

from __future__ import annotations

import pytest

from openzync.client import AsyncOpenZync, OpenZync, _SyncDomainWrapper


class TestAsyncOpenZync:
    """Tests for ``AsyncOpenZync``."""

    @pytest.mark.asyncio
    async def test_context_manager(self, api_key, base_url):
        """__aenter__ yields client, __aexit__ closes."""
        async with AsyncOpenZync(api_key=api_key, base_url=base_url) as client:
            assert isinstance(client, AsyncOpenZync)
            assert client._http is not None
            assert client.memory is not None
            assert client.facts is not None
            assert client.graph is not None
            assert client.users is not None
            assert client.sessions is not None
            assert client.projects is not None

    @pytest.mark.asyncio
    async def test_close_explicitly(self, api_key, base_url):
        """Calling close() explicitly works."""
        client = AsyncOpenZync(api_key=api_key, base_url=base_url)
        await client.close()
        # No exception means success


class TestOpenZyncSync:
    """Tests for the sync ``OpenZync`` client."""

    def test_init_sets_up_sub_clients(self, api_key, base_url):
        """Sync client has all domain wrappers attached."""
        client = OpenZync(api_key=api_key, base_url=base_url)
        assert isinstance(client._async, AsyncOpenZync)
        assert isinstance(client.memory, _SyncDomainWrapper)
        assert isinstance(client.facts, _SyncDomainWrapper)
        assert isinstance(client.graph, _SyncDomainWrapper)
        assert isinstance(client.users, _SyncDomainWrapper)
        assert isinstance(client.sessions, _SyncDomainWrapper)
        assert isinstance(client.projects, _SyncDomainWrapper)

    def test_close(self, api_key, base_url):
        """Sync close() does not raise."""
        client = OpenZync(api_key=api_key, base_url=base_url)
        client.close()
        # No exception means success


class TestSyncDomainWrapper:
    """Tests for ``_SyncDomainWrapper``."""

    def test_getattr_non_async_returns_directly(self):
        """Non-coroutine attributes pass through unchanged."""
        class FakeAsync:
            greeting = "hello"

        wrapper = _SyncDomainWrapper(FakeAsync())
        assert wrapper.greeting == "hello"

    def test_getattr_sync_wrapper_proxies(self, api_key, base_url):
        """Sync wrapper calls async methods via asyncio.run()."""
        async_client = AsyncOpenZync(api_key=api_key, base_url=base_url)
        wrapper = _SyncDomainWrapper(async_client)
        # Check that domain attributes are accessible through the wrapper
        assert hasattr(wrapper, "_async")

    def test_wrapper_repr(self):
        """Wrapper stores a reference to the async client."""
        async_client = object()
        wrapper = _SyncDomainWrapper(async_client)
        assert wrapper._async is async_client

    def test_sync_wrapper_executes_method(self, api_key, base_url, mock_http, mock_resolve):
        """Calling an async method through the sync wrapper executes it."""
        mock_http.get("/v1/projects/p1/graph/communities").respond(json={
            "data": [
                {"id": "c1", "name": "Community 1", "summary": "",
                 "member_count": 1, "metadata": {},
                 "created_at": "2026-01-01T00:00:00Z"},
            ],
        })

        client = OpenZync(api_key=api_key, base_url=base_url)
        result = client.graph.communities()
        assert len(result) == 1
        assert result[0].name == "Community 1"
