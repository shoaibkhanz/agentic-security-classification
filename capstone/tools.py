"""
Capstone tools for the classification agents.

These tools connect agents to external data sources:
- Securities database (SQL-like queries)
- SEC filing search
- Web search
- User questions (simulated)

Tools are defined as @agent.tool functions on the researcher agent.
The same data sources are also available as MCP servers
(see capstone/mcp_servers/).
"""

from __future__ import annotations

from pydantic_ai import RunContext

from shared.deps import AnalystContext


async def search_securities_db(
    ctx: RunContext[AnalystContext],
    query: str,
) -> str:
    """
    Search the securities database for information about a security.

    Args:
        query: Search term — security name, issuer, or keywords.
    """
    results = await ctx.deps.db.search(query)
    if not results:
        return f"No securities found matching '{query}'."

    formatted = []
    for sec in results[:3]:
        info = f"- {sec.name} | Issuer: {sec.issuer}"
        if sec.type_hint:
            info += f" | Type hint: {sec.type_hint}"
        if sec.interest_rate:
            info += f" | Interest: {sec.interest_rate:.1%}"
        if sec.conversion_terms:
            info += f" | Conversion: {sec.conversion_terms}"
        if sec.exemption.value != "unknown":
            info += f" | Exemption: {sec.exemption.value}"
        if sec.offering_amount:
            info += f" | Amount: ${sec.offering_amount:,.0f}"
        info += f"\n  Description: {sec.raw_description[:300]}"
        formatted.append(info)

    return "\n\n".join(formatted)


async def query_securities_sql(
    ctx: RunContext[AnalystContext],
    sql_query: str,
) -> str:
    """
    Run a SQL-like query against the securities database.

    Args:
        sql_query: SQL query (e.g., SELECT * FROM securities WHERE issuer LIKE '%Atlas%').
    """
    results = await ctx.deps.db.query(sql_query)
    if not results:
        return "No results returned from query."

    formatted = []
    for row in results[:5]:
        row_str = " | ".join(
            f"{k}: {v}"
            for k, v in row.items()
            if v is not None and k not in ("raw_description",)
        )
        formatted.append(f"- {row_str}")

    return "\n".join(formatted)


async def search_sec_filings(
    ctx: RunContext[AnalystContext],
    issuer: str,
) -> str:
    """
    Search SEC EDGAR filings for a specific issuer.

    Args:
        issuer: Name of the issuer to search for.
    """
    filings = await ctx.deps.sec_search.search_by_issuer(issuer)
    if not filings:
        return f"No SEC filings found for '{issuer}'."

    formatted = []
    for f in filings:
        info = (
            f"- {f.filing_type} ({f.filing_date}) | "
            f"Issuer: {f.issuer} | "
            f"Exemption: {f.exemption_type.value}"
        )
        if f.amount_raised:
            info += f" | Raised: ${f.amount_raised:,.0f}"
        info += f"\n  Details: {f.details}"
        formatted.append(info)

    return "\n\n".join(formatted)


async def search_web(
    ctx: RunContext[AnalystContext],
    query: str,
) -> str:
    """
    Search the web for public information about a security or issuer.

    Args:
        query: Web search query.
    """
    results = await ctx.deps.web_search.search(query)
    if not results:
        return f"No web results for '{query}'."

    formatted = []
    for r in results[:3]:
        formatted.append(
            f"- [{r.title}]({r.url})\n"
            f"  {r.snippet}\n"
            f"  Relevance: {r.relevance_score:.0%}"
        )

    return "\n\n".join(formatted)


async def ask_user_question(
    ctx: RunContext[AnalystContext],
    question: str,
) -> str:
    """
    Ask the analyst/user a question to gather more information.

    Args:
        question: The question to ask about the security.
    """
    # In production, this would pause for real user input.
    # For the capstone demo, we simulate answers based on the question.
    question_lower = question.lower()

    if "maturity" in question_lower or "term" in question_lower:
        return (
            "The instrument has standard terms for its type. "
            "Maturity details should be in the offering documents."
        )
    elif "issuer" in question_lower or "company" in question_lower:
        return (
            "The issuer is a private company. Limited public information is available."
        )
    elif "convert" in question_lower:
        return (
            "Conversion terms are specified in the offering documents. "
            "Please check the security description for details."
        )
    elif "risk" in question_lower or "guarantee" in question_lower:
        return (
            "No investment is guaranteed. Any claims of guaranteed returns "
            "should be treated with extreme caution."
        )
    elif "exemption" in question_lower or "reg" in question_lower:
        return (
            "The filing should indicate the registration exemption. "
            "Check the SEC filing search results."
        )
    else:
        return (
            "I have limited additional information about this security. "
            "The offering documents and SEC filings are the primary sources."
        )
