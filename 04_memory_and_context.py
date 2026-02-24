"""
Module 04: Memory and Context Management
=========================================

An agent without memory is like an analyst who forgets what they just
researched. This module teaches the four types of agent memory and when
to use each one:

  1. Short-term memory — message_history carries conversation across runs
  2. Working memory  — a Python dataclass accumulating structured findings
  3. Long-term memory — persisting discoveries to disk (JSON) between sessions
  4. Context window management — history_processors trim what the model sees

These four layers work together. A production agent typically uses all of
them: message_history for turn-to-turn continuity, a working-memory
dataclass for structured state, a persistence layer for cross-session
recall, and history_processors to keep the context window focused.

Sections:
  1. Short-Term Memory: message_history
  2. Working Memory: Structured Findings Dataclass
  3. Long-Term Memory: JSON Persistence
  4. Context Window Management: history_processors
  5. Putting It All Together: Multi-Turn Investigation Agent
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pydantic_ai import Agent, ModelMessage, RunContext
from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelRequest, ModelResponse

from shared.deps import AnalystContext


# =============================================================================
# Section 1: Short-Term Memory — message_history
# =============================================================================
# When you call agent.run(), the agent has no memory of previous runs.
# Each run starts fresh. To maintain conversation continuity, you pass
# the previous run's messages into the next run.
#
# Two key methods on every result:
#   result.new_messages()  — only the messages from THIS run (excludes
#                            prior history you passed in)
#   result.all_messages()  — the complete conversation (prior history +
#                            this run's messages)
#
# Typical pattern:
#   result1 = agent.run_sync("first question")
#   result2 = agent.run_sync("follow up", message_history=result1.new_messages())
#   # result2 now has context of result1

memory_demo_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    system_prompt=(
        "You are a securities analyst assistant. When the user asks follow-up "
        "questions, use context from earlier in the conversation to give "
        "informed answers. Keep responses concise (2-3 sentences)."
    ),
)


def demo_short_term_memory() -> None:
    """Demonstrate multi-turn conversation with message_history."""
    print("=" * 70)
    print("SECTION 1: SHORT-TERM MEMORY (message_history)")
    print("=" * 70)
    print()

    # --- First run: ask about a security ---
    print("[Turn 1] User: What is a SAFE instrument in private securities?")
    result1 = memory_demo_agent.run_sync(
        "What is a SAFE instrument in private securities?"
    )
    print(f"[Turn 1] Agent: {result1.output}")
    print()

    # Inspect message counts
    print(f"  new_messages() count: {len(result1.new_messages())}")
    print(f"  all_messages() count: {len(result1.all_messages())}")
    print()

    # --- Second run: follow-up referencing the first answer ---
    # Pass new_messages() to carry context forward.
    # new_messages() gives us only this run's messages (system prompt + user + response).
    # This is usually what you want: it avoids duplicating the system prompt
    # if the agent re-generates it each run.
    print("[Turn 2] User: How does it differ from a convertible note?")
    result2 = memory_demo_agent.run_sync(
        "How does it differ from a convertible note?",
        message_history=result1.new_messages(),
    )
    print(f"[Turn 2] Agent: {result2.output}")
    print()

    # Now result2.all_messages() contains the FULL conversation
    print(f"  all_messages() count after turn 2: {len(result2.all_messages())}")
    print()

    # --- Third run: another follow-up ---
    # Chain again: pass new_messages() from result2 so the agent sees
    # turns 1 and 2 as context.
    print("[Turn 3] User: Which would be better for a seed-stage startup?")
    result3 = memory_demo_agent.run_sync(
        "Which would be better for a seed-stage startup?",
        message_history=result2.new_messages(),
    )
    print(f"[Turn 3] Agent: {result3.output}")
    print()

    # The full conversation is available
    all_msgs = result3.all_messages()
    print(f"  Total messages in conversation: {len(all_msgs)}")
    print("  Message types: " + ", ".join(type(m).__name__ for m in all_msgs))
    print()


# =============================================================================
# Section 2: Working Memory — Structured Findings Dataclass
# =============================================================================
# Short-term memory (message_history) carries raw conversation text.
# But agents often need STRUCTURED state: a running tally of findings,
# a confidence score, a list of questions still to ask.
#
# Working memory is a plain Python dataclass that you maintain alongside
# the agent. Tools update it. The agent's system prompt reads from it.
# This is not pydantic-ai magic — it's just good software design.


@dataclass
class InvestigationMemory:
    """
    Working memory for a securities investigation.

    This accumulates structured findings across multiple agent runs.
    Each tool call can append to findings, update confidence, etc.
    The system prompt reads from this to keep the agent aware of
    what it has already discovered.
    """

    security_name: str = ""
    findings: list[str] = field(default_factory=list)
    evidence_sources: list[str] = field(default_factory=list)
    candidate_categories: list[str] = field(default_factory=list)
    confidence: float = 0.0
    questions_asked: int = 0
    unresolved_questions: list[str] = field(default_factory=list)

    def add_finding(self, finding: str, source: str) -> None:
        """Record a new finding with its source."""
        self.findings.append(finding)
        self.evidence_sources.append(source)

    def update_confidence(self, delta: float) -> None:
        """Adjust confidence, clamping to [0, 1]."""
        self.confidence = max(0.0, min(1.0, self.confidence + delta))

    def summary(self) -> str:
        """Produce a human-readable summary for the system prompt."""
        lines = [f"Investigation: {self.security_name or 'Not yet identified'}"]
        lines.append(f"Confidence: {self.confidence:.0%}")
        lines.append(f"Questions asked so far: {self.questions_asked}")

        if self.findings:
            lines.append("Findings so far:")
            for i, f in enumerate(self.findings, 1):
                lines.append(f"  {i}. {f} (source: {self.evidence_sources[i - 1]})")

        if self.candidate_categories:
            lines.append(
                f"Candidate categories: {', '.join(self.candidate_categories)}"
            )

        if self.unresolved_questions:
            lines.append("Still need to determine:")
            for q in self.unresolved_questions:
                lines.append(f"  - {q}")

        return "\n".join(lines)


# Agent that uses working memory via dynamic system prompt
working_memory_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=AnalystContext,
    system_prompt=(
        "You are a securities classification analyst. You are conducting "
        "a step-by-step investigation to classify a private security. "
        "Use the available tools to gather information. Be systematic: "
        "search the database first, then check SEC filings, then web search."
    ),
)

# We store working memory outside the agent — it is OUR state, not the model's.
# The agent sees it through the dynamic system prompt.
_working_memory = InvestigationMemory()


@working_memory_agent.instructions
async def inject_working_memory(ctx: RunContext[AnalystContext]) -> str:
    """
    Dynamic system prompt that injects working memory state.

    This runs before every LLM call. The model sees the current state
    of our investigation, so it knows what has already been discovered
    and what still needs to be determined.
    """
    return (
        f"\nAnalyst: {ctx.deps.analyst_name}\n"
        f"\n--- Current Investigation State ---\n"
        f"{_working_memory.summary()}\n"
        f"-----------------------------------\n"
    )


@working_memory_agent.tool
async def search_security_db(ctx: RunContext[AnalystContext], query: str) -> str:
    """
    Search the securities database.

    Args:
        query: Search term — security name, issuer, or keyword.
    """
    results = await ctx.deps.db.search(query)
    _working_memory.questions_asked += 1

    if not results:
        return f"No securities found for '{query}'."

    # Update working memory with findings
    for sec in results[:2]:
        finding = f"{sec.name} by {sec.issuer}"
        if sec.type_hint:
            finding += f" (type hint: {sec.type_hint})"
        _working_memory.add_finding(finding, "securities_db")
        _working_memory.security_name = _working_memory.security_name or sec.name
        _working_memory.update_confidence(0.15)

    # Format for LLM
    lines = []
    for sec in results[:3]:
        info = f"- {sec.name} | Issuer: {sec.issuer}"
        if sec.type_hint:
            info += f" | Type: {sec.type_hint}"
        if sec.offering_amount:
            info += f" | Amount: ${sec.offering_amount:,.0f}"
        info += f"\n  Description: {sec.raw_description[:150]}"
        lines.append(info)

    return "Database results:\n" + "\n".join(lines)


@working_memory_agent.tool
async def search_sec_filings(ctx: RunContext[AnalystContext], issuer: str) -> str:
    """
    Search SEC EDGAR filings for an issuer.

    Args:
        issuer: Name of the issuing entity to search for.
    """
    filings = await ctx.deps.sec_search.search_by_issuer(issuer)
    _working_memory.questions_asked += 1

    if not filings:
        return f"No SEC filings found for '{issuer}'."

    for filing in filings[:2]:
        finding = (
            f"SEC {filing.filing_type}: {filing.exemption_type.value}, "
            f"filed {filing.filing_date}"
        )
        _working_memory.add_finding(finding, "sec_edgar")
        _working_memory.update_confidence(0.2)

    lines = []
    for f in filings[:3]:
        lines.append(
            f"- {f.filing_type} | Filed: {f.filing_date} | "
            f"Exemption: {f.exemption_type.value} | Details: {f.details}"
        )

    return "SEC Filings:\n" + "\n".join(lines)


@working_memory_agent.tool
async def web_search(ctx: RunContext[AnalystContext], query: str) -> str:
    """
    Search the web for information about a security or issuer.

    Args:
        query: Search query about the security.
    """
    results = await ctx.deps.web_search.search(query)
    _working_memory.questions_asked += 1

    if not results or results[0].relevance_score < 0.3:
        return f"No relevant web results for '{query}'."

    for r in results[:2]:
        _working_memory.add_finding(
            f"Web: {r.title} — {r.snippet[:100]}",
            "web_search",
        )
        _working_memory.update_confidence(0.1)

    lines = [f"- [{r.title}]({r.url}): {r.snippet}" for r in results[:3]]
    return "Web results:\n" + "\n".join(lines)


async def demo_working_memory() -> None:
    """Demonstrate working memory accumulation across agent runs."""
    print("=" * 70)
    print("SECTION 2: WORKING MEMORY (structured dataclass)")
    print("=" * 70)
    print()

    global _working_memory
    _working_memory = InvestigationMemory()  # Reset for this demo

    deps = AnalystContext.create(analyst_name="Dr. Martinez")

    # Run 1: Start the investigation
    print("[Run 1] User: Investigate the NovaTech SAFE Round")
    result1 = await working_memory_agent.run(
        "Search the database for the NovaTech SAFE Round and tell me what you find.",
        deps=deps,
    )
    print(f"[Run 1] Agent: {result1.output[:300]}...")
    print()
    print("  Working memory after run 1:")
    print(f"    Findings: {len(_working_memory.findings)}")
    print(f"    Confidence: {_working_memory.confidence:.0%}")
    print(f"    Questions asked: {_working_memory.questions_asked}")
    print()

    # Run 2: Dig deeper — the agent's dynamic prompt now shows what we found
    print("[Run 2] User: Check SEC filings for NovaTech")
    result2 = await working_memory_agent.run(
        "Now check SEC filings for NovaTech AI Inc to verify the exemption type.",
        deps=deps,
        message_history=result1.new_messages(),
    )
    print(f"[Run 2] Agent: {result2.output[:300]}...")
    print()
    print("  Working memory after run 2:")
    print(f"    Findings: {len(_working_memory.findings)}")
    print(f"    Confidence: {_working_memory.confidence:.0%}")
    print(f"    Questions asked: {_working_memory.questions_asked}")
    print()

    # Show the full working memory state
    print("  --- Full Working Memory ---")
    print(f"  {_working_memory.summary()}")
    print()


# =============================================================================
# Section 3: Long-Term Memory — JSON Persistence
# =============================================================================
# Working memory lives in RAM — it vanishes when the process ends.
# Long-term memory persists to disk so the agent remembers across sessions.
#
# pydantic-ai provides ModelMessagesTypeAdapter for serializing message
# history to/from JSON. Combined with a JSON file for working-memory
# state, you get full session persistence.
#
# Pattern:
#   1. On startup: load previous session from JSON
#   2. During the session: accumulate findings in working memory
#   3. On shutdown: save working memory + message history to JSON

MEMORY_FILE = Path(__file__).parent / "investigation_memory.json"


@dataclass
class PersistentMemory:
    """
    Long-term memory that persists between sessions.

    Stores both structured findings and raw message history
    so the agent can resume an investigation later.
    """

    security_name: str = ""
    findings: list[str] = field(default_factory=list)
    evidence_sources: list[str] = field(default_factory=list)
    confidence: float = 0.0
    last_updated: str = ""
    session_count: int = 0
    message_history_json: list[dict] = field(default_factory=list)

    def save(self, filepath: Path, messages: list[ModelMessage] | None = None) -> None:
        """
        Persist memory to a JSON file.

        This uses pydantic-ai's ModelMessagesTypeAdapter to serialize
        the message history. The adapter handles all the complex message
        types (system prompts, tool calls, etc.) correctly.
        """
        self.last_updated = datetime.now().isoformat()
        self.session_count += 1

        data = {
            "security_name": self.security_name,
            "findings": self.findings,
            "evidence_sources": self.evidence_sources,
            "confidence": self.confidence,
            "last_updated": self.last_updated,
            "session_count": self.session_count,
        }

        # Serialize message history using pydantic-ai's type adapter
        if messages:
            from pydantic_core import to_jsonable_python

            data["message_history"] = to_jsonable_python(messages)

        filepath.write_text(json.dumps(data, indent=2, default=str))

    @classmethod
    def load(cls, filepath: Path) -> tuple[PersistentMemory, list[ModelMessage]]:
        """
        Load memory from a JSON file.

        Returns both the structured memory and the deserialized
        message history, ready to pass to agent.run().
        """
        if not filepath.exists():
            return cls(), []

        data = json.loads(filepath.read_text())

        memory = cls(
            security_name=data.get("security_name", ""),
            findings=data.get("findings", []),
            evidence_sources=data.get("evidence_sources", []),
            confidence=data.get("confidence", 0.0),
            last_updated=data.get("last_updated", ""),
            session_count=data.get("session_count", 0),
        )

        # Deserialize message history using pydantic-ai's type adapter
        messages: list[ModelMessage] = []
        if "message_history" in data:
            messages = ModelMessagesTypeAdapter.validate_python(data["message_history"])

        return memory, messages


def demo_long_term_memory() -> None:
    """Demonstrate saving and loading agent memory across sessions."""
    print("=" * 70)
    print("SECTION 3: LONG-TERM MEMORY (JSON persistence)")
    print("=" * 70)
    print()

    # Simulate Session 1: discover some facts and save
    print("--- Session 1: Initial Investigation ---")
    memory = PersistentMemory(security_name="Atlas Senior Secured Notes 2024")
    memory.findings = [
        "Senior secured notes from Atlas Infrastructure Corp",
        "8.5% annual interest, 3-year term",
        "SEC Form D filed under Reg D 506(b)",
    ]
    memory.evidence_sources = ["securities_db", "securities_db", "sec_edgar"]
    memory.confidence = 0.75

    # Run the agent to get a real message history
    agent = Agent(
        "anthropic:sonnet-4-5-20250929",
        system_prompt="You are a securities analyst. Be concise.",
    )
    result = agent.run_sync(
        "Summarize what we know about Atlas Senior Secured Notes 2024: "
        "They are senior secured notes from Atlas Infrastructure Corp, "
        "8.5% annual interest, 3-year term, filed under Reg D 506(b)."
    )
    print(f"  Agent summary: {result.output[:200]}...")
    print()

    # Save everything to disk
    memory.save(MEMORY_FILE, messages=result.all_messages())
    print(f"  Saved to: {MEMORY_FILE}")
    print(f"  File size: {MEMORY_FILE.stat().st_size} bytes")
    print()

    # Simulate Session 2: load and continue
    print("--- Session 2: Resume Investigation ---")
    loaded_memory, loaded_messages = PersistentMemory.load(MEMORY_FILE)

    print(f"  Loaded security: {loaded_memory.security_name}")
    print(f"  Loaded findings: {len(loaded_memory.findings)}")
    print(f"  Loaded confidence: {loaded_memory.confidence:.0%}")
    print(f"  Loaded messages: {len(loaded_messages)}")
    print(f"  Sessions so far: {loaded_memory.session_count}")
    print()

    # Continue the conversation using loaded history
    result2 = agent.run_sync(
        "Given what we discussed, what SEC exemption type is this? "
        "And what security category would you classify it as?",
        message_history=loaded_messages,
    )
    print(f"  Continued conversation: {result2.output[:300]}...")
    print()

    # Clean up the demo file
    if MEMORY_FILE.exists():
        MEMORY_FILE.unlink()
        print(f"  Cleaned up: {MEMORY_FILE}")
    print()


# =============================================================================
# Section 4: Context Window Management — history_processors
# =============================================================================
# As conversations grow, they can exceed the model's context window or
# become expensive. history_processors let you trim or transform the
# message history before each LLM call.
#
# A history_processor is a function with one of these signatures:
#   (messages: list[ModelMessage]) -> list[ModelMessage]
#   (ctx: RunContext, messages: list[ModelMessage]) -> list[ModelMessage]
#
# Both sync and async variants are supported. Processors run in sequence.
#
# IMPORTANT: The processed history must:
#   - Not be empty
#   - End with a ModelRequest (user message)


def keep_recent_messages(messages: list[ModelMessage]) -> list[ModelMessage]:
    """
    Simple truncation: keep only the last N message pairs.

    This is the simplest history processor. It discards old turns to
    keep the context window small. The system prompt (in the first
    ModelRequest) is always re-injected by pydantic-ai, so we don't
    need to worry about losing it.

    Production notes:
    - This is a blunt instrument — it loses important context
    - Better approaches: summarize old turns, keep tool results
    - Always keep the LAST message (must end with ModelRequest)
    """
    max_messages = 6  # Keep last 3 turn pairs (request + response)

    if len(messages) <= max_messages:
        return messages

    # Always keep the most recent messages
    return messages[-max_messages:]


def summarize_old_context(
    messages: list[ModelMessage],
) -> list[ModelMessage]:
    """
    Smarter truncation: preserve a summary of old context.

    Instead of just dropping old messages, we extract key facts from
    them and prepend a summary. This loses detail but retains the
    important discoveries.

    Production note: In a real system, you might call a small/cheap
    model to generate this summary. Here we do rule-based extraction.
    """
    max_recent = 4  # Keep last 2 turn pairs

    if len(messages) <= max_recent:
        return messages

    # Extract key content from old messages we're about to drop
    old_messages = messages[:-max_recent]
    key_facts = []

    for msg in old_messages:
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    # Extract first sentence as a key fact
                    first_sentence = part.content.split(".")[0] + "."
                    if len(first_sentence) > 20:  # Skip very short fragments
                        key_facts.append(first_sentence)

    # If we extracted facts, inject them as context in the first
    # of the remaining messages
    recent_messages = messages[-max_recent:]

    if key_facts:
        # Create a summary that will be part of the first remaining request
        summary = (
            "[Context from earlier in conversation: " + " | ".join(key_facts[:5]) + "]"
        )
        # Inject by modifying the first remaining request's user prompt
        if isinstance(recent_messages[0], ModelRequest):
            for part in recent_messages[0].parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    part.content = summary + "\n\n" + part.content
                    break

    return recent_messages


# Agent with history processors
managed_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    system_prompt=(
        "You are a securities analyst conducting a detailed investigation. "
        "Use context from earlier in the conversation to inform your answers. "
        "Keep responses concise."
    ),
    # Processors run in sequence: first summarize, then truncate
    history_processors=[keep_recent_messages],
)


def demo_context_management() -> None:
    """Demonstrate history_processors for context window management."""
    print("=" * 70)
    print("SECTION 4: CONTEXT WINDOW MANAGEMENT (history_processors)")
    print("=" * 70)
    print()

    # Build a long conversation that would fill a context window
    print("Building a multi-turn conversation...")
    print()

    questions = [
        "What are the main types of private securities?",
        "Tell me more about SAFE instruments specifically.",
        "How do SAFE instruments compare to convertible notes?",
        "What SEC exemptions are typically used for SAFEs?",
        "What risks should investors watch for with SAFEs?",
        "Can you summarize everything we've discussed about SAFEs?",
    ]

    history: list[ModelMessage] = []

    for i, question in enumerate(questions):
        print(f"[Turn {i + 1}] User: {question}")

        result = managed_agent.run_sync(
            question,
            message_history=history if history else None,
        )

        # The agent sees a TRIMMED version of history (thanks to
        # history_processors), but we keep the FULL history for
        # our records.
        history = result.all_messages()

        print(f"[Turn {i + 1}] Agent: {result.output[:150]}...")
        print(
            f"  (Full history: {len(history)} messages, processor would trim to <={6})"
        )
        print()

    print(f"Final conversation length: {len(history)} messages")
    print(
        "Without history_processors, all messages would be sent to the model.\n"
        "With keep_recent_messages, only the last 6 are sent — saving tokens\n"
        "and keeping the model focused on the current topic."
    )
    print()


# =============================================================================
# Section 5: Putting It All Together — Multi-Turn Investigation Agent
# =============================================================================
# This combines all four memory types into a complete investigation agent:
#   - message_history for turn-to-turn continuity
#   - InvestigationMemory for structured working memory
#   - JSON persistence for cross-session recall
#   - history_processors to keep the context focused

INVESTIGATION_FILE = Path(__file__).parent / "active_investigation.json"


@dataclass
class InvestigationState:
    """Complete investigation state combining all memory types."""

    memory: InvestigationMemory = field(default_factory=InvestigationMemory)
    message_history: list[ModelMessage] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def save(self, filepath: Path) -> None:
        """Persist the full investigation state to JSON."""
        from pydantic_core import to_jsonable_python

        data = {
            "memory": {
                "security_name": self.memory.security_name,
                "findings": self.memory.findings,
                "evidence_sources": self.memory.evidence_sources,
                "candidate_categories": self.memory.candidate_categories,
                "confidence": self.memory.confidence,
                "questions_asked": self.memory.questions_asked,
                "unresolved_questions": self.memory.unresolved_questions,
            },
            "message_history": to_jsonable_python(self.message_history),
            "started_at": self.started_at,
        }
        filepath.write_text(json.dumps(data, indent=2, default=str))

    @classmethod
    def load(cls, filepath: Path) -> InvestigationState:
        """Load investigation state from JSON."""
        if not filepath.exists():
            return cls()

        data = json.loads(filepath.read_text())
        mem_data = data.get("memory", {})

        memory = InvestigationMemory(
            security_name=mem_data.get("security_name", ""),
            findings=mem_data.get("findings", []),
            evidence_sources=mem_data.get("evidence_sources", []),
            candidate_categories=mem_data.get("candidate_categories", []),
            confidence=mem_data.get("confidence", 0.0),
            questions_asked=mem_data.get("questions_asked", 0),
            unresolved_questions=mem_data.get("unresolved_questions", []),
        )

        messages = []
        if "message_history" in data:
            messages = ModelMessagesTypeAdapter.validate_python(data["message_history"])

        return cls(
            memory=memory,
            message_history=messages,
            started_at=data.get("started_at", datetime.now().isoformat()),
        )


def trim_investigation_history(messages: list[ModelMessage]) -> list[ModelMessage]:
    """
    History processor for the investigation agent.

    Keeps the last 8 messages (4 turn pairs). For an investigation agent,
    we want slightly more context than a simple chatbot because the agent
    needs to remember what tools it has already called.
    """
    max_messages = 8
    if len(messages) <= max_messages:
        return messages
    return messages[-max_messages:]


# The full investigation agent with all memory types
investigation_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=AnalystContext,
    system_prompt=(
        "You are a senior securities analyst conducting a classification "
        "investigation. Your goal is to determine the correct SecurityCategory "
        "for the security under investigation.\n\n"
        "Valid categories: equity, debt, convertible_note, safe, "
        "fund_interest, real_estate, revenue_share, other.\n\n"
        "Process:\n"
        "1. Search the securities database for basic information\n"
        "2. Check SEC filings for regulatory details\n"
        "3. Search the web for additional context\n"
        "4. Synthesize findings into a classification with confidence score\n\n"
        "At each step, explain your reasoning. When you reach sufficient "
        "confidence (>0.8), provide your final classification."
    ),
    history_processors=[trim_investigation_history],
)

# Working memory for the investigation agent (module-level so tools can access it)
_investigation_state = InvestigationState()


@investigation_agent.instructions
async def inject_investigation_context(ctx: RunContext[AnalystContext]) -> str:
    """Inject the current investigation state into the system prompt."""
    return (
        f"\n--- Current Investigation State ---\n"
        f"{_investigation_state.memory.summary()}\n"
        f"-----------------------------------\n"
    )


@investigation_agent.tool
async def db_search(ctx: RunContext[AnalystContext], query: str) -> str:
    """
    Search the securities database.

    Args:
        query: Search term for the securities database.
    """
    results = await ctx.deps.db.search(query)
    _investigation_state.memory.questions_asked += 1

    if not results:
        return f"No database results for '{query}'."

    for sec in results[:2]:
        finding = f"DB: {sec.name} ({sec.issuer})"
        if sec.type_hint:
            finding += f" — type: {sec.type_hint}"
        if sec.exemption.value != "unknown":
            finding += f" — exemption: {sec.exemption.value}"
        _investigation_state.memory.add_finding(finding, "database")
        _investigation_state.memory.security_name = (
            _investigation_state.memory.security_name or sec.name
        )
        _investigation_state.memory.update_confidence(0.15)

    lines = []
    for sec in results[:3]:
        base = f"- {sec.name} | {sec.issuer} | Type: {sec.type_hint or 'unknown'}"
        if sec.offering_amount:
            base += f" | Amount: ${sec.offering_amount:,.0f}"
        lines.append(base)
        lines.append(f"  {sec.raw_description[:200]}")

    return "Database results:\n" + "\n".join(lines)


@investigation_agent.tool
async def sec_filing_search(ctx: RunContext[AnalystContext], issuer: str) -> str:
    """
    Search SEC EDGAR for filings by issuer.

    Args:
        issuer: Name of the issuing entity.
    """
    filings = await ctx.deps.sec_search.search_by_issuer(issuer)
    _investigation_state.memory.questions_asked += 1

    if not filings:
        return f"No SEC filings for '{issuer}'."

    for f in filings[:2]:
        _investigation_state.memory.add_finding(
            f"SEC: {f.filing_type} — {f.exemption_type.value} — {f.details[:80]}",
            "sec_edgar",
        )
        _investigation_state.memory.update_confidence(0.2)

    lines = [
        f"- {f.filing_type} | {f.filing_date} | {f.exemption_type.value} | {f.details}"
        for f in filings[:3]
    ]
    return "SEC filings:\n" + "\n".join(lines)


@investigation_agent.tool
async def internet_search(ctx: RunContext[AnalystContext], query: str) -> str:
    """
    Search the web for additional context.

    Args:
        query: Web search query about the security or issuer.
    """
    results = await ctx.deps.web_search.search(query)
    _investigation_state.memory.questions_asked += 1

    for r in results[:2]:
        if r.relevance_score >= 0.5:
            _investigation_state.memory.add_finding(
                f"Web: {r.title} — {r.snippet[:100]}",
                "web_search",
            )
            _investigation_state.memory.update_confidence(0.1)

    lines = [f"- {r.title}: {r.snippet}" for r in results[:3]]
    return "Web results:\n" + "\n".join(lines)


@investigation_agent.tool
async def record_classification(
    ctx: RunContext[AnalystContext],
    category: str,
    confidence: float,
    reasoning: str,
) -> str:
    """
    Record the final classification decision.

    Args:
        category: The security category (equity, debt, convertible_note, safe, fund_interest, real_estate, revenue_share, other).
        confidence: Confidence score from 0.0 to 1.0.
        reasoning: Brief explanation of the classification reasoning.
    """
    _investigation_state.memory.candidate_categories = [category]
    _investigation_state.memory.confidence = confidence
    _investigation_state.memory.add_finding(
        f"CLASSIFICATION: {category} (confidence: {confidence:.0%}) — {reasoning}",
        "analyst_judgment",
    )
    return (
        f"Classification recorded: {category} at {confidence:.0%} confidence.\n"
        f"Reasoning: {reasoning}"
    )


async def demo_full_investigation() -> None:
    """Run a complete multi-turn investigation using all memory types."""
    print("=" * 70)
    print("SECTION 5: COMPLETE MULTI-TURN INVESTIGATION")
    print("=" * 70)
    print()

    global _investigation_state
    _investigation_state = InvestigationState()

    deps = AnalystContext.create(analyst_name="Dr. Sarah Chen", access_level="senior")

    # Turn 1: Start the investigation
    print("[Turn 1] User: Investigate the Catalyst Convertible Note Series A")
    result1 = await investigation_agent.run(
        "I need you to classify the Catalyst Convertible Note Series A. "
        "Start by searching the database.",
        deps=deps,
    )
    print(f"[Turn 1] Agent: {result1.output[:300]}...")
    _investigation_state.message_history = result1.all_messages()
    print(
        f"  Memory: {len(_investigation_state.memory.findings)} findings, "
        f"{_investigation_state.memory.confidence:.0%} confidence"
    )
    print()

    # Turn 2: Follow up with SEC filing check
    print("[Turn 2] User: Check the SEC filings")
    result2 = await investigation_agent.run(
        "Now check SEC filings for Catalyst Biotech Inc to verify the details.",
        deps=deps,
        message_history=_investigation_state.message_history,
    )
    print(f"[Turn 2] Agent: {result2.output[:300]}...")
    _investigation_state.message_history = result2.all_messages()
    print(
        f"  Memory: {len(_investigation_state.memory.findings)} findings, "
        f"{_investigation_state.memory.confidence:.0%} confidence"
    )
    print()

    # Turn 3: Request final classification
    print("[Turn 3] User: Provide your classification")
    result3 = await investigation_agent.run(
        "Based on everything you've found, provide your final classification. "
        "Use the record_classification tool to log your decision.",
        deps=deps,
        message_history=_investigation_state.message_history,
    )
    print(f"[Turn 3] Agent: {result3.output[:400]}...")
    _investigation_state.message_history = result3.all_messages()
    print()

    # Save the complete investigation state
    _investigation_state.save(INVESTIGATION_FILE)
    print(f"  Investigation saved to: {INVESTIGATION_FILE}")
    print()

    # Show the final investigation summary
    print("--- Final Investigation Summary ---")
    print(_investigation_state.memory.summary())
    print()

    # Demonstrate resuming from saved state
    print("--- Resuming from saved state ---")
    loaded = InvestigationState.load(INVESTIGATION_FILE)
    print(f"  Loaded security: {loaded.memory.security_name}")
    print(f"  Loaded findings: {len(loaded.memory.findings)}")
    print(f"  Loaded confidence: {loaded.memory.confidence:.0%}")
    print(f"  Loaded message history: {len(loaded.message_history)} messages")
    print()

    # Clean up
    if INVESTIGATION_FILE.exists():
        INVESTIGATION_FILE.unlink()
        print(f"  Cleaned up: {INVESTIGATION_FILE}")
    print()


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    print("=" * 70)
    print("MODULE 04: MEMORY AND CONTEXT MANAGEMENT")
    print("Four types of agent memory for production systems")
    print("=" * 70)
    print()

    # Section 1: Short-term memory (message_history)
    demo_short_term_memory()

    # Section 2: Working memory (structured dataclass)
    await demo_working_memory()

    # Section 3: Long-term memory (JSON persistence)
    demo_long_term_memory()

    # Section 4: Context window management (history_processors)
    demo_context_management()

    # Section 5: Full investigation with all memory types
    await demo_full_investigation()

    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. message_history carries conversation across runs")
    print("     result.new_messages() = this run only")
    print("     result.all_messages() = full conversation")
    print("  2. Working memory = a dataclass YOU maintain alongside the agent")
    print("     Tools write to it, dynamic system prompts read from it")
    print("  3. Long-term memory = JSON persistence with ModelMessagesTypeAdapter")
    print("     Save/load both structured state and message history")
    print("  4. history_processors = middleware that trims context before each call")
    print("     Keep context focused, save tokens, avoid confusion")
    print("  5. All four work together in production investigation agents")
    print()
    print("MEMORY TYPE DECISION GUIDE:")
    print("  Within a session, same topic  -> message_history")
    print("  Structured state across runs  -> working memory dataclass")
    print("  Across sessions/restarts      -> JSON persistence")
    print("  Context too long/expensive    -> history_processors")
    print()
    print("Next: Module 05 -- Streaming for real-time output")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
