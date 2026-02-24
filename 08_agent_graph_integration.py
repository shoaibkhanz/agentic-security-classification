"""
Module 08: Agents Inside Graphs, Long-Running Agents, Persistence
===================================================================

This is the power pattern: graphs provide STRUCTURE,
agents provide INTELLIGENCE.

Module 07 used pure rule-based logic in graph nodes.
Now, each node delegates to a specialized pydantic-ai agent.
The graph orchestrates the flow, agents make the decisions.

Three production patterns:
  1. Agents in graph nodes — intelligent decision-making at each step
  2. Long-running workflows — FileStatePersistence survives restarts
  3. Human-in-the-loop — graph.iter() for step-by-step execution

This is the direct architecture preview for the capstone.

Sections:
  1. Agents Inside Graph Nodes
  2. State Management with Agent Messages
  3. Step-by-Step Execution with graph.iter()
  4. Putting It All Together
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Annotated

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_graph import BaseNode, End, Graph, GraphRunContext, Edge

from shared.models import SecurityCategory


# =============================================================================
# Section 1: Agents Inside Graph Nodes
# =============================================================================
# Each graph node's run() method calls an agent.
# The agent uses LLM reasoning for the decision.
# The graph ensures the flow is structured and auditable.


# --- Shared State ---


@dataclass
class ClassificationState:
    """
    State persisted across all graph nodes.

    This is the graph's working memory. It accumulates:
    - Evidence gathered by agents
    - Agent message histories (for conversation continuity)
    - Classification progress
    """

    security_description: str = ""
    gathered_info: list[str] = field(default_factory=list)
    category: SecurityCategory | None = None
    confidence: float = 0.0
    questions_asked: int = 0

    # Agent message histories — preserved across nodes
    # Each agent gets its own message history
    gatherer_messages: list[ModelMessage] = field(default_factory=list)
    classifier_messages: list[ModelMessage] = field(default_factory=list)


# --- Agent Definitions ---


class InfoAssessment(BaseModel):
    """What the info gatherer found."""

    summary: str
    key_facts: list[str]
    needs_more_info: bool
    suggested_question: str | None = None


class ClassificationDecision(BaseModel):
    """The classifier's decision."""

    category: SecurityCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    needs_verification: bool


info_gatherer_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=InfoAssessment,
    system_prompt=(
        "You gather and synthesize information about private securities. "
        "Review what's known, identify key facts, and determine if more "
        "information is needed for classification. Be thorough but efficient."
    ),
)

classifier_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=ClassificationDecision,
    system_prompt=(
        "You classify private securities into categories: equity, debt, "
        "convertible_note, safe, fund_interest, real_estate, revenue_share, other. "
        "Base your classification on the evidence provided. Be honest about confidence. "
        "If confidence is below 0.7, request verification."
    ),
)


# --- Graph Nodes ---


@dataclass
class GatherInfo(BaseNode[ClassificationState, None, dict[str, object]]):
    """
    First node: gather and assess available information.
    The agent reviews what's known and identifies gaps.
    """

    async def run(
        self,
        ctx: GraphRunContext[ClassificationState],
    ) -> (
        Annotated[AskQuestion, Edge(label="need more info")]
        | Annotated[Classify, Edge(label="sufficient info")]
    ):
        """Agent gathers info and decides if more is needed."""
        # Build context for the agent
        context = f"Security description: {ctx.state.security_description}\n\n"
        if ctx.state.gathered_info:
            context += "Previously gathered information:\n"
            for info in ctx.state.gathered_info:
                context += f"- {info}\n"

        # Call the agent with preserved message history
        result = await info_gatherer_agent.run(
            context,
            message_history=ctx.state.gatherer_messages,
        )

        # Update state with agent's findings and message history
        ctx.state.gatherer_messages = list(result.all_messages())
        assessment = result.output

        for fact in assessment.key_facts:
            if fact not in ctx.state.gathered_info:
                ctx.state.gathered_info.append(fact)

        if assessment.needs_more_info and ctx.state.questions_asked < 3:
            return AskQuestion(
                question=assessment.suggested_question
                or "What else can you tell me about this security?"
            )

        return Classify()


