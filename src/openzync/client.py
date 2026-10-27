"""OpenZync client — sync and async entry points.

Usage::

    from openzync import AsyncOpenZync

    async with AsyncOpenZync(api_key="oz_live_...") as client:
        resp = await client.memory.ingest(
            messages=[{"role": "user", "content": "Hello"}],
            session_id="session-1",
        )
"""

from __future__ import annotations

import asyncio
from typing import Any

from openzync._http import AsyncHTTPTransport
from openzync._pagination import AsyncPaginatedIterator
from openzync._sync import _run
from openzync.classifications import AsyncClassificationsClient
from openzync.facts import AsyncFactsClient
from openzync.graph import AsyncGraphClient
from openzync.memory import AsyncMemoryClient
from openzync.observations import AsyncObservationsClient
from openzync.projects import AsyncProjectsClient
from openzync.search import AsyncSearchClient
from openzync.schemas import AsyncSchemasClient
from openzync.sessions import AsyncSessionsClient
from openzync.structured_extractions import AsyncStructuredExtractionsClient
from openzync.users import AsyncUsersClient


class AsyncOpenZync:
    """Async OpenZync client — primary implementation.

    All methods are async. Use within ``async def`` contexts.

    Args:
        api_key: The OpenZync API key.
        base_url: Base URL of the API server.
        timeout: Per-request timeout in seconds.

    Usage::

        async with AsyncOpenZync(api_key="...") as client:
            resp = await client.memory.ingest(messages=[...], session_id="session-1")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
    ) -> None:
        self._http = AsyncHTTPTransport(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        self.memory = AsyncMemoryClient(self._http)
        self.facts = AsyncFactsClient(self._http)
        self.graph = AsyncGraphClient(self._http)
        self.users = AsyncUsersClient(self._http)
        self.sessions = AsyncSessionsClient(self._http)
        self.projects = AsyncProjectsClient(self._http)
        self.search = AsyncSearchClient(self._http)
        self.observations = AsyncObservationsClient(self._http)
        self.classifications = AsyncClassificationsClient(self._http)
        self.structured_extractions = AsyncStructuredExtractionsClient(self._http)
        self.schemas = AsyncSchemasClient(self._http)

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._http.close()

    async def __aenter__(self) -> AsyncOpenZync:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


class OpenZync:
    """Sync OpenZync client — one fresh transport per call.

    Each sync method builds a short-lived ``AsyncOpenZync`` (own
    connection pool), drives it via ``asyncio.run()``, then closes it.
    A shared ``httpx.AsyncClient`` cannot cross ``asyncio.run()`` loop
    boundaries, so per-call transports are correctness, not overhead.

    ⚠️  Not safe to use inside an existing event loop (Jupyter, async apps).
       For async environments, use ``AsyncOpenZync`` directly.

    Args:
        api_key: The OpenZync API key.
        base_url: Base URL of the API server.
        timeout: Per-request timeout in seconds.

    Usage::

        client = OpenZync(api_key="...")
        resp = client.memory.ingest(messages=[...], session_id="session-1")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._project_id: str | None = None
        self.memory = _SyncDomainWrapper(self, "memory")
        self.facts = _SyncDomainWrapper(self, "facts")
        self.graph = _SyncDomainWrapper(self, "graph")
        self.users = _SyncDomainWrapper(self, "users")
        self.sessions = _SyncDomainWrapper(self, "sessions")
        self.projects = _SyncDomainWrapper(self, "projects")
        self.search = _SyncDomainWrapper(self, "search")
        self.observations = _SyncDomainWrapper(self, "observations")
        self.classifications = _SyncDomainWrapper(self, "classifications")
        self.structured_extractions = _SyncDomainWrapper(self, "structured_extractions")
        self.schemas = _SyncDomainWrapper(self, "schemas")

    def _new_client(self) -> AsyncOpenZync:
        """Build a fresh per-call client, injecting the cached project ID.

        Returns:
            An ``AsyncOpenZync`` with its own transport.
        """
        client = AsyncOpenZync(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
        )
        if self._project_id is not None:
            # note: same-package access to the transport's pid cache;
            # avoids a redundant resolve round-trip per call.
            client._http._project_id = self._project_id
        return client

    async def _drive(
        self, client: AsyncOpenZync, attr: Any, args: Any, kwargs: Any
    ) -> Any:
        """Drive one async domain method, then adopt or close the transport.

        Runs inside the per-call event loop, so the transport is
        awaited-closed here (not via :func:`_run`, which refuses a
        running loop).

        Args:
            client: The per-call client owning the transport.
            attr: The bound async domain method.
            args: Positional args for the method.
            kwargs: Keyword args for the method.

        Returns:
            The domain method's result (iterator results carry the
            transport; everything else is returned after closing it).
        """
        try:
            result = await attr(*args, **kwargs)
        except Exception:
            await client.close()
            raise
        self._project_id = client._http._project_id
        if isinstance(result, AsyncPaginatedIterator):
            # Abandoned iterators hold one pool until GC — prefer
            # exhausting the loop over `break`-ing out early.
            result._owner_close = client.close
        else:
            await client.close()
        return result

    def _run_domain(self, domain: str, name: str, *args: Any, **kwargs: Any) -> Any:
        """Run one domain method on a fresh per-call transport.

        A shared ``httpx.AsyncClient`` cannot cross ``asyncio.run()``
        loop boundaries (second call raises ``Event loop is closed``),
        so each sync call builds, uses, then closes its own
        ``AsyncOpenZync``.  The cached ``project_id`` is injected so the
        ``/v1/api-key/project-id`` lookup still happens at most once.

        Sync factories (``list_iter``) return their iterator directly —
        usable with ``for`` (sync drive) or ``async for``; the
        transport is owned by the iterator.

        Bulk users: prefer ``AsyncOpenZync`` with ``async for`` — sync
        ``for`` drives each item through a per-item ``asyncio.run()``
        (see ``AsyncPaginatedIterator.__next__``), which is fine for a
        few pages but wasteful at scale.

        Args:
            domain: Domain client attribute on ``AsyncOpenZync``.
            name: Method name on the domain client.
            *args: Positional args for the domain method.
            **kwargs: Keyword args for the domain method.

        Returns:
            The domain method's result.
        """
        client = self._new_client()
        attr = getattr(getattr(client, domain), name)
        if asyncio.iscoroutinefunction(attr):
            return _run(self._drive(client, attr, args, kwargs))
        result = attr(*args, **kwargs)
        self._project_id = client._http._project_id
        if isinstance(result, AsyncPaginatedIterator):
            # Abandoned iterators hold one pool until GC — prefer
            # exhausting the loop over `break`-ing out early.
            result._owner_close = client.close
            return result
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            _run(client.close())
            return result
        # Inside a running loop (async composition: sync factory +
        # `async for`): cannot block on close — and the pristine pool
        # never opened a connection, so GC reclaims it cleanly.
        return result

    def close(self) -> None:
        """No-op kept for API compatibility — there is no shared pool.

        Each sync call owns and closes its own transport; nothing
        persists to shut down.
        """


class _SyncDomainWrapper:
    """Routes each domain method through the owner's per-call transport.

    ⚠️  Not safe inside a running event loop — use ``AsyncOpenZync`` /
        ``await`` instead. Every sync call fails loud with ``OpenZyncError``
        when a loop is running.
    """

    def __init__(self, owner: OpenZync, domain: str) -> None:
        self._owner = owner
        self._domain = domain

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return self._owner._run_domain(self._domain, name, *args, **kwargs)

        return sync_wrapper
