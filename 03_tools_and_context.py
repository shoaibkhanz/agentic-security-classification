"""
Module 03: Tools, Dependencies, and Dynamic Context
====================================================

In Module 01, you saw basic @agent.tool. In Module 02, you constrained outputs.
Now go deep on the tool and dependency system — the mechanism that connects
your agent to the real world (databases, APIs, search).

Core ideas:
  - @agent.tool: tool receives RunContext[DepsType] — accesses injected services
  - @agent.tool_plain: tool does NOT receive RunContext — pure utility function
  - ModelRetry in tools: when a tool gets bad results, tell the LLM to try again
  - @agent.instructions: dynamic system prompt built from deps at runtime
  - format_as_xml: structured data injection that LLMs parse well
  - AnalystContext: production pattern — bundle all services into one deps object

Why this matters for securities:
  A real securities analyst agent needs to query databases, search SEC filings,
  and access web search — all gated by the analyst's access level. Dependencies
  and dynamic prompts handle this cleanly.

Sections:
  1. Simple Tool with @agent.tool (RunContext)
  2. Plain Tools with @agent.tool_plain (no context)
  3. Tool Retries with ModelRetry
  4. Dynamic System Prompt with @agent.instructions
  5. Complex Dependencies with AnalystContext
  6. format_as_xml for Structured Context Injection
  7. Exercise: Full Security Lookup Agent
"""

from __future__ import annotations

import asyncio

from pydantic_ai import Agent, ModelRetry, RunContext, format_as_xml

from shared.deps import AnalystContext, SecuritiesDB


# =============================================================================
# Section 1: Simple Tool with @agent.tool
# =============================================================================
# @agent.tool decorates a function that receives RunContext[DepsType] as its
# first argument. Through RunContext, the tool accesses injected dependencies.
#
# This is dependency injection:
#   - Agent declares deps_type=SecuritiesDB
#   - You pass deps=SecuritiesDB() at runtime
#   - Every tool decorated with @agent.tool gets ctx.deps = that SecuritiesDB
#
# The LLM sees the tool's name, docstring, and parameter types (minus ctx).
# It decides when to call the tool and with what arguments.

simple_lookup_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=SecuritiesDB,
    output_type=str,
    system_prompt=(
        "You are a securities database assistant. Use the available tools "
        "to look up information about private securities. Provide clear, "
        "concise answers based on the data you find."
    ),
)


@simple_lookup_agent.tool
async def search_database(ctx: RunContext[SecuritiesDB], query: str) -> str:
    """
    Search the securities database by name, issuer, or keyword.

    Args:
        query: Search term — security name, issuer name, or descriptive keyword.
    """
    # ctx.deps is the SecuritiesDB instance passed at runtime.
    # The tool doesn't know or care WHERE the db came from — just uses it.
    results = await ctx.deps.search(query)

    if not results:
        return f"No securities found matching '{query}'."

    # Format results as text for the LLM to read
    lines = []
    for sec in results[:5]:
        line = f"- {sec.name} | Issuer: {sec.issuer}"
        if sec.type_hint:
            line += f" | Type: {sec.type_hint}"
        if sec.offering_amount:
            line += f" | Amount: ${sec.offering_amount:,.0f}"
        lines.append(line)

    return f"Found {len(results)} result(s):\n" + "\n".join(lines)


@simple_lookup_agent.tool
async def get_details(ctx: RunContext[SecuritiesDB], security_name: str) -> str:
    """
    Get full details for a specific security by its exact name.

    Args:
        security_name: The exact name of the security to look up.
    """
    security = await ctx.deps.get_by_name(security_name)
    if security is None:
        return f"No security found with exact name '{security_name}'. Use search_database first."

    # Return all available info
    details = [
        f"Name: {security.name}",
        f"Issuer: {security.issuer}",
        f"Type hint: {security.type_hint or 'Not specified'}",
        f"Exemption: {security.exemption.value}",
        f"Description: {security.raw_description}",
    ]

    if security.offering_amount:
        details.append(f"Offering amount: ${security.offering_amount:,.0f}")
    if security.min_investment:
        details.append(f"Min investment: ${security.min_investment:,.0f}")
    if security.interest_rate:
        details.append(f"Interest rate: {security.interest_rate:.1%}")
    if security.maturity_date:
        details.append(f"Maturity: {security.maturity_date}")
    if security.conversion_terms:
        details.append(f"Conversion: {security.conversion_terms}")

    return "\n".join(details)


