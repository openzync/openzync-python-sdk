"""Memory domain client — ingest, context, delete."""

from __future__ import annotations

from openzync._http import AsyncHTTPTransport
from openzync.models.memory import (
    ContextResponse,
    IngestMemoryResponse,
    Message,
)


class AsyncMemoryClient:
    """Async client for memory operations.

    Args:
        http: The shared async HTTP transport instance.
    """

    def __init__(self, http: AsyncHTTPTransport) -> None:
        self._http = http

    async def ingest(
        self,
        messages: list[Message | dict],
        session_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> IngestMemoryResponse:
        """Ingest conversation messages into a project's memory.

        Args:
            messages: List of message objects (dict or Message).
            session_id: Optional session external ID.
            idempotency_key: Optional ``Idempotency-Key`` header.

        Returns:
            ``IngestMemoryResponse`` with job_id and episode count.
        """
        pid = await self._http.resolve_project_id()
        body: dict = {"messages": [_as_message(m) for m in messages]}
        if session_id is not None:
            body["session_id"] = session_id

        headers = None
        if idempotency_key is not None:
            headers = {"Idempotency-Key": idempotency_key}

        data = await self._http.request(
            "POST",
            f"/v1/projects/{pid}/memory",
            json_body=body,
        )
        return IngestMemoryResponse(**data)

    async def get_context(
        self,
        query: str,
        limit: int = 20,
    ) -> ContextResponse:
        """Assemble a context block for LLM injection.

        Args:
            query: Natural-language query describing the context needed.
            limit: Maximum results per source type.

        Returns:
            ``ContextResponse`` with formatted context text.
        """
        pid = await self._http.resolve_project_id()
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/context",
            params={"query": query, "limit": str(limit)},
        )
        return ContextResponse(**data)

    async def delete(self) -> None:
        """Delete all memory for a project (soft-delete)."""
        pid = await self._http.resolve_project_id()
        await self._http.request("DELETE", f"/v1/projects/{pid}/memory")


def _as_message(m: Message | dict) -> dict:
    """Convert a Message object or dict to a plain dict."""
    if isinstance(m, Message):
        return m.model_dump(exclude_none=True)
    return m
