"""Pydantic models for the observation (graph-topology analysis) domain."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ObservationResponse(BaseModel):
    """A single observation surfaced from graph-topology analysis."""

    id: str = Field(..., description="UUID primary key.")
    subject_entity_id: str = Field(
        ..., description="The entity this observation is about."
    )
    related_entity_id: str | None = Field(
        default=None,
        description="Other entity in a pair-level observation; None for entity-level.",
    )
    observation_type: str = Field(
        ...,
        description="Observation type (co_occurrence, temporal_pattern, behavioral_pattern).",
    )
    content: str = Field(
        ..., description="Natural-language description of the observation."
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score (0.0–1.0)."
    )
    valid_from: str | None = Field(
        default=None, description="Start of temporal validity (UTC)."
    )
    valid_to: str | None = Field(
        default=None, description="End of temporal validity (UTC)."
    )
    created_at: str = Field(..., description="Row creation timestamp (UTC).")
    subject_entity_name: str | None = Field(
        default=None, description="Resolved subject entity name."
    )
    related_entity_name: str | None = Field(
        default=None, description="Resolved related entity name."
    )


class ObservationListResponse(BaseModel):
    """Response from ``GET /v1/projects/{project_id}/observations``."""

    data: list[ObservationResponse] = Field(
        ..., description="Observations for the current page."
    )
    total: int = Field(..., ge=0, description="Total number of matching observations.")
