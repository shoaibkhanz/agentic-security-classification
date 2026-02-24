"""
Capstone domain models.

These extend shared.models with capstone-specific types for the
confidence-driven classification workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from pydantic_ai.messages import ModelMessage

from shared.models import (
    ClassificationResult,
    ConfidenceEstimate,
    EvidenceSource,
    NextAction,
    SecurityCategory,
)


# =============================================================================
# Agent Output Models
# =============================================================================


class InitialAssessmentResult(BaseModel):
    """Output of the initial assessment agent."""

    security_name: str = Field(description="Name of the security being classified")
    initial_observations: list[str] = Field(
        description="What can be inferred from the description alone",
    )
    initial_confidence: ConfidenceEstimate
    suggested_first_action: NextAction


class ResearchFinding(BaseModel):
    """Output of a single research action."""

    action_taken: str = Field(description="What action was executed")
    finding: str = Field(description="What was found")
    evidence: EvidenceSource
    relevance: str = Field(description="How this relates to classification")


class VerificationResult(BaseModel):
    """Output of the verification agent."""

    reasoning_is_consistent: bool
    issues_found: list[str] = Field(default_factory=list)
    adjusted_confidence: float = Field(ge=0.0, le=1.0)
    recommendation: str = Field(
        description="'accept', 'gather_more', or 'reclassify'",
    )


# =============================================================================
# Graph State
# =============================================================================


@dataclass
class ClassificationState:
    """
    Graph state that persists across all nodes.

    This is the working memory of the classification pipeline.
    It accumulates evidence, tracks confidence over time, and
    preserves agent message histories for conversation continuity.
    """

    # Input
    security_description: str = ""

    # Accumulated evidence
    gathered_evidence: list[EvidenceSource] = field(default_factory=list)
    research_findings: list[ResearchFinding] = field(default_factory=list)

    # Confidence tracking
    confidence_history: list[ConfidenceEstimate] = field(default_factory=list)
    current_confidence: float = 0.0
    current_top_category: SecurityCategory | None = None

    # Actions taken
    actions_taken: list[NextAction] = field(default_factory=list)
    questions_asked: int = 0

    # Final result (set by Classify node)
    final_result: ClassificationResult | None = None

    # Agent message histories (preserved across graph transitions)
    planner_messages: list[ModelMessage] = field(default_factory=list)
    researcher_messages: list[ModelMessage] = field(default_factory=list)
    assessor_messages: list[ModelMessage] = field(default_factory=list)
    classifier_messages: list[ModelMessage] = field(default_factory=list)
    verifier_messages: list[ModelMessage] = field(default_factory=list)

    # Configuration
    confidence_threshold: float = 0.82
    max_actions: int = 8


# =============================================================================
# Eval Case Model
# =============================================================================


class EvalCase(BaseModel):
    """A test case for evaluating the classification pipeline."""

    name: str
    security_description: str
    expected_category: SecurityCategory
    difficulty: str = Field(description="easy, medium, hard, edge, adversarial")
    expected_max_questions: int = 5
    notes: str = ""