async def demo_simple_tool() -> None:
    """Show basic @agent.tool with RunContext dependency injection."""
    print("--- Section 1: Simple Tool with @agent.tool ---\n")

    db = SecuritiesDB()

    result = await simple_lookup_agent.run(
        "What can you tell me about convertible notes in the database?",
        deps=db,
    )

    print(f"Response:\n  {result.output[:300]}")
    print(f"\nUsage: {result.usage()}")
    print()


# =============================================================================
# Section 2: Plain Tools with @agent.tool_plain
# =============================================================================
# @agent.tool_plain decorates a function that does NOT receive RunContext.
# Use this for stateless utility functions that don't need dependencies.
#
# When to use each:
#   @agent.tool       -> needs database, API client, user session, etc.
#   @agent.tool_plain -> pure computation, formatting, validation
#
# Under the hood, both become JSON Schema tool definitions for the LLM.
# The only difference is whether RunContext is injected.

utility_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=SecuritiesDB,
    output_type=str,
    system_prompt=(
        "You are a securities analyst assistant. Use tools to look up securities "
        "and perform calculations. Always show your work when computing metrics."
    ),
)


# Tool WITH context — needs the database
@utility_agent.tool
async def lookup_security(ctx: RunContext[SecuritiesDB], name: str) -> str:
    """
    Look up a security by name in the database.

    Args:
        name: Name of the security to look up.
    """
    security = await ctx.deps.get_by_name(name)
    if security is None:
        # Search as fallback
        results = await ctx.deps.search(name)
        if not results:
            return f"Security '{name}' not found."
        security = results[0]

    return (
        f"Name: {security.name}\n"
        f"Issuer: {security.issuer}\n"
        f"Type: {security.type_hint or 'Unknown'}\n"
        f"Amount: ${security.offering_amount:,.0f}"
        if security.offering_amount
        else "Amount: Unknown"
    )


# Tool WITHOUT context — pure utility (no deps needed)
@utility_agent.tool_plain
def calculate_yield(
    face_value: float,
    annual_coupon_payment: float,
    current_price: float,
) -> str:
    """
    Calculate current yield for a fixed-income security.

    Args:
        face_value: The par/face value of the instrument in USD.
        annual_coupon_payment: Total annual coupon payment in USD.
        current_price: Current market price of the instrument in USD.
    """
    # Pure math — no database or API needed, so @tool_plain is correct.
    if current_price <= 0:
        return "Error: current_price must be positive."
    if face_value <= 0:
        return "Error: face_value must be positive."

    coupon_rate = annual_coupon_payment / face_value * 100
    current_yield = annual_coupon_payment / current_price * 100

    return (
        f"Coupon rate: {coupon_rate:.2f}%\n"
        f"Current yield: {current_yield:.2f}%\n"
        f"(Annual payment ${annual_coupon_payment:,.2f} / "
        f"Price ${current_price:,.2f})"
    )


@utility_agent.tool_plain
def format_currency(amount: float, decimals: int = 0) -> str:
    """
    Format a number as USD currency string.

    Args:
        amount: The dollar amount to format.
        decimals: Number of decimal places (default 0).
    """
    # Another pure utility — no deps needed.
    if decimals > 0:
        return f"${amount:,.{decimals}f}"
    return f"${amount:,.0f}"


