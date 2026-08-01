"""Tests for the OpenZync Python SDK — graph domain."""

from __future__ import annotations

import pytest


class TestGraphClient:
    """Tests for ``AsyncGraphClient``."""

    @pytest.mark.asyncio
    async def test_list_nodes(self, async_client, mock_http, mock_resolve):
        """GET /graph/nodes returns paginated entities."""
        mock_http.get("/v1/projects/p1/graph/nodes").respond(json={
            "data": {
                "items": [
                    {"id": "n1", "name": "Alice", "type": "Person", "summary": "",
                     "created_at": "2026-01-01T00:00:00Z", "metadata": {}},
                    {"id": "n2", "name": "Acme Corp", "type": "Organization", "summary": "",
                     "created_at": "2026-01-01T00:00:00Z", "metadata": {}},
                ],
                "next_cursor": None,
                "has_more": False,
            }
        })

        nodes = []
        async for node in await async_client.graph.nodes():
            nodes.append(node)

        assert len(nodes) == 2
        assert nodes[0].name == "Alice"
        assert nodes[1].type == "Organization"

    @pytest.mark.asyncio
    async def test_list_nodes_with_type_filter(self, async_client, mock_http, mock_resolve):
        """GET /graph/nodes passes entity_type filter."""
        mock_http.get(
            "/v1/projects/p1/graph/nodes"
        ).respond(json={
            "data": {
                "items": [
                    {"id": "n1", "name": "Alice", "type": "Person", "summary": "",
                     "created_at": "2026-01-01T00:00:00Z", "metadata": {}},
                ],
                "next_cursor": None,
                "has_more": False,
            }
        })

        nodes = []
        async for node in await async_client.graph.nodes(entity_type="Person"):
            nodes.append(node)

        assert len(nodes) == 1
        assert nodes[0].type == "Person"

    @pytest.mark.asyncio
    async def test_node_detail(self, async_client, mock_http, mock_resolve):
        """GET /graph/nodes/{id} returns node with edges."""
        mock_http.get("/v1/projects/p1/graph/nodes/n1").respond(json={
            "data": {
                "node": {"id": "n1", "name": "Alice", "type": "Person",
                         "summary": "A person", "created_at": "2026-01-01T00:00:00Z",
                         "metadata": {}},
                "edges": [
                    {"id": "e1", "source_id": "n1", "target_id": "n2",
                     "type": "works_at", "weight": 1.0,
                     "created_at": "2026-01-01T00:00:00Z", "metadata": {}},
                ],
            }
        })

        detail = await async_client.graph.node_detail("n1")
        assert detail.node.name == "Alice"
        assert detail.node.summary == "A person"
        assert len(detail.edges) == 1
        assert detail.edges[0].type == "works_at"

    @pytest.mark.asyncio
    async def test_delete_node(self, async_client, mock_http, mock_resolve):
        """DELETE /graph/nodes/{id} returns 204."""
        mock_http.delete("/v1/projects/p1/graph/nodes/n1").respond(status_code=204)

        await async_client.graph.delete_node("n1")
        # No exception means success

    @pytest.mark.asyncio
    async def test_edges(self, async_client, mock_http, mock_resolve):
        """GET /graph/edges returns edges for a subject."""
        mock_http.get("/v1/projects/p1/graph/edges").respond(json={
            "data": {
                "items": [
                    {"id": "e1", "source_id": "n1", "target_id": "n2",
                     "type": "works_at", "weight": 1.0,
                     "created_at": "2026-01-01T00:00:00Z", "metadata": {}},
                ],
                "next_cursor": None,
                "has_more": False,
            }
        })

        edges = []
        async for edge in await async_client.graph.edges(subject_id="n1"):
            edges.append(edge)

        assert len(edges) == 1
        assert edges[0]["type"] == "works_at"

    @pytest.mark.asyncio
    async def test_edges_with_predicate_filter(self, async_client, mock_http, mock_resolve):
        """GET /graph/edges passes predicate filter."""
        mock_http.get("/v1/projects/p1/graph/edges").respond(json={
            "data": {
                "items": [
                    {"id": "e1", "source_id": "n1", "target_id": "n2",
                     "type": "works_at", "weight": 1.0,
                     "created_at": "2026-01-01T00:00:00Z", "metadata": {}},
                ],
                "next_cursor": None,
                "has_more": False,
            }
        })

        edges = []
        async for edge in await async_client.graph.edges(
            subject_id="n1", predicate="works_at"
        ):
            edges.append(edge)

        assert len(edges) == 1

    @pytest.mark.asyncio
    async def test_communities(self, async_client, mock_http, mock_resolve):
        """GET /graph/communities returns communities."""
        mock_http.get("/v1/projects/p1/graph/communities").respond(json={
            "data": [
                {"id": "c1", "name": "Community 1", "summary": "A community",
                 "member_count": 3, "metadata": {},
                 "created_at": "2026-01-01T00:00:00Z"},
            ],
        })

        communities = await async_client.graph.communities()
        assert len(communities) == 1
        assert communities[0].name == "Community 1"
        assert communities[0].member_count == 3

    @pytest.mark.asyncio
    async def test_nodes_multi_page(self, async_client, mock_http, mock_resolve):
        """Multi-page nodes response hits cursor param path (line 49)."""
        from httpx import Response as HXResponse

        mock_http.get("/v1/projects/p1/graph/nodes").side_effect = [
            HXResponse(200, json={
                "data": {
                    "items": [
                        {"id": "n1", "name": "Alice", "type": "Person",
                         "summary": "", "created_at": "2026-01-01T00:00:00Z",
                         "metadata": {}},
                    ],
                    "next_cursor": "cursor-2",
                    "has_more": True,
                }
            }),
            HXResponse(200, json={
                "data": {
                    "items": [
                        {"id": "n2", "name": "Bob", "type": "Person",
                         "summary": "", "created_at": "2026-01-01T00:00:00Z",
                         "metadata": {}},
                    ],
                    "next_cursor": None,
                    "has_more": False,
                }
            }),
        ]

        nodes = []
        async for node in await async_client.graph.nodes():
            nodes.append(node)
        assert len(nodes) == 2
        assert nodes[0].name == "Alice"
        assert nodes[1].name == "Bob"

    @pytest.mark.asyncio
    async def test_edges_multi_page(self, async_client, mock_http, mock_resolve):
        """Multi-page edges response hits cursor param path (line 119)."""
        from httpx import Response as HXResponse

        mock_http.get("/v1/projects/p1/graph/edges").side_effect = [
            HXResponse(200, json={
                "data": {
                    "items": [
                        {"id": "e1", "source_id": "n1", "target_id": "n2",
                         "type": "works_at", "weight": 1.0,
                         "created_at": "2026-01-01T00:00:00Z", "metadata": {}},
                    ],
                    "next_cursor": "cursor-2",
                    "has_more": True,
                }
            }),
            HXResponse(200, json={
                "data": {
                    "items": [
                        {"id": "e2", "source_id": "n1", "target_id": "n3",
                         "type": "reports_to", "weight": 1.0,
                         "created_at": "2026-01-01T00:00:00Z", "metadata": {}},
                    ],
                    "next_cursor": None,
                    "has_more": False,
                }
            }),
        ]

        edges = []
        async for edge in await async_client.graph.edges(subject_id="n1"):
            edges.append(edge)
        assert len(edges) == 2

    @pytest.mark.asyncio
    async def test_search(self, async_client, mock_http, mock_resolve):
        """GET /search returns results."""
        mock_http.get("/v1/projects/p1/search").respond(json={
            "query": "Alice",
            "results": [
                {"id": "e1", "content": "Alice works at Acme Corp", "score": 0.06,
                 "rrf_score": 0.03, "role": "user", "created_at": "2026-01-01T00:00:00Z"},
            ],
            "total": 1,
        })

        results = await async_client.graph.search(query="Alice")
        assert len(results) == 1
        assert "Acme Corp" in results[0]["content"]
