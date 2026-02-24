"""
Module 06: Multi-Agent Orchestration
======================================

Multi-agent in pydantic-ai is not a special framework feature.
It's just one agent calling another through a tool. The key patterns:

  - Parent agent delegates to child agents via @agent.tool
  - usage=ctx.usage passes cost tracking to child agents
  - UsageLimits prevents runaway costs across the pipeline
  - Each agent can use a different model

This module also introduces your FIRST evaluation touchpoint.
Following Hamel Husain's philosophy: write evals for errors you
DISCOVER, not errors you IMAGINE.

Sections:
  1. Agent Delegation Pattern
  2. Usage Tracking Across Agents
  3. Cost Controls with UsageLimits
  4. Multi-Model Pipelines
  5. First Eval Touchpoint — Discover Errors, Then Write Evals
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, UsageLimits

from shared.deps import SecuritiesDB, SECFilingSearch
from shared.models import SecurityCategory


# =============================================================================
# Section 1: Agent Delegation Pattern
# =============================================================================
# The key insight: multi-agent orchestration is just tool calls.
# A "router" agent decides which specialist to consult, then calls
# that specialist agent inside a tool function.
#
# This is the same pattern from Module 00's manual loop, but now
# with typed agents calling typed agents.


class RoutingDecision(BaseModel):
    """The router's decision about which specialist to consult."""

    specialist: str = Field(
        description="Which specialist to route to: 'debt' or 'equity'"
    )
    reasoning: str = Field(description="Why this specialist was chosen")
    query_for_specialist: str = Field(description="Refined query for the specialist")


class SecurityAnalysis(BaseModel):
    """Analysis result from a specialist agent."""

    security_name: str
    category: SecurityCategory
    confidence: float = Field(ge=0.0, le=1.0)
    key_findings: list[str]
    risk_factors: list[str]
    recommendation: str


# --- Specialist Agents ---
# Each specialist focuses on one type of security.
# They use different system prompts to shape their expertise.

debt_specialist = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=SecurityAnalysis,
    system_prompt=(
        "You are a specialist in debt instruments: bonds, notes, promissory notes, "
        "secured and unsecured debt. Analyze the security described and provide "
        "a structured analysis focusing on credit risk, interest rate risk, "
        "maturity, and seniority in the capital structure."
    ),
)

equity_specialist = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=SecurityAnalysis,
    system_prompt=(
        "You are a specialist in equity instruments: common stock, preferred stock, "
        "partnership interests, fund interests, SAFEs, and convertible equity. "
        "Analyze the security described and provide a structured analysis "
        "focusing on ownership rights, dilution risk, liquidity, and valuation."
    ),
)


# --- Router Agent ---
# The router decides which specialist to consult.
# It has tools that delegate to the specialists.


@dataclass
class RouterDeps:
    """Dependencies for the router agent."""

    db: SecuritiesDB
    sec_search: SECFilingSearch


router_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=RouterDeps,
    output_type=SecurityAnalysis,
    system_prompt=(
        "You are a securities classification router. Given a query about a private "
        "security, first look it up in the database, then decide whether to route "
        "to the debt specialist or equity specialist for detailed analysis. "
        "Route to debt_specialist for: bonds, notes, loans, debt instruments. "
        "Route to equity_specialist for: stocks, fund interests, SAFEs, convertibles, partnerships."
    ),
)


# =============================================================================
# Section 2: Usage Tracking Across Agents
# =============================================================================
# The critical pattern: pass usage=ctx.usage to child agents.
# This lets you track total cost across the ENTIRE pipeline,
# not just individual agents.


@router_agent.tool
async def lookup_security(ctx: RunContext[RouterDeps], query: str) -> str:
    """
    Search the securities database for information.

    Args:
        query: Search term for the security.
    """
    results = await ctx.deps.db.search(query)
    if not results:
        return f"No securities found matching '{query}'."

    formatted = []
    for sec in results[:3]:
        info = f"- {sec.name} | Issuer: {sec.issuer}"
        if sec.type_hint:
            info += f" | Type hint: {sec.type_hint}"
        if sec.raw_description:
            info += f"\n  Description: {sec.raw_description[:200]}"
        formatted.append(info)

    return "\n".join(formatted)


