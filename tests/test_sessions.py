"""Tests for the OpenZync Python SDK — sessions domain."""

from __future__ import annotations

import pytest


class TestSessionsClient:
    """Tests for ``AsyncSessionsClient``."""

    @pytest.mark.asyncio
    async def test_create_session(self, async_client, mock_http, mock_resolve):
        """POST /sessions returns SessionResponse."""
        mock_http.post("/v1/projects/p1/sessions").respond(json={
            "id": "s1",
            "project_id": "p1",
            "created_by": "u1",
            "external_id": "demo",
            "metadata": {},
            "is_active": True,
            "message_count": 0,
            "fact_count": 0,
            "created_at": "2026-01-01T00:00:00Z",
        })

        session = await async_client.sessions.create(external_id="demo")
        assert session.id == "s1"
        assert session.external_id == "demo"
        assert session.project_id == "p1"
        assert session.created_by == "u1"

    @pytest.mark.asyncio
    async def test_get_session(self, async_client, mock_http, mock_resolve):
        """GET /sessions/{id} returns session."""
        session_id = "s1"
        mock_http.get(f"/v1/projects/p1/sessions/{session_id}").respond(json={
            "id": session_id, "project_id": "p1", "created_by": "u1",
            "external_id": "demo",
            "metadata": {}, "is_active": True,
            "message_count": 0, "fact_count": 0,
            "created_at": "2026-01-01T00:00:00Z",
        })

        session = await async_client.sessions.get(session_id=session_id)
        assert session.external_id == "demo"

    @pytest.mark.asyncio
    async def test_delete_session(self, async_client, mock_http, mock_resolve):
        """DELETE /sessions/{id} returns 204."""
        mock_http.delete("/v1/projects/p1/sessions/s1").respond(status_code=204)

        await async_client.sessions.delete(session_id="s1")
        # No exception means success

    @pytest.mark.asyncio
    async def test_list_sessions(self, async_client, mock_http, mock_resolve):
        """GET /sessions returns paginated sessions."""
        mock_http.get("/v1/projects/p1/sessions").respond(json={
            "data": [
                {"id": "s1", "project_id": "p1", "created_by": "u1",
                 "external_id": "demo", "metadata": {},
                 "is_active": True, "message_count": 2, "fact_count": 0,
                 "created_at": "2026-01-01T00:00:00Z"},
            ],
            "next_cursor": None,
            "has_more": False,
        })

        result = await async_client.sessions.list()
        assert len(result["data"]) == 1
        assert result["data"][0]["external_id"] == "demo"

    @pytest.mark.asyncio
    async def test_list_sessions_with_cursor(self, async_client, mock_http, mock_resolve):
        """GET /sessions passes cursor param."""
        mock_http.get("/v1/projects/p1/sessions").respond(json={
            "data": [],
            "next_cursor": "next-page",
            "has_more": True,
        })

        result = await async_client.sessions.list(cursor="abc")
        assert result["has_more"] is True

    @pytest.mark.asyncio
    async def test_get_messages(self, async_client, mock_http, mock_resolve):
        """GET /sessions/{id}/messages returns messages."""
        session_id = "s1"
        mock_http.get(f"/v1/projects/p1/sessions/{session_id}/messages").respond(json={
            "data": [
                {"id": "e1", "role": "user", "content": "Hello",
                 "metadata": {}, "token_count": 0, "sequence_number": 0,
                 "created_at": "2026-01-01T00:00:00Z"},
                {"id": "e2", "role": "assistant", "content": "Hi",
                 "metadata": {}, "token_count": 0, "sequence_number": 1,
                 "created_at": "2026-01-01T00:00:00Z"},
            ],
            "next_cursor": None,
            "has_more": False,
        })

        msgs = await async_client.sessions.messages(
            session_id=session_id
        )
        assert len(msgs.data) == 2
        assert msgs.data[0].role == "user"

    @pytest.mark.asyncio
    async def test_get_messages_with_cursor(self, async_client, mock_http, mock_resolve):
        """GET /sessions/{id}/messages passes cursor param."""
        mock_http.get("/v1/projects/p1/sessions/s1/messages").respond(json={
            "data": [],
            "next_cursor": None,
            "has_more": False,
        })

        msgs = await async_client.sessions.messages(
            session_id="s1", cursor="c1"
        )
        assert len(msgs.data) == 0
