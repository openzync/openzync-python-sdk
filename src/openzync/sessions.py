"""Sessions domain client — CRUD operations."""

from __future__ import annotations

from openzync._http import AsyncHTTPTransport
from openzync._pagination import AsyncPaginatedIterator
from openzync.models.session import (
    SessionCreateRequest,
    SessionMessagesResponse,
    SessionResponse,
)


class AsyncSessionsClient:
    """Async client for session operations.

    Args:
        http: The shared async HTTP transport instance.
    """

    def __init__(self, http: AsyncHTTPTransport) -> None:
        self._http = http

    async def create(
        self,
        external_id: str,
        metadata: dict | None = None,
    ) -> SessionResponse:
        """Create a new session within a project.

        Args:
            external_id: Caller-defined session identifier.
            metadata: Optional metadata dict.

        Returns:
            ``SessionResponse`` with the created session.
        """
        pid = await self._http.resolve_project_id()
        body = SessionCreateRequest(external_id=external_id, metadata=metadata if metadata is not None else {})
        data = await self._http.request(
            "POST",
            f"/v1/projects/{pid}/sessions",
            json_body=body.model_dump(exclude_none=True),
        )
        return SessionResponse(**data)

    async def get(
        self,
        session_id: str,
    ) -> SessionResponse:
        """Get session details by internal UUID.

        Args:
            session_id: The internal UUID of the session.
        """
        pid = await self._http.resolve_project_id()
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/sessions/{session_id}",
        )
        return SessionResponse(**data)

    async def delete(
        self,
        session_id: str,
    ) -> None:
        """Close and soft-delete a session.

        Args:
            session_id: The internal UUID of the session.
        """
        pid = await self._http.resolve_project_id()
        await self._http.request(
            "DELETE",
            f"/v1/projects/{pid}/sessions/{session_id}",
        )

    async def list(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict:
        """List sessions for a project with cursor-based pagination.

        Args:
            limit: Maximum results per page.
            cursor: Opaque cursor from a previous response.

        Returns:
            Dict with ``data``, ``next_cursor``, and ``has_more`` keys.
        """
        pid = await self._http.resolve_project_id()
        params: dict[str, str | int] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        return await self._http.request(
            "GET",
            f"/v1/projects/{pid}/sessions",
            params=params,
        )

    async def messages(
        self,
        session_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> SessionMessagesResponse:
        """Get messages for a session.

        Args:
            session_id: The internal UUID of the session.
            limit: Maximum results per page.
            cursor: Opaque cursor from a previous response.

        Returns:
            ``SessionMessagesResponse`` with message list.
        """
        pid = await self._http.resolve_project_id()
        params: dict[str, str | int] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/sessions/{session_id}/messages",
            params=params,
        )
        return SessionMessagesResponse(**data)
