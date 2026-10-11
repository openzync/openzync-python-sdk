"""Search domain client — organization-wide resource search."""

from __future__ import annotations

from typing import Literal

from openzync._errors import ValidationError
from openzync._http import AsyncHTTPTransport
from openzync.models.search import GlobalSearchResponse

# Mirrors core's schemas/sorting.py SearchSort.
SearchSort = Literal["relevance", "recent"]


class AsyncSearchClient:
    """Async client for cross-resource global search.

    Args:
        http: The shared async HTTP transport instance.
    """

    def __init__(self, http: AsyncHTTPTransport) -> None:
        self._http = http

    async def global_search(
        self,
        query: str,
        limit: int = 10,
        sort: SearchSort = "relevance",
    ) -> GlobalSearchResponse:
        """Search across projects, users, and sessions in your organization.

        Results are scoped to resources the authenticated principal can
        access.

        Args:
            query: Search query string (1–200 chars).
            limit: Maximum results (1–50).
            sort: Result order — ``"relevance"`` or ``"recent"``.

        Returns:
            ``GlobalSearchResponse`` with matching results and the query.

        Raises:
            ValidationError: If ``sort`` is not a known order.
        """
        if sort not in ("relevance", "recent"):
            raise ValidationError(f"unknown sort order: {sort!r}")
        data = await self._http.request(
            "GET",
            "/v1/search",
            params={"q": query, "limit": limit, "sort": sort},
        )
        return GlobalSearchResponse(**data)
