"""
Module 05b: MCP Tools — Build and Consume
==========================================

MCP (Model Context Protocol) is how agents connect to external tools
in a standardized way. Any MCP server works with any MCP client —
Desktop, pydantic-ai, Cursor, or your own apps.

In Module 03, you built tools with @agent.tool. Those tools are locked
to that specific agent. MCP tools are defined once, usable everywhere.

This module:
  1. Build a tool the old way (@agent.tool) — locked to one agent
  2. Build the same tool as an MCP server with FastMCP
  3. Consume the MCP server from pydantic-ai
  4. Compare: same agent, same task, different tool delivery

Teaching approach: See the same tool implemented both ways.
Understand what MCP adds (reusability, standardization) and what
it costs (process overhead, serialization).

Sections:
  1. The Old Way — @agent.tool (quick recap)
  2. Build an MCP Server with FastMCP
  3. Consume MCP from pydantic-ai
  4. Side-by-Side Comparison
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic_ai import Agent, RunContext

from shared.deps import SecuritiesDB
from shared.models import SecuritySummary


# =============================================================================
# Section 1: The Old Way — @agent.tool
# =============================================================================
# In Module 03, tools are defined as decorated methods on an agent.
# They're fast, simple, and direct. But they only work with THIS agent.

old_way_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=SecuritiesDB,
    output_type=SecuritySummary,
    system_prompt=(
        "You help analysts look up private securities. "
        "Use your tools to find and summarize securities."
    ),
)


@old_way_agent.tool
async def search_securities_direct(ctx: RunContext[SecuritiesDB], query: str) -> str:
    """
    Search the securities database for matching records.

    Args:
        query: Search term — security name, issuer, or keyword.
    """
    results = await ctx.deps.search(query)
    if not results:
        return f"No securities found matching '{query}'."

    formatted = []
    for sec in results[:3]:
        info = f"- {sec.name} (Issuer: {sec.issuer})"
        if sec.type_hint:
            info += f" | Type: {sec.type_hint}"
        if sec.offering_amount:
            info += f" | Amount: ${sec.offering_amount:,.0f}"
        formatted.append(info)

    return "Securities found:\n" + "\n".join(formatted)


@old_way_agent.tool
async def get_security_details_direct(ctx: RunContext[SecuritiesDB], name: str) -> str:
    """
    Get detailed information about a specific security.

    Args:
        name: The exact name of the security.
    """
    security = await ctx.deps.get_by_name(name)
    if security is None:
        return f"Security '{name}' not found."

    return (
        f"Name: {security.name}\n"
        f"Issuer: {security.issuer}\n"
        f"Type: {security.type_hint or 'Unknown'}\n"
        f"Description: {security.raw_description}\n"
        f"Exemption: {security.exemption.value}"
    )


# =============================================================================
# Section 2: Build an MCP Server with FastMCP
# =============================================================================
# FastMCP lets you define tools once as an MCP server.
# Any MCP-compatible client can connect and use them.
#
# The MCP server runs as a separate process. Tools are exposed via
# the MCP protocol (stdio or HTTP transport).
#
# NOTE: We define the server code here but write it to a separate file
# so it can be run as a subprocess by the MCP client.

MCP_SERVER_CODE = '''
"""
Securities Database MCP Server

This FastMCP server exposes securities search and lookup tools.
Any MCP client (Desktop, pydantic-ai, etc.) can connect.