@dataclass
class AskQuestion(BaseNode[ClassificationState, None, dict[str, object]]):
    """
    Ask a follow-up question to gather more information.
    Simulates getting an answer and loops back to GatherInfo.
    """

    question: str = ""

    async def run(
        self,
        ctx: GraphRunContext[ClassificationState],
    ) -> Annotated[GatherInfo, Edge(label="continue gathering")]:
        """Simulate asking a question and getting an answer."""
        ctx.state.questions_asked += 1

        # In the capstone, this would use ask_user_question tool
        # Here we simulate based on the description
        simulated_answer = (
            f"[Simulated answer to: {self.question}] "
            f"The security has standard terms for its type. "
            f"The issuer has a good track record."
        )
        ctx.state.gathered_info.append(f"Q: {self.question} → A: {simulated_answer}")

        return GatherInfo()


@dataclass
class Classify(BaseNode[ClassificationState, None, dict[str, object]]):
    """
    Classify the security based on gathered evidence.
    Routes to either Verify or End based on confidence.
    """

    async def run(
        self,
        ctx: GraphRunContext[ClassificationState],
    ) -> (
        Annotated[Verify, Edge(label="needs verification")]
        | Annotated[End[dict[str, object]], Edge(label="confident")]
    ):
        """Agent classifies based on accumulated evidence."""
        evidence = "\n".join(f"- {info}" for info in ctx.state.gathered_info)
        prompt = (
            f"Classify this security based on the evidence:\n\n"
            f"Description: {ctx.state.security_description}\n\n"
            f"Evidence gathered:\n{evidence}"
        )

        result = await classifier_agent.run(
            prompt,
            message_history=ctx.state.classifier_messages,
        )
        ctx.state.classifier_messages = list(result.all_messages())
        decision = result.output

        ctx.state.category = decision.category
        ctx.state.confidence = decision.confidence

        if decision.needs_verification or decision.confidence < 0.7:
            return Verify(reasoning=decision.reasoning)

        return End(
            {
                "category": decision.category.value,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
                "questions_asked": ctx.state.questions_asked,
                "evidence_count": len(ctx.state.gathered_info),
            }
        )


@dataclass
class Verify(BaseNode[ClassificationState, None, dict[str, object]]):
    """
    Verify the classification — ask for more info or accept.
    In the capstone, the verifier agent checks reasoning consistency.
    """

    reasoning: str = ""

    async def run(
        self,
        ctx: GraphRunContext[ClassificationState],
    ) -> (
        Annotated[GatherInfo, Edge(label="need more evidence")]
        | Annotated[End[dict[str, object]], Edge(label="verified")]
    ):
        """Verify or request more evidence."""
        # If we've already asked enough questions, accept the classification
        if ctx.state.questions_asked >= 2:
            return End(
                {
                    "category": ctx.state.category.value
                    if ctx.state.category
                    else "unknown",
                    "confidence": ctx.state.confidence,
                    "reasoning": self.reasoning,
                    "questions_asked": ctx.state.questions_asked,
                    "evidence_count": len(ctx.state.gathered_info),
                    "verified": True,
                }
            )

        # Otherwise, gather more evidence
        ctx.state.gathered_info.append(
            f"Verification note: classification as {ctx.state.category} "
            f"needs more evidence (confidence: {ctx.state.confidence:.0%})"
        )
        return GatherInfo()


# Build the graph
classification_graph = Graph(
    nodes=(GatherInfo, AskQuestion, Classify, Verify),
)


# =============================================================================
# Section 2: State Management with Agent Messages
# =============================================================================
# Key pattern: agent message histories are stored IN the graph state.
# This means agents maintain conversation continuity across graph nodes.
#
# When GatherInfo runs the info_gatherer_agent, it passes
# ctx.state.gatherer_messages as message_history. After the call,
# it updates ctx.state.gatherer_messages with the new messages.
#
# This is how agents "remember" across graph transitions.


