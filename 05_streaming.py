"""
Module 05: Streaming for Real-Time Output
==========================================

Waiting 10 seconds for a complete response is painful. Streaming lets
the user see output as it's generated, token by token. This is essential
for production agents — it makes response times feel faster and lets
users interrupt or redirect early.

pydantic-ai supports three streaming modes:
  1. Text streaming  — stream_text() yields growing/delta text chunks
  2. Structured streaming — stream_output() yields partial Pydantic models
  3. Event streaming — AgentStreamEvent for fine-grained control

This module teaches all three, with Rich live-rendering for structured
data — a pattern you'll use whenever you need to display streaming
structured output in a terminal or web UI.

Sections:
  1. Basic Text Streaming
  2. Structured Output Streaming
  3. Rich Live Rendering of Structured Data
  4. Event Streaming (AgentStreamEvent)
  5. Putting It All Together: Streaming Security Analysis
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    AgentStreamEvent,
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPartDelta,
    ToolCallPartDelta,
)
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from shared.deps import AnalystContext


# =============================================================================
# Domain Models for This Module
# =============================================================================
# These models are defined locally because they are specific to the streaming
# exercises. The shared/ package models are for cross-module use.


class Finding(BaseModel):
    """A single finding from the security analysis."""

    category: str = Field(
        description="Area of the finding (e.g., 'structure', 'risk', 'regulatory')"
    )
    detail: str = Field(description="Description of the finding")
    severity: Literal["low", "medium", "high"] = Field(
        description="How significant this finding is"
    )


class SecurityAnalysis(BaseModel):
    """
    Structured analysis of a private security.

    This is the output type for the streaming agent. During streaming,
    you'll receive PARTIAL versions of this model — fields populate
    progressively as the LLM generates them.
    """

    security_name: str = Field(
        default="", description="Name of the security being analyzed"
    )
    issuer: str = Field(default="", description="Issuing entity")
    findings: list[Finding] = Field(
        default_factory=list,
        description="Key findings from the analysis",
    )
    risk_factors: list[str] = Field(
        default_factory=list,
        description="Identified risk factors",
    )
    classification_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the classification (0-1)",
    )
    recommended_category: str = Field(
        default="",
        description="Recommended SecurityCategory",
    )
    summary: str = Field(
        default="",
        description="Brief human-readable summary",
    )


# =============================================================================
# Section 1: Basic Text Streaming
# =============================================================================
# The simplest streaming mode: get text as the model generates it.
#
# Pattern:
#   async with agent.run_stream(prompt) as result:
#       async for text in result.stream_text():
#           print(text)  # Accumulating: "The", "The security", "The security is"...
#
# stream_text() yields the FULL accumulated text by default.
# Pass delta=True to get only the NEW tokens each iteration.
#
# WARNING: When using delta=True, the final output message is NOT added
# to result messages. Use the default (accumulated) mode if you need
# the message history afterward.

text_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    system_prompt=(
        "You are a securities analyst. When asked about a security, "
        "provide a detailed but concise analysis. Structure your response "
        "with clear paragraphs covering: overview, key terms, risks, "
        "and classification recommendation."
    ),
)


async def demo_text_streaming_accumulated() -> None:
    """Stream text with accumulated output (default mode)."""
    print("--- Text Streaming (accumulated) ---")
    print("Each iteration yields the FULL text so far:\n")

    async with text_agent.run_stream(
        "Analyze the NovaTech AI SAFE instrument: it's a $5M SAFE round "
        "with a 20% discount and $20M valuation cap, filed under Reg D 506(b)."
    ) as result:
        chunk_count = 0
        async for text in result.stream_text():
            chunk_count += 1
            # In a real UI, you'd replace the display with each chunk.
            # Here we just show progress markers.
            if chunk_count % 10 == 0:
                print(f"  [chunk {chunk_count}] {len(text)} chars so far...")

        # After the stream completes, result.output has the final text
        print(f"\n  Total chunks received: {chunk_count}")
        print(f"  Final output length: {len(text)} chars")
        print(f"  First 200 chars: {text[:200]}...")

    print()


async def demo_text_streaming_delta() -> None:
    """Stream text with delta output (new tokens only)."""
    print("--- Text Streaming (delta mode) ---")
    print("Each iteration yields only NEW tokens:\n")

    print("  ", end="", flush=True)

    async with text_agent.run_stream(
        "In one paragraph, explain why SAFE instruments are popular with startups."
    ) as result:
        async for delta in result.stream_text(delta=True):
            # delta contains only the NEW text since the last yield.
            # This is what you'd send to a WebSocket for real-time display.
            print(delta, end="", flush=True)

    print("\n")


# =============================================================================
# Section 2: Structured Output Streaming
# =============================================================================
# The real power: stream a Pydantic model as it's being built.
#
# stream_output() yields PARTIAL instances of your output model.
# Fields populate progressively:
#   Iteration 1: SecurityAnalysis(security_name="Nova...")
#   Iteration 2: SecurityAnalysis(security_name="NovaTech", issuer="Nov...")
#   Iteration 3: SecurityAnalysis(security_name="NovaTech", issuer="NovaTech AI", findings=[...])
#
# pydantic-ai uses Pydantic's experimental partial validation under
# the hood: incomplete JSON is parsed, and missing fields get their
# defaults. This is why all fields in our model have defaults.
#
# The debounce_by parameter controls how often you receive updates.
# Higher values = fewer updates but less overhead from partial validation.

structured_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=SecurityAnalysis,
    system_prompt=(
        "You are a securities analyst. Analyze the given security and "
        "return a structured SecurityAnalysis. Be thorough but concise.\n\n"
        "For findings, include at least 3 findings covering structure, "
        "regulatory status, and investor terms.\n\n"
        "For risk_factors, list 2-4 specific risks.\n\n"
        "Set classification_confidence between 0 and 1 based on how "
        "certain you are of the recommended_category."
    ),
)


async def demo_structured_streaming() -> None:
    """Stream a structured Pydantic model as it builds up."""
    print("--- Structured Output Streaming ---")
    print("Watching a SecurityAnalysis model populate field by field:\n")

    prompt = (
        "Analyze the Atlas Senior Secured Notes 2024: $25M offering of 3-year "
        "senior secured notes at 8.5% annual interest from Atlas Infrastructure Corp. "
        "Secured by infrastructure assets. Filed under Reg D 506(b). "
        "Available to accredited investors."
    )

    iteration = 0
    async with structured_agent.run_stream(prompt) as result:
        async for partial_analysis in result.stream_output(debounce_by=0.1):
            iteration += 1

            # partial_analysis is a SecurityAnalysis with whatever fields
            # have been generated so far. Missing fields have defaults.
            populated_fields = []
            if partial_analysis.security_name:
                populated_fields.append("security_name")
            if partial_analysis.issuer:
                populated_fields.append("issuer")
            if partial_analysis.findings:
                populated_fields.append(f"findings({len(partial_analysis.findings)})")
            if partial_analysis.risk_factors:
                populated_fields.append(
                    f"risk_factors({len(partial_analysis.risk_factors)})"
                )
            if partial_analysis.classification_confidence > 0:
                populated_fields.append("confidence")
            if partial_analysis.recommended_category:
                populated_fields.append("category")
            if partial_analysis.summary:
                populated_fields.append("summary")

            if iteration % 5 == 0 or iteration <= 3:
                print(
                    f"  [iter {iteration:3d}] Fields populated: {', '.join(populated_fields)}"
                )

    # The final complete model
    final = partial_analysis  # Last value from the loop
    print("\n  --- Final SecurityAnalysis ---")
    print(f"  Security: {final.security_name}")
    print(f"  Issuer: {final.issuer}")
    print(f"  Category: {final.recommended_category}")
    print(f"  Confidence: {final.classification_confidence:.0%}")
    print(f"  Findings: {len(final.findings)}")
    for f in final.findings:
        print(f"    [{f.severity.upper():6s}] {f.category}: {f.detail[:80]}")
    print(f"  Risk factors: {len(final.risk_factors)}")
    for r in final.risk_factors:
        print(f"    - {r[:80]}")
    print(f"  Summary: {final.summary[:200]}")

    print()


# =============================================================================
# Section 3: Rich Live Rendering of Structured Data
# =============================================================================
# In production, you want to display streaming structured data as a
# live-updating table or panel. The Rich library's Live context manager
# is perfect for this — it redraws a renderable on each update.
#
# Pattern:
#   from rich.live import Live
#   from rich.table import Table
#
#   with Live(refresh_per_second=4) as live:
#       async with agent.run_stream(prompt) as result:
#           async for partial in result.stream_output(debounce_by=0.1):
#               table = build_table(partial)
#               live.update(table)

console = Console()


def build_analysis_table(analysis: SecurityAnalysis) -> Table:
    """
    Build a Rich table from a (possibly partial) SecurityAnalysis.

    This function is called on every streaming iteration. It handles
    partially-populated models gracefully — empty fields show as
    placeholder text.
    """
    table = Table(
        title="Security Analysis (Live)",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
        expand=True,
    )

    # Header section
    table.add_column("Field", style="bold", width=22)
    table.add_column("Value", ratio=1)

    table.add_row("Security", analysis.security_name or "[dim]streaming...[/dim]")
    table.add_row("Issuer", analysis.issuer or "[dim]streaming...[/dim]")
    table.add_row(
        "Category",
        analysis.recommended_category or "[dim]pending...[/dim]",
    )

    # Confidence with color coding
    if analysis.classification_confidence > 0:
        conf = analysis.classification_confidence
        color = "green" if conf >= 0.8 else "yellow" if conf >= 0.5 else "red"
        table.add_row("Confidence", f"[{color}]{conf:.0%}[/{color}]")
    else:
        table.add_row("Confidence", "[dim]calculating...[/dim]")

    # Findings
    if analysis.findings:
        findings_text = ""
        for i, f in enumerate(analysis.findings):
            severity_color = {
                "low": "green",
                "medium": "yellow",
                "high": "red",
            }.get(f.severity, "white")
            findings_text += (
                f"[{severity_color}][{f.severity.upper()}][/{severity_color}] "
                f"{f.category}: {f.detail}\n"
            )
        table.add_row("Findings", findings_text.strip())
    else:
        table.add_row("Findings", "[dim]analyzing...[/dim]")

    # Risk factors
    if analysis.risk_factors:
        risks_text = "\n".join(f"  - {r}" for r in analysis.risk_factors)
        table.add_row("Risk Factors", risks_text)
    else:
        table.add_row("Risk Factors", "[dim]assessing...[/dim]")

    # Summary
    if analysis.summary:
        table.add_row("Summary", analysis.summary)
    else:
        table.add_row("Summary", "[dim]composing...[/dim]")

    return table


async def demo_rich_live_streaming() -> None:
    """Stream structured data into a live-updating Rich table."""
    print("--- Rich Live Rendering ---")
    print("Watch the table populate in real time:\n")

    prompt = (
        "Analyze the Diamond Legacy Trust Units: $100M offering of trust units "
        "from Diamond Legacy Trust. Claims guaranteed 25% annual returns from "
        "AI-driven cryptocurrency arbitrage. Principal guaranteed by issuer. "
        "Limited availability. Minimum investment $500,000."
    )

    # Rich's Live context manager handles terminal redrawing
    with Live(
        build_analysis_table(SecurityAnalysis()),  # Start with empty table
        console=console,
        refresh_per_second=4,  # Redraw up to 4 times per second
    ) as live:
        async with structured_agent.run_stream(prompt) as result:
            async for partial in result.stream_output(debounce_by=0.15):
                # Build a new table from the partial model and update
                # the live display. Rich handles the terminal magic.
                live.update(build_analysis_table(partial))

    # After streaming completes, show the final result cleanly
    print()
    print("  Streaming complete. Final analysis rendered above.")
    print()


# =============================================================================
# Section 4: Event Streaming (AgentStreamEvent)
# =============================================================================
# For fine-grained control over what the agent is doing, use the
# event_stream_handler parameter. This gives you access to:
#
#   PartStartEvent          — A new response part started (text, tool call)
#   PartDeltaEvent          — Delta update for a part (text chunk, tool args)
#   FinalResultEvent        — The model started producing a final result
#   FunctionToolCallEvent   — A tool is about to be called
#   FunctionToolResultEvent — A tool returned its result
#
# This is powerful for building UIs that show:
#   "Searching database..." → "Found 3 results" → "Analyzing..." → result

# Agent with tools so we can see tool-related events
event_demo_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=AnalystContext,
    system_prompt=(
        "You are a securities analyst. Use tools to research the security, "
        "then provide a brief analysis. Be concise."
    ),
)


@event_demo_agent.tool
async def lookup_security(ctx: RunContext[AnalystContext], name: str) -> str:
    """
    Look up a security in the database.

    Args:
        name: Name of the security to look up.
    """
    result = await ctx.deps.db.get_by_name(name)
    if result is None:
        # Try a search instead
        results = await ctx.deps.db.search(name)
        if not results:
            return f"Security '{name}' not found."
        result = results[0]

    base = f"Found: {result.name} | Issuer: {result.issuer}"
    if result.type_hint:
        base += f" | Type: {result.type_hint}"
    if result.offering_amount:
        base += f" | Amount: ${result.offering_amount:,.0f}"
    base += f"\nDescription: {result.raw_description[:200]}"
    return base


@event_demo_agent.tool
async def check_filings(ctx: RunContext[AnalystContext], issuer: str) -> str:
    """
    Check SEC filings for an issuer.

    Args:
        issuer: The issuing entity name.
    """
    filings = await ctx.deps.sec_search.search_by_issuer(issuer)
    if not filings:
        return f"No filings found for '{issuer}'."

    lines = [
        f"- {f.filing_type}: {f.exemption_type.value} ({f.filing_date}) — {f.details}"
        for f in filings[:3]
    ]
    return "SEC Filings:\n" + "\n".join(lines)


# Event log for the demo
_event_log: list[str] = []


async def event_handler(
    ctx: RunContext[AnalystContext],
    event_stream: AsyncIterable[AgentStreamEvent],
) -> None:
    """
    Handle agent stream events for real-time status updates.

    This handler receives every event the agent produces during
    streaming. You can use it to:
    - Show "Searching..." / "Analyzing..." status messages
    - Log tool calls and results
    - Track when the model starts producing the final result
    - Build progress indicators
    """
    async for event in event_stream:
        if isinstance(event, PartStartEvent):
            # A new part of the response started
            _event_log.append(
                f"  [START] New part #{event.index}: {type(event.part).__name__}"
            )

        elif isinstance(event, PartDeltaEvent):
            # Incremental update to an existing part
            if isinstance(event.delta, TextPartDelta):
                # Only log occasionally to avoid flooding
                if len(event.delta.content_delta) > 5:
                    preview = event.delta.content_delta[:30].replace("\n", " ")
                    _event_log.append(f'  [DELTA] Text: "{preview}..."')
            elif isinstance(event.delta, ToolCallPartDelta):
                _event_log.append(f"  [DELTA] Tool args: {event.delta.args_delta[:50]}")

        elif isinstance(event, FunctionToolCallEvent):
            # A tool is about to be called
            _event_log.append(
                f"  [TOOL CALL] {event.part.tool_name}({event.part.args[:80]})"
            )

        elif isinstance(event, FunctionToolResultEvent):
            # A tool returned its result
            content_preview = str(event.result.content)[:80]
            _event_log.append(
                f"  [TOOL RESULT] {event.tool_call_id}: {content_preview}..."
            )

        elif isinstance(event, FinalResultEvent):
            # The model started producing a final result
            _event_log.append(
                f"  [FINAL] Model is producing final result "
                f"(tool_name={event.tool_name})"
            )


async def demo_event_streaming() -> None:
    """Demonstrate fine-grained event streaming."""
    print("--- Event Streaming (AgentStreamEvent) ---")
    print("Observing every event the agent produces:\n")

    global _event_log
    _event_log = []

    deps = AnalystContext.create(analyst_name="Event Demo User")

    # The event_stream_handler runs concurrently with the main stream
    async with event_demo_agent.run_stream(
        "Look up the Meridian Growth Fund LP in the database and check "
        "SEC filings for Meridian Capital Partners, then give me a brief analysis.",
        deps=deps,
        event_stream_handler=event_handler,
    ) as result:
        # We can still stream text while events are being captured
        final_text = ""
        async for text in result.stream_text():
            final_text = text

    # Display the event log
    print("Event log (chronological):")
    for entry in _event_log:
        print(entry)
    print()

    print(f"Final output ({len(final_text)} chars):")
    print(f"  {final_text[:300]}...")
    print()


# =============================================================================
# Section 5: Putting It All Together — Streaming Security Analysis
# =============================================================================
# A complete example that combines:
#   - Structured streaming (stream_output)
#   - Rich live rendering
#   - Event tracking
#   - Tool usage
#
# This is the pattern you'd use in a production CLI tool or web backend.

analysis_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=AnalystContext,
    output_type=SecurityAnalysis,
    system_prompt=(
        "You are a senior securities analyst. Research the given security "
        "using the available tools, then produce a comprehensive "
        "SecurityAnalysis.\n\n"
        "Guidelines:\n"
        "- Include at least 3 findings covering different aspects\n"
        "- Identify 2-4 specific risk factors\n"
        "- Set classification_confidence based on evidence quality\n"
        "- recommended_category must be one of: equity, debt, "
        "convertible_note, safe, fund_interest, real_estate, "
        "revenue_share, other\n"
        "- Write a clear, professional summary"
    ),
)


@analysis_agent.tool
async def research_security(ctx: RunContext[AnalystContext], query: str) -> str:
    """
    Search the securities database for information.

    Args:
        query: Security name, issuer, or search term.
    """
    results = await ctx.deps.db.search(query)
    if not results:
        return f"No results for '{query}'."

    lines = []
    for sec in results[:3]:
        lines.append(f"Name: {sec.name}")
        lines.append(f"  Issuer: {sec.issuer}")
        lines.append(f"  Type: {sec.type_hint or 'unspecified'}")
        if sec.offering_amount:
            lines.append(f"  Amount: ${sec.offering_amount:,.0f}")
        if sec.interest_rate:
            lines.append(f"  Interest: {sec.interest_rate:.1%}")
        if sec.conversion_terms:
            lines.append(f"  Conversion: {sec.conversion_terms}")
        lines.append(f"  Exemption: {sec.exemption.value}")
        lines.append(f"  Description: {sec.raw_description}")
        lines.append("")

    return "\n".join(lines)


@analysis_agent.tool
async def research_filings(ctx: RunContext[AnalystContext], issuer: str) -> str:
    """
    Search SEC filings for regulatory information.

    Args:
        issuer: The issuing entity to search for.
    """
    filings = await ctx.deps.sec_search.search_by_issuer(issuer)
    if not filings:
        return f"No SEC filings for '{issuer}'."

    lines = []
    for f in filings:
        entry = f"{f.filing_type} | {f.filing_date} | {f.exemption_type.value}"
        if f.amount_raised:
            entry += f" | Amount: ${f.amount_raised:,.0f}"
        lines.append(entry)
        lines.append(f"  {f.details}")

    return "SEC Filings:\n" + "\n".join(lines)


@analysis_agent.tool
async def research_web(ctx: RunContext[AnalystContext], query: str) -> str:
    """
    Search the web for additional context about a security.

    Args:
        query: Web search query.
    """
    results = await ctx.deps.web_search.search(query)
    lines = [f"- {r.title}: {r.snippet}" for r in results[:3]]
    return "Web results:\n" + "\n".join(lines)


def build_investigation_panel(
    analysis: SecurityAnalysis,
    status: str = "Streaming...",
) -> Panel:
    """
    Build a Rich Panel with the full analysis for live rendering.

    This is a richer display than the simple table from Section 3.
    It includes color-coded findings, risk factors, and a status bar.
    """
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Field", style="bold", width=20)
    table.add_column("Value", ratio=1)

    # Basic info
    table.add_row("Security", analysis.security_name or "[dim]...[/dim]")
    table.add_row("Issuer", analysis.issuer or "[dim]...[/dim]")
    table.add_row(
        "Category",
        analysis.recommended_category or "[dim]pending[/dim]",
    )

    # Confidence with color
    if analysis.classification_confidence > 0:
        conf = analysis.classification_confidence
        bar_filled = int(conf * 20)
        bar_empty = 20 - bar_filled
        color = "green" if conf >= 0.8 else "yellow" if conf >= 0.5 else "red"
        bar = f"[{color}]{'█' * bar_filled}[/{color}]{'░' * bar_empty} {conf:.0%}"
        table.add_row("Confidence", bar)
    else:
        table.add_row("Confidence", "[dim]░░░░░░░░░░░░░░░░░░░░ ...[/dim]")

    # Findings as a sub-table
    if analysis.findings:
        findings_parts = []
        for f in analysis.findings:
            severity_colors = {"low": "green", "medium": "yellow", "high": "red"}
            color = severity_colors.get(f.severity, "white")
            findings_parts.append(
                f"[{color}]■[/{color}] [{color}]{f.severity.upper():6s}[/{color}] "
                f"[bold]{f.category}[/bold]: {f.detail}"
            )
        table.add_row("Findings", "\n".join(findings_parts))
    else:
        table.add_row("Findings", "[dim]Analyzing...[/dim]")

    # Risk factors
    if analysis.risk_factors:
        risks = "\n".join(f"  [red]![/red] {r}" for r in analysis.risk_factors)
        table.add_row("Risk Factors", risks)
    else:
        table.add_row("Risk Factors", "[dim]Assessing...[/dim]")

    # Summary
    if analysis.summary:
        table.add_row("Summary", analysis.summary)
    else:
        table.add_row("Summary", "[dim]Composing...[/dim]")

    return Panel(
        table,
        title=f"[bold blue]Security Analysis[/bold blue] — [dim]{status}[/dim]",
        border_style="blue",
    )


# Event tracking for the combined demo
_analysis_events: list[str] = []


async def analysis_event_handler(
    ctx: RunContext[AnalystContext],
    event_stream: AsyncIterable[AgentStreamEvent],
) -> None:
    """Track events for the analysis agent."""
    async for event in event_stream:
        if isinstance(event, FunctionToolCallEvent):
            _analysis_events.append(f"Calling: {event.part.tool_name}")
        elif isinstance(event, FunctionToolResultEvent):
            _analysis_events.append("Got result from tool")
        elif isinstance(event, FinalResultEvent):
            _analysis_events.append("Building final analysis...")


async def demo_full_streaming_analysis() -> None:
    """Complete streaming analysis with Rich live rendering and event tracking."""
    print("--- Complete Streaming Analysis ---")
    print("Combining structured streaming + Rich + event tracking:\n")

    global _analysis_events
    _analysis_events = []

    deps = AnalystContext.create(analyst_name="Dr. Chen", access_level="senior")

    # Security to analyze — this one has interesting characteristics
    prompt = (
        "Research and analyze the Cascade SAFE+Note from Cascade Robotics. "
        "Look it up in the database and check SEC filings for Cascade Robotics. "
        "This is a hybrid instrument — determine whether it's more like a SAFE "
        "or a convertible note."
    )

    iteration_count = 0

    with Live(
        build_investigation_panel(SecurityAnalysis(), "Initializing..."),
        console=console,
        refresh_per_second=4,
    ) as live:
        async with analysis_agent.run_stream(
            prompt,
            deps=deps,
            event_stream_handler=analysis_event_handler,
        ) as result:
            async for partial in result.stream_output(debounce_by=0.1):
                iteration_count += 1

                # Build status from events
                status = _analysis_events[-1] if _analysis_events else "Streaming..."
                live.update(build_investigation_panel(partial, status))

        # Final update with "Complete" status
        live.update(build_investigation_panel(partial, "Complete"))

    print()
    print(f"  Streaming iterations: {iteration_count}")
    print(f"  Events captured: {len(_analysis_events)}")
    if _analysis_events:
        print("  Event timeline:")
        for e in _analysis_events:
            print(f"    -> {e}")
    print()

    # Show the final output details
    print("  Final SecurityAnalysis:")
    print(f"    Name: {partial.security_name}")
    print(f"    Category: {partial.recommended_category}")
    print(f"    Confidence: {partial.classification_confidence:.0%}")
    print(f"    Findings: {len(partial.findings)}")
    print(f"    Risk factors: {len(partial.risk_factors)}")
    print()


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    print("=" * 70)
    print("MODULE 05: STREAMING FOR REAL-TIME OUTPUT")
    print("Three streaming modes for production agents")
    print("=" * 70)
    print()

    # Section 1: Basic text streaming
    print("=" * 70)
    print("SECTION 1: BASIC TEXT STREAMING")
    print("=" * 70)
    print()
    await demo_text_streaming_accumulated()
    await demo_text_streaming_delta()

    # Section 2: Structured output streaming
    print("=" * 70)
    print("SECTION 2: STRUCTURED OUTPUT STREAMING")
    print("=" * 70)
    print()
    await demo_structured_streaming()

    # Section 3: Rich live rendering
    print("=" * 70)
    print("SECTION 3: RICH LIVE RENDERING")
    print("=" * 70)
    print()
    await demo_rich_live_streaming()

    # Section 4: Event streaming
    print("=" * 70)
    print("SECTION 4: EVENT STREAMING")
    print("=" * 70)
    print()
    await demo_event_streaming()

    # Section 5: Full analysis with everything combined
    print("=" * 70)
    print("SECTION 5: COMPLETE STREAMING ANALYSIS")
    print("=" * 70)
    print()
    await demo_full_streaming_analysis()

    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. stream_text() for real-time text display")
    print("     Default: accumulated text | delta=True: new tokens only")
    print("  2. stream_output() for structured Pydantic model streaming")
    print("     Partial models populate progressively as JSON is generated")
    print("     debounce_by controls update frequency (0.1s default)")
    print("  3. Rich Live + stream_output() = production-grade terminal UI")
    print("     Build a table/panel from each partial, live.update() it")
    print("  4. event_stream_handler for fine-grained event tracking")
    print("     See tool calls, deltas, and final result events")
    print("  5. All three modes can work together in one streaming session")
    print()
    print("WHEN TO USE EACH MODE:")
    print("  Chat interface    -> stream_text(delta=True)")
    print("  Dashboard/table   -> stream_output() + Rich Live")
    print("  Debug/monitoring  -> event_stream_handler")
    print("  Production API    -> stream_text() for SSE, stream_output() for WS")
    print()
    print("Next: Module 06 -- Tool orchestration and multi-agent patterns")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
