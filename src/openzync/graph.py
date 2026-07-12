"""Graph domain client — nodes, edges, communities, search."""

from __future__ import annotations

from typing import Any

from openzync._http import AsyncHTTPTransport
from openzync._pagination import AsyncPaginatedIterator
from openzync.models.graph import (
    GraphCommunity,
    GraphEdge,
    GraphNode,
    GraphNodeDetail,
)


class AsyncGraphClient:
    """Async client for knowledge graph operations.

    Args:
        http: The shared async HTTP transport instance.
    """

    def __init__(self, http: AsyncHTTPTransport) -> None:
        self._http = http

    async def nodes(
        self,
        *,
        entity_type: str | None = None,
        limit: int = 50,
    ) -> AsyncPaginatedIterator:
        """List entity nodes with optional type filter.

        Args:
            entity_type: Optional entity type filter.
            limit: Maximum results per page.

        Returns an async iterator that auto-fetches subsequent pages.
        Yields ``GraphNode`` objects.
        """
        pid = await self._http.resolve_project_id()

        async def fetch_page(cursor: str | None = None) -> dict:
            params: dict[str, str | int] = {"limit": limit}
            if entity_type is not None:
                params["entity_type"] = entity_type
            if cursor is not None:
                params["cursor"] = cursor
            raw = await self._http.request(
                "GET",
                f"/v1/projects/{pid}/graph/nodes",
                params=params,
            )
            # API wraps items in data.items — flatten for paginator
            data = raw.get("data", raw)
            items = data.get("items", [])
            return {
                "items": [GraphNode(**i) for i in items],
                "next_cursor": data.get("next_cursor"),
                "has_more": data.get("has_more", False),
            }

        return AsyncPaginatedIterator(fetch_page, limit)

    async def node_detail(
        self,
        node_id: str,
    ) -> GraphNodeDetail:
        """Get a single entity node with all its incident edges.

        Args:
            node_id: The UUID of the entity node.
        """
        pid = await self._http.resolve_project_id()
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/graph/nodes/{node_id}",
        )
        inner = data.get("data", data)
        return GraphNodeDetail(
            node=GraphNode(**inner["node"]),
            edges=[GraphEdge(**e) for e in inner.get("edges", [])],
        )

    async def delete_node(self, node_id: str) -> None:
        """Delete an entity node from the knowledge graph.

        Args:
            node_id: The UUID of the entity node.
        """
        pid = await self._http.resolve_project_id()
        await self._http.request(
            "DELETE",
            f"/v1/projects/{pid}/graph/nodes/{node_id}",
        )

    async def edges(
        self,
        subject_id: str,
        *,
        predicate: str | None = None,
        limit: int = 50,
    ) -> AsyncPaginatedIterator:
        """List relationship edges for a specific entity.

        Args:
            subject_id: The UUID of the source entity.
            predicate: Optional relationship type filter.
            limit: Maximum results per page.
        """
        pid = await self._http.resolve_project_id()

        async def fetch_page(cursor: str | None = None) -> dict:
            params: dict[str, str | int] = {"subject_id": subject_id, "limit": limit}
            if predicate is not None:
                params["predicate"] = predicate
            if cursor is not None:
                params["cursor"] = cursor
            raw = await self._http.request(
                "GET",
                f"/v1/projects/{pid}/graph/edges",
                params=params,
            )
            data = raw.get("data", raw)
            return {
                "items": data.get("items", []),
                "next_cursor": data.get("next_cursor"),
                "has_more": data.get("has_more", False),
            }

        return AsyncPaginatedIterator(fetch_page, limit)

    async def communities(
        self,
    ) -> list[GraphCommunity]:
        """List community summary nodes.
        """
        pid = await self._http.resolve_project_id()
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/graph/communities",
        )
        items = data.get("data", [])
        return [GraphCommunity(**c) for c in items]

    async def search(
        self,
        query: str,
        *,
        types: str = "episodes,facts",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Hybrid search across project memory.

        Args:
            query: Search query string.
            types: Comma-separated result types (episodes, facts, entities).
            limit: Maximum results per type.

        Returns:
            List of result dicts with ``content``, ``score``, etc.
        """
        pid = await self._http.resolve_project_id()
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/search",
            params={"query": query, "types": types, "limit": str(limit)},
        )
        return data.get("results", [])
