"""Tests for the OpenZync Python SDK — structured extractions domain."""

from __future__ import annotations

import pytest

from openzync.models.extraction import (
    StructuredExtractionListResponse,
    StructuredExtractionResponse,
)


class TestStructuredExtractionsClient:
    """Tests for ``AsyncStructuredExtractionsClient``."""

    @pytest.mark.asyncio
    async def test_list_structured_extractions(
        self, async_client, mock_http, mock_resolve
    ):
        """GET /sessions/{sid}/structured-extractions returns list response."""
        route = mock_http.get(
            "/v1/projects/p1/sessions/s1/structured-extractions"
        ).respond(
            json={
                "items": [
                    {
                        "id": "x1",
                        "session_id": "s1",
                        "episode_id": "ep1",
                        "schema_id": None,
                        "data": {"company": "Acme", "role": "engineer"},
                        "created_at": "2026-01-01T00:00:00Z",
                    },
                ],
                "total": 1,
            }
        )

        result = await async_client.structured_extractions.list("s1")

        assert isinstance(result, StructuredExtractionListResponse)
        assert isinstance(result.items[0], StructuredExtractionResponse)
        assert result.items[0].data["company"] == "Acme"
        assert result.total == 1
        assert route.calls.last.request.url.path.endswith(
            "/sessions/s1/structured-extractions"
        )

    @pytest.mark.asyncio
    async def test_get_extraction_by_episode(
        self, async_client, mock_http, mock_resolve
    ):
        """GET /sessions/{sid}/structured-extractions/{episode_id} returns one."""
        route = mock_http.get(
            "/v1/projects/p1/sessions/s1/structured-extractions/ep1"
        ).respond(
            json={
                "id": "x1",
                "session_id": "s1",
                "episode_id": "ep1",
                "schema_id": None,
                "data": {"topic": "pricing"},
                "created_at": "2026-01-01T00:00:00Z",
            }
        )

        result = await async_client.structured_extractions.get_by_episode("s1", "ep1")

        assert isinstance(result, StructuredExtractionResponse)
        assert result.episode_id == "ep1"
        assert route.calls.last.request.url.path.endswith(
            "/sessions/s1/structured-extractions/ep1"
        )