async def demo_plain_tools() -> None:
    """Show the difference between @agent.tool and @agent.tool_plain."""
    print("--- Section 2: Plain Tools with @agent.tool_plain ---\n")

    db = SecuritiesDB()

    result = await utility_agent.run(
        "Look up the Atlas Senior Secured Notes 2024. "
        "What is the current yield if the notes are trading at $48,000 "
        "(face value $50,000, 8.5% coupon)?",
        deps=db,
    )

    print(f"Response:\n  {result.output[:400]}")
    print(f"\nUsage: {result.usage()}")
    print()


# =============================================================================
# Section 3: Tool Retries with ModelRetry
# =============================================================================
# Tools can raise ModelRetry to tell the LLM its approach didn't work.
# This is different from output validators (Module 02):
#   - Output validator: retries the FINAL result
#   - Tool ModelRetry: retries a TOOL CALL mid-conversation
#
# Pattern:
#   1. LLM calls tool("narrow query")
#   2. Tool gets 0 results
#   3. Tool raises ModelRetry("No results, try broader terms")
#   4. LLM calls tool("broader query")
#   5. Tool returns results
#
# The retries parameter limits how many times the LLM can retry each tool.

retry_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=SecuritiesDB,
    output_type=str,
    system_prompt=(
        "You are a securities search assistant. Find information about "
        "private securities. If a search returns no results, try different "
        "search terms — the database uses keyword matching."
    ),
)


@retry_agent.tool(retries=3)
async def search_with_retry(ctx: RunContext[SecuritiesDB], query: str) -> str:
    """
    Search the securities database. Retries with guidance if no results found.

    Args:
        query: Search term — try issuer name, security name, or keywords
               like 'SAFE', 'convertible', 'real estate', 'fund'.
    """
    results = await ctx.deps.search(query)

    if not results:
        # ModelRetry sends this message back to the LLM as a tool error.
        # The LLM sees the error and tries again with different arguments.
        # retries=3 means it gets 3 retry attempts before giving up.
        raise ModelRetry(
            f"No results for '{query}'. Try different search terms. "
            "The database contains securities with names like 'Meridian Growth Fund', "
            "'Atlas Senior Secured Notes', 'NovaTech SAFE Round', etc. "
            "Try searching by issuer name, security type, or broader keywords."
        )

    lines = []
    for sec in results[:5]:
        line = f"- {sec.name} (Issuer: {sec.issuer})"
        if sec.type_hint:
            line += f" | Type: {sec.type_hint}"
        if sec.exemption.value != "unknown":
            line += f" | Exemption: {sec.exemption.value}"
        lines.append(line)

    return f"Found {len(results)} result(s):\n" + "\n".join(lines)


async def demo_tool_retries() -> None:
    """Show how ModelRetry in tools creates a search refinement loop."""
    print("--- Section 3: Tool Retries with ModelRetry ---\n")

    db = SecuritiesDB()

    # Deliberately ask about something using unusual phrasing.
    # The tool may need to guide the LLM toward better search terms.
    result = await retry_agent.run(
        "Find me any SAFE instruments in the database.",
        deps=db,
    )

    print(f"Response:\n  {result.output[:300]}")
    print(f"\nUsage (extra tokens = retries happened): {result.usage()}")
    print()


# =============================================================================
# Section 4: Dynamic System Prompt with @agent.instructions
# =============================================================================
# @agent.instructions runs before every LLM call and builds the system prompt
# from the current dependencies. This lets you change agent behavior based on
# who is using it, their access level, their preferences, etc.
#
# This is different from a static system_prompt string:
#   - static: same prompt every time, defined at agent creation
#   - dynamic: computed at runtime from ctx.deps
#
# For securities: an analyst's access level determines what they can see
# and how the agent should respond.

dynamic_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=AnalystContext,
    output_type=str,
    # No static system_prompt here — we build it dynamically below.
    # You CAN combine static + dynamic: static runs first, then dynamic appends.
)


