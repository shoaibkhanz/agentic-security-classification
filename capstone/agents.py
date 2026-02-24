"""
Capstone agents for the classification pipeline.

Five specialized agents, each with a clear role:

  question_planner  — Decides the highest-value next action
  researcher        — Executes research actions using tools
  confidence_assessor — Re-estimates confidence after new evidence
  classifier        — Produces final ClassificationResult
  verifier          — Checks reasoning consistency
"""

from __future__ import annotations

from pydantic_ai import Agent

from capstone.models import (
    InitialAssessmentResult,
    ResearchFinding,
    VerificationResult,
)
from capstone.tools import (
    ask_user_question,
    query_securities_sql,
    search_sec_filings,
    search_securities_db,
    search_web,
)
from shared.deps import AnalystContext
from shared.models import (
    ClassificationResult,
    ConfidenceEstimate,
    NextAction,
)


# =============================================================================
# Agent 1: Question Planner
# =============================================================================
# Given what's known so far + current confidence, decides the single
# highest-value next action. Optimizes for max confidence gain per action.

question_planner = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=NextAction,
    system_prompt=(
        "You are a securities analysis planner. Your job is to decide the single "
        "best next action to increase classification confidence.\n\n"
        "Available actions:\n"
        "- query_db: Search the securities database\n"
        "- search_sec: Search SEC EDGAR filings\n"
        "- search_web: Search the web for public info\n"
        "- ask_question: Ask the analyst a question\n"
        "- classify: Produce final classification (only when confidence is high enough)\n\n"
        "Prioritize actions by expected information gain. Ask yourself: "
        "'What single piece of information would most reduce my uncertainty?'\n\n"
        "Consider what's already known and avoid redundant actions. "
        "If the security description already contains clear indicators "
        "(e.g., 'SAFE', 'notes', 'fund'), you may not need many actions."
    ),
)


# =============================================================================
# Agent 2: Initial Assessor
# =============================================================================
# Produces the first assessment from the raw description alone.

initial_assessor = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=InitialAssessmentResult,
    system_prompt=(
        "You perform an initial assessment of a private security from its description. "
        "Identify what can be inferred immediately, estimate initial confidence, "
        "and suggest the most valuable first research action.\n\n"
        "Categories: equity, debt, convertible_note, safe, fund_interest, "
        "real_estate, revenue_share, other.\n\n"
        "Be conservative with initial confidence. Most securities need at least "
        "one research action to classify with high confidence."
    ),
)


# =============================================================================
# Agent 3: Researcher
# =============================================================================
# Executes research actions using tools. Has access to all data sources.

researcher = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=AnalystContext,
    output_type=ResearchFinding,
    system_prompt=(
        "You are a securities researcher. Execute the requested research action "
        "using your tools and report what you found. Be specific about the evidence "
        "and how it relates to classifying this security.\n\n"
        "Always cite the source of your findings (database, SEC filing, web search, "
        "or user answer)."
    ),
)

# Register tools on the researcher agent
researcher.tool(search_securities_db)
researcher.tool(query_securities_sql)
researcher.tool(search_sec_filings)
researcher.tool(search_web)
researcher.tool(ask_user_question)


# =============================================================================
# Agent 4: Confidence Assessor
# =============================================================================
# After each new piece of evidence, re-estimates confidence.

confidence_assessor = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=ConfidenceEstimate,
    system_prompt=(
        "You assess classification confidence for private securities. "
        "Given the evidence gathered so far, estimate:\n"
        "1. Confidence score (0.0 to 1.0) for the top category\n"
        "2. The most likely category\n"
        "3. The runner-up category (if any)\n"
        "4. What is still unknown that would increase confidence\n\n"
        "Categories: equity, debt, convertible_note, safe, fund_interest, "
        "real_estate, revenue_share, other.\n\n"
        "Be honest about uncertainty. If evidence is contradictory, "
        "confidence should be lower. If evidence clearly points to one "
        "category, confidence can be high."
    ),
)


# =============================================================================
# Agent 5: Classifier
# =============================================================================
# When confidence >= threshold, produces the final ClassificationResult
# with full reasoning chain.

classifier = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=ClassificationResult,
    system_prompt=(
        "You produce the final classification of a private security. "
        "Your output must include:\n"
        "1. The primary category\n"
        "2. A confidence score\n"
        "3. A reasoning chain where each step cites specific evidence\n"
        "4. All evidence sources used\n"
        "5. Alternative classifications considered\n"
        "6. A human-readable summary\n\n"
        "Categories: equity, debt, convertible_note, safe, fund_interest, "
        "real_estate, revenue_share, other.\n\n"
        "Every reasoning step must reference a specific piece of evidence "
        "from the tools. Do not hallucinate evidence. If you're uncertain, "
        "say so in the summary."
    ),
)


# =============================================================================
# Agent 6: Verifier
# =============================================================================
# Reviews the classification for logical consistency. Can lower confidence
# and send back for more research.

verifier = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=VerificationResult,
    system_prompt=(
        "You verify securities classifications for logical consistency. "
        "Review the reasoning chain and check:\n"
        "1. Does each reasoning step logically follow from the evidence?\n"
        "2. Is the confidence score justified by the evidence?\n"
        "3. Were important contradictory signals addressed?\n"
        "4. Are there alternative classifications that weren't considered?\n\n"
        "If you find issues, lower the confidence and recommend 'gather_more'. "
        "If the reasoning is sound, recommend 'accept'. "
        "If the classification seems wrong, recommend 'reclassify'."
    ),
)
