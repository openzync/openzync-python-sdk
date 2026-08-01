"""Tests for LangChain tools."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from openzync.client import AsyncOpenZync
from openzync.integrations.langchain.tools.facts import AddFactsInput, AddFactsTool
from openzync.integrations.langchain.tools.graph import (
    GraphNodeDetailInput,
    GraphNodeDetailTool,
    GraphSearchInput,
    GraphSearchTool,
    ListGraphNodesInput,
    ListGraphNodesTool,
)


@pytest.fixture
def mock_client():
    """Create a real AsyncOpenZync with mocked sub-clients."""
    client = AsyncOpenZync(api_key="test", base_url="http://test")
    client.graph = AsyncMock()
    client.facts = AsyncMock()
    return client


class AsyncIterableMock:
    """Mock that can be used in ``async for`` loops."""

    def __init__(self, items: list):
        self._items = items
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


class TestGraphSearchTool:
    """Tests for GraphSearchTool."""

    def test_name_and_description(self, mock_client):
        tool = GraphSearchTool(client=mock_client)
        assert tool.name == "graph_search"
        assert len(tool.description) > 0

    def test_args_schema(self, mock_client):
        tool = GraphSearchTool(client=mock_client)
        assert tool.args_schema == GraphSearchInput

    def test_input_schema_valid(self):
        inp = GraphSearchInput(query="test query", project_id="project-1")
        assert inp.query == "test query"
        assert inp.project_id == "project-1"

    def test_input_schema_with_optionals(self):
        inp = GraphSearchInput(
            query="test",
            project_id="project-1",
            types="facts",
            limit=10,
        )
        assert inp.types == "facts"
        assert inp.limit == 10

    @pytest.mark.asyncio
    async def test_arun_returns_formatted_results(self, mock_client):
        mock_client.graph.search.return_value = [
            {"content": "Alice works at Acme", "score": 0.95, "type": "fact"},
        ]

        tool = GraphSearchTool(client=mock_client)
        result = await tool._arun(query="Alice", project_id="project-1")

        assert "Alice works at Acme" in result
        assert "0.950" in result

    @pytest.mark.asyncio
    async def test_arun_empty_results(self, mock_client):
        mock_client.graph.search.return_value = []

        tool = GraphSearchTool(client=mock_client)
        result = await tool._arun(query="nothing", project_id="project-1")
        assert result == "No results found."

    def test_run_sync(self, mock_client):
        """Sync _run delegates to async."""
        mock_client.graph.search.return_value = [
            {"content": "sync result", "score": 0.5, "type": "entity"},
        ]
        tool = GraphSearchTool(client=mock_client)
        result = tool._run(query="test", project_id="project-1")
        assert "sync result" in result


class TestGraphNodeDetailTool:
    """Tests for GraphNodeDetailTool."""

    def test_name_and_args_schema(self, mock_client):
        tool = GraphNodeDetailTool(client=mock_client)
        assert tool.name == "graph_node_detail"
        assert tool.args_schema == GraphNodeDetailInput

    @pytest.mark.asyncio
    async def test_arun_returns_details(self, mock_client):
        """_arun formats node details with edges."""
        from openzync.models.graph import GraphNode, GraphEdge, GraphNodeDetail

        detail = GraphNodeDetail(
            node=GraphNode(id="n1", name="Alice", type="Person", summary="Engineer",
                           created_at="2026-01-01T00:00:00Z", metadata={}),
            edges=[
                GraphEdge(id="e1", source_id="n1", target_id="n2",
                          type="works_at", weight=1.0,
                          created_at="2026-01-01T00:00:00Z", metadata={}),
            ],
        )
        mock_client.graph.node_detail = AsyncMock(return_value=detail)

        tool = GraphNodeDetailTool(client=mock_client)
        result = await tool._arun(project_id="p1", node_id="n1")

        assert "Alice" in result
        assert "Person" in result
        assert "--[works_at]-->" in result

    @pytest.mark.asyncio
    async def test_arun_without_edges(self, mock_client):
        """_arun handles nodes with no edges."""
        from openzync.models.graph import GraphNode, GraphNodeDetail

        detail = GraphNodeDetail(
            node=GraphNode(id="n2", name="Bob", type="Person", summary="Alone",
                           created_at="2026-01-01T00:00:00Z", metadata={}),
            edges=[],
        )
        mock_client.graph.node_detail = AsyncMock(return_value=detail)

        tool = GraphNodeDetailTool(client=mock_client)
        result = await tool._arun(project_id="p1", node_id="n2")

        assert "Bob" in result
        assert "Relationships:" in result

    def test_run_sync(self, mock_client):
        """Sync _run delegates to async."""
        from openzync.models.graph import GraphNode, GraphNodeDetail

        detail = GraphNodeDetail(
            node=GraphNode(id="n1", name="Alice", type="Person", summary="E",
                           created_at="2026-01-01T00:00:00Z", metadata={}),
            edges=[],
        )
        mock_client.graph.node_detail = AsyncMock(return_value=detail)

        tool = GraphNodeDetailTool(client=mock_client)
        result = tool._run(project_id="p1", node_id="n1")
        assert "Alice" in result


class TestListGraphNodesTool:
    """Tests for ListGraphNodesTool."""

    def test_name_and_args_schema(self, mock_client):
        tool = ListGraphNodesTool(client=mock_client)
        assert tool.name == "list_graph_nodes"
        assert tool.args_schema == ListGraphNodesInput

    @pytest.mark.asyncio
    async def test_arun_lists_nodes(self, mock_client):
        """_arun iterates nodes and formats them."""
        from openzync.models.graph import GraphNode

        mock_node = GraphNode(id="n1", name="Alice", type="Person", summary="",
                              created_at="2026-01-01T00:00:00Z", metadata={})
        mock_client.graph.nodes = AsyncMock(
            return_value=AsyncIterableMock([mock_node])
        )

        tool = ListGraphNodesTool(client=mock_client)
        result = await tool._arun(project_id="p1")

        assert "Alice" in result
        assert "(Person)" in result

    @pytest.mark.asyncio
    async def test_arun_empty(self, mock_client):
        """_arun returns 'No nodes found' for empty result."""
        mock_client.graph.nodes = AsyncMock(
            return_value=AsyncIterableMock([])
        )

        tool = ListGraphNodesTool(client=mock_client)
        result = await tool._arun(project_id="p1")
        assert result == "No nodes found."

    @pytest.mark.asyncio
    async def test_arun_with_filters(self, mock_client):
        """_arun passes entity_type and limit."""
        mock_client.graph.nodes = AsyncMock(
            return_value=AsyncIterableMock([])
        )

        tool = ListGraphNodesTool(client=mock_client)
        await tool._arun(project_id="p1", entity_type="Person", limit=10)

        mock_client.graph.nodes.assert_awaited_once_with(
            entity_type="Person", limit=10
        )

    def test_run_sync(self, mock_client):
        """Sync _run delegates to async."""
        from openzync.models.graph import GraphNode

        mock_node = GraphNode(id="n1", name="Alice", type="Person", summary="",
                              created_at="2026-01-01T00:00:00Z", metadata={})
        mock_client.graph.nodes = AsyncMock(
            return_value=AsyncIterableMock([mock_node])
        )

        tool = ListGraphNodesTool(client=mock_client)
        result = tool._run(project_id="p1")
        assert "Alice" in result


class TestAddFactsTool:
    """Tests for AddFactsTool."""

    def test_name_and_args_schema(self, mock_client):
        tool = AddFactsTool(client=mock_client)
        assert tool.name == "add_facts"
        assert tool.args_schema == AddFactsInput

    @pytest.mark.asyncio
    async def test_arun_accepts_facts(self, mock_client):
        mock_client.facts.add.return_value = AsyncMock(
            accepted_count=2, job_id="job-1"
        )

        tool = AddFactsTool(client=mock_client)
        facts = [
            {"subject": "Alice", "predicate": "works_at", "object": "Acme"},
            {"subject": "Alice", "predicate": "role", "object": "Engineer"},
        ]
        result = await tool._arun(project_id="project-1", facts=facts)

        assert "Accepted 2 fact(s)" in result
        assert "job-1" in result

    @pytest.mark.asyncio
    async def test_arun_calls_facts_add(self, mock_client):
        mock_client.facts.add.return_value = AsyncMock(
            accepted_count=1, job_id="job-1"
        )

        tool = AddFactsTool(client=mock_client)
        facts = [{"subject": "Alice", "predicate": "likes", "object": "Python"}]
        await tool._arun(project_id="project-1", facts=facts)

        # The tool normalizes dicts, adding content/confidence defaults
        mock_client.facts.add.assert_awaited_once()
        call_args = mock_client.facts.add.await_args
        expected = [
            {"subject": "Alice", "predicate": "likes", "object": "Python",
             "content": None, "confidence": 1.0},
        ]
        assert call_args.args[0] == expected

    def test_run_sync(self, mock_client):
        """Sync _run delegates to async."""
        mock_client.facts.add.return_value = AsyncMock(
            accepted_count=1, job_id="job-1"
        )
        facts = [{"subject": "X", "predicate": "y", "object": "z"}]

        tool = AddFactsTool(client=mock_client)
        result = tool._run(project_id="p1", facts=facts)
        assert "Accepted 1 fact(s)" in result