@dynamic_agent.instructions
async def analyst_instructions(ctx: RunContext[AnalystContext]) -> str:
    """
    Build system prompt based on the analyst's identity and access level.

    This function runs before every LLM call. It receives the same RunContext
    that tools receive, so it can access all injected dependencies.
    """
    base = (
        f"You are a securities analyst assistant for {ctx.deps.analyst_name}. "
        "Help them research and understand private securities.\n\n"
    )

    # Access level determines behavior — this is authorization via prompt
    if ctx.deps.access_level == "standard":
        base += (
            "ACCESS LEVEL: Standard\n"
            "- You can search the securities database and provide general information.\n"
            "- You should NOT provide specific investment recommendations.\n"
            "- Flag any securities that appear to have red flags but do not make "
            "definitive fraud determinations.\n"
            "- Always recommend consulting a senior analyst for complex cases."
        )
    elif ctx.deps.access_level == "senior":
        base += (
            "ACCESS LEVEL: Senior\n"
            "- You have full access to the securities database and SEC filings.\n"
            "- You can provide detailed analysis including risk assessments.\n"
            "- You can flag potential regulatory concerns.\n"
            "- Provide confidence levels with your assessments."
        )
    elif ctx.deps.access_level == "admin":
        base += (
            "ACCESS LEVEL: Admin\n"
            "- Full access to all data sources including restricted filings.\n"
            "- You can make definitive assessments and recommendations.\n"
            "- Include compliance notes in your analysis.\n"
            "- You may access all securities regardless of restriction level."
        )

    return base


@dynamic_agent.tool
async def analyst_search(ctx: RunContext[AnalystContext], query: str) -> str:
    """
    Search the securities database.

    Args:
        query: Search term for finding securities.
    """
    results = await ctx.deps.db.search(query)
    if not results:
        return f"No results for '{query}'."

    lines = []
    for sec in results[:5]:
        # Access level determines how much detail to show
        line = f"- {sec.name} | Issuer: {sec.issuer}"
        if ctx.deps.access_level in ("senior", "admin"):
            line += f" | Exemption: {sec.exemption.value}"
            if sec.offering_amount:
                line += f" | Amount: ${sec.offering_amount:,.0f}"
        lines.append(line)

    return "\n".join(lines)


@dynamic_agent.tool
async def search_sec_filings(ctx: RunContext[AnalystContext], issuer: str) -> str:
    """
    Search SEC EDGAR filings for a specific issuer.

    Args:
        issuer: Name of the issuer to search for in SEC filings.
    """
    # Access control at the tool level
    if ctx.deps.access_level == "standard":
        return "SEC filing search requires senior or admin access level."

    filings = await ctx.deps.sec_search.search_by_issuer(issuer)
    if not filings:
        return f"No SEC filings found for '{issuer}'."

    lines = []
    for filing in filings:
        lines.append(
            f"- {filing.filing_type} | {filing.filing_date} | "
            f"{filing.issuer} | {filing.exemption_type.value}\n"
            f"  Details: {filing.details}"
        )

    return "\n".join(lines)


async def demo_dynamic_prompt() -> None:
    """Show how @agent.instructions changes behavior based on access level."""
    print("--- Section 4: Dynamic System Prompt with @agent.instructions ---\n")

    query = "Tell me about the Diamond Legacy Trust. Should I be concerned?"

    # Standard analyst — gets cautious response
    standard_ctx = AnalystContext.create(
        analyst_name="Alex (Standard Analyst)",
        access_level="standard",
    )
    result_standard = await dynamic_agent.run(query, deps=standard_ctx)
    print(f"Standard analyst response:\n  {result_standard.output[:250]}...\n")

    # Senior analyst — gets detailed response with SEC filings
    senior_ctx = AnalystContext.create(
        analyst_name="Dr. Chen (Senior Analyst)",
        access_level="senior",
    )
    result_senior = await dynamic_agent.run(query, deps=senior_ctx)
    print(f"Senior analyst response:\n  {result_senior.output[:250]}...\n")