# =============================================================================
# Section 3: Step-by-Step Execution with graph.iter()
# =============================================================================
# graph.iter() yields control after each node, enabling:
#   - Human-in-the-loop review
#   - Progress monitoring
#   - Conditional stopping


async def demo_step_by_step() -> None:
    """Demonstrate step-by-step execution with graph.iter()."""
    print("=== Step-by-Step Execution with graph.iter() ===\n")

    state = ClassificationState(
        security_description=(
            "Apex Hybrid Instrument 2024: Pays 4% coupon with mandatory "
            "conversion to common equity at maturity. 5-year duration. "
            "Functions as debt during term, becomes equity at maturity."
        ),
    )

    step_count = 0
    async with classification_graph.iter(
        GatherInfo(),
        state=state,
    ) as run:
        async for node in run:
            step_count += 1
            node_name = type(node).__name__

            if isinstance(node, End):
                print(f"  Step {step_count}: END")
                print(f"    Result: {node.data}")
                break

            print(f"  Step {step_count}: {node_name}")
            if isinstance(node, AskQuestion):
                print(f"    Question: {node.question}")  # type: ignore[union-attr]
            elif isinstance(node, Verify):
                print(f"    Verifying: {node.reasoning[:100]}...")  # type: ignore[union-attr]
            print(
                f"    State: {len(state.gathered_info)} facts, "
                f"{state.questions_asked} questions asked"
            )
            print()

    print(f"  Total steps: {step_count}")
    print(f"  Final category: {state.category}")
    print(f"  Final confidence: {state.confidence:.0%}")
    print()


# =============================================================================
# Section 4: Putting It All Together
# =============================================================================


async def demo_full_classification() -> None:
    """Run a complete classification through the graph."""
    print("=== Full Classification: NovaTech SAFE ===\n")

    state = ClassificationState(
        security_description=(
            "NovaTech AI Inc is raising $5M via Simple Agreement for Future "
            "Equity (SAFE) instruments. 20% discount to next priced round, "
            "$20M valuation cap. Y Combinator standard SAFE terms. "
            "Pre-seed stage AI/ML startup."
        ),
    )

    result, history = await classification_graph.run(
        GatherInfo(),
        state=state,
    )

    print(f"  Result: {result}")
    print(f"  Questions asked: {state.questions_asked}")
    print(f"  Evidence gathered: {len(state.gathered_info)} facts")
    print(f"  Graph history: {len(history)} nodes traversed")
    print()


async def demo_mermaid() -> None:
    """Show the graph structure."""
    print("=== Graph Structure (Mermaid) ===\n")
    print(classification_graph.mermaid_code(start_node=GatherInfo))
    print()


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    print("=" * 70)
    print("MODULE 08: AGENTS INSIDE GRAPHS")
    print("Graphs = structure, Agents = intelligence")
    print("=" * 70)
    print()

    # Show graph structure
    await demo_mermaid()

    # Full classification
    await demo_full_classification()

    # Step-by-step execution
    await demo_step_by_step()

    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. Graph nodes call agents: intelligent decisions at each step")
    print("  2. Agent message histories stored in graph state (continuity)")
    print("  3. graph.iter() enables human-in-the-loop review")
    print("  4. FileStatePersistence makes workflows survive restarts")
    print("  5. This is the capstone architecture — agents in a confidence loop")
    print()
    print("PRODUCTION PATTERNS:")
    print("  - Agent messages IN state = memory across graph transitions")
    print("  - graph.iter() = pause/resume for human review")
    print("  - FileStatePersistence = durable, long-running workflows")
    print("  - Max questions/steps = guard against infinite loops")
    print()
    print("Next: Module 09 — Evaluation fundamentals with pydantic-evals")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
