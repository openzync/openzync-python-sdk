"""Structured extractions domain client — extraction result queries."""

from __future__ import annotations

from openzync._http import AsyncHTTPTransport
from openzync.models.extraction import (
    StructuredExtractionListResponse,
    StructuredExtractionResponse,
)


class AsyncStructuredExtractionsClient:
    """Async client for session-scoped structured-extraction queries.

    Args:
        http: The shared async HTTP transport instance.
    """

    def __init__(self, http: AsyncHTTPTransport) -> None:
        self._http = http

    async def list(self, session_id: str) -> StructuredExtractionListResponse:
        """List all structured extractions for episodes in a session.

        Args:
            session_id: The internal UUID of the session.

        Returns:
            ``StructuredExtractionListResponse`` — empty if no episodes have
            been processed by the extract_structured worker yet.
        """
        pid = await self._http.resolve_project_id()
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/sessions/{session_id}/structured-extractions",
        )
        return StructuredExtractionListResponse(**data)

    async def get_by_episode(
        self,
        session_id: str,
        episode_id: str,
    ) -> StructuredExtractionResponse:
        """Get the structured extraction for a specific episode in a session.

        Args:
            session_id: The internal UUID of the session.
            episode_id: The UUID of the episode.

        Returns:
            ``StructuredExtractionResponse`` for the episode.

        Raises:
            openzync._errors.NotFoundError: If no matching extraction exists.
        """
        pid = await self._http.resolve_project_id()
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/sessions/{session_id}/structured-extractions/{episode_id}",
        )
        return StructuredExtractionResponse(**data)
