"""SDK retry keeps the same Idempotency-Key across retries (respx, no I/O)."""

from __future__ import annotations

import httpx
import pytest
import respx

from openzync import AsyncOpenZync


@pytest.mark.unit
async def test_retry_preserves_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 503 then 200: both attempts carry the identical Idempotency-Key."""
    monkeypatch.setenv("OPENZYNC_ALLOWED_HOSTS", "t,test")
    seen: list[str | None] = []

    async def _capture(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Idempotency-Key"))
        if len(seen) == 1:
            return httpx.Response(503, json={"detail": "busy"})
        return httpx.Response(200, json={"job_id": "j", "accepted_count": 1,
                                        "status": "accepted", "message": "ok"})

    # Exercise the transport directly: POST with idempotency key retries once
    from openzync._http import AsyncHTTPTransport

    transport = AsyncHTTPTransport(api_key="k", base_url="http://t")
    transport._client = httpx.AsyncClient(base_url="http://t")
    try:
        async with respx.mock(base_url="http://t") as mock2:
            mock2.post("/v1/projects/p/memory").mock(side_effect=_capture)
            resp = await transport.request(
                        "POST", "/v1/projects/p/memory",
                        headers={"Idempotency-Key": "stable-key-123"},
                        json_body={"a": 1},
                    )
            assert resp["job_id"] == "j"
    finally:
        await transport._client.aclose()
    assert seen and all(k == "stable-key-123" for k in seen), seen
