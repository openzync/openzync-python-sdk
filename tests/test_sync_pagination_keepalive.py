"""User-dictated SDK tests: ``list_iter`` over real HTTP.

Covers:
    - ``list_iter`` over a multi-page result pages past p1 without
      ``RuntimeError`` (keep-alive connection reuse on the second fetch).
    - The null-cursor ``has_more`` guard stops instead of looping.

Real HTTP against a local stub server (stdlib ``http.server`` with
HTTP/1.1 keep-alive) — ``respx`` is prohibited for these tests, and no
HTTP is mocked: the real ``AsyncOpenZync`` client drives real sockets.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import pytest

from openzync.client import AsyncOpenZync


def _user_item(external_id: str) -> dict[str, Any]:
    """Minimal valid ``UserResponse`` payload."""
    now = "2026-01-01T00:00:00Z"
    return {
        "id": str(uuid.uuid4()),
        "external_id": external_id,
        "organization_id": str(uuid.uuid4()),
        "created_at": now,
        "updated_at": now,
        "permissions": [],
    }


class _StubHandler(BaseHTTPRequestHandler):
    """Two-page ``GET /v1/users`` stub with request counting."""

    server_version = "StubZync/1.0"
    protocol_version = "HTTP/1.1"  # keep-alive — p2 must reuse the connection
    mode: str = "multi"
    requests_seen: int = 0

    def log_message(self, *args: Any) -> None:  # keep test output clean
        pass

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        type(self).requests_seen += 1
        query = urlparse(self.path).query
        if type(self).mode == "null-cursor":
            self._send_json(
                {
                    "data": [_user_item("u-1"), _user_item("u-2")],
                    "next_cursor": None,
                    "has_more": True,  # lies — guard must stop anyway
                }
            )
            return
        if "cursor=c2" in query:
            self._send_json(
                {
                    "data": [_user_item("u-3")],
                    "next_cursor": None,
                    "has_more": False,
                }
            )
        else:
            self._send_json(
                {
                    "data": [_user_item("u-1"), _user_item("u-2")],
                    "next_cursor": "c2",
                    "has_more": True,
                }
            )


@pytest.fixture
def stub_server():
    """Threaded keep-alive stub; yields its base URL, then shuts down."""
    _StubHandler.requests_seen = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


class TestListIterRealHttp:
    """``list_iter`` driven by the real client over real HTTP."""

    @pytest.mark.asyncio
    async def test_list_iter_pages_past_p1(self, stub_server: str) -> None:
        """Multi-page iteration fetches p2 over keep-alive, no RuntimeError."""
        _StubHandler.mode = "multi"
        _StubHandler.requests_seen = 0
        client = AsyncOpenZync(
            api_key="oz_test_" + "k" * 60, base_url=stub_server
        )
        try:
            items = [
                item async for item in client.users.list_iter(limit=2)
            ]
        finally:
            await client.close()
        assert [u.external_id for u in items] == ["u-1", "u-2", "u-3"]
        assert _StubHandler.requests_seen == 2, (
            "p2 must be fetched over real HTTP (keep-alive reuse)"
        )

    @pytest.mark.asyncio
    async def test_null_cursor_has_more_guard_stops(
        self, stub_server: str
    ) -> None:
        """``has_more=True`` with a null cursor stops after one page."""
        _StubHandler.mode = "null-cursor"
        _StubHandler.requests_seen = 0
        client = AsyncOpenZync(
            api_key="oz_test_" + "k" * 60, base_url=stub_server
        )
        try:

            async def _collect() -> list:
                return [item async for item in client.users.list_iter(limit=2)]

            items = await asyncio.wait_for(_collect(), timeout=10)
        finally:
            await client.close()
        assert [u.external_id for u in items] == ["u-1", "u-2"]
        assert _StubHandler.requests_seen == 1, (
            "null-cursor guard must stop instead of re-fetching forever"
        )
