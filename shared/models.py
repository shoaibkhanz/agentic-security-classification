"""
Shared domain models for private securities classification.

These Pydantic models are used across all tutorial modules.
They represent the core domain: securities, classifications,
SEC filings, and the reasoning/evidence structures that
the capstone agent produces.

Production note: Every data structure is a typed Pydantic model,
never a raw dict. This gives us validation, serialization, and
documentation for free.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# =============================================================================
# Security Categories
# =============================================================================


class SecurityCategory(str, Enum):
    """Classification categories for private securities."""

    EQUITY = "equity"
    DEBT = "debt"
    CONVERTIBLE_NOTE = "convertible_note"
    SAFE = "safe"  # Simple Agreement for Future Equity
    FUND_INTEREST = "fund_interest"
    REAL_ESTATE = "real_estate"
    REVENUE_SHARE = "revenue_share"
    OTHER = "other"


class ExemptionType(str, Enum):
    """SEC registration exemption types for private securities."""

    REG_D_506B = "reg_d_506b"
    REG_D_506C = "reg_d_506c"
    REG_A = "reg_a"
    REG_A_PLUS = "reg_a_plus"
    REG_CF = "reg_cf"
    REG_S = "reg_s"
    SECTION_4A2 = "section_4a2"
    UNKNOWN = "unknown"


# =============================================================================
# Core Domain Models
# =============================================================================


class SecurityInfo(BaseModel):
    """Information about a private security, possibly incomplete."""

    name: str = Field(description="Name of the security or offering")
    issuer: str = Field(description="Name of the issuing entity")
    type_hint: str | None = Field(
        default=None,
        description="Any hint about the security type from available docs",
    )
    offering_amount: float | None = Field(
        default=None,
        description="Total offering amount in USD",
    )
    min_investment: float | None = Field(
        default=None,
        description="Minimum investment amount in USD",
    )
    offering_date: date | None = Field(
        default=None,
        description="Date the offering was initiated",
    )
    maturity_date: date | None = Field(
        default=None,
        description="Maturity date for debt-like instruments",
    )
    interest_rate: float | None = Field(
        default=None,
        description="Interest rate for debt instruments (as decimal, e.g., 0.08)",
    )
    conversion_terms: str | None = Field(
        default=None,
        description="Conversion terms for convertible instruments",
    )
    exemption: ExemptionType = Field(
        default=ExemptionType.UNKNOWN,
        description="SEC registration exemption type",
    )
    limited_info: bool = Field(
        default=True,
        description="Whether information about this security is limited",
    )
    raw_description: str = Field(
        default="",
        description="Raw text description from offering documents",
    )


class SECAdvisory(BaseModel):
    """An SEC filing or advisory related to a security."""

    filing_type: str = Field(description="Type of SEC filing (e.g., Form D, 8-K)")
    filing_date: date = Field(description="Date the filing was made")
    issuer: str = Field(description="Name of the filing issuer")
    exemption_type: ExemptionType = Field(description="Claimed exemption")
    amount_raised: float | None = Field(
        default=None,
        description="Amount raised per the filing",
    )
    details: str = Field(description="Summary of filing details")


class SearchResult(BaseModel):
    """A web search result."""

    title: str
    snippet: str
    url: str
    relevance_score: float = Field(ge=0.0, le=1.0)


# =============================================================================
# Classification and Reasoning Models (used in later modules + capstone)
# =============================================================================


class EvidenceSource(BaseModel):
    """A piece of evidence and where it came from."""

    source_type: Literal["database", "sec_filing", "web_search", "user_answer"]
    source_detail: str = Field(
        description="Specific source (e.g., tool name, filing ID)"
    )
    content: str = Field(description="The evidence content")


class ReasoningStep(BaseModel):
    """A single step in the classification reasoning chain."""

    step: int = Field(description="Step number in the reasoning chain")
    evidence: str = Field(description="What was found")
    source: str = Field(description="Which tool or question provided it")
    inference: str = Field(description="What this evidence implies for classification")
    confidence_delta: float = Field(
        description="How much this step changed confidence (positive = more confident)",
    )


class AlternativeClassification(BaseModel):
    """A runner-up classification with its confidence."""

    category: SecurityCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class ClassificationResult(BaseModel):
    """The final output of the securities classification agent."""

    category: SecurityCategory = Field(description="Primary classification")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for the classification",
    )
    reasoning: list[ReasoningStep] = Field(
        description="Ordered chain: evidence -> inference -> conclusion",
    )
    evidence_sources: list[EvidenceSource] = Field(
        description="All evidence used in the classification",
    )
    questions_asked: int = Field(
        description="Number of questions/actions taken (efficiency metric)",
    )
    alternative_classifications: list[AlternativeClassification] = Field(
        default_factory=list,
        description="Runner-up classifications with their confidence",
    )
    summary: str = Field(
        description="Human-readable summary of why this classification was chosen",
    )


# =============================================================================
# Planning Models (used in Module 06b and capstone)
# =============================================================================


class ConfidenceEstimate(BaseModel):
    """Running confidence estimate during classification."""

    score: float = Field(ge=0.0, le=1.0)
    top_category: SecurityCategory
    runner_up: SecurityCategory | None = None
    uncertainty_reasons: list[str] = Field(
        description="What is still unknown that would increase confidence",
    )


class NextAction(BaseModel):
    """The planner's decision about what to do next."""

    action_type: Literal[
        "ask_question",
        "search_web",
        "query_db",
        "search_sec",
        "classify",
    ]
    detail: str = Field(description="The question, query, or search term")
    expected_info_gain: str = Field(
        description="Why this action would increase classification confidence",
    )
    estimated_confidence_after: float = Field(
        ge=0.0,
        le=1.0,
        description="Predicted confidence if this action succeeds",
    )


class PlanStep(BaseModel):
    """A step in an execution plan."""

    action: str = Field(description="What to do")
    rationale: str = Field(description="Why this step is needed")
    dependencies: list[int] = Field(
        default_factory=list,
        description="Indices of steps that must complete first",
    )
    completed: bool = False


# =============================================================================
# Simplified Output Models (used in early modules)
# =============================================================================


class SecuritySummary(BaseModel):
    """Simple summary returned by the basic lookup agent (Module 01)."""

    name: str
    issuer: str
    security_type: str
    key_details: str


class ParsedOffering(BaseModel):
    """Structured extraction from an offering memorandum (Module 02)."""

    issuer: str = Field(min_length=1)
    security_type: str = Field(min_length=1)
    min_investment: float | None = None
    exemption: ExemptionType
    key_terms: str = Field(default="", description="Summary of key terms")


class InsufficientInfo(BaseModel):
    """Returned when the offering document lacks enough information (Module 02)."""

    missing_fields: list[str] = Field(
        description="Fields that could not be extracted",
    )
    questions_to_ask: list[str] = Field(
        description="Questions that would help complete the extraction",
    )
    partial_extraction: dict[str, str] = Field(
        default_factory=dict,
        description="Whatever could be partially extracted",
    )
