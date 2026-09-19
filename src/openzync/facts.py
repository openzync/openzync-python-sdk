"""Facts domain client — batch ingestion, listing, retraction, history."""

from __future__ import annotations

from openzync._http import AsyncHTTPTransport
from openzync.models.facts import (
    FactBatchResponse,
    FactHistoryResponse,
    FactResponse,
    FactTriple,
    PaginatedFactsResponse,
)


class AsyncFactsClient:
    """Async client for business fact operations.

    Args:
        http: The shared async HTTP transport instance.
    """

    def __init__(self, http: AsyncHTTPTransport) -> None:
        self._http = http

    async def add(
        self,
        facts: list[FactTriple | dict],
        session_id: str,
        idempotency_key: str | None = None,
    ) -> FactBatchResponse:
        """Ingest a batch of fact triples.

        Args:
            facts: List of fact triples (max 500).
            session_id: Session external ID — required, all ingestion targets
                an existing session.
            idempotency_key: Optional ``Idempotency-Key`` header. When
                provided, ``POST`` retries on 429/5xx and timeouts are
                enabled (safe retry — the server dedupes by key); without
                it the request fails fast with no retry so a write is never
                duplicated.

        Returns:
            ``FactBatchResponse`` with job_id and accepted count.
        """
        pid = await self._http.resolve_project_id()
        body: dict = {
            "facts": [
                f.model_dump(exclude_none=True) if isinstance(f, FactTriple) else f
                for f in facts
            ],
            "session_id": session_id,
        }
        headers = None
        if idempotency_key is not None:
            headers = {"Idempotency-Key": idempotency_key}

        data = await self._http.request(
            "POST",
            f"/v1/projects/{pid}/facts",
            json_body=body,
            headers=headers,
        )
        return FactBatchResponse(**data)

    async def list(
        self,
        *,
        as_of: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedFactsResponse:
        """List facts valid at a point in time.

        Superseded and retracted facts are excluded — only facts whose
        validity range contains ``as_of`` (default now) are returned.

        Args:
            as_of: Optional effective-at timestamp (ISO-8601). Defaults to now.
            limit: Maximum facts per page (1–200).
            offset: Number of facts to skip (offset pagination).

        Returns:
            ``PaginatedFactsResponse`` with facts, next cursor, and has_more.
        """
        pid = await self._http.resolve_project_id()
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if as_of is not None:
            params["as_of"] = as_of
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/facts",
            params=params,
        )
        return PaginatedFactsResponse(**data)

    async def retract(
        self,
        fact_id: str,
        reason: str | None = None,
    ) -> FactResponse:
        """Retract a fact by setting its invalid_at timestamp.

        Idempotent — retracting an already-closed fact is a no-op returning
        the unchanged fact.

        Args:
            fact_id: The UUID of the fact to retract.
            reason: Optional human-readable explanation of the retraction.

        Returns:
            The retracted fact (or the unchanged fact if already closed).
        """
        pid = await self._http.resolve_project_id()
        body = {"reason": reason} if reason is not None else None
        data = await self._http.request(
            "POST",
            f"/v1/projects/{pid}/facts/{fact_id}/retract",
            json_body=body,
        )
        return FactResponse(**data)

    async def history(self, fact_id: str) -> FactHistoryResponse:
        """Get a fact plus its invalidation-lineage events (newest first).

        Args:
            fact_id: The UUID of the fact whose lineage to fetch.

        Returns:
            ``FactHistoryResponse`` with the fact and its lineage events.
        """
        pid = await self._http.resolve_project_id()
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/facts/{fact_id}/history",
        )
        return FactHistoryResponse(**data)
