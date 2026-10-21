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
        assert client._api_key == api_key
        assert client._project_id is None
        domains = [
            "memory",
            "facts",
            "graph",
            "users",
            "sessions",
            "projects",
            "search",
            "observations",
            "classifications",
            "structured_extractions",
            "schemas",
        ]
        for domain in domains:
            wrapper = getattr(client, domain)
            assert isinstance(wrapper, _SyncDomainWrapper)
            assert wrapper._owner is client
            assert wrapper._domain == domain
        assert isinstance(client._new_client(), AsyncOpenZync)

    def test_close(self, api_key, base_url):
        """Sync close() does not raise."""
        client = OpenZync(api_key=api_key, base_url=base_url)
        client.close()
        # No exception means success


class TestSyncDomainWrapper:
    """Tests for ``_SyncDomainWrapper``."""

    def test_getattr_non_async_returns_directly(self, api_key, base_url):
        """Non-underscore attrs return a callable sync wrapper; _-prefixed raise."""
        owner = OpenZync(api_key=api_key, base_url=base_url)
        wrapper = _SyncDomainWrapper(owner, "memory")
        assert callable(wrapper.ingest)
        with pytest.raises(AttributeError):
            wrapper._secret

    def test_getattr_sync_wrapper_proxies(self, api_key, base_url):
        """Wrapper stores owner and domain for proxying."""
        owner = OpenZync(api_key=api_key, base_url=base_url)
        wrapper = _SyncDomainWrapper(owner, "graph")
        assert wrapper._owner is owner
        assert wrapper._domain == "graph"

    def test_wrapper_repr(self, api_key, base_url):
        """Wrapper stores a reference to the owner client."""
        owner = OpenZync(api_key=api_key, base_url=base_url)
        wrapper = _SyncDomainWrapper(owner, "memory")
        assert wrapper._owner is owner
        assert wrapper._domain == "memory"

    def test_sync_wrapper_executes_method(
        self, api_key, base_url, mock_http, mock_resolve
    ):
        """Calling an async method through the sync wrapper executes it."""
        mock_http.get("/v1/projects/p1/graph/communities").respond(
            json={
                "data": [
                    {
                        "id": "c1",
                        "name": "Community 1",
                        "summary": "",
                        "member_count": 1,
                        "metadata": {},
                        "created_at": "2026-01-01T00:00:00Z",
                    },
                ],
            }
        )

        client = OpenZync(api_key=api_key, base_url=base_url)
        result = client.graph.communities()
        assert len(result) == 1
        assert result[0].name == "Community 1"
