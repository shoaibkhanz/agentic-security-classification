"""
Module 01: Agent Foundations with pydantic-ai
==============================================

In Module 00, you built an agent loop from scratch:
  prompt -> LLM -> check for tool calls -> execute tools -> repeat

Now see how pydantic-ai wraps that exact pattern with:
  - Type safety: Agent[DepsType, OutputType]
  - Dependency injection: RunContext[DepsType] in every tool
  - Structured output: Pydantic models, not raw strings
  - Production features: retries, model settings, usage tracking

This is what you built by hand — here's the production version.

Sections:
  1. Agent as Typed Container
  2. System Prompts (static and dynamic)
  3. Dependencies and RunContext
  4. Tools with @agent.tool
  5. run_sync vs run (sync wrapper around async)
  6. Putting It All Together
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from shared.deps import SecuritiesDB
from shared.models import SecuritySummary


# =============================================================================
# Section 1: Agent as Typed Container
# =============================================================================
# An Agent[DepsType, OutputType] maps to the loop from Module 00:
#   - DepsType = the resources your tools need (DB connections, API keys)
#   - OutputType = what the agent returns (structured or str)
#
# Compare to Module 00:
#   - Your manual loop had global variables → Agent has typed deps
#   - Your manual loop returned raw strings → Agent returns Pydantic models
#   - Your manual loop had no type checking → Agent validates at runtime

# The simplest possible agent: no deps, returns a string
simple_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    system_prompt="You are a securities analyst assistant.",
)


# =============================================================================
# Section 2: System Prompts — Static and Dynamic
# =============================================================================
# Static: defined at agent creation, same every run
# Dynamic: computed at runtime from dependencies using @agent.instructions

# Static system prompt
static_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    system_prompt=(
        "You are a senior securities analyst specializing in private markets. "
        "When asked about a security, provide concise, factual analysis. "
        "Always note when information is limited or uncertain."
    ),
)


# Dynamic system prompt — built from dependencies at runtime
@dataclass
class AnalystSession:
    """Dependencies for the securities analyst agent."""

    db: SecuritiesDB
    analyst_name: str
    access_level: str  # "junior" | "senior" | "admin"


analyst_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=AnalystSession,
    output_type=str,
)


# @agent.instructions lets you build the system prompt dynamically
# from the current dependencies. This runs before every LLM call.
@analyst_agent.instructions
async def build_system_prompt(ctx: RunContext[AnalystSession]) -> str:
    """Build system prompt based on who's using the agent."""
    base = (
        f"You are a securities analyst assistant for {ctx.deps.analyst_name}. "
        "Provide analysis of private securities based on available data."
    )

    # Adjust behavior based on access level
    if ctx.deps.access_level == "junior":
        base += (
            " Always recommend senior review for classification decisions. "
            "Do not provide definitive classifications."
        )
    elif ctx.deps.access_level == "admin":
        base += (
            " You have access to all data including restricted filings. "
            "Provide full analysis with confidence scores."
        )

    return base


# =============================================================================
# Section 3: Dependencies and RunContext
# =============================================================================
# In Module 00, your tools accessed globals. In pydantic-ai:
#   - deps_type declares what your agent needs
#   - deps are passed at runtime: agent.run(prompt, deps=my_deps)
#   - Tools access deps via RunContext[DepsType]
#
# This makes agents testable: swap real deps for fakes in tests.

# A production-style agent with typed dependencies and structured output
security_lookup_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=SecuritiesDB,
    output_type=SecuritySummary,
    system_prompt=(
        "You help analysts look up information about private securities. "
        "Use the search tool to find securities, then return a structured summary. "
        "If the security is not found, return what you know with 'Unknown' for missing fields."
    ),
)


# =============================================================================
# Section 4: Tools with @agent.tool
# =============================================================================
# In Module 00, you registered tools manually and parsed args from JSON.
# pydantic-ai tools:
#   - Are defined with decorators (@agent.tool)
#   - Get RunContext[DepsType] as first arg (dependency injection)
#   - Have type hints that become the tool's JSON Schema automatically
#   - Have docstrings that become the tool's description for the LLM


@security_lookup_agent.tool
async def search_securities(ctx: RunContext[SecuritiesDB], query: str) -> str:
    """
    Search the securities database for matching records.

    Args:
        query: Search term — can be security name, issuer name, or keyword.
    """
    results = await ctx.deps.search(query)
    if not results:
        return f"No securities found matching '{query}'. Try a broader search term."

    # Format results for the LLM
    formatted = []
    for sec in results[:3]:  # Limit to top 3
        info = f"- {sec.name} (Issuer: {sec.issuer})"
        if sec.type_hint:
            info += f" | Type hint: {sec.type_hint}"
        if sec.offering_amount:
            info += f" | Amount: ${sec.offering_amount:,.0f}"
        if sec.exemption.value != "unknown":
            info += f" | Exemption: {sec.exemption.value}"
        info += f" | Limited info: {sec.limited_info}"
        formatted.append(info)

    return "Securities found:\n" + "\n".join(formatted)


