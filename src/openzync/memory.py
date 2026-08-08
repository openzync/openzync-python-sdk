"""Memory domain client — ingest, context, delete."""

from __future__ import annotations

import json

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
        session_id: str,
        idempotency_key: str | None = None,
        blobs: list[tuple[str, bytes, str]] | None = None,
    ) -> IngestMemoryResponse:
        """Ingest conversation messages into a project's memory.

        Supports optional file attachments (images, PDFs, documents) which
        are uploaded as multipart form data.

        Args:
            messages: List of message objects (dict or Message).  Each message
                may include a ``blobs`` array referencing uploaded files by
                their positional index.
            session_id: Session external ID — required, all ingestion targets
                an existing session.
            idempotency_key: Optional ``Idempotency-Key`` header.
            blobs: Optional list of ``(filename, data, mime_type)`` tuples.
                When provided, the request is sent as ``multipart/form-data``
                with the JSON payload in a ``data`` field and each blob as a
                ``blobs`` file field.

        Returns:
            ``IngestMemoryResponse`` with job_id, episode_count, and blob_count.
        """
        pid = await self._http.resolve_project_id()
        body: dict = {"messages": [_as_message(m) for m in messages]}
        body["session_id"] = session_id

        headers = None
        if idempotency_key is not None:
            headers = {"Idempotency-Key": idempotency_key}

        if blobs:
            files: list[tuple[str, tuple[str, bytes, str]]] = [
                ("blobs", (name, data, mime)) for name, data, mime in blobs
            ]
            data = await self._http.request_multipart(
                "POST",
                f"/v1/projects/{pid}/memory",
                data={"data": json.dumps(body)},
                files=files,
                params=None,
            )
        else:
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
