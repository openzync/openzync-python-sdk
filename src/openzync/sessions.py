"""Sessions domain client — CRUD operations."""

from __future__ import annotations

from openzync._http import AsyncHTTPTransport
from openzync.models.facts import PaginatedFactsResponse
from openzync.models.session import (
    SessionCreateRequest,
    SessionListResponse,
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
        body = SessionCreateRequest(
            external_id=external_id, metadata=metadata if metadata is not None else {}
        )
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
        include_closed: bool = False,
    ) -> SessionListResponse:
        """List sessions for a project with cursor-based pagination.

        BREAKING: returns ``SessionListResponse`` — use ``result.data``,
        not ``result["data"]``.

        Args:
            limit: Maximum results per page.
            cursor: Opaque cursor from a previous response.
            include_closed: When True, include closed sessions.
                Omitted from the query when False (backend default).

        Returns:
            ``SessionListResponse`` with sessions, next cursor, and has_more.
        """
        pid = await self._http.resolve_project_id()
        params: dict[str, str | int] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        if include_closed:
            params["include_closed"] = True
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/sessions",
            params=params,
        )
        return SessionListResponse(**data)

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

    async def facts(
        self,
        session_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> PaginatedFactsResponse:
        """Get facts extracted from messages in a session (newest first).

        Only non-invalidated facts are included.

        Args:
            session_id: The internal UUID of the session.
            limit: Maximum facts per page (1–200).
            cursor: Opaque cursor from a previous response.

        Returns:
            ``PaginatedFactsResponse`` with facts, next cursor, and has_more.
        """
        pid = await self._http.resolve_project_id()
        params: dict[str, str | int] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/sessions/{session_id}/facts",
            params=params,
        )
        return PaginatedFactsResponse(**data)
