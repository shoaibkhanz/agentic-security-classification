"""
Module 07: Graph Fundamentals with pydantic-graph
===================================================

pydantic-graph is a state machine framework where:
  - Nodes are processing steps (dataclasses)
  - Edges are defined by return type annotations
  - State persists across nodes via a typed dataclass
  - The type system IS the graph topology

Key insight: Each node's return type annotation defines where the
graph can go next. `async def run() -> NodeA | NodeB | End[Result]`
means this node can transition to NodeA, NodeB, or finish.

No agents yet — this module is pure graph logic.
Module 08 puts agents inside graph nodes.

Sections:
  1. Nodes, Edges, and State
  2. Conditional Routing
  3. End Nodes and Results
  4. Mermaid Diagram Generation
  5. Running a Graph
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Annotated

from pydantic_graph import BaseNode, End, Graph, GraphRunContext, Edge

from shared.models import ExemptionType, SecurityCategory


# =============================================================================
# Section 1: Nodes, Edges, and State
# =============================================================================
# A graph has three type parameters:
#   BaseNode[StateType, DepsType, EndType]
#   - StateType: shared state that persists across all nodes
#   - DepsType: external dependencies (like RunContext deps)
#   - EndType: the type returned when the graph finishes
#
# State is a dataclass. Every node can read and write to it.


@dataclass
class ReviewState:
    """
    State that persists across all nodes in the review workflow.

    This is the graph's "working memory" — accumulated findings,
    decisions, and audit trail. Compare to Module 04's working memory.
    """

    security_name: str = ""
    issuer: str = ""
    document_complete: bool = False
    has_sec_filing: bool = False
    exemption_type: ExemptionType = ExemptionType.UNKNOWN
    category: SecurityCategory | None = None
    risk_flags: list[str] = field(default_factory=list)
    review_notes: list[str] = field(default_factory=list)
    escalation_reason: str = ""


# --- Node Definitions ---
# Each node is a dataclass with an async run() method.
# The return type annotation defines the possible next nodes.


@dataclass
class ReceiveDocument(BaseNode[ReviewState]):
    """
    Entry point: receive a security document for review.
    Always transitions to ValidateCompleteness.
    """

    security_name: str = ""
    issuer: str = ""
    description: str = ""

    async def run(
        self,
        ctx: GraphRunContext[ReviewState],
    ) -> Annotated[ValidateCompleteness, Edge(label="validate")]:
        """Process the incoming document and set initial state."""
        ctx.state.security_name = self.security_name
        ctx.state.issuer = self.issuer
        ctx.state.review_notes.append(
            f"Received document: {self.security_name} from {self.issuer}"
        )
        return ValidateCompleteness(description=self.description)


@dataclass
class ValidateCompleteness(BaseNode[ReviewState]):
    """
    Check if the document has enough information for classification.
    Routes to either RequestMoreInfo or RouteToReview.
    """

    description: str = ""

    async def run(
        self,
        ctx: GraphRunContext[ReviewState],
    ) -> (
        Annotated[RequestMoreInfo, Edge(label="incomplete")]
        | Annotated[RouteToReview, Edge(label="complete")]
    ):
        """Validate document completeness."""
        # Simple completeness check
        has_name = bool(ctx.state.security_name)
        has_issuer = bool(ctx.state.issuer)
        has_description = len(self.description) > 50

        ctx.state.document_complete = has_name and has_issuer and has_description

        if not ctx.state.document_complete:
            missing = []
            if not has_name:
                missing.append("security name")
            if not has_issuer:
                missing.append("issuer")
            if not has_description:
                missing.append("detailed description")
            return RequestMoreInfo(missing_fields=missing)

        ctx.state.review_notes.append("Document validation: COMPLETE")
        return RouteToReview()


@dataclass
class RequestMoreInfo(BaseNode[ReviewState]):
    """
    Document is incomplete — request additional information.
    For this demo, we simulate receiving the info and loop back.
    """

    missing_fields: list[str] = field(default_factory=list)

    async def run(
        self,
        ctx: GraphRunContext[ReviewState],
    ) -> Annotated[ValidateCompleteness, Edge(label="retry validation")]:
        """Request and simulate receiving missing info."""
        ctx.state.review_notes.append(
            f"Requested additional info: {', '.join(self.missing_fields)}"
        )
        # Simulate receiving the missing info
        if "detailed description" in self.missing_fields:
            return ValidateCompleteness(
                description="Updated: This is a private equity fund offering limited partnership interests."
            )
        return ValidateCompleteness(description="")


# =============================================================================
# Section 2: Conditional Routing
# =============================================================================
# The real power: a node can return DIFFERENT node types based on logic.
# The type annotation `NodeA | NodeB | End[T]` defines all possible routes.


@dataclass
class RouteToReview(BaseNode[ReviewState]):
    """
    Route the document to the appropriate review track.
    Conditional routing based on security characteristics.
    """

    async def run(
        self,
        ctx: GraphRunContext[ReviewState],
    ) -> (
        Annotated[ClassifyType, Edge(label="classify")]
        | Annotated[FlagForEscalation, Edge(label="escalate")]
    ):
        """Route based on initial assessment."""
        # Check for red flags that require escalation
        description_lower = " ".join(ctx.state.review_notes).lower()

        if any(flag in description_lower for flag in ["guaranteed", "no risk", "25%"]):
            ctx.state.risk_flags.append("Potentially fraudulent claims detected")
            return FlagForEscalation(reason="Red flags in offering document")

        return ClassifyType()


@dataclass
class ClassifyType(BaseNode[ReviewState]):
    """
    Classify the security type based on available information.
    This is the core classification logic (without an agent — pure rules).
    """

    async def run(
        self,
        ctx: GraphRunContext[ReviewState],
    ) -> (
        Annotated[ApproveClassification, Edge(label="approve")]
        | Annotated[FlagForEscalation, Edge(label="uncertain")]
    ):
        """Classify using rule-based logic (agents come in Module 08)."""
        notes = " ".join(ctx.state.review_notes).lower()

        # Simple rule-based classification
        if any(
            kw in notes for kw in ["bond", "note", "debt", "interest rate", "maturity"]
        ):
            ctx.state.category = SecurityCategory.DEBT
        elif any(kw in notes for kw in ["safe", "future equity"]):
            ctx.state.category = SecurityCategory.SAFE
        elif any(kw in notes for kw in ["fund", "partnership", "lp interest"]):
            ctx.state.category = SecurityCategory.FUND_INTEREST
        elif any(kw in notes for kw in ["preferred", "common", "stock", "equity"]):
            ctx.state.category = SecurityCategory.EQUITY
        elif any(kw in notes for kw in ["real estate", "property"]):
            ctx.state.category = SecurityCategory.REAL_ESTATE
        else:
            ctx.state.category = SecurityCategory.OTHER
            return FlagForEscalation(reason="Could not determine security type")

        ctx.state.review_notes.append(f"Classified as: {ctx.state.category.value}")
        return ApproveClassification()


# =============================================================================
# Section 3: End Nodes and Results
# =============================================================================
# End[ResultType] terminates the graph and returns a value.
# The third type parameter of BaseNode defines the End type.


@dataclass
class ReviewResult:
    """The final result of the securities review workflow."""

    security_name: str
    category: SecurityCategory | None
    approved: bool
    escalated: bool
    risk_flags: list[str]
    review_notes: list[str]


@dataclass
class ApproveClassification(BaseNode[ReviewState, None, ReviewResult]):
    """Approve the classification — graph ends successfully."""

    async def run(
        self,
        ctx: GraphRunContext[ReviewState],
    ) -> Annotated[End[ReviewResult], Edge(label="approved")]:
        """Approve and produce final result."""
        ctx.state.review_notes.append("Classification APPROVED")
        return End(
            ReviewResult(
                security_name=ctx.state.security_name,
                category=ctx.state.category,
                approved=True,
                escalated=False,
                risk_flags=ctx.state.risk_flags,
                review_notes=ctx.state.review_notes,
            )
        )


@dataclass
class FlagForEscalation(BaseNode[ReviewState, None, ReviewResult]):
    """Flag for human review — graph ends with escalation."""

    reason: str = ""

    async def run(
        self,
        ctx: GraphRunContext[ReviewState],
    ) -> Annotated[End[ReviewResult], Edge(label="escalated")]:
        """Escalate and produce final result."""
        ctx.state.escalation_reason = self.reason
        ctx.state.review_notes.append(f"ESCALATED: {self.reason}")
        return End(
            ReviewResult(
                security_name=ctx.state.security_name,
                category=ctx.state.category,
                approved=False,
                escalated=True,
                risk_flags=ctx.state.risk_flags,
                review_notes=ctx.state.review_notes,
            )
        )


# =============================================================================
# Section 4: Mermaid Diagram Generation
# =============================================================================
# The graph topology is defined by type annotations.
# pydantic-graph can generate a Mermaid diagram from these annotations.

# Create the graph
review_graph = Graph(
    nodes=(
        ReceiveDocument,
        ValidateCompleteness,
        RequestMoreInfo,
        RouteToReview,
        ClassifyType,
        ApproveClassification,
        FlagForEscalation,
    ),
)


def show_mermaid() -> None:
    """Generate and display the Mermaid diagram."""
    print("--- Mermaid Diagram (paste into mermaid.live) ---\n")
    mermaid_code = review_graph.mermaid_code(start_node=ReceiveDocument)
    print(mermaid_code)
    print()


# =============================================================================
# Section 5: Running a Graph
# =============================================================================


async def demo_normal_flow() -> None:
    """Run a security through the normal classification flow."""
    print("=== Normal Flow: Complete Document ===\n")

    state = ReviewState()
    start_node = ReceiveDocument(
        security_name="Meridian Growth Fund LP",
        issuer="Meridian Capital Partners",
        description=(
            "Meridian Growth Fund LP offers limited partnership interests "
            "in a diversified private equity fund targeting mid-market buyouts."
        ),
    )

    result, history = await review_graph.run(
        start_node,
        state=state,
    )

    print(f"  Security: {result.security_name}")
    print(f"  Category: {result.category.value if result.category else 'None'}")
    print(f"  Approved: {result.approved}")
    print(f"  Escalated: {result.escalated}")
    print("  Review notes:")
    for note in result.review_notes:
        print(f"    - {note}")
    print()


async def demo_escalation_flow() -> None:
    """Run a suspicious security that gets escalated."""
    print("=== Escalation Flow: Red Flags Detected ===\n")

    state = ReviewState()
    start_node = ReceiveDocument(
        security_name="Diamond Legacy Trust Units",
        issuer="Diamond Legacy Trust",
        description=(
            "Guaranteed 25% annual returns. Trust units backed by proprietary "
            "AI-driven cryptocurrency arbitrage strategy. Principal guaranteed."
        ),
    )

    result, history = await review_graph.run(
        start_node,
        state=state,
    )

    print(f"  Security: {result.security_name}")
    print(f"  Approved: {result.approved}")
    print(f"  Escalated: {result.escalated}")
    print(f"  Risk flags: {result.risk_flags}")
    print("  Review notes:")
    for note in result.review_notes:
        print(f"    - {note}")
    print()


async def demo_incomplete_flow() -> None:
    """Run a document with incomplete information."""
    print("=== Incomplete Flow: Missing Information ===\n")

    state = ReviewState()
    start_node = ReceiveDocument(
        security_name="Mystery Fund",
        issuer="Unknown Corp",
        description="Short.",  # Too short — will trigger RequestMoreInfo
    )

    result, history = await review_graph.run(
        start_node,
        state=state,
    )

    print(f"  Security: {result.security_name}")
    print(f"  Category: {result.category.value if result.category else 'None'}")
    print("  Review notes:")
    for note in result.review_notes:
        print(f"    - {note}")
    print()


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    print("=" * 70)
    print("MODULE 07: GRAPH FUNDAMENTALS WITH PYDANTIC-GRAPH")
    print("State machines where types define topology")
    print("=" * 70)
    print()

    # Show the graph structure
    show_mermaid()

    # Demo flows
    await demo_normal_flow()
    await demo_escalation_flow()
    await demo_incomplete_flow()

    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. Nodes are dataclasses with async run() methods")
    print("  2. Return type annotations define the graph edges")
    print("  3. State (dataclass) persists across all nodes")
    print("  4. End[ResultType] terminates the graph with a typed result")
    print("  5. graph.mermaid_code() generates visual diagrams")
    print()
    print("NO AGENTS YET — this is pure graph logic.")
    print("Module 08 puts agents inside graph nodes for intelligent routing.")
    print()
    print("Next: Module 08 — Agents inside graphs + long-running workflows")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
