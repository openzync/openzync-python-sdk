"""Sync bridge for the async SDK — one shared ``asyncio.run()`` guard.

All sync entry points (``OpenZync``, ``AsyncPaginatedIterator`` sync
iteration, LangChain sync methods) drive coroutines through :func:`_run`,
which fails loud inside a running event loop instead of raising the
cryptic ``asyncio.run() cannot be called from a running event loop``.
"""

from __future__ import annotations

import asyncio
from typing import Any

from openzync._errors import OpenZyncError

_DEFAULT_LOOP_MESSAGE = (
    "sync client inside running loop — use AsyncOpenZync / await "
    "instead of the sync client"
)
"""Fail-loud message when ``_run`` is called inside a running loop."""


def _run(coro: Any, *, loop_message: str = _DEFAULT_LOOP_MESSAGE) -> Any:
    """Drive a coroutine to completion from sync code.

    BREAKING: sync entry points raise (instead of hanging or returning
    partial results) when called inside a running event loop — use
    ``AsyncOpenZync`` with ``await`` there instead.

    Args:
        coro: The coroutine to run in a fresh event loop.
        loop_message: Override for the fail-loud message, so call sites
            with a more specific alternative (e.g. ``async for`` for
            paginated iteration) can point at it.

    Returns:
        The coroutine's result.

    Raises:
        OpenZyncError: If an event loop is already running in this
            thread — use ``AsyncOpenZync`` / ``await`` instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise OpenZyncError(message=loop_message)
    return asyncio.run(coro)