# =============================================================================
# Section 5: Complex Dependencies with AnalystContext
# =============================================================================
# Production agents need multiple services: database, SEC search, web search.
# Bundle them into a single deps dataclass — AnalystContext.
#
# This is the standard pattern:
#   @dataclass
#   class AnalystContext:
#       db: SecuritiesDB
#       sec_search: SECFilingSearch
#       web_search: WebSearchClient
#       analyst_name: str
#       access_level: str
#
# One deps object, multiple services, clean injection.
# See shared/deps.py for the full definition.

multi_service_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=AnalystContext,
    output_type=str,
    system_prompt=(
        "You are a comprehensive securities research assistant. "
        "Use all available tools to provide thorough analysis. "
        "Cross-reference multiple data sources when possible."
    ),
)


@multi_service_agent.tool(retries=2)
async def search_by_issuer(ctx: RunContext[AnalystContext], query: str) -> str:
    """
    Search the securities database by issuer name or keyword.

    Args:
        query: Issuer name or keyword to search for.
    """
    results = await ctx.deps.db.search(query)
    if not results:
        raise ModelRetry(
            f"No results for '{query}'. Try broader terms or check spelling. "
            "You can search by issuer name (e.g., 'Meridian', 'Atlas', 'NovaTech') "
            "or security type (e.g., 'fund', 'notes', 'SAFE')."
        )

    lines = []
    for sec in results[:5]:
        line = f"- {sec.name} | Issuer: {sec.issuer}"
        if sec.type_hint:
            line += f" | Type: {sec.type_hint}"
        if sec.offering_amount:
            line += f" | Amount: ${sec.offering_amount:,.0f}"
        if sec.exemption.value != "unknown":
            line += f" | Exemption: {sec.exemption.value}"
        lines.append(line)

    return "Database results:\n" + "\n".join(lines)


@multi_service_agent.tool
async def get_filing_details(ctx: RunContext[AnalystContext], issuer: str) -> str:
    """
    Search SEC EDGAR for filings related to an issuer.

    Args:
        issuer: Name of the issuer to search for in SEC filings.
    """
    filings = await ctx.deps.sec_search.search_by_issuer(issuer)
    if not filings:
        return f"No SEC filings found for '{issuer}'."

    lines = []
    for filing in filings:
        amount_str = f"${filing.amount_raised:,.0f}" if filing.amount_raised else "N/A"
        lines.append(
            f"- {filing.filing_type} filed {filing.filing_date}\n"
            f"  Issuer: {filing.issuer}\n"
            f"  Exemption: {filing.exemption_type.value}\n"
            f"  Amount: {amount_str}\n"
            f"  Details: {filing.details}"
        )

    return "SEC filings found:\n" + "\n".join(lines)


@multi_service_agent.tool
async def check_exemption_status(ctx: RunContext[AnalystContext], issuer: str) -> str:
    """
    Check the SEC exemption status for an issuer by cross-referencing
    the database and SEC filings.

    Args:
        issuer: Name of the issuer to check exemption status for.
    """
    # Cross-reference database and SEC filings
    db_results = await ctx.deps.db.search(issuer)
    sec_filings = await ctx.deps.sec_search.search_by_issuer(issuer)

    lines = ["Exemption Status Report:"]

    if db_results:
        for sec in db_results:
            lines.append(f"  Database: {sec.name} — Exemption: {sec.exemption.value}")
    else:
        lines.append("  Database: No matching records.")

    if sec_filings:
        for filing in sec_filings:
            lines.append(
                f"  SEC Filing: {filing.filing_type} — "
                f"Exemption: {filing.exemption_type.value} — "
                f"Filed: {filing.filing_date}"
            )
    else:
        lines.append("  SEC Filings: No matching filings.")

    # Check for consistency
    if db_results and sec_filings:
        db_exemptions = {sec.exemption for sec in db_results}
        sec_exemptions = {f.exemption_type for f in sec_filings}
        if db_exemptions == sec_exemptions:
            lines.append("\n  Status: CONSISTENT — Database and SEC filings agree.")
        else:
            lines.append(
                "\n  Status: DISCREPANCY — Database and SEC filings show "
                "different exemption types. Recommend further investigation."
            )

    return "\n".join(lines)


