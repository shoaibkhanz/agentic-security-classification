"""
Module 00: Async Foundations — From Scratch, No Framework
=========================================================

Before touching pydantic-ai, we need to understand what async/await actually does
and why every serious agent framework is built on top of it.

Key insight: An AI agent is fundamentally an I/O-bound loop.
It sends a request to an LLM API, waits, processes the response, maybe calls tools
(more I/O), and loops. Async lets us do this efficiently without blocking.

Teaching approach (Paul Iusztin / Decoding AI):
  Build from scratch first. Understand the "why" before using any framework.

Sections:
  1. Sync vs Async — why async matters for agents
  2. The Event Loop — what asyncio.run() actually does
  3. Async Generators — how streaming works under the hood
  4. Async Context Managers — how run_stream() works
  5. Build a Manual Agent Loop — the pattern pydantic-ai abstracts
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx

# =============================================================================
# Section 1: Sync vs Async — Why This Matters for Agents
# =============================================================================
# An agent typically makes 3-10 I/O calls per interaction:
#   - LLM API call (100-2000ms)
#   - Tool calls: database queries, web searches, file reads (50-500ms each)
#   - Maybe delegate to another agent (another LLM call)
#
# With sync code, these happen sequentially. With async, independent calls
# can overlap. For agents with parallel tool execution, this is critical.


def sync_fetch_multiple(urls: list[str]) -> list[str]:
    """Fetch URLs sequentially. Each request blocks until complete."""
    results = []
    with httpx.Client() as client:
        for url in urls:
            response = client.get(url)
            results.append(f"{url}: {response.status_code}")
    return results


async def async_fetch_multiple(urls: list[str]) -> list[str]:
    """Fetch URLs concurrently. All requests fly in parallel."""
    async with httpx.AsyncClient() as client:
        # asyncio.gather runs all coroutines concurrently
        tasks = [client.get(url) for url in urls]
        responses = await asyncio.gather(*tasks)
        return [f"{url}: {r.status_code}" for url, r in zip(urls, responses)]


def demo_sync_vs_async() -> None:
    """Show the timing difference between sync and async I/O."""
    urls = [
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/1",
    ]

    # Sync: ~3 seconds (1s + 1s + 1s)
    print("--- Sync fetch (sequential) ---")
    start = time.perf_counter()
    sync_results = sync_fetch_multiple(urls)
    sync_duration = time.perf_counter() - start
    for r in sync_results:
        print(f"  {r}")
    print(f"  Duration: {sync_duration:.2f}s\n")

    # Async: ~1 second (all 3 in parallel)
    print("--- Async fetch (concurrent) ---")
    start = time.perf_counter()
    async_results = asyncio.run(async_fetch_multiple(urls))
    async_duration = time.perf_counter() - start
    for r in async_results:
        print(f"  {r}")
    print(f"  Duration: {async_duration:.2f}s\n")

    print(f"Speedup: {sync_duration / async_duration:.1f}x faster with async")
    print("This is why agent frameworks use async — tool calls run in parallel.\n")


# =============================================================================
# Section 2: The Event Loop — What asyncio.run() Does
# =============================================================================
# asyncio.run() creates an event loop, runs your coroutine, then closes the loop.
# The event loop is the scheduler that decides which coroutine runs when.
#
# Key mental model:
#   - `await` means "I'm waiting for I/O, let someone else run"
#   - The event loop picks up another ready coroutine
#   - When I/O completes, the event loop resumes the waiting coroutine
#
# This is cooperative multitasking — coroutines voluntarily yield at await points.


async def demonstrate_event_loop() -> None:
    """Show how the event loop interleaves coroutines."""

    async def worker(name: str, delay: float) -> str:
        print(f"  [{name}] Starting (will take {delay}s)")
        await asyncio.sleep(delay)  # Yields to event loop here
        print(f"  [{name}] Done")
        return f"{name} completed"

    print("--- Event loop interleaving ---")
    # These three workers run concurrently on a single thread
    results = await asyncio.gather(
        worker("LLM-Call", 0.3),
        worker("DB-Query", 0.1),
        worker("Web-Search", 0.2),
    )
    print(f"  Results: {results}")
    print("  Notice: DB-Query finished first despite being started second.\n")


# =============================================================================
# Section 3: Async Generators — How Streaming Works
# =============================================================================
# When you stream from an LLM, you get tokens one at a time.
# Under the hood, this is an async generator: a function that yields values
# asynchronously, pausing between yields to wait for the next chunk.
#
# pydantic-ai's `stream_text()` and `stream_output()` are async generators.


async def simulate_llm_stream(prompt: str) -> AsyncIterator[str]:
    """
    Simulate an LLM streaming response, token by token.

    In reality, this would be reading chunks from an HTTP response stream.
    The `async for` pattern lets us process each chunk as it arrives
    without buffering the entire response.
    """
    response_tokens = [
        "Based on ",
        "the offering ",
        "memorandum, ",
        "this security ",
        "appears to be ",
        "a convertible ",
        "note with ",
        "a 2-year ",
        "maturity.",
    ]
    for token in response_tokens:
        await asyncio.sleep(0.05)  # Simulate network delay between chunks
        yield token


async def demonstrate_streaming() -> None:
    """Show how async generators enable token-by-token processing."""
    print("--- Async generator streaming ---")
    print("  Response: ", end="", flush=True)

    # `async for` is the consumer pattern for async generators
    # Each iteration awaits the next yielded value
    full_response = ""
    async for token in simulate_llm_stream("Classify this security"):
        print(token, end="", flush=True)
        full_response += token

    print(f"\n  Full response length: {len(full_response)} chars")
    print("  This is how run_stream().stream_text() works under the hood.\n")


# =============================================================================
# Section 4: Async Context Managers — How run_stream() Works
# =============================================================================
# pydantic-ai's `agent.run_stream()` returns an async context manager.
# This pattern manages resources (HTTP connections, streaming state)
# that need cleanup when you're done.
#
# `async with` ensures cleanup happens even if an exception occurs.


@dataclass
class StreamingResponse:
    """Simulates the streaming response object from an LLM API."""

    prompt: str
    _connection_open: bool = False

    async def __aenter__(self) -> StreamingResponse:
        """Open the streaming connection."""
        self._connection_open = True
        print(f"  Connection opened for: {self.prompt!r}")
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Close the connection and clean up resources."""
        self._connection_open = False
        print("  Connection closed (resources cleaned up)")

    async def stream_text(self) -> AsyncIterator[str]:
        """Stream the response text token by token."""
        if not self._connection_open:
            raise RuntimeError("Connection not open — use `async with`")
        async for token in simulate_llm_stream(self.prompt):
            yield token


