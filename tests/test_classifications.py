"""Tests for the OpenZync Python SDK — classifications domain."""

from __future__ import annotations

import pytest

from openzync.models.classification import (
    ClassificationListResponse,
    ClassificationResponse,
)


class TestClassificationsClient:
    """Tests for ``AsyncClassificationsClient``."""

    @pytest.mark.asyncio
    async def test_list_classifications(self, async_client, mock_http, mock_resolve):
        """GET /sessions/{sid}/classifications returns ClassificationListResponse."""
        route = mock_http.get("/v1/projects/p1/sessions/s1/classifications").respond(
            json={
                "data": [
                    {
                        "id": "c1",
                        "episode_id": "ep1",
                        "intent": "question",
                        "emotion": "curious",
                        "valence": "positive",
                        "arousal": "low",
                        "confidence": 0.92,
                        "created_at": "2026-01-01T00:00:00Z",
                        "message": "How does this work?",
                        "role": "user",
                    },
                ],
                "total": 1,
            }
        )

        result = await async_client.classifications.list("s1")

        assert isinstance(result, ClassificationListResponse)
        assert isinstance(result.data[0], ClassificationResponse)
        assert result.data[0].intent == "question"
        assert result.total == 1
        assert route.calls.last.request.url.path.endswith(
            "/sessions/s1/classifications"
        )

    @pytest.mark.asyncio
    async def test_get_classification_by_episode(
        self, async_client, mock_http, mock_resolve
    ):
        """GET /sessions/{sid}/classifications/{episode_id} returns one result."""
        route = mock_http.get(
            "/v1/projects/p1/sessions/s1/classifications/ep1"
        ).respond(
            json={
                "id": "c1",
                "episode_id": "ep1",
                "intent": "request",
                "confidence": 0.8,
                "created_at": "2026-01-01T00:00:00Z",
            }
        )

        result = await async_client.classifications.get_by_episode("s1", "ep1")

        assert isinstance(result, ClassificationResponse)
        assert result.episode_id == "ep1"
        assert route.calls.last.request.url.path.endswith(
            "/sessions/s1/classifications/ep1"
        )
