"""Projects domain client — CRUD operations and member management."""

from __future__ import annotations

from typing import Literal

from openzync._http import AsyncHTTPTransport
from openzync._pagination import AsyncPaginatedIterator
from openzync.models.project import (
    AddMemberRequest,
    CreateProjectRequest,
    ProjectMemberResponse,
    ProjectResponse,
    UpdateProjectRequest,
)

# Mirrors core's schemas/sorting.py Literals, minus keys unreachable from the
# SDK: ``pinned_at`` only resolves in core's pinned_only branch, which 422s
# for API-key auth (pinned_only requires dashboard auth).
ProjectSortBy = Literal["name", "created_at", "updated_at"]
ProjectMemberSortBy = Literal["created_at", "role", "name", "email"]
SortDir = Literal["asc", "desc"]


class AsyncProjectsClient:
    """Async client for project operations.

    Args:
        http: The shared async HTTP transport instance.
    """

    def __init__(self, http: AsyncHTTPTransport) -> None:
        self._http = http

    async def create(
        self,
        name: str,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> ProjectResponse:
        """Create a new project.

        The authenticated user is automatically added as an ``owner``.

        Args:
            name: Display name for the project (1-255 chars).
            description: Optional description.
            metadata: Optional metadata dict.

        Returns:
            ``ProjectResponse`` with the created project.
        """
        body = CreateProjectRequest(
            name=name,
            description=description,
            metadata=metadata if metadata is not None else {},
        )
        data = await self._http.request(
            "POST",
            "/v1/projects",
            json_body=body.model_dump(exclude_none=True),
        )
        return ProjectResponse(**data)

    async def get(self) -> ProjectResponse:
        """Get project details by UUID.

        Returns:
            ``ProjectResponse`` with project details including member count.
        """
        pid = await self._http.resolve_project_id()
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}",
        )
        return ProjectResponse(**data)

    async def update(
        self,
        name: str | None = None,
        description: str | None = None,
        metadata: dict | None = None,
        is_archived: bool | None = None,
    ) -> ProjectResponse:
        """Update project fields.

        Args:
            name: Optional new display name.
            description: Optional new description.
            metadata: Optional new metadata dict.
            is_archived: Optional archive flag.

        Returns:
            ``ProjectResponse`` with updated fields.
        """
        pid = await self._http.resolve_project_id()
        body = UpdateProjectRequest(
            name=name,
            description=description,
            metadata=metadata,
            is_archived=is_archived,
        )
        data = await self._http.request(
            "PATCH",
            f"/v1/projects/{pid}",
            json_body=body.model_dump(exclude_none=True),
        )
        return ProjectResponse(**data)

    # ⚠️ BREAKING: returns core's real contract — a flat list of typed
    # ``ProjectResponse`` models (core's ``response_model=list[ProjectResponse]``)
    # — instead of the fabricated ``{"data", "next_cursor", "has_more"} envelope.
    # The ``cursor`` param is gone: core paginates offset-based, so callers now
    # advance ``offset`` explicitly.
    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False,
        sort_by: ProjectSortBy | None = None,
        sort_dir: SortDir = "desc",
    ) -> list[ProjectResponse]:
        """List projects in the organisation (offset-based pagination).

        Args:
            limit: Maximum results per page (core accepts 1–200; larger
                values are rejected with 422).
            offset: Number of results to skip. Advance by ``limit`` to
                page through results.
            include_archived: When True, include archived projects.
                Omitted from the query when False (backend default).
            sort_by: Sort key. Omitted from the query when None (backend
                default ``created_at``/``desc``).
            sort_dir: Sort direction; only sent alongside ``sort_by``
                (core ignores a direction without a key).

        Returns:
            Flat list of ``ProjectResponse`` models — exactly what core
            returns. A page shorter than ``limit`` is the last page.
        """
        params: dict[str, str | int | bool] = {"limit": limit, "offset": offset}
        if include_archived:
            params["include_archived"] = True
        if sort_by is not None:
            params["sort_by"] = sort_by
            params["sort_dir"] = sort_dir
        data = await self._http.request(
            "GET",
            "/v1/projects",
            params=params,
        )
        return [ProjectResponse(**item) for item in data]

    # ⚠️ BREAKING: now offset-paginates core's flat-array contract and yields
    # typed ``ProjectResponse`` models. The old synthesized envelope always
    # carried ``has_more=False``, so iteration stopped after page 1 and any
    # org with more than ``limit`` projects silently saw exactly ``limit``
    # items.
    def list_iter(
        self,
        *,
        limit: int = 50,
        include_archived: bool = False,
        sort_by: ProjectSortBy | None = None,
        sort_dir: SortDir = "desc",
    ) -> AsyncPaginatedIterator:
        """Iterate over all projects with auto-pagination.

        Fetches pages of ``limit`` projects by advancing ``offset`` and
        stops when a short page (fewer than ``limit`` items) or an empty
        page returns.

        Usage::

            async for project in client.projects.list_iter():
                print(project.name)
        """

        async def fetch_page(cursor: str | None = None) -> dict:
            offset = int(cursor) if cursor is not None else 0
            page = await self.list(
                limit=limit,
                offset=offset,
                include_archived=include_archived,
                sort_by=sort_by,
                sort_dir=sort_dir,
            )
            # Core returns a bare array with no envelope — translate the
            # offset semantics into the iterator's cursor contract: a full
            # page implies more rows may follow; a short page terminates.
            has_more = len(page) == limit
            return {
                "data": page,
                "next_cursor": str(offset + limit) if has_more else None,
                "has_more": has_more,
            }

        return AsyncPaginatedIterator(fetch_page, limit)

    async def archive(self) -> None:
        """Archive (soft-delete) a project."""
        pid = await self._http.resolve_project_id()
        await self._http.request(
            "DELETE",
            f"/v1/projects/{pid}",
        )

    async def unarchive(self) -> ProjectResponse:
        """Restore an archived project.

        Note: pin/unpin are dashboard-JWT-only and intentionally not exposed.

        Returns:
            ``ProjectResponse`` with the restored project.
        """
        pid = await self._http.resolve_project_id()
        data = await self._http.request(
            "POST",
            f"/v1/projects/{pid}/unarchive",
        )
        return ProjectResponse(**data)

    async def add_member(
        self,
        user_id: str,
        role: str = "member",
    ) -> ProjectMemberResponse:
        """Add a member to a project.

        Args:
            user_id: The UUID of the user to add.
            role: Project role (``"owner"`` or ``"member"``).

        Returns:
            ``ProjectMemberResponse`` with membership details.
        """
        pid = await self._http.resolve_project_id()
        body = AddMemberRequest(user_id=user_id, role=role)
        data = await self._http.request(
            "POST",
            f"/v1/projects/{pid}/members",
            json_body=body.model_dump(exclude_none=True),
        )
        return ProjectMemberResponse(**data)

    async def remove_member(self, user_id: str) -> None:
        """Remove a member from a project.

        Args:
            user_id: The UUID of the user to remove.
        """
        pid = await self._http.resolve_project_id()
        await self._http.request(
            "DELETE",
            f"/v1/projects/{pid}/members/{user_id}",
        )

    async def update_member(
        self,
        user_id: str,
        role: str = "member",
    ) -> ProjectMemberResponse:
        """Change a member's role within a project.

        Args:
            user_id: The UUID of the user whose role to change.
            role: New project role (``"owner"`` or ``"member"``).

        Returns:
            ``ProjectMemberResponse`` with the updated membership.

        Raises:
            openzync._errors.NotFoundError: If the member does not exist.
        """
        pid = await self._http.resolve_project_id()
        data = await self._http.request(
            "PATCH",
            f"/v1/projects/{pid}/members/{user_id}",
            params={"role": role},
        )
        return ProjectMemberResponse(**data)

    # ⚠️ BREAKING: returns core's real contract — a flat list of typed
    # ``ProjectMemberResponse`` models (core's
    # ``response_model=list[ProjectMemberResponse]``) — instead of the raw
    # envelope dict the docstring used to promise. ``limit``/``cursor`` are
    # gone: core's members endpoint is not paginated (it lists all members)
    # and silently ignored those params.
    async def list_members(
        self,
        *,
        sort_by: ProjectMemberSortBy | None = None,
        sort_dir: SortDir = "asc",
    ) -> list[ProjectMemberResponse]:
        """List all members of a project.

        Args:
            sort_by: Sort key — ``created_at``, ``role``, ``name`` (member's
                display name), or ``email``. Omitted from the query when
                None (backend default ``created_at``/``asc``).
            sort_dir: Sort direction; only sent alongside ``sort_by``
                (core ignores a direction without a key).

        Returns:
            Flat list of ``ProjectMemberResponse`` models with nested
            ``user`` details (``None`` on the member when the user row is
            missing).
        """
        pid = await self._http.resolve_project_id()
        params: dict[str, str | int] = {}
        if sort_by is not None:
            params["sort_by"] = sort_by
            params["sort_dir"] = sort_dir
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/members",
            params=params,
        )
        return [ProjectMemberResponse(**item) for item in data]
