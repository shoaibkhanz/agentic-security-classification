"""
Module 06b: Planning and Reasoning Patterns
=============================================

This module teaches how agents THINK — not just react.

Three reasoning patterns that make agents intelligent:
  1. ReAct (Reason-Act-Observe) — think before each action
  2. Plan-and-Execute — generate a plan, then execute steps
  3. Structured Chain-of-Thought — auditable reasoning chains

In Module 00, you built a reactive loop (see tool calls → execute them).
Here, we add explicit reasoning BETWEEN actions. The agent decides
WHAT to do and WHY before doing it.

This is the direct precursor to the capstone's confidence-optimizing
planner. The capstone adds confidence tracking on top of these patterns.

Sections:
  1. ReAct From Scratch — think-act-observe loop
  2. Plan-and-Execute — plan first, then execute with revision
  3. Structured Chain-of-Thought — typed reasoning chains
  4. When NOT to Plan — meta-decision about planning overhead
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from shared.deps import AnalystContext
from shared.models import PlanStep, SecurityCategory


# =============================================================================
# Section 1: ReAct From Scratch
# =============================================================================
# ReAct = Reason + Act. Before each action, the agent generates
# an explicit thought about what to do and why.
#
# The loop: Thought → Action → Observation → Thought → Action → ...
#
# In Module 00, the loop was: Action → Observation → Action → ...
# Adding explicit "Thought" steps makes the agent's reasoning visible
# and debuggable.


class ReActThought(BaseModel):
    """The agent's explicit reasoning before taking an action."""

    thought: str = Field(description="What I know so far and what I need to find out")
    action: str = Field(description="The action I'll take next")
    action_input: str = Field(description="The specific input for the action")
    reasoning: str = Field(description="Why this action is the best next step")


class ReActConclusion(BaseModel):
    """The agent's final answer after reasoning."""

    conclusion: str = Field(description="Final answer based on all observations")
    category: SecurityCategory
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_used: list[str] = Field(
        description="Key evidence that led to this conclusion"
    )


# The ReAct agent generates Thought before each action
react_thinker = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=ReActThought | ReActConclusion,
    system_prompt=(
        "You are a securities analyst using the ReAct framework. "
        "Given a question and any observations so far, either:\n"
        "1. Generate a Thought + Action (if you need more information)\n"
        "2. Generate a Conclusion (if you have enough to answer)\n\n"
        "Available actions: search_db, check_sec_filings, web_search\n"
        "Be specific about what you're looking for and why."
    ),
)


@dataclass
class ReActState:
    """Accumulated state during a ReAct loop."""

    observations: list[str] = field(default_factory=list)
    thoughts: list[ReActThought] = field(default_factory=list)
    max_steps: int = 5


async def react_loop(question: str, deps: AnalystContext) -> ReActConclusion:
    """
    Execute a complete ReAct loop.

    This is the same agent loop from Module 00, but with explicit
    reasoning at each step. The agent THINKS before acting.
    """
    state = ReActState()
    message_history = None

    print(f"  Question: {question}\n")

    for step in range(state.max_steps):
        # Build context from accumulated observations
        context = f"Question: {question}\n\n"
        if state.observations:
            context += "Observations so far:\n"
            for i, obs in enumerate(state.observations, 1):
                context += f"  {i}. {obs}\n"
            context += "\nBased on these observations, what should I do next?"
        else:
            context += "No observations yet. What should I investigate first?"

        # Ask the agent to think and decide
        result = await react_thinker.run(context, message_history=message_history)
        message_history = result.all_messages()

        if isinstance(result.output, ReActConclusion):
            print(f"  Step {step + 1}: CONCLUSION")
            print(f"    {result.output.conclusion}")
            print(f"    Category: {result.output.category.value}")
            print(f"    Confidence: {result.output.confidence:.0%}")
            return result.output

        # It's a thought — execute the action
        thought = result.output
        state.thoughts.append(thought)
        print(f"  Step {step + 1}: THOUGHT → ACTION")
        print(f"    Thought: {thought.thought}")
        print(f"    Action: {thought.action}({thought.action_input})")
        print(f"    Why: {thought.reasoning}")

        # Execute the action (simulated tool calls)
        observation = await execute_react_action(thought, deps)
        state.observations.append(observation)
        print(f"    Observation: {observation[:150]}...")
        print()

    # If we hit max steps, force a conclusion
    return ReActConclusion(
        conclusion="Reached maximum reasoning steps without definitive answer.",
        category=SecurityCategory.OTHER,
        confidence=0.3,
        evidence_used=[obs[:100] for obs in state.observations],
    )


