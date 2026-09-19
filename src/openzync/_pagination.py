"""Paginated iteration over list endpoints.

OpenZync uses cursor-based pagination for all list endpoints.
This module provides async and sync iterators that auto-fetch
subsequent pages as items are consumed.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from openzync._errors import OpenZyncError


class AsyncPaginatedIterator:
    """Async iterator over paginated results.

    Usage::

        async for user in client.users.list():
            print(user.name)
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

    async def _fetch_page(self) -> None:
        result = await self._fetch(self._cursor)
        self._items = result.get("data", result.get("items", []))
        self._cursor = result.get("next_cursor")
        self._has_more = result.get("has_more", False)
        self._index = 0


class SyncPaginatedIterator:
    """Sync iterator over paginated results.

    Wraps ``AsyncPaginatedIterator`` via ``asyncio.run()``.

    ⚠️  Not safe inside a running event loop (Jupyter, async apps).
        Use ``AsyncOpenZync`` / ``await`` the async iterator instead.

    Usage::

        for user in client.users.list():
            print(user.name)
    """

    def __init__(
        self,
        fetch_page: Callable[[str | None], Any],
        limit: int = 50,
    ) -> None:
        self._async_iter = AsyncPaginatedIterator(fetch_page, limit)
        self._run = asyncio.run

    def __iter__(self) -> SyncPaginatedIterator:
        return self

    def __next__(self) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise OpenZyncError(
                message=(
                    "sync client inside running loop — use AsyncOpenZync / await "
                    "the async iterator (async for ...) instead of the sync client"
                ),
            )
        try:
            return self._run(self._async_iter.__anext__())
        except StopAsyncIteration:
            raise StopIteration