async def demonstrate_context_managers() -> None:
    """Show how async context managers manage streaming resources."""
    print("--- Async context managers ---")

    # This is the same pattern as pydantic-ai's run_stream:
    #   async with agent.run_stream(prompt) as response:
    #       async for text in response.stream_text():
    #           process(text)
    async with StreamingResponse("Analyze this offering") as response:
        full_text = ""
        async for token in response.stream_text():
            full_text += token
        print(f"  Received: {full_text}")

    print("  Notice: connection was automatically closed.\n")


# A more Pythonic way using @asynccontextmanager:
@asynccontextmanager
async def managed_llm_call(prompt: str) -> AsyncIterator[AsyncIterator[str]]:
    """
    Context manager wrapping an LLM streaming call.
    Handles connection setup and teardown.
    """
    print(f"  [Setup] Preparing call for: {prompt!r}")
    try:
        yield simulate_llm_stream(prompt)
    finally:
        print("  [Teardown] Cleaning up streaming resources")


# =============================================================================
# Section 5: Build a Manual Agent Loop — The Pattern pydantic-ai Abstracts
# =============================================================================
# This is the core insight: every agent framework is just a loop that:
#   1. Sends messages to an LLM
#   2. Checks if the LLM wants to call tools
#   3. Executes those tools (possibly in parallel)
#   4. Feeds results back to the LLM
#   5. Repeats until the LLM produces a final answer
#
# pydantic-ai wraps this with type safety, dependency injection,
# and structured output. But the loop is the same.


@dataclass
class LLMResponse:
    """Simulated LLM response that might contain tool calls."""

    content: str | None = None
    tool_calls: list[dict[str, str]] | None = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


# Simulated tools that an agent might use
AVAILABLE_TOOLS: dict[str, object] = {}


def tool(func: object) -> object:
    """Register a function as an available tool."""
    AVAILABLE_TOOLS[func.__name__] = func  # type: ignore[union-attr]
    return func


@tool
async def search_securities_db(query: str) -> str:
    """Search the securities database for matching records."""
    await asyncio.sleep(0.1)  # Simulate DB query latency
    # Simulated results
    if "acme" in query.lower():
        return "Found: ACME Growth Fund - Private equity fund, $50M AUM, Reg D 506(c)"
    return f"No results for: {query}"


@tool
async def check_sec_filings(issuer: str) -> str:
    """Check SEC EDGAR for filings related to the issuer."""
    await asyncio.sleep(0.1)  # Simulate API call latency
    if "acme" in issuer.lower():
        return "SEC Filing: Form D filed 2024-03-15, Exemption: Rule 506(c), Amount: $50,000,000"
    return f"No SEC filings found for: {issuer}"


