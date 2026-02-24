"""
Request/response models for the classification API.

These mirror the capstone's domain models for the HTTP boundary,
adding API-specific fields (IDs, timestamps, corrections).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ClassifyRequest(BaseModel):
    """Request body for POST /api/classify."""

    description: str = Field(
        min_length=10, description="Security description to classify"
    )
    additional_context: str | None = Field(
        default=None,
        description="Additional context from user feedback (for reruns)",
    )
    confidence_threshold: float = Field(
        default=0.82,
        ge=0.5,
        le=1.0,
        description="Confidence threshold to stop gathering info",
    )
    demo: bool = Field(
        default=False,
        description="Use simulated classification (no LLM API key needed)",
    )


class StreamEvent(BaseModel):
    """A single SSE event sent during classification streaming."""

    event_type: Literal[
        "node_start",
        "node_complete",
        "confidence_update",
        "evidence_found",
        "result",
        "error",
    ]
    node_name: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(description="Elapsed seconds since classification start")


class FeedbackRequest(BaseModel):
    """Request body for POST /api/feedback/{record_id}."""

    feedback: str = Field(
        min_length=1, description="User's correction or additional context"
    )
    correct_category: str | None = Field(
        default=None,
        description="What the user thinks the correct category is",
    )
    rerun: bool = Field(
        default=False,
        description="Whether to rerun classification with this context",
    )


class CorrectionRecord(BaseModel):
    """A single correction/feedback entry."""

    feedback: str
    correct_category: str | None = None
    new_result_id: str | None = Field(
        default=None,
        description="ID of the rerun classification, if one was triggered",
    )
    created_at: datetime


class ClassificationRecord(BaseModel):
    """A persisted classification result with its corrections."""

    id: str
    description: str
    additional_context: str | None = None
    result: dict[str, Any] = Field(description="Serialized ClassificationResult")
    corrections: list[CorrectionRecord] = Field(default_factory=list)
    operator_reviews: list[OperatorReview] = Field(default_factory=list)
    created_at: datetime


class OperatorReviewRequest(BaseModel):
    """Request body for POST /api/operator-review/{record_id}."""

    action: Literal["approve", "reject", "override"]
    override_category: str | None = None
    comment: str | None = None


class OperatorReview(BaseModel):
    """A single operator review entry."""

    action: str
    override_category: str | None = None
    comment: str | None = None
    reviewed_at: datetime


class ExampleSecurity(BaseModel):
    """An example security for the frontend example cards."""

    name: str
    issuer: str
    description: str
    difficulty: str
    type_hint: str | None = None
    category_code: str | None = None
    category_label: str | None = None
