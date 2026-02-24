"""
Capstone runner: Private Securities Classification Agent.

Run with:
    uv run python -m capstone.run

This demonstrates the full confidence-driven classification pipeline:
1. Initial assessment from the raw description
2. Iterative research to build evidence
3. Confidence tracking to know when to stop
4. Final classification with reasoning chain
5. Verification of reasoning consistency
"""

from __future__ import annotations

import asyncio

from capstone.graph import (
    InitialAssessment,
    classification_graph,
    classify_security,
)
from capstone.models import ClassificationState
from shared.deps import AnalystContext


async def demo_single_classification() -> None:
    """Classify a single security to show the full pipeline."""
    print("=== Single Classification: NovaTech SAFE ===\n")

    result, state = await classify_security(
        description=(
            "NovaTech AI Inc is raising $5M via Simple Agreement for Future "
            "Equity (SAFE) instruments. 20% discount to next priced round, "
            "$20M valuation cap. Y Combinator standard SAFE terms. "
            "Pre-seed stage AI/ML startup."
        ),
    )

    print(f"  Category: {result.category.value}")
    print(f"  Confidence: {result.confidence:.0%}")
    print(f"  Questions asked: {state.questions_asked}")
    print(f"  Evidence sources: {len(result.evidence_sources)}")
    print()

    print("  Reasoning chain:")
    for step in result.reasoning:
        delta = (
            f"+{step.confidence_delta:.2f}"
            if step.confidence_delta > 0
            else f"{step.confidence_delta:.2f}"
        )
        print(f"    Step {step.step}: [{delta}] {step.inference[:100]}")
    print()

    if result.alternative_classifications:
        print("  Alternatives considered:")
        for alt in result.alternative_classifications:
            print(
                f"    - {alt.category.value} ({alt.confidence:.0%}): {alt.reasoning[:80]}"
            )
        print()

    print(f"  Summary: {result.summary[:200]}")
    print()

    # Show confidence progression
    print("  Confidence progression:")
    for i, est in enumerate(state.confidence_history):
        print(
            f"    Step {i}: {est.score:.0%} -> {est.top_category.value}"
            f" (uncertainties: {len(est.uncertainty_reasons)})"
        )
    print()


async def demo_step_by_step() -> None:
    """Show step-by-step execution with graph.iter()."""
    print("=== Step-by-Step: Hybrid Instrument ===\n")

    deps = AnalystContext.create()
    state = ClassificationState(
        security_description=(
            "Apex Hybrid Instrument 2024: Pays 4% coupon with mandatory "
            "conversion to common equity at maturity. 5-year duration. "
            "Functions as debt during term, becomes equity at maturity. "
            "$12M offering under Reg D 506(c)."
        ),
        confidence_threshold=0.80,
        max_actions=6,
    )

    step_count = 0
    async with classification_graph.iter(
        InitialAssessment(),
        state=state,
        deps=deps,
    ) as run:
        async for node in run:
            step_count += 1
            node_name = type(node).__name__

            from pydantic_graph import End

            if isinstance(node, End):
                print(f"  Step {step_count}: END")
                result = node.data
                print(f"    Category: {result.category.value}")
                print(f"    Confidence: {result.confidence:.0%}")
                break

            print(f"  Step {step_count}: {node_name}")
            print(
                f"    Confidence: {state.current_confidence:.0%} "
                f"| Evidence: {len(state.research_findings)} "
                f"| Actions: {state.questions_asked}"
            )

    print(f"\n  Total steps: {step_count}")
    print(f"  Final category: {state.current_top_category}")
    print()


async def demo_multiple_classifications() -> None:
    """Classify multiple securities to show pipeline versatility."""
    print("=== Multiple Classifications ===\n")

    securities = [
        (
            "Atlas Senior Secured Notes 2024: $25M in 3-year senior secured "
            "notes bearing 8.5% annual interest, paid quarterly. Notes are "
            "secured by infrastructure asset portfolio."
        ),
        (
            "Meridian Growth Fund LP: Limited partnership interests in a "
            "diversified private equity fund targeting mid-market buyouts. "
            "$250K minimum. Accredited investors only."
        ),
        (
            "Cascade Robotics SAFE+Note: Hybrid SAFE with note-like features. "
            "Accrues 5% interest, converts at next priced round with 20% "
            "discount, $10M cap."
        ),
    ]

    for description in securities:
        short_name = description.split(":")[0]
        print(f"  Classifying: {short_name}")

        result, state = await classify_security(
            description=description,
            max_actions=5,
        )

        print(f"    -> {result.category.value} ({result.confidence:.0%})")
        print(
            f"       Questions: {state.questions_asked} | Evidence: {len(result.evidence_sources)}"
        )
        print()


async def demo_graph_structure() -> None:
    """Show the graph structure as a Mermaid diagram."""
    print("=== Graph Structure (Mermaid) ===\n")
    print(classification_graph.mermaid_code(start_node=InitialAssessment))
    print()


async def main() -> None:
    print("=" * 70)
    print("CAPSTONE: PRIVATE SECURITIES CLASSIFICATION AGENT")
    print("Confidence-driven classification with adaptive research")
    print("=" * 70)
    print()

    # Show graph structure
    await demo_graph_structure()

    # Single classification with full output
    await demo_single_classification()

    # Step-by-step execution
    await demo_step_by_step()

    # Multiple classifications
    await demo_multiple_classifications()

    print("=" * 70)
    print("ARCHITECTURE:")
    print("  Graph nodes: InitialAssessment -> GatherInfo -> AssessConfidence")
    print("    -> [low confidence] PlanNextAction -> GatherInfo (loop)")
    print("    -> [high confidence] Classify -> Verify -> End")
    print()
    print("AGENTS:")
    print("  question_planner  - Decides highest-value next action")
    print("  researcher        - Executes research with tools")
    print("  confidence_assessor - Re-estimates confidence after evidence")
    print("  classifier        - Produces final ClassificationResult")
    print("  verifier          - Checks reasoning consistency")
    print()
    print("KEY INNOVATION:")
    print("  The agent optimizes for CONFIDENCE, not for following a fixed")
    print("  questionnaire. At each step it asks: 'What single action would")
    print("  most reduce my uncertainty about this classification?'")
    print()
    print("NEXT STEPS:")
    print("  uv run python -m capstone.evaluate   # Run evaluation suite")
    print("  uv run python -m capstone.compare_models  # Compare models")
    print("  uv run mlflow server --port 5000      # View traces")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
