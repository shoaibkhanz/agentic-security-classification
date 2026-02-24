"""
Capstone graph: Confidence-driven classification workflow.

Architecture:
  InitialAssessment -> GatherInfo -> AssessConfidence
    -> [low confidence] PlanNextAction -> GatherInfo (loop)
    -> [high confidence] Classify -> Verify
      -> [issues found] PlanNextAction (loop back)
      -> [verified] End[ClassificationResult]

The graph provides STRUCTURE. The agents provide INTELLIGENCE.
State accumulates evidence, confidence history, and agent messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from pydantic_graph import BaseNode, End, Graph, GraphRunContext, Edge

from capstone.agents import (
    classifier,
    confidence_assessor,
    initial_assessor,
    question_planner,
    researcher,
    verifier,
)
from capstone.models import ClassificationState
from shared.deps import AnalystContext
from shared.models import ClassificationResult, EvidenceSource, NextAction


# =============================================================================
# Node 1: Initial Assessment
# =============================================================================


@dataclass
class InitialAssessment(
    BaseNode[ClassificationState, AnalystContext, ClassificationResult]
):
    """
    Entry point: assess the security description and plan the first action.
    """

    async def run(
        self,
        ctx: GraphRunContext[ClassificationState],
    ) -> Annotated[GatherInfo, Edge(label="research")]:
        """Run initial assessment agent on the raw description."""
        result = await initial_assessor.run(
            f"Assess this security for classification:\n\n"
            f"{ctx.state.security_description}",
        )

        assessment = result.output

        # Initialize state from assessment
        ctx.state.current_confidence = assessment.initial_confidence.score
        ctx.state.current_top_category = assessment.initial_confidence.top_category
        ctx.state.confidence_history.append(assessment.initial_confidence)

        # Queue the first action
        ctx.state.actions_taken.append(assessment.suggested_first_action)

        return GatherInfo(action=assessment.suggested_first_action)


# =============================================================================
# Node 2: Gather Info
# =============================================================================


@dataclass
class GatherInfo(BaseNode[ClassificationState, AnalystContext, ClassificationResult]):
    """
    Execute a research action using the researcher agent.
    The action was planned by the question_planner or initial_assessor.
    """

    action: NextAction | None = None

    async def run(
        self,
        ctx: GraphRunContext[ClassificationState],
    ) -> Annotated[AssessConfidence, Edge(label="assess")]:
        """Execute the planned research action."""
        action = self.action or NextAction(
            action_type="query_db",
            detail=ctx.state.security_description[:100],
            expected_info_gain="Search for matching securities",
            estimated_confidence_after=0.5,
        )

        # Build context for the researcher
        evidence_summary = ""
        if ctx.state.research_findings:
            evidence_summary = "\n\nPrevious findings:\n" + "\n".join(
                f"- {f.finding[:150]}" for f in ctx.state.research_findings
            )

        prompt = (
            f"Execute this research action for classifying a security:\n\n"
            f"Security: {ctx.state.security_description}\n\n"
            f"Action: {action.action_type}\n"
            f"Detail: {action.detail}\n"
            f"Rationale: {action.expected_info_gain}"
            f"{evidence_summary}"
        )

        deps = ctx.deps or AnalystContext.create()
        result = await researcher.run(
            prompt,
            deps=deps,
            message_history=ctx.state.researcher_messages,
        )
        ctx.state.researcher_messages = list(result.all_messages())

        finding = result.output
        ctx.state.research_findings.append(finding)
        ctx.state.gathered_evidence.append(finding.evidence)
        ctx.state.questions_asked += 1

        return AssessConfidence()


# =============================================================================
# Node 3: Assess Confidence
# =============================================================================


@dataclass
class AssessConfidence(
    BaseNode[ClassificationState, AnalystContext, ClassificationResult]
):
    """
    Re-estimate confidence after new evidence.
    Routes to Classify if confident enough, otherwise PlanNextAction.
    """

    async def run(
        self,
        ctx: GraphRunContext[ClassificationState],
    ) -> (
        Annotated[Classify, Edge(label="confident enough")]
        | Annotated[PlanNextAction, Edge(label="need more info")]
    ):
        """Assess confidence and decide next step."""
        # Build evidence summary for the assessor
        evidence_lines = []
        for finding in ctx.state.research_findings:
            evidence_lines.append(
                f"- [{finding.evidence.source_type}] {finding.finding[:200]}"
            )
        evidence_text = (
            "\n".join(evidence_lines) if evidence_lines else "No evidence yet."
        )

        prompt = (
            f"Assess classification confidence for this security:\n\n"
            f"Description: {ctx.state.security_description}\n\n"
            f"Evidence gathered ({len(ctx.state.research_findings)} findings):\n"
            f"{evidence_text}\n\n"
            f"Previous confidence: {ctx.state.current_confidence:.0%}\n"
            f"Actions taken so far: {ctx.state.questions_asked}"
        )

        result = await confidence_assessor.run(
            prompt,
            message_history=ctx.state.assessor_messages,
        )
        ctx.state.assessor_messages = list(result.all_messages())

        estimate = result.output
        ctx.state.confidence_history.append(estimate)
        ctx.state.current_confidence = estimate.score
        ctx.state.current_top_category = estimate.top_category

        # Decision: confident enough or need more?
        if (
            estimate.score >= ctx.state.confidence_threshold
            or ctx.state.questions_asked >= ctx.state.max_actions
        ):
            return Classify()

        return PlanNextAction()


# =============================================================================
# Node 4: Plan Next Action
# =============================================================================


@dataclass
class PlanNextAction(
    BaseNode[ClassificationState, AnalystContext, ClassificationResult]
):
    """
    Plan the next highest-value research action.
    Optimizes for maximum confidence gain per action.
    """

    async def run(
        self,
        ctx: GraphRunContext[ClassificationState],
    ) -> Annotated[GatherInfo, Edge(label="execute action")]:
        """Plan the next action and transition to GatherInfo."""
        # Build context showing what's known and what's still uncertain
        evidence_lines = []
        for finding in ctx.state.research_findings:
            evidence_lines.append(f"- {finding.finding[:150]}")
        evidence_text = "\n".join(evidence_lines) if evidence_lines else "None yet."

        actions_taken = []
        for action in ctx.state.actions_taken:
            actions_taken.append(f"- {action.action_type}: {action.detail}")
        actions_text = "\n".join(actions_taken) if actions_taken else "None yet."

        uncertainty_reasons = []
        if ctx.state.confidence_history:
            latest = ctx.state.confidence_history[-1]
            uncertainty_reasons = latest.uncertainty_reasons

        prompt = (
            f"Plan the next research action to classify this security:\n\n"
            f"Description: {ctx.state.security_description}\n\n"
            f"Current confidence: {ctx.state.current_confidence:.0%}\n"
            f"Current best guess: {ctx.state.current_top_category}\n"
            f"Target confidence: {ctx.state.confidence_threshold:.0%}\n"
            f"Actions remaining: {ctx.state.max_actions - ctx.state.questions_asked}\n\n"
            f"Evidence gathered:\n{evidence_text}\n\n"
            f"Actions already taken:\n{actions_text}\n\n"
            f"What's still uncertain:\n"
            + "\n".join(f"- {r}" for r in uncertainty_reasons)
            + "\n\nWhat single action would most increase confidence?"
        )

        result = await question_planner.run(
            prompt,
            message_history=ctx.state.planner_messages,
        )
        ctx.state.planner_messages = list(result.all_messages())

        next_action = result.output
        ctx.state.actions_taken.append(next_action)

        return GatherInfo(action=next_action)


# =============================================================================
# Node 5: Classify
# =============================================================================


@dataclass
class Classify(BaseNode[ClassificationState, AnalystContext, ClassificationResult]):
    """
    Produce the final classification with full reasoning chain.
    Routes to Verify for consistency check.
    """

    async def run(
        self,
        ctx: GraphRunContext[ClassificationState],
    ) -> Annotated[Verify, Edge(label="verify")]:
        """Generate final classification from accumulated evidence."""
        # Build comprehensive prompt with all evidence
        evidence_lines = []
        for i, finding in enumerate(ctx.state.research_findings, 1):
            evidence_lines.append(
                f"  {i}. [{finding.evidence.source_type}] {finding.finding}"
            )
        evidence_text = "\n".join(evidence_lines)

        confidence_progression = " -> ".join(
            f"{est.score:.0%}({est.top_category.value})"
            for est in ctx.state.confidence_history
        )

        prompt = (
            f"Classify this private security based on all evidence gathered.\n\n"
            f"Security description:\n{ctx.state.security_description}\n\n"
            f"Evidence gathered ({len(ctx.state.research_findings)} findings):\n"
            f"{evidence_text}\n\n"
            f"Confidence progression: {confidence_progression}\n"
            f"Current confidence: {ctx.state.current_confidence:.0%}\n"
            f"Current best category: {ctx.state.current_top_category}\n"
            f"Questions asked: {ctx.state.questions_asked}\n\n"
            f"Produce a classification with:\n"
            f"- The category and confidence score\n"
            f"- A reasoning chain where each step cites specific evidence\n"
            f"- Evidence sources list\n"
            f"- Alternative classifications considered\n"
            f"- A summary explaining the classification"
        )

        result = await classifier.run(
            prompt,
            message_history=ctx.state.classifier_messages,
        )
        ctx.state.classifier_messages = list(result.all_messages())
        ctx.state.final_result = result.output

        return Verify()


# =============================================================================
# Node 6: Verify
# =============================================================================


@dataclass
class Verify(BaseNode[ClassificationState, AnalystContext, ClassificationResult]):
    """
    Verify the classification for logical consistency.
    Can accept, request more evidence, or trigger reclassification.
    """

    async def run(
        self,
        ctx: GraphRunContext[ClassificationState],
    ) -> (
        Annotated[End[ClassificationResult], Edge(label="verified")]
        | Annotated[PlanNextAction, Edge(label="needs more evidence")]
    ):
        """Verify the classification reasoning."""
        if ctx.state.final_result is None:
            # Should not happen, but handle gracefully
            return PlanNextAction()

        classification = ctx.state.final_result

        # Build verification prompt
        reasoning_chain = "\n".join(
            f"  Step {step.step}: [{step.source}] {step.evidence} -> {step.inference} "
            f"(confidence delta: {step.confidence_delta:+.2f})"
            for step in classification.reasoning
        )

        prompt = (
            f"Verify this securities classification:\n\n"
            f"Security: {ctx.state.security_description}\n\n"
            f"Classification: {classification.category.value}\n"
            f"Confidence: {classification.confidence:.0%}\n\n"
            f"Reasoning chain:\n{reasoning_chain}\n\n"
            f"Evidence sources: {len(classification.evidence_sources)}\n"
            f"Alternative classifications: "
            + ", ".join(
                f"{alt.category.value} ({alt.confidence:.0%})"
                for alt in classification.alternative_classifications
            )
            + f"\n\nSummary: {classification.summary}\n\n"
            f"Is this classification logically consistent and well-supported?"
        )

        result = await verifier.run(
            prompt,
            message_history=ctx.state.verifier_messages,
        )
        ctx.state.verifier_messages = list(result.all_messages())
        verification = result.output

        if verification.recommendation == "accept":
            return End(classification)

        # If verifier says gather more and we haven't hit limits
        if (
            verification.recommendation in ("gather_more", "reclassify")
            and ctx.state.questions_asked < ctx.state.max_actions
        ):
            ctx.state.current_confidence = verification.adjusted_confidence
            ctx.state.gathered_evidence.append(
                EvidenceSource(
                    source_type="database",
                    source_detail="verifier",
                    content=f"Verification issues: {'; '.join(verification.issues_found)}",
                )
            )
            return PlanNextAction()

        # Hit limits — accept the classification as-is
        return End(classification)


# =============================================================================
# Build the Graph
# =============================================================================

classification_graph = Graph(
    nodes=(
        InitialAssessment,
        GatherInfo,
        AssessConfidence,
        PlanNextAction,
        Classify,
        Verify,
    ),
)


# =============================================================================
# Convenience runner
# =============================================================================


async def classify_security(
    description: str,
    deps: AnalystContext | None = None,
    confidence_threshold: float = 0.82,
    max_actions: int = 8,
) -> tuple[ClassificationResult, ClassificationState]:
    """
    Run the full classification pipeline on a security description.

    Returns the classification result and the final state (for inspection).
    """
    if deps is None:
        deps = AnalystContext.create()

    state = ClassificationState(
        security_description=description,
        confidence_threshold=confidence_threshold,
        max_actions=max_actions,
    )

    result, _history = await classification_graph.run(
        InitialAssessment(),
        state=state,
        deps=deps,
    )

    return result, state
