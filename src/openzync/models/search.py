"""Pydantic models for the global search domain."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GlobalSearchItem(BaseModel):
    """A single result from a global search."""

    type: str = Field(..., description="Result type: project, user, or session.")
    id: str = Field(..., description="Resource UUID.")
    label: str = Field(..., description="Primary display text.")
    subtitle: str | None = Field(default=None, description="Secondary display text.")
    href: str = Field(..., description="Frontend URL for navigation.")


class GlobalSearchResponse(BaseModel):
    """Response from ``GET /v1/search``."""

    results: list[GlobalSearchItem] = Field(..., description="Matching resources.")
    query: str = Field(..., description="The original query string.")