async def call_llm(messages: list[dict[str, str]], turn: int = 0) -> LLMResponse:
    """
    Simulate an LLM API call.

    In production, this would be an httpx POST to the LLM provider's API.
    The LLM decides whether to call tools or produce a final answer.
    """
    await asyncio.sleep(0.1)  # Simulate API latency

    # Simulate the LLM's decision-making across turns
    if turn == 0:
        # First turn: LLM decides it needs to search the database
        return LLMResponse(
            tool_calls=[
                {
                    "name": "search_securities_db",
                    "args": '{"query": "ACME Growth Fund"}',
                },
                {"name": "check_sec_filings", "args": '{"issuer": "ACME Capital"}'},
            ]
        )
    else:
        # Second turn: LLM has enough info to answer
        return LLMResponse(
            content=(
                "Based on the database search and SEC filings, ACME Growth Fund "
                "is a private equity fund with $50M AUM, filed under Reg D 506(c). "
                "Classification: FUND_INTEREST. Confidence: 0.92."
            )
        )


async def execute_tool(tool_call: dict[str, str]) -> dict[str, str]:
    """Execute a single tool call and return the result."""
    tool_name = tool_call["name"]
    tool_fn = AVAILABLE_TOOLS.get(tool_name)
    if tool_fn is None:
        return {"role": "tool", "content": f"Error: Unknown tool {tool_name}"}

    # In a real implementation, we'd parse args from JSON
    # For simplicity, we call with a default arg
    import json

    args = json.loads(tool_call["args"])
    result = await tool_fn(**args)  # type: ignore[operator]
    return {"role": "tool", "name": tool_name, "content": result}


async def agent_loop(question: str) -> str:
    """
    A complete agent loop built from scratch.

    This is the EXACT pattern that pydantic-ai abstracts:
      1. Send messages to LLM
      2. If LLM returns tool calls → execute tools in parallel → loop
      3. If LLM returns content → return as final answer

    When you use pydantic-ai's Agent.run(), this is what happens under the hood,
    but with type safety, dependency injection, retries, and structured output.
    """
    messages: list[dict[str, str]] = [{"role": "user", "content": question}]
    turn = 0
    max_turns = 5  # Safety limit — production agents need this

    print(f"  User: {question}")

    while turn < max_turns:
        # Step 1: Call the LLM
        response = await call_llm(messages, turn=turn)

        if response.has_tool_calls:
            # Step 2: Execute all tool calls in parallel
            assert response.tool_calls is not None
            print(f"  Turn {turn}: LLM wants to call {len(response.tool_calls)} tools")

            # asyncio.gather runs tools concurrently — this is why async matters
            tool_results = await asyncio.gather(
                *[execute_tool(tc) for tc in response.tool_calls]
            )

            for result in tool_results:
                tool_name = result.get("name", "unknown")
                print(f"    Tool [{tool_name}]: {result['content'][:80]}...")
                messages.append(result)
        else:
            # Step 3: LLM produced a final answer
            assert response.content is not None
            print(f"  Turn {turn}: LLM produced final answer")
            print(f"  Answer: {response.content}")
            return response.content

        turn += 1

    raise RuntimeError(f"Agent exceeded max turns ({max_turns})")


async def demonstrate_agent_loop() -> None:
    """Run the manual agent loop."""
    print("--- Manual Agent Loop (what pydantic-ai abstracts) ---")
    result = await agent_loop("What type of security is the ACME Growth Fund?")
    print(f"\n  Final result: {result}")
    print("\n  This is exactly what `agent.run()` does under the hood.")
    print(
        "  pydantic-ai adds: type safety, deps injection, structured output, retries.\n"
    )


# =============================================================================
# Main: Run All Demonstrations
# =============================================================================


async def main() -> None:
    """Run all async demonstrations."""
    print("=" * 70)
    print("MODULE 00: ASYNC FOUNDATIONS")
    print("Understanding the patterns that pydantic-ai is built on")
    print("=" * 70)
    print()

    # Section 2: Event loop interleaving
    await demonstrate_event_loop()

    # Section 3: Async generators (streaming)
    await demonstrate_streaming()

    # Section 4: Async context managers (resource management)
    await demonstrate_context_managers()

    # Section 5: The complete agent loop
    await demonstrate_agent_loop()

    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. async/await enables concurrent I/O (tools run in parallel)")
    print("  2. Async generators power token-by-token streaming")
    print("  3. Async context managers handle connection lifecycle")
    print("  4. An agent is just a loop: prompt → LLM → tools → repeat")
    print("  5. pydantic-ai wraps this loop with production-grade features")
    print()
    print("Next: Module 01 — see how pydantic-ai turns this raw loop")
    print("into a typed, production-ready agent.")
    print("=" * 70)


if __name__ == "__main__":
    # Section 1 uses sync code, so run it outside asyncio
    print("=" * 70)
    print("MODULE 00: ASYNC FOUNDATIONS")
    print("=" * 70)
    print()

    # Uncomment the next line to run the sync vs async timing demo
    # (requires network access to httpbin.org — takes ~4 seconds)
    # demo_sync_vs_async()

    # Run the async demonstrations
    asyncio.run(main())
