"""Pydantic models for the structured-extraction query domain."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StructuredExtractionResponse(BaseModel):
    """A single structured extraction result."""

    id: str = Field(..., description="Extraction UUID.")
    session_id: str = Field(..., description="Owning session UUID.")
    episode_id: str = Field(..., description="Source episode UUID.")
    schema_id: str | None = Field(default=None, description="Extraction schema UUID.")
    data: dict[str, Any] = Field(..., description="Extracted data payload.")
    created_at: str = Field(..., description="Creation timestamp (UTC).")


class StructuredExtractionListResponse(BaseModel):
    """Response from ``GET .../sessions/{sid}/structured-extractions``."""

    items: list[StructuredExtractionResponse] = Field(
        ..., description="Extractions in the session."
    )
    total: int = Field(..., ge=0, description="Total number of extractions.")
