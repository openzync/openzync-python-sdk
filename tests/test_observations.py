"""Tests for the OpenZync Python SDK — observations domain."""

from __future__ import annotations

import pytest

from openzync.models.observation import ObservationListResponse, ObservationResponse


class TestObservationsClient:
    """Tests for ``AsyncObservationsClient``."""

    @pytest.mark.asyncio
    async def test_list_observations(self, async_client, mock_http, mock_resolve):
        """GET /observations returns ObservationListResponse."""
        route = mock_http.get("/v1/projects/p1/observations").respond(
            json={
                "data": [
                    {
                        "id": "o1",
                        "subject_entity_id": "e1",
                        "related_entity_id": "e2",
                        "observation_type": "co_occurrence",
                        "content": "Alice and Bob frequently co-occur",
                        "confidence": 0.85,
                        "created_at": "2026-01-01T00:00:00Z",
                        "subject_entity_name": "Alice",
                        "related_entity_name": "Bob",
                    },
                ],
                "total": 1,
            }
        )

        result = await async_client.observations.list(limit=10)

        request = route.calls.last.request
        assert request.url.params["limit"] == "10"
        assert isinstance(result, ObservationListResponse)
        assert isinstance(result.data[0], ObservationResponse)
        assert result.total == 1

    @pytest.mark.asyncio
    async def test_list_observations_with_filters(
        self, async_client, mock_http, mock_resolve
    ):
        """GET /observations passes subject_entity_id and observation_type."""
        route = mock_http.get("/v1/projects/p1/observations").respond(
            json={
                "data": [],
                "total": 0,
            }
        )

        await async_client.observations.list(
            subject_entity_id="e1", observation_type="temporal_pattern"
        )

        request = route.calls.last.request
        assert request.url.params["subject_entity_id"] == "e1"
        assert request.url.params["observation_type"] == "temporal_pattern"
