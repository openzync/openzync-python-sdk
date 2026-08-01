"""Tests for pagination iterators."""

from __future__ import annotations

from typing import Any

import pytest

from openzync._pagination import AsyncPaginatedIterator, SyncPaginatedIterator


def _make_fetch(pages: list[dict[str, Any]], call_count: list[int] | None = None):
    """Create a fetch callback that returns pre-defined pages."""
    call_count = call_count or [0]

    async def fetch(cursor: str | None = None) -> dict[str, Any]:
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(pages):
            return pages[idx]
        return {"data": [], "next_cursor": None, "has_more": False}

    return fetch


class TestAsyncPaginatedIterator:
    """Tests for ``AsyncPaginatedIterator``."""

    @pytest.mark.asyncio
    async def test_single_page(self):
        """Single page of results is iterated correctly."""
        fetch = _make_fetch([
            {"data": [{"id": 1}, {"id": 2}], "next_cursor": None, "has_more": False},
        ])
        items = []
        async for item in AsyncPaginatedIterator(fetch, limit=50):
            items.append(item)
        assert len(items) == 2
        assert items[0]["id"] == 1
        assert items[1]["id"] == 2

    @pytest.mark.asyncio
    async def test_multi_page(self):
        """Multiple pages are auto-fetched."""
        fetch = _make_fetch([
            {"data": [{"id": 1}], "next_cursor": "cursor-2", "has_more": True},
            {"data": [{"id": 2}], "next_cursor": None, "has_more": False},
        ])
        items = []
        async for item in AsyncPaginatedIterator(fetch, limit=50):
            items.append(item)
        assert len(items) == 2
        assert items[0]["id"] == 1
        assert items[1]["id"] == 2

    @pytest.mark.asyncio
    async def test_empty_results(self):
        """Empty page stops iteration immediately."""
        fetch = _make_fetch([
            {"data": [], "next_cursor": None, "has_more": False},
        ])
        items = []
        async for item in AsyncPaginatedIterator(fetch, limit=50):
            items.append(item)
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_page_after_empty_fetch(self):
        """If fetch returns empty set, iteration stops."""
        fetch = _make_fetch([
            {"data": [{"id": 1}], "next_cursor": "cursor-2", "has_more": True},
            {"data": [], "next_cursor": None, "has_more": False},
        ])
        items = []
        async for item in AsyncPaginatedIterator(fetch, limit=50):
            items.append(item)
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_uses_items_key_fallback(self):
        """Falls back to 'items' key when 'data' is absent."""
        fetch = _make_fetch([
            {"items": [{"id": 1}], "next_cursor": None, "has_more": False},
        ])
        items = []
        async for item in AsyncPaginatedIterator(fetch, limit=50):
            items.append(item)
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_aiter_returns_self(self):
        """__aiter__ returns self."""
        fetch = _make_fetch([{"data": [], "next_cursor": None, "has_more": False}])
        iterator = AsyncPaginatedIterator(fetch, limit=50)
        assert iterator.__aiter__() is iterator


class TestSyncPaginatedIterator:
    """Tests for ``SyncPaginatedIterator``."""

    def test_single_page(self):
        """Sync wrapper iterates a single page."""
        fetch = _make_fetch([
            {"data": [{"id": 1}], "next_cursor": None, "has_more": False},
        ])
        items = []
        for item in SyncPaginatedIterator(fetch, limit=50):
            items.append(item)
        assert len(items) == 1

    def test_multi_page(self):
        """Sync wrapper auto-fetches multiple pages."""
        fetch = _make_fetch([
            {"data": [{"id": 1}], "next_cursor": "c2", "has_more": True},
            {"data": [{"id": 2}], "next_cursor": None, "has_more": False},
        ])
        items = []
        for item in SyncPaginatedIterator(fetch, limit=50):
            items.append(item)
        assert len(items) == 2

    def test_empty(self):
        """Sync wrapper handles empty results."""
        fetch = _make_fetch([
            {"data": [], "next_cursor": None, "has_more": False},
        ])
        items = []
        for item in SyncPaginatedIterator(fetch, limit=50):
            items.append(item)
        assert len(items) == 0

    def test_iter_returns_self(self):
        """__iter__ returns self."""
        fetch = _make_fetch([{"data": [], "next_cursor": None, "has_more": False}])
        iterator = SyncPaginatedIterator(fetch, limit=50)
        assert iterator.__iter__() is iterator