@multi_service_agent.tool
async def web_search(ctx: RunContext[AnalystContext], query: str) -> str:
    """
    Search the web for additional information about a security or issuer.

    Args:
        query: Search query for web search.
    """
    results = await ctx.deps.web_search.search(query)

    lines = []
    for r in results:
        lines.append(
            f"- [{r.title}]({r.url})\n"
            f"  {r.snippet}\n"
            f"  Relevance: {r.relevance_score:.0%}"
        )

    return "Web search results:\n" + "\n".join(lines)


async def demo_complex_deps() -> None:
    """Show how multiple services are bundled in AnalystContext."""
    print("--- Section 5: Complex Dependencies with AnalystContext ---\n")

    # AnalystContext.create() is a factory method that initializes all services
    ctx = AnalystContext.create(
        analyst_name="Jordan (Research)",
        access_level="senior",
    )

    result = await multi_service_agent.run(
        "Research NovaTech AI. Cross-reference the database with SEC filings "
        "and web search to give me a complete picture.",
        deps=ctx,
    )

    print(f"Multi-source research:\n{result.output[:500]}")
    print(f"\nUsage: {result.usage()}")
    print()


# =============================================================================
# Section 6: format_as_xml for Structured Context Injection
# =============================================================================
# LLMs parse XML-formatted data better than JSON for in-context data.
# format_as_xml converts Pydantic models, dicts, and dataclasses to XML
# that the LLM can easily reference.
#
# Use case: inject database results into the system prompt or a tool response
# as structured XML instead of ad-hoc string formatting.
#
# This is especially useful when you want the LLM to reason about
# multiple structured records simultaneously.

xml_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=AnalystContext,
    output_type=str,
    system_prompt=(
        "You are a securities analyst. You will be given structured data "
        "about securities in XML format. Analyze the data and provide insights."
    ),
)


@xml_agent.tool
async def get_securities_as_xml(ctx: RunContext[AnalystContext], query: str) -> str:
    """
    Search for securities and return results as structured XML.

    Args:
        query: Search term to find securities.
    """
    results = await ctx.deps.db.search(query)
    if not results:
        return f"No securities found for '{query}'."

    # format_as_xml converts Pydantic models to XML that LLMs read well.
    # The root_tag wraps all results, and each SecurityInfo becomes an <item>.
    #
    # Output looks like:
    #   <securities>
    #     <SecurityInfo>
    #       <name>Meridian Growth Fund LP</name>
    #       <issuer>Meridian Capital Partners</issuer>
    #       ...
    #     </SecurityInfo>
    #     ...
    #   </securities>
    return format_as_xml(results[:3], root_tag="securities")


@xml_agent.tool
async def get_filings_as_xml(ctx: RunContext[AnalystContext], issuer: str) -> str:
    """
    Search SEC filings and return results as structured XML.

    Args:
        issuer: Issuer name to search for in SEC filings.
    """
    filings = await ctx.deps.sec_search.search_by_issuer(issuer)
    if not filings:
        return f"No SEC filings found for '{issuer}'."

    return format_as_xml(filings, root_tag="sec_filings")


async def demo_format_as_xml() -> None:
    """Show how format_as_xml provides structured context to the LLM."""
    print("--- Section 6: format_as_xml for Structured Context ---\n")

    # First, demonstrate what format_as_xml produces
    db = SecuritiesDB()
    sample_results = await db.search("fund")

    print("format_as_xml output (what the LLM sees):")
    xml_output = format_as_xml(sample_results[:2], root_tag="securities")
    # Print first 500 chars of XML to show the format
    print(xml_output[:500])
    print("...\n")

    # Now use it in an agent
    ctx = AnalystContext.create(
        analyst_name="Sam (XML Demo)",
        access_level="senior",
    )

    result = await xml_agent.run(
        "Find all funds in the database and compare their offering amounts "
        "and exemption types.",
        deps=ctx,
    )

    print(f"Agent analysis from XML data:\n{result.output[:400]}")
    print()