@security_lookup_agent.tool
async def get_security_details(ctx: RunContext[SecuritiesDB], name: str) -> str:
    """
    Get detailed information about a specific security by exact name.

    Args:
        name: The exact name of the security to look up.
    """
    security = await ctx.deps.get_by_name(name)
    if security is None:
        return f"Security '{name}' not found. Use search_securities to find the correct name."

    details = [
        f"Name: {security.name}",
        f"Issuer: {security.issuer}",
        f"Type hint: {security.type_hint or 'Not specified'}",
        f"Offering amount: ${security.offering_amount:,.0f}"
        if security.offering_amount
        else "Offering amount: Unknown",
        f"Min investment: ${security.min_investment:,.0f}"
        if security.min_investment
        else "Min investment: Unknown",
        f"Exemption: {security.exemption.value}",
        f"Description: {security.raw_description}",
    ]

    if security.interest_rate:
        details.append(f"Interest rate: {security.interest_rate:.1%}")
    if security.maturity_date:
        details.append(f"Maturity: {security.maturity_date}")
    if security.conversion_terms:
        details.append(f"Conversion terms: {security.conversion_terms}")

    return "\n".join(details)


# =============================================================================
# Section 5: run_sync vs run
# =============================================================================
# agent.run() is async — the native interface (matches Module 00's async loop)
# agent.run_sync() is a convenience wrapper that calls asyncio.run() for you
#
# Use run_sync() for scripts and learning.
# Use run() in production async code (FastAPI, etc.)


def demo_run_sync() -> None:
    """Demonstrate the synchronous convenience wrapper."""
    print("--- run_sync: Synchronous convenience wrapper ---")
    print("(This calls asyncio.run() under the hood)\n")

    db = SecuritiesDB()

    # run_sync is the simplest way to call an agent
    result = security_lookup_agent.run_sync(
        "Look up the NovaTech SAFE Round and summarize it",
        deps=db,
    )

    print(f"Output type: {type(result.output).__name__}")
    print(f"Name: {result.output.name}")
    print(f"Issuer: {result.output.issuer}")
    print(f"Type: {result.output.security_type}")
    print(f"Details: {result.output.key_details}")
    print()

    # Usage tracking — know exactly what the agent cost
    usage = result.usage()
    print(f"Token usage: {usage}")
    print()


async def demo_run_async() -> None:
    """Demonstrate the native async interface."""
    print("--- run: Native async interface ---")
    print("(Use this in production async code)\n")

    db = SecuritiesDB()

    # run() is the native async interface — no wrapper needed
    result = await security_lookup_agent.run(
        "Find information about Atlas Senior Secured Notes",
        deps=db,
    )

    print(f"Output: {result.output}")
    print(f"Usage: {result.usage()}")
    print()


# =============================================================================
# Section 6: Putting It All Together
# =============================================================================


async def demo_dynamic_prompt() -> None:
    """Show how dynamic system prompts change agent behavior."""
    print("--- Dynamic system prompts based on deps ---\n")

    db = SecuritiesDB()

    # Junior analyst gets cautious responses
    junior_session = AnalystSession(
        db=db,
        analyst_name="Alex (Junior)",
        access_level="junior",
    )

    result = await analyst_agent.run(
        "What type of security is the Meridian Growth Fund?",
        deps=junior_session,
    )
    print(f"Junior analyst response:\n  {result.output[:200]}...\n")

    # Senior analyst gets full analysis
    senior_session = AnalystSession(
        db=db,
        analyst_name="Dr. Chen (Senior)",
        access_level="admin",
    )

    result = await analyst_agent.run(
        "What type of security is the Meridian Growth Fund?",
        deps=senior_session,
    )
    print(f"Senior analyst response:\n  {result.output[:200]}...\n")


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    print("=" * 70)
    print("MODULE 01: AGENT FOUNDATIONS WITH PYDANTIC-AI")
    print("The production version of Module 00's manual agent loop")
    print("=" * 70)
    print()

    # Demo 1: Basic agent with structured output and tools
    demo_run_sync()

    # Demo 2: Native async interface
    await demo_run_async()

    # Demo 3: Dynamic system prompts
    await demo_dynamic_prompt()

    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. Agent[DepsType, OutputType] = typed container for your loop")
    print("  2. @agent.instructions = dynamic system prompt from deps")
    print("  3. @agent.tool + RunContext = dependency-injected tools")
    print("  4. run_sync() for scripts, run() for production async code")
    print("  5. result.usage() tracks token costs automatically")
    print()
    print("COMPARE TO MODULE 00:")
    print("  Manual loop → Agent class (same loop, production features)")
    print("  Global tools → @agent.tool with RunContext (testable)")
    print("  Raw strings → Pydantic models (validated, typed)")
    print("  No cost tracking → result.usage() (know your costs)")
    print()
    print("Next: Module 02 — Structured output, unions, and validators")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
