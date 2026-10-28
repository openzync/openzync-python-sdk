"""Memory domain client — ingest, context, delete."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Literal

from openzync._errors import ValidationError
from openzync._http import AsyncHTTPTransport
from openzync.models.memory import (
    ContextResponse,
    IngestMemoryResponse,
    Message,
)
from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger(__name__)

# Mirrors core's schemas/sorting.py SearchSort.
ContextSort = Literal["relevance", "recent"]


def new_idempotency_key() -> str:
    """Generate a time-ordered idempotency key for a write request.

    Uses UUIDv7 when the runtime provides it (Python 3.14+), UUIDv4
    otherwise — both are unique per call, which is all the server's
    ``Idempotency-Key`` dedupe requires.

    Returns:
        A hex key unique to this call (never reuse across retries of
        different logical operations).
    """
    new_uuid = getattr(uuid, "uuid7", None) or uuid.uuid4
    return new_uuid().hex


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

        The request is always sent as ``multipart/form-data`` — even for
        text-only calls — with the JSON payload in the ``data`` form field;
        the backend rejects plain ``application/json`` bodies with 422.
        Supports optional file attachments (images, PDFs, documents) uploaded
        as ``blobs`` parts.

        Args:
            messages: List of message objects (dict or Message).  Each message
                may include a ``blobs`` array referencing uploaded files by
                their positional index.
            session_id: Session external ID — required, all ingestion targets
                an existing session.
            idempotency_key: Optional ``Idempotency-Key`` header. When
                omitted, a fresh key is generated once per call — it is
                reused across the transport's automatic retries of THIS
                call only. A new ``ingest`` call generates a new key and
                creates a new episode, so caller-level retries (a new call
                after a timeout or ambiguous failure) MUST pass an explicit
                key or the write will be duplicated.
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

        # Generated once per call and reused for every transport-level
        # retry of this call (the transport resends the same headers) —
        # never regenerated on retry, so retries dedupe server-side.
        if idempotency_key is None:
            logger.warning(
                "openzync.ingest.auto_idempotency_key: generated a fresh key "
                "for this call only — pass idempotency_key explicitly and "
                "reuse it across caller-level retries or a retry after a "
                "timeout will create a duplicate episode."
            )
            key = new_idempotency_key()
        else:
            key = idempotency_key
        headers = {"Idempotency-Key": key}

        files: list[tuple[str, tuple[str, bytes, str]]] | None = None
        if blobs:
            files = [("blobs", (name, data, mime)) for name, data, mime in blobs]

        # Always multipart — the backend accepts only multipart/form-data,
        # even for text-only calls. With no blobs the transport sends a
        # `data`-only multipart form.
        data = await self._http.request_multipart(
            "POST",
            f"/v1/projects/{pid}/memory",
            data={"data": json.dumps(body)},
            files=files,
            headers=headers,
            params=None,
        )
        return IngestMemoryResponse(**data)

    async def get_context(
        self,
        query: str,
        limit: int = 20,
        as_of: str | None = None,
        format: str = "text",
        sort: ContextSort = "relevance",
    ) -> ContextResponse:
        """Assemble a context block for LLM injection.

        Args:
            query: Natural-language query describing the context needed.
            limit: Maximum results per source type (1–100).
            as_of: Optional effective-at timestamp (ISO-8601) — facts valid
                at this instant are used instead of "now".
            format: Output format — ``"text"`` (plain text) or ``"json"``
                (JSON-serialised context string).
            sort: Result order — ``"relevance"`` or ``"recent"``. Part of
                core's Redis cache key.

        Returns:
            ``ContextResponse`` with formatted context text.

        Raises:
            ValidationError: If ``limit`` is outside 1–100 or ``sort`` is
                not a known order (core would reject with 422).
        """
        if limit < 1 or limit > 100:
            raise ValidationError(
                f"limit must be 1–100 (core rejects {limit} with 422)"
            )
        if sort not in ("relevance", "recent"):
            raise ValidationError(f"unknown sort order: {sort!r}")
        pid = await self._http.resolve_project_id()
        params: dict[str, str | int] = {
            "query": query,
            "limit": str(limit),
            "format": format,
            "sort": sort,
        }
        if as_of is not None:
            params["as_of"] = as_of
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/context",
            params=params,
        )
        return ContextResponse(**data)

    async def delete(self, *, confirm: str) -> None:
        """Delete all memory for a project (soft-delete, confirm-gated).

        This is the GDPR memory-wipe operation and is **not** reversible —
        deleted data is marked inactive but preserved for a 30-day grace
        period before hard-purge.

        Args:
            confirm: Must equal the project ID — the server rejects any
                other value with 422. Pass the project ID explicitly to
                prove intent; there is no default.

        Raises:
            ValidationError: If ``confirm`` does not match the project ID.
        """
        pid = await self._http.resolve_project_id()
        await self._http.request(
            "DELETE",
            f"/v1/projects/{pid}/memory",
            json_body={"confirm": confirm},
        )


def _as_message(m: Message | dict) -> dict:
    """Convert a Message object or dict to a plain dict.

    Dicts are validated through ``Message`` so a bad role fails locally
    with ``ValidationError`` instead of a server 422 round-trip.
    """
    if isinstance(m, Message):
        return m.model_dump(exclude_none=True)
    try:
        return Message(**m).model_dump(exclude_none=True)
    except PydanticValidationError as e:
        raise ValidationError(str(e)) from e
