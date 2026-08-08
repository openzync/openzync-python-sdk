"""Tests for the OpenZync Python SDK — memory domain."""

from __future__ import annotations

import pytest
from httpx import Response

from openzync.models.memory import (
    IngestMemoryResponse,
    Message,
)
from tests.conftest import mock_error_response, mock_response


class TestMemoryClient:
    """Tests for ``AsyncMemoryClient``."""

    @pytest.mark.asyncio
    async def test_ingest_memory(self, async_client, mock_http, mock_resolve):
        """POST /memory returns IngestMemoryResponse."""
        expected = {
            "job_id": "job-456",
            "episode_count": 2,
            "status": "accepted",
            "message": "Messages accepted for processing",
        }
        mock_http.post("/v1/projects/p1/memory").respond(
            status_code=202, json=expected
        )

        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there"),
        ]
        result = await async_client.memory.ingest(messages=messages, session_id="s1")

        assert isinstance(result, IngestMemoryResponse)
        assert result.job_id == "job-456"
        assert result.episode_count == 2
        assert result.status == "accepted"

    @pytest.mark.asyncio
    async def test_ingest_memory_with_session(self, async_client, mock_http, mock_resolve):
        """POST /memory with session_id."""
        mock_http.post("/v1/projects/p1/memory").respond(
            status_code=202, json={"job_id": "j1", "episode_count": 1, "status": "accepted"}
        )

        result = await async_client.memory.ingest(
            messages=[{"role": "user", "content": "test"}],
            session_id="s1",
        )
        assert result.episode_count == 1

    @pytest.mark.asyncio
    async def test_ingest_memory_with_idempotency_key(self, async_client, mock_http, mock_resolve):
        """POST /memory with Idempotency-Key header."""
        mock_http.post("/v1/projects/p1/memory").respond(
            status_code=202, json={"job_id": "j1", "episode_count": 1, "status": "accepted"}
        )

        result = await async_client.memory.ingest(
            messages=[{"role": "user", "content": "test"}],
            session_id="s1",
            idempotency_key="idem-1",
        )
        assert result.job_id == "j1"

    @pytest.mark.asyncio
    async def test_ingest_memory_text_only_sends_multipart(
        self, async_client, mock_http, mock_resolve
    ):
        """Text-only ingest is sent as multipart/form-data, not application/json.

        The backend ``POST /v1/projects/{project_id}/memory`` endpoint accepts
        only multipart/form-data (the ``data`` form field holds the JSON
        payload) — a plain JSON body is rejected with 422.
        """
        route = mock_http.post("/v1/projects/p1/memory")
        route.respond(
            status_code=202,
            json={"job_id": "j3", "episode_count": 1, "status": "accepted"},
        )

        await async_client.memory.ingest(
            messages=[{"role": "user", "content": "text only"}],
            session_id="s1",
        )

        request = route.calls.last.request
        assert request.headers["content-type"].startswith("multipart/form-data")

    @pytest.mark.asyncio
    async def test_ingest_memory_with_blobs(self, async_client, mock_http, mock_resolve):
        """POST /memory with file blobs (multipart)."""
        mock_http.post("/v1/projects/p1/memory").respond(
            status_code=202,
            json={"job_id": "j2", "episode_count": 1, "blob_count": 1, "status": "accepted"},
        )

        result = await async_client.memory.ingest(
            messages=[{"role": "user", "content": "see attachment"}],
            session_id="s1",
            blobs=[("photo.jpg", b"\xff\xd8\xff\xe0", "image/jpeg")],
        )
        assert result.job_id == "j2"
        assert result.blob_count == 1

    @pytest.mark.asyncio
    async def test_get_context(self, async_client, mock_http, mock_resolve):
        """GET /context returns context text."""
        expected = {
            "context": "Recent Episodes (1):\n1. Hello world",
            "metadata": {"assembly_time_ms": 5.0, "source_counts": {}},
        }
        mock_http.get("/v1/projects/p1/context").respond(json=expected)

        result = await async_client.memory.get_context(
            query="hello", limit=10
        )
        assert "Hello world" in result.context
        assert result.metadata["assembly_time_ms"] == 5.0

    @pytest.mark.asyncio
    async def test_delete_memory(self, async_client, mock_http, mock_resolve):
        """DELETE /memory returns 204."""
        mock_http.delete("/v1/projects/p1/memory").respond(status_code=204)

        await async_client.memory.delete()
        # No exception means success

    @pytest.mark.asyncio
    async def test_ingest_memory_validation_error(self, async_client, mock_http, mock_resolve):
        """POST /memory with invalid data raises error."""
        mock_http.post("/v1/projects/p1/memory").respond(
            status_code=422,
            json={"detail": "Validation error", "status": 422},
        )

        with pytest.raises(Exception):
            await async_client.memory.ingest(messages=[], session_id="s1")