@router_agent.tool
async def consult_debt_specialist(
    ctx: RunContext[RouterDeps],
    security_description: str,
) -> str:
    """
    Route to the debt specialist for analysis of debt-like instruments.

    Args:
        security_description: Description of the security to analyze.
    """
    # KEY PATTERN: usage=ctx.usage passes cost tracking to child agent
    result = await debt_specialist.run(
        security_description,
        usage=ctx.usage,
    )
    return result.output.model_dump_json()


@router_agent.tool
async def consult_equity_specialist(
    ctx: RunContext[RouterDeps],
    security_description: str,
) -> str:
    """
    Route to the equity specialist for analysis of equity-like instruments.

    Args:
        security_description: Description of the security to analyze.
    """
    # usage=ctx.usage tracks child agent costs in the parent's usage
    result = await equity_specialist.run(
        security_description,
        usage=ctx.usage,
    )
    return result.output.model_dump_json()


# =============================================================================
# Section 3: Cost Controls with UsageLimits
# =============================================================================
# In production, you need guardrails against runaway agents.
# UsageLimits caps total requests and tokens across all agents.


async def demo_with_cost_controls() -> None:
    """Demonstrate cost controls across the multi-agent pipeline."""
    print("--- Multi-Agent with Cost Controls ---\n")

    deps = RouterDeps(
        db=SecuritiesDB(),
        sec_search=SECFilingSearch(),
    )

    # UsageLimits applies to the ENTIRE pipeline (router + specialists)
    result = await router_agent.run(
        "Analyze the Atlas Senior Secured Notes 2024 — what type of security is it?",
        deps=deps,
        usage_limits=UsageLimits(
            request_limit=10,  # Max 10 LLM API calls across all agents
        ),
    )

    print(f"Security: {result.output.security_name}")
    print(f"Category: {result.output.category.value}")
    print(f"Confidence: {result.output.confidence:.0%}")
    print(f"Key findings: {result.output.key_findings}")
    print(f"Risk factors: {result.output.risk_factors}")
    print()

    # Combined usage shows cost across ALL agents
    usage = result.usage()
    print("Combined usage across all agents:")
    print(f"  Total requests: {usage.requests}")
    print(f"  Total tokens: {usage.total_tokens}")
    print()


# =============================================================================
# Section 4: Multi-Model Pipelines
# =============================================================================
# Different agents can use different models.
# Router might use a fast/cheap model for triage.
# Specialists use a more capable model for analysis.
#
# Example (not run — just demonstrating the pattern):
#
#   router = Agent("openai:gpt-4o-mini", ...)   # Fast, cheap routing
#   specialist = Agent("anthropic:sonnet-4-5-20250929", ...)  # Deep analysis
#
# You can also override the model at runtime:
#   result = await agent.run(prompt, model="openai:gpt-4o")


# =============================================================================
# Section 5: First Eval Touchpoint
# =============================================================================
# Following Hamel Husain's philosophy:
#   "Start with error analysis, not imagined failures."
#
# After running the router, you'll notice it sometimes misroutes.
# For example, a convertible note has both debt AND equity characteristics.
# The router might send it to the wrong specialist.
#
# These discovered errors become your first eval cases.


@dataclass
class RoutingTestCase:
    """A test case for evaluating routing accuracy."""

    name: str
    query: str
    expected_specialist: str  # "debt" or "equity"
    difficulty: str  # "easy" | "medium" | "hard"


