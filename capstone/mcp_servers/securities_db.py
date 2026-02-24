"""
MCP server exposing the securities database.

Tools:
  - search_securities: fuzzy search by name, issuer, or description
  - get_security_details: exact lookup by security name
  - query_sql: simple SQL-like query against the database

Run:
  uv run python -m capstone.mcp_servers.securities_db
"""

from __future__ import annotations

from fastmcp import FastMCP

from shared.fake_data import SECURITIES_DATABASE
from shared.models import SecurityInfo

mcp = FastMCP("Securities Database")


def _format_security(sec: SecurityInfo) -> str:
    """Format a single security record into a readable string."""
    lines = [
        f"Name: {sec.name}",
        f"Issuer: {sec.issuer}",
    ]
    if sec.type_hint:
        lines.append(f"Type hint: {sec.type_hint}")
    if sec.offering_amount is not None:
        lines.append(f"Offering amount: ${sec.offering_amount:,.0f}")
    if sec.min_investment is not None:
        lines.append(f"Min investment: ${sec.min_investment:,.0f}")
    if sec.offering_date:
        lines.append(f"Offering date: {sec.offering_date}")
    if sec.maturity_date:
        lines.append(f"Maturity date: {sec.maturity_date}")
    if sec.interest_rate is not None:
        lines.append(f"Interest rate: {sec.interest_rate:.1%}")
    if sec.conversion_terms:
        lines.append(f"Conversion terms: {sec.conversion_terms}")
    if sec.exemption.value != "unknown":
        lines.append(f"Exemption: {sec.exemption.value}")
    lines.append(f"Description: {sec.raw_description}")
    return "\n".join(lines)


@mcp.tool()
def search_securities(query: str) -> str:
    """Search the securities database by name, issuer, or description keywords.

    Args:
        query: Search term -- security name, issuer, or keywords.
    """
    query_lower = query.lower()
    matches = [
        sec
        for sec in SECURITIES_DATABASE
        if query_lower in sec.name.lower()
        or query_lower in sec.issuer.lower()
        or query_lower in sec.raw_description.lower()
    ]

    if not matches:
        return f"No securities found matching '{query}'."

    sections = []
    for sec in matches[:5]:
        sections.append(_format_security(sec))

    return f"Found {len(matches)} result(s):\n\n" + "\n\n---\n\n".join(sections)


@mcp.tool()
def get_security_details(name: str) -> str:
    """Get full details for a security by its exact name.

    Args:
        name: Exact name of the security (case-insensitive).
    """
    for sec in SECURITIES_DATABASE:
        if sec.name.lower() == name.lower():
            return _format_security(sec)

    # Fall back to partial match
    name_lower = name.lower()
    partials = [s for s in SECURITIES_DATABASE if name_lower in s.name.lower()]
    if partials:
        return f"No exact match for '{name}'. Did you mean one of these?\n" + "\n".join(
            f"  - {s.name}" for s in partials
        )

    return f"No security found with name '{name}'."


@mcp.tool()
def query_sql(sql: str) -> str:
    """Run a SQL-like query against the securities database.

    This is a simplified SQL simulator. It searches all securities
    whose fields contain any significant word from the WHERE clause.

    Args:
        sql: SQL query (e.g. SELECT * FROM securities WHERE issuer LIKE '%Atlas%').
    """
    sql_lower = sql.lower()

    if "where" in sql_lower:
        results = []
        for sec in SECURITIES_DATABASE:
            sec_dict = sec.model_dump()
            for field_value in sec_dict.values():
                if isinstance(field_value, str) and any(
                    word in field_value.lower()
                    for word in sql_lower.split()
                    if len(word) > 3
                ):
                    results.append(sec)
                    break
    else:
        results = list(SECURITIES_DATABASE[:5])

    if not results:
        return "No results returned from query."

    rows = []
    for sec in results[:5]:
        row_parts = [f"name: {sec.name}", f"issuer: {sec.issuer}"]
        if sec.type_hint:
            row_parts.append(f"type_hint: {sec.type_hint}")
        if sec.exemption.value != "unknown":
            row_parts.append(f"exemption: {sec.exemption.value}")
        if sec.offering_amount is not None:
            row_parts.append(f"offering_amount: ${sec.offering_amount:,.0f}")
        rows.append(" | ".join(row_parts))

    return f"Query returned {len(results)} row(s):\n" + "\n".join(
        f"  {i + 1}. {row}" for i, row in enumerate(rows)
    )


if __name__ == "__main__":
    mcp.run()
