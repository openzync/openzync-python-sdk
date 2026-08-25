"""Tests for the OpenZync Python SDK — facts domain."""

from __future__ import annotations

import pytest

from openzync.models.facts import FactBatchResponse, FactResponse, FactTriple
from tests.conftest import mock_response


class TestFactsClient:
    """Tests for ``AsyncFactsClient``."""

    @pytest.mark.asyncio
    async def test_add_facts(self, async_client, mock_http, mock_resolve):
        """POST /facts returns FactBatchResponse."""
        expected = {
            "job_id": "job-789",
            "accepted_count": 2,
            "status": "accepted",
            "message": "2 facts accepted",
        }
        mock_http.post("/v1/projects/p1/facts").respond(status_code=202, json=expected)

        result = await async_client.facts.add(
            facts=[
                {"subject": "Alice", "predicate": "works_at", "object": "Acme"},
                {"subject": "Alice", "predicate": "likes", "object": "hiking"},
            ],
            session_id="s1",
        )

        assert isinstance(result, FactBatchResponse)
        assert result.accepted_count == 2
        assert result.job_id == "job-789"

    @pytest.mark.asyncio
    async def test_add_facts_with_session(self, async_client, mock_http, mock_resolve):
        """POST /facts with session_id."""
        mock_http.post("/v1/projects/p1/facts").respond(
            status_code=202,
            json={"job_id": "j1", "accepted_count": 1, "status": "accepted"},
        )

        result = await async_client.facts.add(
            facts=[{"subject": "X", "predicate": "y", "object": "z"}],
            session_id="s1",
        )
        assert result.accepted_count == 1

    @pytest.mark.asyncio
    async def test_add_facts_with_model_objects(
        self, async_client, mock_http, mock_resolve
    ):
        """POST /facts with FactTriple model objects."""
        mock_http.post("/v1/projects/p1/facts").respond(
            status_code=202,
            json={"job_id": "j1", "accepted_count": 1, "status": "accepted"},
        )

        result = await async_client.facts.add(
            facts=[FactTriple(subject="Alice", predicate="knows", object="Bob")],
            session_id="s1",
        )
        assert result.accepted_count == 1


class TestFactsListRetractHistory:
    """Tests for facts list / retract / history endpoints."""

    @pytest.mark.asyncio
    async def test_list_facts(self, async_client, mock_http, mock_resolve):
        """GET /facts returns PaginatedFactsResponse with offset pagination."""
        route = mock_http.get("/v1/projects/p1/facts").respond(
            json={
                "data": [
                    {
                        "id": "f1",
                        "content": "Alice works at Acme",
                        "subject": "Alice",
                        "predicate": "works_at",
                        "object": "Acme",
                        "confidence": 0.9,
                        "valid_from": "2026-01-01T00:00:00Z",
                        "valid_to": None,
                        "invalid_at": None,
                        "created_at": "2026-01-01T00:00:00Z",
                    },
                ],
                "next_cursor": "50",
                "has_more": True,
            }
        )

        result = await async_client.facts.list(
            as_of="2026-01-01T00:00:00Z", limit=50, offset=0
        )

        request = route.calls.last.request
        assert request.url.params["as_of"] == "2026-01-01T00:00:00Z"
        assert request.url.params["limit"] == "50"
        assert request.url.params["offset"] == "0"
        assert isinstance(result.data[0], FactResponse)
        assert result.has_more is True
        assert result.next_cursor == "50"

    @pytest.mark.asyncio
    async def test_retract_fact(self, async_client, mock_http, mock_resolve):
        """POST /facts/{id}/retract sends optional reason body."""
        route = mock_http.post("/v1/projects/p1/facts/f1/retract").respond(
            json={
                "id": "f1",
                "content": "Alice works at Acme",
                "subject": "Alice",
                "predicate": "works_at",
                "object": "Acme",
                "confidence": 0.9,
                "invalid_at": "2026-08-24T12:00:00Z",
                "created_at": "2026-01-01T00:00:00Z",
            }
        )

        result = await async_client.facts.retract("f1", reason="outdated")

        request = route.calls.last.request
        assert (
            b'"reason":"outdated"' in request.content
            or b'"reason": "outdated"' in request.content
        )
        assert result.invalid_at == "2026-08-24T12:00:00Z"

    @pytest.mark.asyncio
    async def test_retract_fact_without_reason_sends_no_body(
        self, async_client, mock_http, mock_resolve
    ):
        """POST /facts/{id}/retract omits the body when no reason given."""
        route = mock_http.post("/v1/projects/p1/facts/f1/retract").respond(
            json={
                "id": "f1",
                "content": "c",
                "created_at": "2026-01-01T00:00:00Z",
            }
        )

        await async_client.facts.retract("f1")

        request = route.calls.last.request
        # httpx drops json=None entirely — the retract POST carries no body.
        assert request.read() == b""

    @pytest.mark.asyncio
    async def test_fact_history(self, async_client, mock_http, mock_resolve):
        """GET /facts/{id}/history returns fact plus lineage events."""
        mock_http.get("/v1/projects/p1/facts/f1/history").respond(
            json={
                "fact": {
                    "id": "f2",
                    "content": "Alice works at Globex",
                    "created_at": "2026-02-01T00:00:00Z",
                },
                "events": [
                    {
                        "id": "ev1",
                        "old_fact_id": "f1",
                        "new_fact_id": "f2",
                        "kind": "superseded",
                        "reason": None,
                        "at_time": "2026-02-01T00:00:00Z",
                        "source_episode_id": None,
                    },
                ],
            }
        )

        result = await async_client.facts.history("f1")

        assert result.fact.id == "f2"
        assert result.events[0].kind == "superseded"