# =============================================================================
# Section 7: Exercise — Full Security Lookup Agent
# =============================================================================
# Combine everything into a production-style agent:
#   - AnalystContext with all services
#   - Tools with retry for search
#   - Dynamic system prompt based on access level
#   - format_as_xml for structured data
#   - Cross-referencing multiple data sources

exercise_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=AnalystContext,
    output_type=str,
    # Static prompt provides base behavior. Dynamic prompt (below) adds
    # analyst-specific context. They combine: static first, then dynamic.
    system_prompt=(
        "You are an expert private securities analyst. Your job is to research "
        "securities using all available data sources and provide comprehensive "
        "analysis. Always cross-reference when possible and note any discrepancies."
    ),
)


@exercise_agent.instructions
async def exercise_dynamic_prompt(ctx: RunContext[AnalystContext]) -> str:
    """Inject analyst identity and access-level-specific instructions."""
    prompt = (
        f"\nAnalyst: {ctx.deps.analyst_name}\nAccess Level: {ctx.deps.access_level}\n\n"
    )

    if ctx.deps.access_level == "standard":
        prompt += (
            "RESTRICTIONS:\n"
            "- Provide factual summaries only, no investment recommendations.\n"
            "- Flag concerns but recommend senior review for definitive assessments.\n"
            "- You cannot access SEC filings at this access level."
        )
    elif ctx.deps.access_level == "senior":
        prompt += (
            "CAPABILITIES:\n"
            "- Full database and SEC filing access.\n"
            "- You can provide risk assessments with confidence levels.\n"
            "- Cross-reference multiple sources for thorough analysis."
        )
    elif ctx.deps.access_level == "admin":
        prompt += (
            "CAPABILITIES:\n"
            "- Unrestricted access to all data sources.\n"
            "- You can make compliance determinations.\n"
            "- Include regulatory risk assessment in your analysis."
        )

    return prompt


@exercise_agent.tool(retries=3)
async def exercise_search_by_issuer(ctx: RunContext[AnalystContext], query: str) -> str:
    """
    Search securities database by issuer name or keyword.

    Args:
        query: Issuer name or keyword. Try broad terms if specific ones fail.
    """
    results = await ctx.deps.db.search(query)
    if not results:
        raise ModelRetry(
            f"No results for '{query}'. Try different search terms. "
            "Hint: search by issuer name (e.g., 'Meridian', 'NovaTech', 'Atlas') "
            "or by type (e.g., 'fund', 'notes', 'SAFE', 'convertible')."
        )

    return format_as_xml(results[:5], root_tag="database_results")


@exercise_agent.tool
async def exercise_get_filing_details(
    ctx: RunContext[AnalystContext], issuer: str
) -> str:
    """
    Look up SEC filings for an issuer. Requires senior or admin access.

    Args:
        issuer: Name of the issuer.
    """
    if ctx.deps.access_level == "standard":
        return (
            "ACCESS DENIED: SEC filing search requires senior or admin access. "
            "Recommend escalating this query to a senior analyst."
        )

    filings = await ctx.deps.sec_search.search_by_issuer(issuer)
    if not filings:
        return f"No SEC filings found for issuer '{issuer}'."

    return format_as_xml(filings, root_tag="sec_filings")


@exercise_agent.tool
async def exercise_check_exemption_status(
    ctx: RunContext[AnalystContext], issuer: str
) -> str:
    """
    Cross-reference database and SEC filings to verify exemption status.

    Args:
        issuer: Name of the issuer to check.
    """
    db_results = await ctx.deps.db.search(issuer)
    sec_filings = await ctx.deps.sec_search.search_by_issuer(issuer)

    report = {
        "issuer_query": issuer,
        "database_records": len(db_results),
        "sec_filings_found": len(sec_filings),
    }

    # Build exemption comparison
    db_exemptions = [
        {"security": sec.name, "exemption": sec.exemption.value} for sec in db_results
    ]
    sec_exemptions = [
        {
            "filing_type": f.filing_type,
            "exemption": f.exemption_type.value,
            "filing_date": str(f.filing_date),
        }
        for f in sec_filings
    ]

    data = {
        "report": report,
        "database_exemptions": db_exemptions,
        "sec_filing_exemptions": sec_exemptions,
    }

    # Detect discrepancies
    db_set = {sec.exemption for sec in db_results}
    sec_set = {f.exemption_type for f in sec_filings}
    if db_set and sec_set:
        data["status"] = "CONSISTENT" if db_set == sec_set else "DISCREPANCY_DETECTED"
    else:
        data["status"] = "INSUFFICIENT_DATA"

    return format_as_xml(data, root_tag="exemption_status_report")


