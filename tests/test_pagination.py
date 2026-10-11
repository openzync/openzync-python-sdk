"""Tests for pagination iterators."""

from __future__ import annotations

from typing import Any

import pytest

from openzync._errors import OpenZyncError
from openzync._pagination import AsyncPaginatedIterator


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
        fetch = _make_fetch(
            [
                {
                    "data": [{"id": 1}, {"id": 2}],
                    "next_cursor": None,
                    "has_more": False,
                },
            ]
        )
        items = []
        async for item in AsyncPaginatedIterator(fetch, limit=50):
            items.append(item)
        assert len(items) == 2
        assert items[0]["id"] == 1
        assert items[1]["id"] == 2

    @pytest.mark.asyncio
    async def test_multi_page(self):
        """Multiple pages are auto-fetched."""
        fetch = _make_fetch(
            [
                {"data": [{"id": 1}], "next_cursor": "cursor-2", "has_more": True},
                {"data": [{"id": 2}], "next_cursor": None, "has_more": False},
            ]
        )
        items = []
        async for item in AsyncPaginatedIterator(fetch, limit=50):
            items.append(item)
        assert len(items) == 2
        assert items[0]["id"] == 1
        assert items[1]["id"] == 2

    @pytest.mark.asyncio
    async def test_empty_results(self):
        """Empty page stops iteration immediately."""
        fetch = _make_fetch(
            [
                {"data": [], "next_cursor": None, "has_more": False},
            ]
        )
        items = []
        async for item in AsyncPaginatedIterator(fetch, limit=50):
            items.append(item)
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_page_after_empty_fetch(self):
        """If fetch returns empty set, iteration stops."""
        fetch = _make_fetch(
            [
                {"data": [{"id": 1}], "next_cursor": "cursor-2", "has_more": True},
                {"data": [], "next_cursor": None, "has_more": False},
            ]
        )
        items = []
        async for item in AsyncPaginatedIterator(fetch, limit=50):
            items.append(item)
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_uses_items_key_fallback(self):
        """Falls back to 'items' key when 'data' is absent."""
        fetch = _make_fetch(
            [
                {"items": [{"id": 1}], "next_cursor": None, "has_more": False},
            ]
        )
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


class TestAsyncPaginatedIteratorSyncDrive:
    """Sync ``for`` drive of ``AsyncPaginatedIterator`` (via asyncio.run)."""

    def test_sync_for_across_pages(self):
        """Plain ``for`` drives the iterator — full page then short page."""
        call_count = [0]
        fetch = _make_fetch(
            [
                {"data": [{"id": 1}, {"id": 2}], "next_cursor": "c2", "has_more": True},
                {"data": [{"id": 3}], "next_cursor": None, "has_more": False},
            ],
            call_count,
        )

        items = [item["id"] for item in AsyncPaginatedIterator(fetch, limit=2)]

        assert items == [1, 2, 3]
        assert call_count[0] == 2

    def test_stop_iteration_when_exhausted(self):
        """``next`` raises StopIteration once all pages are consumed."""
        fetch = _make_fetch(
            [{"data": [{"id": 1}], "next_cursor": None, "has_more": False}]
        )
        iterator = iter(AsyncPaginatedIterator(fetch, limit=2))

        assert next(iterator)["id"] == 1
        with pytest.raises(StopIteration):
            next(iterator)

    @pytest.mark.asyncio
    async def test_sync_drive_inside_running_loop_raises(self):
        """Plain ``for`` inside a running event loop fails loud."""
        fetch = _make_fetch([{"data": [], "next_cursor": None, "has_more": False}])
        iterator = AsyncPaginatedIterator(fetch, limit=2)

        with pytest.raises(OpenZyncError, match="sync iteration inside running loop"):
            for _ in iterator:
                pass
