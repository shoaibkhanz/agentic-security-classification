"""
SSE streaming for the classification pipeline.

Uses pydantic-graph's `graph.iter()` to yield SSE events
as each graph node executes. This gives the frontend
live updates on the classification progress.
"""

from __future__ import annotations

import json
import time
import traceback
from collections.abc import AsyncGenerator
from typing import Any

from capstone.graph import InitialAssessment, classification_graph
from capstone.models import ClassificationState
from shared.deps import AnalystContext
from web.api.schemas import ClassifyRequest, StreamEvent

# ---------------------------------------------------------------------------
# Metadata maps for enriching SSE events
# ---------------------------------------------------------------------------

STAGE_MAP: dict[str, dict[str, str]] = {
    "InitialAssessment": {"stage": "I", "stage_name": "Initial Assessment"},
    "GatherInfo": {"stage": "II", "stage_name": "Research & Data Gathering"},
    "AssessConfidence": {"stage": "III", "stage_name": "Confidence Assessment"},
    "PlanNextAction": {"stage": "IV", "stage_name": "Action Planning"},
    "Classify": {"stage": "V", "stage_name": "Classification"},
    "Verify": {"stage": "VI", "stage_name": "Verification"},
}

TOOL_LABELS: dict[str, dict[str, str]] = {
    "query_db": {
        "tool_name": "Securities Database Query",
        "data_source": "Internal Database",
    },
    "search_sec": {
        "tool_name": "SEC EDGAR Data Parser",
        "data_source": "SEC EDGAR",
    },
    "search_web": {
        "tool_name": "Web Intelligence Search",
        "data_source": "Public Web",
    },
    "ask_question": {
        "tool_name": "Analyst Query",
        "data_source": "Human Input",
    },
}


def _serialize_event(event: StreamEvent) -> str:
    """Serialize a StreamEvent to JSON for SSE.

    Returns plain JSON — sse-starlette's EventSourceResponse adds
    the 'data:' prefix and newlines automatically.
    """
    return json.dumps(event.model_dump(mode="json"))


async def stream_classification(
    request: ClassifyRequest,
) -> AsyncGenerator[str, None]:
    """
    Run the classification pipeline and yield SSE events.

    Uses graph.iter() for node-by-node streaming.
    """
    description = request.description
    if request.additional_context:
        description += (
            f"\n\nAdditional context from analyst: {request.additional_context}"
        )

    state = ClassificationState(
        security_description=description,
        confidence_threshold=request.confidence_threshold,
    )
    deps = AnalystContext.create(analyst_name="WebUI")
    start = time.perf_counter()

    # Track previously seen findings/confidence to avoid duplicates
    seen_findings = 0
    seen_confidence = 0
    previous_confidence = 0.0
    initial_category: str | None = None

    try:
        async with classification_graph.iter(
            InitialAssessment(), state=state, deps=deps
        ) as run:
            async for node in run:
                elapsed = time.perf_counter() - start
                node_name = type(node).__name__
                stage_info = STAGE_MAP.get(node_name, {})

                # Build enriched node start event
                node_data: dict[str, Any] = {
                    "questions_asked": state.questions_asked,
                    "question_number": state.questions_asked,
                    "stage": stage_info.get("stage", ""),
                    "stage_name": stage_info.get("stage_name", ""),
                }
                if state.current_top_category is not None:
                    node_data["current_category"] = state.current_top_category.value
                    if initial_category is None:
                        initial_category = state.current_top_category.value

                if node_name == "GatherInfo" and state.actions_taken:
                    last_action = state.actions_taken[-1]
                    tool_info = TOOL_LABELS.get(last_action.action_type, {})
                    node_data["action_type"] = last_action.action_type
                    node_data["action_detail"] = last_action.detail
                    node_data["tool_name"] = tool_info.get(
                        "tool_name", last_action.action_type
                    )
                    node_data["data_source"] = tool_info.get("data_source", "Unknown")
                    node_data["expected_info_gain"] = last_action.expected_info_gain

                yield _serialize_event(
                    StreamEvent(
                        event_type="node_start",
                        node_name=node_name,
                        data=node_data,
                        timestamp=elapsed,
                    )
                )

                # Emit new confidence updates with delta
                if len(state.confidence_history) > seen_confidence:
                    for estimate in state.confidence_history[seen_confidence:]:
                        delta = estimate.score - previous_confidence
                        yield _serialize_event(
                            StreamEvent(
                                event_type="confidence_update",
                                node_name=node_name,
                                data={
                                    "score": estimate.score,
                                    "top_category": estimate.top_category.value,
                                    "runner_up": (
                                        estimate.runner_up.value
                                        if estimate.runner_up
                                        else None
                                    ),
                                    "uncertainty_reasons": estimate.uncertainty_reasons,
                                    "step": seen_confidence + 1,
                                    "confidence_delta": round(delta, 4),
                                    "confidence_delta_pct": round(delta * 100),
                                },
                                timestamp=elapsed,
                            )
                        )
                        previous_confidence = estimate.score
                    seen_confidence = len(state.confidence_history)

                # Emit new evidence findings with tool metadata
                if len(state.research_findings) > seen_findings:
                    for finding in state.research_findings[seen_findings:]:
                        tool_info = TOOL_LABELS.get(finding.evidence.source_type, {})
                        yield _serialize_event(
                            StreamEvent(
                                event_type="evidence_found",
                                node_name=node_name,
                                data={
                                    "finding": finding.finding,
                                    "source_type": finding.evidence.source_type,
                                    "source_detail": finding.evidence.source_detail,
                                    "content": finding.evidence.content[:500],
                                    "relevance": finding.relevance,
                                    "question_number": state.questions_asked,
                                    "tool_name": tool_info.get(
                                        "tool_name",
                                        finding.evidence.source_type,
                                    ),
                                    "data_source": tool_info.get(
                                        "data_source", "Unknown"
                                    ),
                                },
                                timestamp=elapsed,
                            )
                        )
                    seen_findings = len(state.research_findings)

        # Final result with enriched metadata
        elapsed = time.perf_counter() - start
        result_data: dict[str, Any] = {}
        if state.final_result is not None:
            result_data = state.final_result.model_dump(mode="json")
        result_data["total_duration"] = round(elapsed, 2)
        result_data["prior_category"] = initial_category
        result_data["needs_operator_review"] = (
            state.final_result.confidence < 1.0 if state.final_result else True
        )
        result_data["uncertainty_reasons"] = (
            state.confidence_history[-1].uncertainty_reasons
            if state.confidence_history
            else []
        )
        # Build audit comment from reasoning
        if state.final_result:
            steps = state.final_result.reasoning
            audit_parts = []
            for step in steps[:3]:
                audit_parts.append(f"{step.source}: {step.inference}")
            result_data["audit_comment"] = ". ".join(audit_parts) if audit_parts else ""

        yield _serialize_event(
            StreamEvent(
                event_type="result",
                node_name="End",
                data=result_data,
                timestamp=elapsed,
            )
        )

    except Exception as exc:
        elapsed = time.perf_counter() - start
        yield _serialize_event(
            StreamEvent(
                event_type="error",
                node_name=None,
                data={
                    "error": str(exc),
                    "type": type(exc).__name__,
                    "traceback": traceback.format_exc(),
                },
                timestamp=elapsed,
            )
        )
