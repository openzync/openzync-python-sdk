"""Pydantic models for the facts (business data ingestion) domain."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FactTriple(BaseModel):
    """A single fact triple for batch ingestion."""

    subject: str = Field(
        ..., min_length=1, max_length=500, description="Subject entity name."
    )
    predicate: str = Field(
        ..., min_length=1, max_length=200, description="Relationship verb."
    )
    object: str = Field(
        ..., min_length=1, max_length=500, description="Object entity name."
    )
    content: str | None = Field(
        default=None, description="Human-readable fact statement."
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score."
    )


class FactBatchResponse(BaseModel):
    """Response returned after successful fact batch ingestion."""

    job_id: str = Field(..., description="UUID of the async enrichment job.")
    accepted_count: int = Field(..., ge=0, description="Number of facts accepted.")
    superseded_count: int = Field(
        default=0,
        ge=0,
        description="Number of previously-active facts invalidated by "
        "supersession in this batch.",
    )
    status: str = Field(default="accepted")
    message: str = Field(default="Facts accepted for processing.")


class FactResponse(BaseModel):
    """A single extracted fact, returned from list/retract/history endpoints."""

    id: str = Field(..., description="Internal fact UUID.")
    content: str = Field(..., description="Human-readable fact statement.")
    subject: str | None = Field(default=None, description="Subject entity name.")
    predicate: str | None = Field(default=None, description="Relationship verb.")
    object: str | None = Field(default=None, description="Object entity name.")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence."
    )
    source_episode_id: str | None = Field(
        default=None, description="Source episode UUID."
    )
    subject_type: str = Field(
        default="literal",
        description="Entity type of the subject ('literal' or 'entity').",
    )
    object_type: str = Field(
        default="literal",
        description="Entity type of the object ('literal' or 'entity').",
    )
    subject_entity_id: str | None = Field(
        default=None,
        description="FK to graph_entities if the subject was resolved to an entity.",
    )
    object_entity_id: str | None = Field(
        default=None,
        description="FK to graph_entities if the object was resolved to an entity.",
    )
    valid_from: datetime | None = Field(
        default=None, description="Temporal validity start (UTC)."
    )
    valid_to: datetime | None = Field(
        default=None,
        description="Temporal validity end (UTC) — set when superseded; None while current.",
    )
    invalid_at: datetime | None = Field(
        default=None,
        description="Hard-retraction timestamp (UTC); None unless explicitly invalidated.",
    )
    created_at: datetime = Field(..., description="Fact creation timestamp (UTC).")


class PaginatedFactsResponse(BaseModel):
    """Paginated response for fact list endpoints."""

    data: list[FactResponse] = Field(..., description="Facts for the current page.")
    next_cursor: str | None = Field(
        default=None, description="Cursor for the next page."
    )
    has_more: bool = Field(default=False)


class FactHistoryEvent(BaseModel):
    """One invalidation-lineage event for a fact."""

    id: str = Field(..., description="Event UUID.")
    old_fact_id: str | None = Field(
        default=None, description="The fact that stopped being current."
    )
    new_fact_id: str | None = Field(
        default=None, description="The replacing fact, if any."
    )
    kind: str = Field(
        ..., description="Invalidation kind (superseded, retracted, ...)."
    )
    reason: str | None = Field(
        default=None, description="Optional explanation of the invalidation."
    )
    at_time: str = Field(..., description="Instant the invalidation took effect (UTC).")
    source_episode_id: str | None = Field(
        default=None, description="Episode that drove the invalidation."
    )


class FactHistoryResponse(BaseModel):
    """A fact plus its invalidation-lineage events (newest first)."""

    fact: FactResponse = Field(..., description="The fact whose lineage this is.")
    events: list[FactHistoryEvent] = Field(
        ..., description="Invalidation events, newest first."
    )