async def execute_react_action(thought: ReActThought, deps: AnalystContext) -> str:
    """Execute a ReAct action and return the observation."""
    action = thought.action.lower()
    query = thought.action_input

    if "search_db" in action or "database" in action:
        results = await deps.db.search(query)
        if results:
            sec = results[0]
            return f"Found: {sec.name} by {sec.issuer}. Type hint: {sec.type_hint}. Description: {sec.raw_description[:200]}"
        return f"No results found for '{query}'"

    elif "sec" in action or "filing" in action:
        filings = await deps.sec_search.search(query)
        if filings:
            f = filings[0]
            return f"SEC Filing: {f.filing_type} by {f.issuer}, {f.exemption_type.value}, {f.details}"
        return f"No SEC filings found for '{query}'"

    elif "web" in action:
        results = await deps.web_search.search(query)
        if results:
            r = results[0]
            return f"Web: {r.title} — {r.snippet}"
        return f"No web results for '{query}'"

    return f"Unknown action: {thought.action}"


# =============================================================================
# Section 2: Plan-and-Execute
# =============================================================================
# Instead of deciding one step at a time (ReAct), generate a complete
# plan FIRST, then execute it. Revise the plan if new info changes things.
#
# This is what the capstone's question_planner does.


class AnalysisPlan(BaseModel):
    """A plan for analyzing a security."""

    goal: str = Field(description="What we're trying to determine")
    steps: list[PlanStep] = Field(description="Ordered steps to execute")
    estimated_actions: int = Field(description="How many actions this plan requires")


class PlanRevision(BaseModel):
    """Revision to an existing plan based on new information."""

    revised_steps: list[PlanStep]
    revision_reason: str = Field(description="Why the plan was revised")
    steps_removed: list[str] = Field(default_factory=list)
    steps_added: list[str] = Field(default_factory=list)


# Planning agent — generates the plan
planner_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=AnalysisPlan,
    system_prompt=(
        "You are a securities analysis planner. Given a question about a security, "
        "create a step-by-step plan to classify it. Available actions:\n"
        "- search_db: Search the securities database\n"
        "- check_sec_filings: Look up SEC filings\n"
        "- web_search: Search the web for public info\n"
        "- analyze: Synthesize findings into a classification\n\n"
        "Order steps by information value — what would most reduce uncertainty?"
    ),
)

# Executor agent — executes individual steps
executor_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=AnalystContext,
    output_type=str,
    system_prompt=(
        "You execute a single step of an analysis plan. "
        "Use your tools to gather the requested information. "
        "Return a concise summary of what you found."
    ),
)


@executor_agent.tool
async def search_database(ctx: RunContext[AnalystContext], query: str) -> str:
    """Search the securities database."""
    results = await ctx.deps.db.search(query)
    if not results:
        return f"No results for '{query}'"
    return "\n".join(
        f"- {s.name} ({s.issuer}): {s.raw_description[:150]}" for s in results[:3]
    )


@executor_agent.tool
async def check_filings(ctx: RunContext[AnalystContext], issuer: str) -> str:
    """Check SEC filings for an issuer."""
    filings = await ctx.deps.sec_search.search_by_issuer(issuer)
    if not filings:
        return f"No SEC filings for '{issuer}'"
    return "\n".join(
        f"- {f.filing_type} ({f.filing_date}): {f.details}" for f in filings
    )


async def plan_and_execute(question: str, deps: AnalystContext) -> str:
    """
    Plan-and-Execute pattern: plan first, then execute step by step.
    """
    print(f"  Question: {question}\n")

    # Step 1: Generate the plan
    plan_result = await planner_agent.run(f"Plan how to answer: {question}")
    plan = plan_result.output

    print(f"  PLAN: {plan.goal}")
    print(f"  Estimated actions: {plan.estimated_actions}")
    for i, step in enumerate(plan.steps):
        print(f"    {i + 1}. {step.action} — {step.rationale}")
    print()

    # Step 2: Execute each step, accumulating findings
    findings: list[str] = []

    for i, step in enumerate(plan.steps):
        if step.completed:
            continue

        print(f"  EXECUTING Step {i + 1}: {step.action}")
        step_result = await executor_agent.run(
            f"Execute this step: {step.action}\nRationale: {step.rationale}\n"
            f"Previous findings: {findings}",
            deps=deps,
        )
        findings.append(f"Step {i + 1}: {step_result.output}")
        step.completed = True
        print(f"    Finding: {step_result.output[:150]}...")
        print()

    # Step 3: Synthesize findings
    synthesis = "\n".join(findings)
    print(f"  SYNTHESIS: Combining {len(findings)} findings")
    print(f"  {synthesis[:300]}...")
    return synthesis


# =============================================================================
# Section 3: Structured Chain-of-Thought
# =============================================================================
# Instead of free-text reasoning, force the agent to output typed
# reasoning steps. Each step has evidence, inference, and confidence_delta.
# This is how the capstone produces auditable reasoning chains.


class StructuredReasoning(BaseModel):
    """A complete reasoning chain with typed steps."""

    steps: list[ReasoningStepLocal] = Field(description="Ordered reasoning steps")
    conclusion: str
    final_category: SecurityCategory
    total_confidence: float = Field(ge=0.0, le=1.0)