@exercise_agent.tool
async def exercise_web_search(ctx: RunContext[AnalystContext], query: str) -> str:
    """
    Search the web for additional context about a security or issuer.

    Args:
        query: Web search query.
    """
    results = await ctx.deps.web_search.search(query)
    return format_as_xml(results, root_tag="web_results")


async def demo_exercise() -> None:
    """Run the full exercise agent with different scenarios."""
    print("--- Section 7: Exercise — Full Security Lookup Agent ---\n")

    # Scenario 1: Senior analyst investigates a suspicious offering
    print("Scenario 1: Senior analyst investigates Diamond Legacy Trust\n")
    senior_ctx = AnalystContext.create(
        analyst_name="Dr. Chen",
        access_level="senior",
    )

    result1 = await exercise_agent.run(
        "Research the Diamond Legacy Trust. They claim 25% guaranteed returns. "
        "Check the database, SEC filings, and web for any red flags.",
        deps=senior_ctx,
    )
    print(f"Senior analysis:\n{result1.output[:500]}")
    print(f"\nUsage: {result1.usage()}")
    print()

    # Scenario 2: Standard analyst tries the same query (restricted access)
    print("Scenario 2: Standard analyst asks same question\n")
    standard_ctx = AnalystContext.create(
        analyst_name="Alex",
        access_level="standard",
    )

    result2 = await exercise_agent.run(
        "What can you tell me about Meridian Growth Fund? "
        "I need to understand the exemption type and structure.",
        deps=standard_ctx,
    )
    print(f"Standard analyst response:\n{result2.output[:400]}")
    print(f"\nUsage: {result2.usage()}")
    print()


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    print("=" * 70)
    print("MODULE 03: TOOLS, DEPENDENCIES, AND DYNAMIC CONTEXT")
    print("Connecting agents to real-world services with dependency injection")
    print("=" * 70)
    print()

    # Section 1: Basic @agent.tool with RunContext
    await demo_simple_tool()

    # Section 2: @agent.tool_plain for stateless utilities
    await demo_plain_tools()

    # Section 3: ModelRetry in tools for search refinement
    await demo_tool_retries()

    # Section 4: Dynamic system prompts with @agent.instructions
    await demo_dynamic_prompt()

    # Section 5: Complex dependencies bundled in AnalystContext
    await demo_complex_deps()

    # Section 6: format_as_xml for structured context
    await demo_format_as_xml()

    # Section 7: Exercise — full agent combining all patterns
    await demo_exercise()

    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. @agent.tool + RunContext[Deps] = dependency-injected tools")
    print("  2. @agent.tool_plain = stateless utility tools (no context)")
    print("  3. ModelRetry in tools = search refinement loop")
    print("  4. @agent.instructions = dynamic system prompt from deps")
    print("  5. AnalystContext bundles multiple services into one deps object")
    print("  6. format_as_xml = structured data injection LLMs parse well")
    print("  7. Access control via deps + dynamic prompts + tool guards")
    print()
    print("PATTERNS:")
    print(
        "  Tool retry:    tool('narrow') -> no results -> ModelRetry -> tool('broad')"
    )
    print("  Access control: deps.access_level checked in both prompts and tools")
    print("  Multi-source:  database + SEC + web -> cross-referenced analysis")
    print()
    print("Next: Module 04 — Conversation history and multi-turn agents")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