# These are errors we DISCOVERED by running the agent, not imagined ones
ROUTING_TEST_CASES = [
    # Easy: clear debt
    RoutingTestCase(
        name="clear_debt_instrument",
        query="Analyze Atlas Senior Secured Notes 2024 — 3-year secured notes at 8.5%",
        expected_specialist="debt",
        difficulty="easy",
    ),
    # Easy: clear equity
    RoutingTestCase(
        name="clear_equity_instrument",
        query="Analyze Quantum Series B Preferred stock — preferred equity at $200M pre-money",
        expected_specialist="equity",
        difficulty="easy",
    ),
    # Easy: clear fund interest
    RoutingTestCase(
        name="fund_interest",
        query="Analyze Meridian Growth Fund LP — limited partnership interests in PE fund",
        expected_specialist="equity",
        difficulty="easy",
    ),
    # Medium: SAFE (often misrouted to debt because of "future equity" language)
    RoutingTestCase(
        name="safe_instrument",
        query="Analyze NovaTech SAFE Round — simple agreement for future equity with discount and cap",
        expected_specialist="equity",
        difficulty="medium",
    ),
    # Hard: Convertible note (has both debt AND equity features)
    RoutingTestCase(
        name="convertible_note",
        query="Analyze Catalyst Convertible Note — 6% interest, converts at Series A with 25% discount",
        expected_specialist="debt",  # It's a note (debt) that converts to equity
        difficulty="hard",
    ),
]


async def run_routing_eval() -> None:
    """
    Run a simple evaluation of routing accuracy.

    This is your FIRST taste of evals. In Module 09, you'll formalize
    this with pydantic-evals' Case, Dataset, and Evaluator classes.
    """
    print("--- First Eval: Routing Accuracy (discovered errors) ---\n")

    deps = RouterDeps(
        db=SecuritiesDB(),
        sec_search=SECFilingSearch(),
    )

    correct = 0
    total = len(ROUTING_TEST_CASES)

    for case in ROUTING_TEST_CASES:
        result = await router_agent.run(
            case.query,
            deps=deps,
            usage_limits=UsageLimits(request_limit=5),
        )

        # Check which specialist was consulted by examining the messages
        messages = result.all_messages()
        called_debt = any("consult_debt_specialist" in str(msg) for msg in messages)
        called_equity = any("consult_equity_specialist" in str(msg) for msg in messages)

        if case.expected_specialist == "debt":
            is_correct = called_debt
        else:
            is_correct = called_equity

        status = "PASS" if is_correct else "FAIL"
        correct += int(is_correct)

        print(f"  [{status}] {case.name} ({case.difficulty})")
        print(f"    Expected: {case.expected_specialist}")
        print(f"    Called debt: {called_debt}, Called equity: {called_equity}")
        print(f"    Category: {result.output.category.value}")
        print()

    accuracy = correct / total
    print(f"  Routing accuracy: {correct}/{total} = {accuracy:.0%}")
    print()

    if accuracy < 1.0:
        print("  INSIGHT: Some cases were misrouted. This is expected!")
        print("  Convertible instruments are genuinely ambiguous.")
        print("  In Module 09, we'll formalize these into a pydantic-evals Dataset.")
    print()


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    print("=" * 70)
    print("MODULE 06: MULTI-AGENT ORCHESTRATION")
    print("Agents calling agents through tools")
    print("=" * 70)
    print()

    # Demo 1: Multi-agent pipeline with cost controls
    await demo_with_cost_controls()

    # Demo 2: First evaluation touchpoint
    await run_routing_eval()

    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. Multi-agent = one agent calling another via @agent.tool")
    print("  2. usage=ctx.usage tracks costs across the entire pipeline")
    print("  3. UsageLimits prevents runaway costs (production essential)")
    print("  4. Different agents can use different models")
    print("  5. Evals start from DISCOVERED errors, not imagined ones")
    print()
    print("EVAL PHILOSOPHY (Hamel Husain):")
    print("  We ran the router, found it misroutes convertibles.")
    print("  THAT discovery becomes the eval case.")
    print("  Don't predict failures — find them, then codify them.")
    print()
    print("Next: Module 06b — Planning and reasoning patterns")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
