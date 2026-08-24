"""Pydantic models for the dialog-classification query domain."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ClassificationResponse(BaseModel):
    """Classification result for a single episode."""

    id: str = Field(..., description="Classification UUID.")
    episode_id: str = Field(..., description="Classified episode UUID.")
    intent: str | None = Field(default=None, description="Detected intent.")
    emotion: str | None = Field(default=None, description="Detected emotion.")
    valence: str | None = Field(default=None, description="Emotional valence.")
    arousal: str | None = Field(default=None, description="Emotional arousal level.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classifier confidence.")
    created_at: str = Field(..., description="Creation timestamp (UTC).")
    message: str = Field(default="", description="Full episode content text.")
    role: str = Field(
        default="", description="Episode role (user/assistant/system/tool)."
    )


class ClassificationListResponse(BaseModel):
    """Response from ``GET .../sessions/{sid}/classifications``."""

    data: list[ClassificationResponse] = Field(
        ..., description="Classifications in the session."
    )
    total: int = Field(..., ge=0, description="Total number of classifications.")
