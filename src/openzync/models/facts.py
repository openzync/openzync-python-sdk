"""Pydantic models for the facts (business data ingestion) domain."""

from __future__ import annotations

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


class FactBatchRequest(BaseModel):
    """Request body for ``POST /v1/users/{user_id}/facts``."""

    session_id: str = Field(
        ...,
        description="Session external ID — required, all ingestion targets an existing session.",
    )
    facts: list[FactTriple] = Field(..., min_length=1, max_length=500)


class FactBatchResponse(BaseModel):
    """Response returned after successful fact batch ingestion."""

    job_id: str = Field(..., description="UUID of the async enrichment job.")
    accepted_count: int = Field(..., ge=0, description="Number of facts accepted.")
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
    valid_from: str | None = Field(
        default=None, description="Temporal validity start (UTC)."
    )
    valid_to: str | None = Field(
        default=None,
        description="Temporal validity end (UTC) — set when superseded; None while current.",
    )
    invalid_at: str | None = Field(
        default=None,
        description="Hard-retraction timestamp (UTC); None unless explicitly invalidated.",
    )
    created_at: str = Field(..., description="Fact creation timestamp (UTC).")


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
