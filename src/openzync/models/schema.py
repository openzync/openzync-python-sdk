"""Pydantic models for the admin schemas domain."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SchemaResponse(BaseModel):
    """Response from ``POST /v1/admin/schemas``."""

    id: str = Field(..., description="Schema UUID.")
    name: str = Field(..., description="Schema display name.")
    json_schema: dict[str, Any] = Field(..., description="JSON Schema definition.")
    prompt_template: str | None = Field(
        default=None, description="Optional extraction prompt template."
    )
    created_at: str | None = Field(
        default=None, description="ISO-8601 creation timestamp."
    )


class SchemaPreviewResponse(BaseModel):
    """Response from ``POST /v1/admin/schemas/preview``."""

    data: dict[str, Any] = Field(
        default_factory=dict, description="Extracted data preview."
    )
    validation_errors: list[str] = Field(
        default_factory=list, description="Extraction validation errors."
    )
