"""Classifications domain client — dialog classification queries."""

from __future__ import annotations

from openzync._http import AsyncHTTPTransport
from openzync.models.classification import (
    ClassificationListResponse,
    ClassificationResponse,
)


class AsyncClassificationsClient:
    """Async client for session-scoped dialog classification queries.

    Args:
        http: The shared async HTTP transport instance.
    """

    def __init__(self, http: AsyncHTTPTransport) -> None:
        self._http = http

    async def list(self, session_id: str) -> ClassificationListResponse:
        """List all classifications for episodes in a session.

        Args:
            session_id: The internal UUID of the session.

        Returns:
            ``ClassificationListResponse`` — empty if no episodes have been
            classified yet (the classify_dialog worker may not have run).
        """
        pid = await self._http.resolve_project_id()
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/sessions/{session_id}/classifications",
        )
        return ClassificationListResponse(**data)

    async def get_by_episode(
        self,
        session_id: str,
        episode_id: str,
    ) -> ClassificationResponse:
        """Get the classification for a specific episode in a session.

        Args:
            session_id: The internal UUID of the session.
            episode_id: The UUID of the episode.

        Returns:
            ``ClassificationResponse`` for the episode.

        Raises:
            openzync._errors.NotFoundError: If the episode has not been
                classified yet.
        """
        pid = await self._http.resolve_project_id()
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/sessions/{session_id}/classifications/{episode_id}",
        )
        return ClassificationResponse(**data)
