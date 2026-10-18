"""Pydantic models for the session domain."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    """Request body for ``POST /v1/projects/{project_id}/sessions``."""

    external_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Caller-defined session identifier.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionResponse(BaseModel):
    """Response from session CRUD endpoints."""

    id: str = Field(..., description="Internal UUID.")
    project_id: str = Field(..., description="Owning project UUID.")
    created_by: str = Field(..., description="User UUID who created the session.")
    external_id: str = Field(..., description="Caller-defined identifier.")
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(default=True)
    message_count: int = Field(default=0)
    fact_count: int = Field(default=0)
    pending_enrichment_count: int = Field(
        default=0,
        description="Number of messages in this session pending enrichment completion.",
    )
    observation_count: int = Field(
        default=0,
        description="Total number of observations in this project (computed by graph-topology analysis).",
    )
    closed_at: datetime | None = Field(
        default=None,
        description="Timestamp when the session was closed. Null if open.",
    )
    created_at: datetime = Field(..., description="ISO-8601 creation timestamp.")
    updated_at: datetime = Field(..., description="Last activity timestamp (UTC).")


class SessionMessageBlob(BaseModel):
    """A blob attachment referenced in a message response."""

    id: str = Field(..., description="Blob UUID.")
    file_name: str = Field(..., description="Original filename.")
    mime_type: str = Field(..., description="MIME type.")
    file_size: int = Field(..., description="Size in bytes.")
    download_url: str | None = Field(
        default=None,
        description="Presigned download URL (short TTL). Null when storage config is unavailable.",
    )


class SessionMessagesResponse(BaseModel):
    """Response from ``GET /v1/projects/{project_id}/sessions/{session_id}/messages``."""

    class MessageItem(BaseModel):
        id: str = Field(..., description="Episode UUID.")
        role: str = Field(..., description="Message role.")
        content: str = Field(..., description="Message content.")
        metadata: dict[str, Any] = Field(default_factory=dict)
        token_count: int = Field(default=0)
        sequence_number: int = Field(default=0)
        created_at: datetime = Field(..., description="ISO-8601 timestamp.")
        blobs: list[SessionMessageBlob] = Field(
            default_factory=list,
            description="Blob attachments for this message (images, PDFs, etc.).",
        )

    data: list[MessageItem] = Field(..., description="List of messages.")
    next_cursor: str | None = Field(default=None)
    has_more: bool = Field(default=False)


class SessionListResponse(BaseModel):
    """Paginated response for ``GET /v1/projects/{project_id}/sessions``.

    BREAKING: ``AsyncSessionsClient.list`` returns this model — callers
    doing ``result["data"]`` must move to ``result.data``.
    """

    data: list[SessionResponse] = Field(..., description="Sessions for the current page.")
    next_cursor: str | None = Field(default=None)
    has_more: bool = Field(default=False)
