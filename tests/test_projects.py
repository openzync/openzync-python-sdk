"""Tests for the OpenZync Python SDK — projects domain."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import Response

from openzync.models.project import ProjectMemberResponse, ProjectResponse


class TestProjectsClient:
    """Tests for ``AsyncProjectsClient``."""

    @pytest.mark.asyncio
    async def test_create_project(self, async_client, mock_http):
        """POST /projects returns ProjectResponse."""
        mock_http.post("/v1/projects").respond(
            json={
                "id": "p1",
                "name": "My Project",
                "description": "A test project",
                "metadata": {},
                "is_archived": False,
                "member_count": 1,
                "created_by": "u1",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        )

        project = await async_client.projects.create(
            name="My Project",
            description="A test project",
        )
        assert isinstance(project, ProjectResponse)
        assert project.id == "p1"
        assert project.name == "My Project"
        assert project.member_count == 1
        assert project.created_by == "u1"

    @pytest.mark.asyncio
    async def test_get_project(self, async_client, mock_http, mock_resolve):
        """GET /projects/{id} returns project."""
        mock_http.get("/v1/projects/p1").respond(
            json={
                "id": "p1",
                "name": "My Project",
                "description": None,
                "metadata": {},
                "is_archived": False,
                "member_count": 2,
                "created_by": "u1",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        )

        project = await async_client.projects.get()
        assert project.id == "p1"
        assert project.member_count == 2

    @pytest.mark.asyncio
    async def test_list_projects(self, async_client, mock_http):
        """GET /projects returns a flat, typed list of ProjectResponse."""
        mock_http.get("/v1/projects").respond(
            json=[
                {
                    "id": "p1",
                    "name": "Project 1",
                    "metadata": {},
                    "is_archived": False,
                    "is_pinned": False,
                    "member_count": 1,
                    "created_by": "u1",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
                {
                    "id": "p2",
                    "name": "Project 2",
                    "metadata": {},
                    "is_archived": False,
                    "is_pinned": True,
                    "member_count": 3,
                    "created_by": "u2",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
            ]
        )

        result = await async_client.projects.list()
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(project, ProjectResponse) for project in result)
        assert result[0].name == "Project 1"
        assert result[1].is_pinned is True
        assert result[0].created_at == datetime(2026, 1, 1, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_list_projects_passes_offset(self, async_client, mock_http):
        """GET /projects sends limit/offset — the cursor param is gone."""
        route = mock_http.get("/v1/projects").respond(json=[])

        await async_client.projects.list(offset=10)

        request = route.calls.last.request
        assert request.url.params["limit"] == "50"
        assert request.url.params["offset"] == "10"
        assert "cursor" not in request.url.params

    @pytest.mark.asyncio
    async def test_list_projects_include_archived(self, async_client, mock_http):
        """include_archived is sent only when True."""
        route = mock_http.get("/v1/projects").respond(json=[])

        await async_client.projects.list(include_archived=True)
        assert route.calls.last.request.url.params["include_archived"] == "true"

        await async_client.projects.list()
        assert "include_archived" not in route.calls.last.request.url.params

    @pytest.mark.asyncio
    async def test_list_projects_sort_params(self, async_client, mock_http):
        """sort_by sends sort_dir alongside; both omitted by default."""
        route = mock_http.get("/v1/projects").respond(json=[])

        await async_client.projects.list(sort_by="name", sort_dir="asc")
        request = route.calls.last.request
        assert request.url.params["sort_by"] == "name"
        assert request.url.params["sort_dir"] == "asc"

        await async_client.projects.list()
        request = route.calls.last.request
        assert "sort_by" not in request.url.params
        assert "sort_dir" not in request.url.params

    @pytest.mark.asyncio
    async def test_list_iter(self, async_client, mock_http):
        """list_iter pages by offset and yields typed ProjectResponse models."""
        mock_http.get("/v1/projects").side_effect = [
            Response(
                200,
                json=[
                    {
                        "id": "p1",
                        "name": "Project 1",
                        "metadata": {},
                        "is_archived": False,
                        "is_pinned": False,
                        "member_count": 1,
                        "created_by": "u1",
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z",
                    },
                    {
                        "id": "p2",
                        "name": "Project 2",
                        "metadata": {},
                        "is_archived": False,
                        "is_pinned": False,
                        "member_count": 2,
                        "created_by": "u1",
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z",
                    },
                ],
            ),
            Response(
                200,
                json=[
                    {
                        "id": "p3",
                        "name": "Project 3",
                        "metadata": {},
                        "is_archived": False,
                        "is_pinned": True,
                        "member_count": 4,
                        "created_by": "u2",
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z",
                    },
                ],
            ),
        ]

        projects = [
            project async for project in async_client.projects.list_iter(limit=2)
        ]

        assert len(projects) == 3
        assert all(isinstance(project, ProjectResponse) for project in projects)
        assert [project.name for project in projects] == [
            "Project 1",
            "Project 2",
            "Project 3",
        ]
        # Full first page (2 items at limit=2) implies more — second page
        # advances offset by limit; the short page terminates iteration.
        assert mock_http.calls[0].request.url.params["offset"] == "0"
        assert mock_http.calls[1].request.url.params["offset"] == "2"
        assert mock_http.calls[1].request.url.params["limit"] == "2"

    @pytest.mark.asyncio
    async def test_update_project(self, async_client, mock_http, mock_resolve):
        """PATCH /projects/{id} updates and returns project."""
        mock_http.patch("/v1/projects/p1").respond(
            json={
                "id": "p1",
                "name": "Updated Name",
                "description": "Updated desc",
                "metadata": {"key": "val"},
                "is_archived": False,
                "member_count": 1,
                "created_by": "u1",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            }
        )

        project = await async_client.projects.update(
            name="Updated Name",
        )
        assert project.name == "Updated Name"
        assert project.metadata == {"key": "val"}

    @pytest.mark.asyncio
    async def test_archive_project(self, async_client, mock_http, mock_resolve):
        """DELETE /projects/{id} returns 204."""
        mock_http.delete("/v1/projects/p1").respond(status_code=204)

        await async_client.projects.archive()
        # No exception means success

    @pytest.mark.asyncio
    async def test_add_member(self, async_client, mock_http, mock_resolve):
        """POST /projects/{id}/members adds a member."""
        mock_http.post("/v1/projects/p1/members").respond(
            json={
                "id": "m1",
                "user_id": "u2",
                "role": "member",
                "created_at": "2026-01-01T00:00:00Z",
            }
        )

        member = await async_client.projects.add_member(
            user_id="u2",
            role="member",
        )
        assert isinstance(member, ProjectMemberResponse)
        assert member.user_id == "u2"
        assert member.role == "member"

    @pytest.mark.asyncio
    async def test_remove_member(self, async_client, mock_http, mock_resolve):
        """DELETE /projects/{id}/members/{user_id} returns 204."""
        user_id = "u2"
        mock_http.delete(f"/v1/projects/p1/members/{user_id}").respond(status_code=204)

        await async_client.projects.remove_member(
            user_id=user_id,
        )

    @pytest.mark.asyncio
    async def test_list_members(self, async_client, mock_http, mock_resolve):
        """GET /projects/{id}/members returns a flat typed list with nested user."""
        mock_http.get("/v1/projects/p1/members").respond(
            json=[
                {
                    "id": "m1",
                    "user_id": "u1",
                    "role": "owner",
                    "created_at": "2026-01-01T00:00:00Z",
                    "user": {
                        "id": "u1",
                        "external_id": "alice",
                        "organization_id": "org-1",
                        "name": "Alice",
                        "email": "alice@example.com",
                        "permissions": ["project:read", "project:write"],
                        "role": "admin",
                        "is_pending_invite": False,
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z",
                    },
                },
                {
                    "id": "m2",
                    "user_id": "u2",
                    "role": "member",
                    "created_at": "2026-01-01T00:00:00Z",
                    "user": None,
                },
            ]
        )

        result = await async_client.projects.list_members()
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(member, ProjectMemberResponse) for member in result)
        assert result[0].role == "owner"
        assert result[0].user is not None
        assert result[0].user.name == "Alice"
        assert result[0].user.created_at == datetime(2026, 1, 1, tzinfo=UTC)
        assert result[1].user is None
        # core never returns project_id on members
        assert not hasattr(result[0], "project_id")

    @pytest.mark.asyncio
    async def test_list_members_sort_params(
        self, async_client, mock_http, mock_resolve
    ):
        """list_members sends sort_by/sort_dir; limit/cursor are gone."""
        route = mock_http.get("/v1/projects/p1/members").respond(json=[])

        await async_client.projects.list_members(sort_by="role", sort_dir="desc")
        request = route.calls.last.request
        assert request.url.params["sort_by"] == "role"
        assert request.url.params["sort_dir"] == "desc"

        await async_client.projects.list_members()
        request = route.calls.last.request
        assert "sort_by" not in request.url.params
        assert "limit" not in request.url.params
        assert "cursor" not in request.url.params

    @pytest.mark.asyncio
    async def test_update_project_sends_patch(
        self, async_client, mock_http, mock_resolve
    ):
        """BREAKING regression: update() sends PATCH — the backend only defines
        PATCH /v1/projects/{id}; the old PUT produced a live 405."""
        route = mock_http.patch("/v1/projects/p1").respond(
            json={
                "id": "p1",
                "name": "Renamed",
                "description": None,
                "metadata": {},
                "is_archived": False,
                "member_count": 1,
                "created_by": None,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            }
        )

        result = await async_client.projects.update(name="Renamed")

        request = route.calls.last.request
        assert request.method == "PATCH"
        assert result.name == "Renamed"

    @pytest.mark.asyncio
    async def test_update_member_role(self, async_client, mock_http, mock_resolve):
        """PATCH /projects/{id}/members/{user_id} passes role as query param."""
        route = mock_http.patch("/v1/projects/p1/members/u2").respond(
            json={
                "id": "m2",
                "user_id": "u2",
                "role": "owner",
                "created_at": "2026-01-01T00:00:00Z",
            }
        )

        result = await async_client.projects.update_member(user_id="u2", role="owner")

        request = route.calls.last.request
        assert request.method == "PATCH"
        assert request.url.params["role"] == "owner"
        assert result.role == "owner"

    @pytest.mark.asyncio
    async def test_update_member_requires_role(self, async_client):
        """``role`` is mandatory — a missing role must not default to "member".

        The old default silently demoted a project OWNER when the caller
        meant to change nothing, so the argument is now required and the
        call fails loudly instead.
        """
        with pytest.raises(TypeError, match="role"):
            await async_client.projects.update_member(user_id="u2")
