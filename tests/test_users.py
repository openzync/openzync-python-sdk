"""Tests for the OpenZync Python SDK — users domain."""

from __future__ import annotations

import json

import pytest

from tests.conftest import mock_response


class TestUsersClient:
    """Tests for ``AsyncUsersClient``."""

    @pytest.mark.asyncio
    async def test_create_user(self, async_client, mock_http):
        """POST /users returns UserResponse."""
        mock_http.post("/v1/users").respond(json={
            "id": "u1",
            "external_id": "alice",
            "name": "Alice",
            "email": None,
            "metadata": {},
            "organization_id": "org-1",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "is_deleted": False,
            "message_count": 0,
            "fact_count": 0,
            "session_count": 0,
            "permissions": ["project:read", "project:write"],
        })

        user = await async_client.users.create(external_id="alice", name="Alice")
        assert user.id == "u1"
        assert user.external_id == "alice"
        assert user.name == "Alice"
        assert user.permissions == ["project:read", "project:write"]

    @pytest.mark.asyncio
    async def test_create_user_with_permissions(self, async_client, mock_http):
        """POST /users passes explicit permissions through."""
        mock_http.post("/v1/users").respond(json={
            "id": "u1",
            "external_id": "alice",
            "name": "Alice",
            "email": None,
            "metadata": {},
            "organization_id": "org-1",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "is_deleted": False,
            "message_count": 0,
            "fact_count": 0,
            "session_count": 0,
            "permissions": ["project:read", "project:write", "members:read"],
        })

        user = await async_client.users.create(
            external_id="alice",
            name="Alice",
            permissions=["project:read", "project:write", "members:read"],
        )
        assert user.permissions == ["project:read", "project:write", "members:read"]
        sent = json.loads(mock_http.calls[-1].request.content)
        assert sent["permissions"] == ["project:read", "project:write", "members:read"]

    @pytest.mark.asyncio
    async def test_create_user_omits_permissions_when_unset(self, async_client, mock_http):
        """POST /users omits permissions when not provided (backend seeds defaults)."""
        mock_http.post("/v1/users").respond(json={
            "id": "u1",
            "external_id": "alice",
            "name": "Alice",
            "email": None,
            "metadata": {},
            "organization_id": "org-1",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "is_deleted": False,
            "message_count": 0,
            "fact_count": 0,
            "session_count": 0,
            "permissions": ["project:read", "project:write"],
        })

        await async_client.users.create(external_id="alice", name="Alice")
        sent = json.loads(mock_http.calls[-1].request.content)
        assert "permissions" not in sent

    @pytest.mark.asyncio
    async def test_get_user(self, async_client, mock_http):
        """GET /users/{id} returns user."""
        user_id = "u1"
        mock_http.get(f"/v1/users/{user_id}").respond(json={
            "id": user_id, "external_id": "alice", "name": "Alice",
            "organization_id": "org-1",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "is_deleted": False,
            "message_count": 5, "fact_count": 3, "session_count": 2,
            "permissions": ["project:read", "project:write"],
        })

        user = await async_client.users.get(user_id)
        assert user.message_count == 5

    @pytest.mark.asyncio
    async def test_update_user(self, async_client, mock_http):
        """PATCH /users/{id} returns updated user."""
        user_id = "u1"
        mock_http.patch(f"/v1/users/{user_id}").respond(json={
            "id": user_id, "external_id": "alice", "name": "Alice Updated",
            "organization_id": "org-1",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "is_deleted": False,
            "message_count": 0, "fact_count": 0, "session_count": 0,
            "permissions": ["project:read", "project:write"],
        })

        user = await async_client.users.update(user_id, name="Alice Updated")
        assert user.name == "Alice Updated"

    @pytest.mark.asyncio
    async def test_delete_user(self, async_client, mock_http):
        """DELETE /users/{id} returns 204."""
        user_id = "u1"
        mock_http.delete(f"/v1/users/{user_id}").respond(status_code=204)
        await async_client.users.delete(user_id)

    @pytest.mark.asyncio
    async def test_list_users(self, async_client, mock_http):
        """GET /users returns paginated list."""
        mock_http.get("/v1/users").respond(json={
            "data": [
                {"id": "u1", "external_id": "alice", "name": "Alice",
                 "organization_id": "org-1",
                 "created_at": "2026-01-01T00:00:00Z",
                 "updated_at": "2026-01-01T00:00:00Z",
                 "is_deleted": False,
                 "message_count": 0, "fact_count": 0, "session_count": 0,
                 "permissions": ["project:read", "project:write"]},
            ],
            "next_cursor": None,
            "has_more": False,
        })

        result = await async_client.users.list()
        assert len(result["data"]) == 1

    @pytest.mark.asyncio
    async def test_list_users_with_cursor(self, async_client, mock_http):
        """GET /users passes cursor param."""
        mock_http.get("/v1/users").respond(json={
            "data": [],
            "next_cursor": None,
            "has_more": False,
        })

        result = await async_client.users.list(cursor="abc")
        assert len(result["data"]) == 0

    @pytest.mark.asyncio
    async def test_list_iter(self, async_client, mock_http):
        """list_iter yields paginated user results."""
        mock_http.get("/v1/users").respond(json={
            "data": [
                {"id": "u1", "external_id": "alice", "name": "Alice",
                 "organization_id": "org-1",
                 "created_at": "2026-01-01T00:00:00Z",
                 "updated_at": "2026-01-01T00:00:00Z",
                 "is_deleted": False,
                 "message_count": 0, "fact_count": 0, "session_count": 0,
                 "permissions": ["project:read", "project:write"]},
            ],
            "next_cursor": None,
            "has_more": False,
        })

        users = []
        async for user in async_client.users.list_iter():
            users.append(user)
        assert len(users) == 1
        assert users[0]["external_id"] == "alice"
