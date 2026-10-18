"""Paginated iteration over list endpoints.

OpenZync uses cursor-based pagination for all list endpoints.
``AsyncPaginatedIterator`` is dual-mode: ``async for`` drives it
inside an event loop, plain ``for`` drives it via ``asyncio.run()``.
"""

from __future__ import annotations

from typing import Any, Callable

from openzync._sync import _run


class AsyncPaginatedIterator:
    """Iterator over paginated results — async loop or sync drive.

    Two drive modes share one instance:

    - ``async for item in client.users.list_iter():`` — inside an
      already-running event loop (``AsyncOpenZync``).
    - ``for item in client.users.list_iter():`` — sync drive, each
      ``__next__`` runs one ``__anext__`` step in a fresh event loop
      via ``asyncio.run()`` (the sync ``OpenZync`` client).

    ⚠️  Sync iteration inside a running event loop (Jupyter, async
        apps) fails loud with ``OpenZyncError`` — use ``async for``
        there instead.
    """

    def __init__(
        self,
        fetch_page: Callable[[str | None], Any],
        limit: int = 50,
    ) -> None:
        self._fetch = fetch_page
        self._limit = limit
        self._items: list[Any] = []
        self._index: int = 0
        self._cursor: str | None = None
        self._has_more: bool = True

    def __aiter__(self) -> AsyncPaginatedIterator:
        return self

    async def __anext__(self) -> Any:
        if self._index >= len(self._items):
            if not self._has_more:
                raise StopAsyncIteration
            await self._fetch_page()

        if self._index >= len(self._items):
            raise StopAsyncIteration

        item = self._items[self._index]
        self._index += 1
        return item

    def __iter__(self) -> AsyncPaginatedIterator:
        """Return self for plain ``for`` iteration.

        Returns:
            This iterator, driven synchronously by ``__next__``.
        """
        return self

    def __next__(self) -> Any:
        """Return the next item, driving the async step synchronously.

        Runs ``__anext__`` in a fresh event loop via ``asyncio.run()``
        — the same drive pattern ``_SyncDomainWrapper`` uses for
        coroutines. Page fetches happen lazily: only exhausted
        buffers trigger ``self._fetch``.

        Raises:
            OpenZyncError: If called inside a running event loop —
                use ``AsyncOpenZync`` / ``async for`` instead.
            StopIteration: When all pages are exhausted.
        """
        try:
            return _run(
                self.__anext__(),
                loop_message=(
                    "sync iteration inside running loop — use AsyncOpenZync / "
                    "await the async iterator (async for ...) instead of "
                    "the sync client"
                ),
            )
        except StopAsyncIteration:
            raise StopIteration

    async def _fetch_page(self) -> None:
        result = await self._fetch(self._cursor)
        if isinstance(result, dict):
            self._items = result.get("data", result.get("items", []))
            self._cursor = result.get("next_cursor")
            self._has_more = result.get("has_more", False)
        else:
            # Pydantic list response (e.g. SessionListResponse) — the
            # typed replacement for the old bare-dict list payloads.
            self._items = list(getattr(result, "data", []))
            self._cursor = getattr(result, "next_cursor", None)
            self._has_more = getattr(result, "has_more", False)
        self._index = 0
