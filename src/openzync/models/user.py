"""Pydantic models for the user domain."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ⚠️ BREAKING: the `permissions` field was removed from this model — core
# validates but silently drops it on POST /v1/users (it seeds role defaults
# instead), so sending it promised grants the backend never applied.
class UserCreateRequest(BaseModel):
    """Request body for ``POST /v1/users``.

    Permissions are seeded server-side from the role defaults and cannot be
    set at creation — use ``UserUpdateRequest`` to change them afterwards.
    """

    external_id: str = Field(
        ..., min_length=1, max_length=255, description="Caller-defined user identifier."
    )
    name: str | None = Field(default=None, max_length=512)
    email: str | None = Field(default=None, max_length=320)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UserUpdateRequest(BaseModel):
    """Request body for ``PATCH /v1/users/{user_id}``."""

    name: str | None = Field(default=None, max_length=512)
    email: str | None = Field(default=None, max_length=320)
    metadata: dict[str, Any] | None = Field(default=None)
    permissions: list[str] | None = Field(
        default=None,
        description="Explicit permission grants. Omit to leave unchanged.",
    )


class UserResponse(BaseModel):
    """Response from user CRUD endpoints."""

    id: str = Field(..., description="Internal UUID.")
    external_id: str = Field(..., description="Caller-defined identifier.")
    name: str | None = None
    email: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    role: str = Field(
        default="member",
        description="Dashboard role — 'admin' or 'member'.",
    )
    organization_id: str = Field(..., description="Owning organization UUID.")
    created_at: datetime = Field(..., description="ISO-8601 creation timestamp.")
    updated_at: datetime = Field(..., description="ISO-8601 update timestamp.")
    is_deleted: bool = Field(default=False)
    is_pending_invite: bool = Field(
        default=False,
        description="True while the user has a pending admin invite "
        "(invite_token_hash is not NULL) — the user cannot log in "
        "until the invite is accepted.",
    )
    message_count: int = Field(default=0)
    fact_count: int = Field(default=0)
    session_count: int = Field(default=0)
    permissions: list[str] = Field(
        ...,
        description="Effective permission grants. Empty array = full access (admin).",
    )


class UserListResponse(BaseModel):
    """Paginated response for ``GET /v1/users``.

    BREAKING: ``AsyncUsersClient.list`` returns this model — callers
    doing ``result["data"]`` must move to ``result.data``.
    """

    data: list[UserResponse] = Field(..., description="Users for the current page.")
    next_cursor: str | None = Field(default=None)
    has_more: bool = Field(default=False)
