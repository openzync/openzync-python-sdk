"""Pydantic models for the admin schemas domain."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SchemaResponse(BaseModel):
    """Response from ``POST /v1/admin/schemas``."""

    id: str = Field(..., description="Schema UUID.")
    organization_id: str = Field(..., description="Owning organization UUID.")
    name: str = Field(..., description="Schema display name.")
    type: str = Field(..., description="Schema type: 'structured' or 'classification'.")
    json_schema: dict[str, Any] = Field(..., description="JSON Schema definition.")
    prompt_template: str | None = Field(
        default=None, description="Optional extraction prompt template."
    )
    is_active: bool = Field(..., description="Whether the schema is active.")
    created_at: datetime | None = Field(
        default=None, description="ISO-8601 creation timestamp."
    )
    updated_at: datetime = Field(..., description="ISO-8601 update timestamp.")


class SchemaPreviewResponse(BaseModel):
    """Response from ``POST /v1/admin/schemas/preview``."""

    data: dict[str, Any] = Field(
        default_factory=dict, description="Extracted data preview."
    )
    validation_errors: list[str] = Field(
        default_factory=list, description="Extraction validation errors."
    )


class SchemaTemplateResponse(BaseModel):
    """Response from ``GET /v1/admin/schemas/templates``."""

    key: str = Field(..., description="Template identifier.")
    name: str = Field(..., description="Template display name.")
    description: str = Field(..., description="Template description.")
    json_schema: dict[str, Any] = Field(..., description="JSON Schema definition.")
    sample_text: str = Field(..., description="Sample text for extraction preview.")
