"""Tests for the OpenZync Python SDK — search domain."""

from __future__ import annotations

import pytest

from openzync.models.search import GlobalSearchItem, GlobalSearchResponse


class TestSearchClient:
    """Tests for ``AsyncSearchClient``."""

    @pytest.mark.asyncio
    async def test_global_search(self, async_client, mock_http):
        """GET /v1/search sends q (alias) and limit params.

        No ``mock_resolve`` — global search is org-scoped and never
        resolves a project_id."""
        route = mock_http.get("/v1/search").respond(
            json={
                "results": [
                    {
                        "type": "project",
                        "id": "p9",
                        "label": "Acme Project",
                        "subtitle": "The Acme workspace",
                        "href": "/projects/p9",
                    },
                    {
                        "type": "session",
                        "id": "s9",
                        "label": "support-chat-42",
                        "subtitle": None,
                        "href": "/projects/p9/sessions/s9",
                    },
                ],
                "query": "acme",
            }
        )

        result = await async_client.search.global_search(query="acme", limit=5)

        request = route.calls.last.request
        assert request.url.params["q"] == "acme"
        assert request.url.params["limit"] == "5"
        assert isinstance(result, GlobalSearchResponse)
        assert result.query == "acme"
        assert isinstance(result.results[0], GlobalSearchItem)
        assert result.results[0].type == "project"
