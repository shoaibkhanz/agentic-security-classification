"""
MCP server exposing web search over simulated results.

Tools:
  - web_search: search the web for information about a security or issuer

Run:
  uv run python -m capstone.mcp_servers.web_search
"""

from __future__ import annotations

from fastmcp import FastMCP

from shared.fake_data import WEB_SEARCH_RESULTS
from shared.models import SearchResult

mcp = FastMCP("Web Search")


def _format_result(r: SearchResult) -> str:
    """Format a single search result into a readable string."""
    return (
        f"Title: {r.title}\n"
        f"URL: {r.url}\n"
        f"Snippet: {r.snippet}\n"
        f"Relevance: {r.relevance_score:.0%}"
    )


@mcp.tool()
def web_search(query: str) -> str:
    """Search the web for public information about a security or issuer.

    Args:
        query: Web search query (e.g. company name, security name, keywords).
    """
    query_lower = query.lower()

    # Check for matching pre-built results by keyword overlap
    for key, results in WEB_SEARCH_RESULTS.items():
        if any(word in query_lower for word in key.split() if len(word) > 3):
            sections = [_format_result(r) for r in results]
            return (
                f"Found {len(results)} web result(s) for '{query}':\n\n"
                + "\n\n---\n\n".join(sections)
            )

    # No matching results
    return (
        f"No specific web results for '{query}'.\n"
        "Limited public information available for this private security."
    )


if __name__ == "__main__":
    mcp.run()
