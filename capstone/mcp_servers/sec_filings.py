"""
MCP server exposing SEC filing search.

Tools:
  - search_filings_by_issuer: find filings for a specific issuer
  - search_filings_by_type: find filings by filing type (Form D, Form C, etc.)

Run:
  uv run python -m capstone.mcp_servers.sec_filings
"""

from __future__ import annotations

from fastmcp import FastMCP

from shared.fake_data import SEC_FILINGS
from shared.models import SECAdvisory

mcp = FastMCP("SEC Filings")


def _format_filing(f: SECAdvisory) -> str:
    """Format a single SEC filing into a readable string."""
    lines = [
        f"Filing type: {f.filing_type}",
        f"Filing date: {f.filing_date}",
        f"Issuer: {f.issuer}",
        f"Exemption: {f.exemption_type.value}",
    ]
    if f.amount_raised is not None:
        lines.append(f"Amount raised: ${f.amount_raised:,.0f}")
    lines.append(f"Details: {f.details}")
    return "\n".join(lines)


@mcp.tool()
def search_filings_by_issuer(issuer: str) -> str:
    """Search SEC EDGAR filings by issuer name.

    Args:
        issuer: Name (or partial name) of the issuer to search for.
    """
    issuer_lower = issuer.lower()
    matches = [
        filing for filing in SEC_FILINGS if issuer_lower in filing.issuer.lower()
    ]

    if not matches:
        return f"No SEC filings found for issuer '{issuer}'."

    sections = [_format_filing(f) for f in matches]
    return f"Found {len(matches)} filing(s) for '{issuer}':\n\n" + "\n\n---\n\n".join(
        sections
    )


@mcp.tool()
def search_filings_by_type(filing_type: str) -> str:
    """Search SEC filings by filing type.

    Args:
        filing_type: Type of filing to search for (e.g. 'Form D', 'Form C', 'Form 1-A').
    """
    type_lower = filing_type.lower()
    matches = [
        filing for filing in SEC_FILINGS if filing.filing_type.lower() == type_lower
    ]

    if not matches:
        return f"No SEC filings found of type '{filing_type}'."

    sections = [_format_filing(f) for f in matches]
    return f"Found {len(matches)} '{filing_type}' filing(s):\n\n" + "\n\n---\n\n".join(
        sections
    )


if __name__ == "__main__":
    mcp.run()