class ReasoningStepLocal(BaseModel):
    """One step in a structured reasoning chain."""

    step_number: int
    evidence: str = Field(description="What evidence was considered")
    inference: str = Field(description="What this evidence implies")
    confidence_delta: float = Field(
        description="How much this step changes confidence (+/-)",
    )


# Fix forward reference
StructuredReasoning.model_rebuild()


cot_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=StructuredReasoning,
    system_prompt=(
        "You are a securities analyst that reasons step by step. "
        "Given information about a security, produce a structured reasoning chain. "
        "Each step should cite specific evidence, state what it implies, "
        "and indicate how much it increases or decreases your confidence "
        "in the classification. Be honest about uncertainty."
    ),
)


async def demo_structured_reasoning() -> None:
    """Demonstrate structured chain-of-thought reasoning."""
    print("--- Structured Chain-of-Thought ---\n")

    # Provide raw security info for the agent to reason about
    security_info = (
        "Security: Cascade SAFE+Note\n"
        "Issuer: Cascade Robotics\n"
        "Description: Hybrid SAFE with note-like features. Accrues 5% interest, "
        "converts at next priced round with 20% discount, $10M cap. "
        "If no priced round by maturity, converts to common at cap.\n"
        "Maturity: 2 years\n"
        "Interest: 5%\n"
        "Exemption: Reg D 506(b)"
    )

    result = await cot_agent.run(
        f"Analyze and classify this security:\n\n{security_info}"
    )

    reasoning = result.output
    print(f"  Classification: {reasoning.final_category.value}")
    print(f"  Confidence: {reasoning.total_confidence:.0%}")
    print(f"  Reasoning chain ({len(reasoning.steps)} steps):")

    for step in reasoning.steps:
        direction = "+" if step.confidence_delta > 0 else ""
        print(f"    Step {step.step_number}: [{direction}{step.confidence_delta:.2f}]")
        print(f"      Evidence: {step.evidence}")
        print(f"      Inference: {step.inference}")
    print(f"  Conclusion: {reasoning.conclusion}")
    print()


# =============================================================================
# Section 4: When NOT to Plan
# =============================================================================
# Planning has overhead. Simple queries don't need it.
# Build a meta-decision: "Does this query need a plan?"


class QueryComplexity(BaseModel):
    """Assessment of whether a query needs planning."""

    needs_planning: bool
    reasoning: str
    estimated_steps: int = Field(description="How many steps if planning is needed")


complexity_assessor = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=QueryComplexity,
    system_prompt=(
        "Assess whether a securities query needs a multi-step plan or can "
        "be answered directly. Simple lookups don't need planning. "
        "Complex analyses with multiple data sources do."
    ),
)


async def smart_route(question: str, deps: AnalystContext) -> str:
    """Route to planning or direct answer based on complexity."""
    print(f"  Question: {question}")

    # Assess complexity
    assessment = await complexity_assessor.run(question)
    complexity = assessment.output

    print(f"  Needs planning: {complexity.needs_planning}")
    print(f"  Reasoning: {complexity.reasoning}")
    print(f"  Estimated steps: {complexity.estimated_steps}")
    print()

    if complexity.needs_planning:
        return await plan_and_execute(question, deps)
    else:
        # Direct answer — use a simple agent call
        direct = Agent(
            "anthropic:sonnet-4-5-20250929",
            output_type=str,
            system_prompt="Answer the securities question directly and concisely.",
        )
        result = await direct.run(question)
        print(f"  Direct answer: {result.output[:200]}")
        return result.output


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    print("=" * 70)
    print("MODULE 06b: PLANNING AND REASONING PATTERNS")
    print("How agents THINK, not just react")
    print("=" * 70)
    print()

    deps = AnalystContext.create(analyst_name="Tutorial User")

    # Demo 1: ReAct loop
    print("=== 1. ReAct: Reason-Act-Observe ===\n")
    conclusion = await react_loop(
        "What type of security is the Apex Hybrid Instrument 2024?",
        deps,
    )
    print(f"\n  Final: {conclusion.category.value} ({conclusion.confidence:.0%})\n")

    # Demo 2: Plan-and-Execute
    print("=== 2. Plan-and-Execute ===\n")
    await plan_and_execute(
        "Classify the Greenfield Token Offering and assess its regulatory status",
        deps,
    )
    print()

    # Demo 3: Structured Chain-of-Thought
    print("=== 3. Structured Chain-of-Thought ===\n")
    await demo_structured_reasoning()

    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. ReAct: explicit Thought before each Action (debuggable)")
    print("  2. Plan-and-Execute: plan first, then execute with revision")
    print("  3. Structured CoT: typed reasoning chains (auditable)")
    print("  4. Know when NOT to plan — simple queries don't need overhead")
    print()
    print("CAPSTONE CONNECTION:")
    print("  The capstone combines Plan-and-Execute with Structured CoT,")
    print("  adding confidence tracking to optimize question selection.")
    print()
    print("Next: Module 07 — Graph fundamentals")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