Run with: uv run python securities_mcp_server.py
"""
from __future__ import annotations

from fastmcp import FastMCP

# Initialize the MCP server with a descriptive name
mcp = FastMCP("securities-data")

# We import our shared modules for the actual data
import sys
sys.path.insert(0, ".")
from shared.deps import SecuritiesDB
from shared.models import SecurityInfo

# Instantiate the database (in production, this would be a real DB connection)
db = SecuritiesDB()


@mcp.tool()
async def search_securities(query: str) -> str:
    """
    Search the securities database for matching records.

    Args:
        query: Search term — security name, issuer, or keyword.

    Returns:
        Formatted search results or a message if none found.
    """
    results = await db.search(query)
    if not results:
        return f"No securities found matching '{query}'."

    formatted = []
    for sec in results[:3]:
        info = f"- {sec.name} (Issuer: {sec.issuer})"
        if sec.type_hint:
            info += f" | Type: {sec.type_hint}"
        if sec.offering_amount:
            info += f" | Amount: ${sec.offering_amount:,.0f}"
        formatted.append(info)

    return "Securities found:\\n" + "\\n".join(formatted)


@mcp.tool()
async def get_security_details(name: str) -> str:
    """
    Get detailed information about a specific security by exact name.

    Args:
        name: The exact name of the security to look up.

    Returns:
        Detailed security information or not-found message.
    """
    security = await db.get_by_name(name)
    if security is None:
        return f"Security '{name}' not found."

    return (
        f"Name: {security.name}\\n"
        f"Issuer: {security.issuer}\\n"
        f"Type: {security.type_hint or 'Unknown'}\\n"
        f"Description: {security.raw_description}\\n"
        f"Exemption: {security.exemption.value}"
    )


@mcp.tool()
async def list_all_securities() -> str:
    """
    List all securities in the database.

    Returns:
        A formatted list of all available securities.
    """
    all_secs = await db.list_all()
    lines = [f"- {sec.name} ({sec.issuer})" for sec in all_secs]
    return f"Total securities: {len(all_secs)}\\n" + "\\n".join(lines)


if __name__ == "__main__":
    mcp.run()
'''


def write_mcp_server() -> Path:
    """Write the MCP server code to a file so it can run as a subprocess."""
    server_path = Path(__file__).parent / "securities_mcp_server.py"
    server_path.write_text(MCP_SERVER_CODE)
    print(f"  MCP server written to: {server_path}")
    return server_path


# =============================================================================
# Section 3: Consume MCP from pydantic-ai
# =============================================================================
# pydantic-ai connects to MCP servers via MCPServerStdio or MCPServerHTTP.
# The agent discovers available tools at runtime from the MCP server.
#
# Key difference from @agent.tool:
#   - Tools are NOT defined in Python code — they come from the MCP server
#   - The agent discovers tool schemas dynamically
#   - Any MCP server works — could be written in TypeScript, Rust, etc.

from pydantic_ai.mcp import MCPServerStdio  # noqa: E402


def create_mcp_agent(server_path: Path) -> Agent[None, SecuritySummary]:
    """
    Create an agent that gets its tools from an MCP server.

    The MCPServerStdio launches the MCP server as a subprocess
    and communicates via stdio.
    """
    mcp_server = MCPServerStdio(
        "uv",
        args=["run", "python", str(server_path)],
    )

    mcp_agent = Agent(
        "anthropic:sonnet-4-5-20250929",
        output_type=SecuritySummary,
        system_prompt=(
            "You help analysts look up private securities. "
            "Use your MCP tools to find and summarize securities."
        ),
        mcp_servers=[mcp_server],
    )

    return mcp_agent


# =============================================================================
# Section 4: Side-by-Side Comparison
# =============================================================================


async def demo_old_way() -> SecuritySummary:
    """Run the old-way agent with @agent.tool."""
    print("--- Old Way: @agent.tool (tools locked to this agent) ---")
    db = SecuritiesDB()
    result = await old_way_agent.run(
        "Look up the NovaTech SAFE Round and summarize it",
        deps=db,
    )
    print(f"  Result: {result.output}")
    print(f"  Usage: {result.usage()}")
    return result.output


async def demo_mcp_way(server_path: Path) -> SecuritySummary:
    """Run the MCP agent with tools from the MCP server."""
    print("\n--- MCP Way: Tools from MCP server (reusable across clients) ---")

    mcp_agent = create_mcp_agent(server_path)

    # MCP servers need to be started as async context managers
    async with mcp_agent:
        result = await mcp_agent.run(
            "Look up the NovaTech SAFE Round and summarize it",
        )
        print(f"  Result: {result.output}")
        print(f"  Usage: {result.usage()}")
        return result.output


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    print("=" * 70)
    print("MODULE 05b: MCP TOOLS — BUILD AND CONSUME")
    print("Same tools, two delivery mechanisms")
    print("=" * 70)
    print()

    # Step 1: Write the MCP server file
    print("Step 1: Write MCP server to disk")
    server_path = write_mcp_server()
    print()

    # Step 2: Run with old-way tools (@agent.tool)
    old_result = await demo_old_way()
    print()

    # Step 3: Run with MCP tools
    print("Step 2: Connect to MCP server and run agent")
    mcp_result = await demo_mcp_way(server_path)
    print()

    # Step 4: Compare
    print("--- Comparison ---")
    print(f"  Old way result: {old_result.name} - {old_result.security_type}")
    print(f"  MCP way result: {mcp_result.name} - {mcp_result.security_type}")
    print()
    print("  Same query, same results, different delivery:")
    print("  @agent.tool  → Fast, simple, locked to this agent")
    print("  MCP server   → Reusable across any MCP client")
    print("               → Desktop, Cursor, other agents")
    print("               → Can be written in any language")
    print("               → Process overhead for subprocess communication")

    print()
    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. MCP = standard protocol for tools, any server + any client")
    print("  2. FastMCP makes building MCP servers as easy as @agent.tool")
    print("  3. pydantic-ai connects via MCPServerStdio or MCPServerHTTP")
    print("  4. Use @agent.tool for agent-specific tools (fast, simple)")
    print("  5. Use MCP for reusable tools shared across applications")
    print()
    print("CAPSTONE CONNECTION:")
    print("  The capstone's tools (web search, SQL, SEC advisory)")
    print("  will be built as MCP servers — reusable beyond the capstone.")
    print()
    print("Next: Module 06 — Multi-agent orchestration")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
