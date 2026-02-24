"""Pure state transitions and view models for streamed classification events."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any


def _safe_list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def build_confidence_history(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") != "confidence_update":
            continue
        data = event.get("data", {})
        history.append(
            {
                "step": int(data.get("step", len(history) + 1)),
                "score": float(data.get("score", 0.0)),
                "category": str(data.get("top_category", "unknown")),
            }
        )
    return history


def build_evidence_list(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") != "evidence_found":
            continue
        data = event.get("data", {})
        evidence.append(
            {
                "finding": data.get("finding", ""),
                "sourceType": data.get("source_type", "unknown"),
                "sourceDetail": data.get("source_detail", ""),
                "content": data.get("content", ""),
                "relevance": data.get("relevance", "unknown"),
                "questionNumber": int(data.get("question_number", 0)),
            }
        )
    return evidence


def build_workflow_questions(
    events: list[dict[str, Any]],
    status: str,
) -> list[dict[str, Any]]:
    node_starts = [event for event in events if event.get("event_type") == "node_start"]
    confidence_events = [
        event for event in events if event.get("event_type") == "confidence_update"
    ]
    evidence_events = [event for event in events if event.get("event_type") == "evidence_found"]

    questions: list[dict[str, Any]] = []
    for idx, event in enumerate(node_starts):
        data = event.get("data", {})
        q_num = int(data.get("question_number", idx + 1))
        confidence_match = next(
            (
                confidence
                for confidence in confidence_events
                if int(confidence.get("data", {}).get("step", -1)) == q_num
            ),
            None,
        )
        evidence_match = next(
            (
                finding
                for finding in evidence_events
                if int(finding.get("data", {}).get("question_number", -1)) == q_num
            ),
            None,
        )

        is_last = idx == len(node_starts) - 1
        question_status = "complete" if status == "complete" or not is_last else "active"

        questions.append(
            {
                "questionNumber": q_num,
                "stage": data.get("stage", ""),
                "stageName": data.get("stage_name", ""),
                "actionDetail": data.get("action_detail"),
                "finding": (
                    evidence_match.get("data", {}).get("finding")
                    if isinstance(evidence_match, dict)
                    else None
                ),
                "status": question_status,
                "confidenceDelta": (
                    confidence_match.get("data", {}).get("confidence_delta")
                    if isinstance(confidence_match, dict)
                    else None
                ),
                "timestamp": float(event.get("timestamp", 0.0)),
            }
        )
    return questions


def build_workflow_stages(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for question in questions:
        stage = str(question.get("stage", "unknown"))
        if stage not in grouped:
            grouped[stage] = {
                "stage": question.get("stage", ""),
                "stageName": question.get("stageName", ""),
                "questions": [],
            }
        grouped[stage]["questions"].append(question)
    return list(grouped.values())


def build_execution_details(
    result: dict[str, Any] | None,
    workflow_questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(result, dict):
        reasoning = _safe_list(result.get("reasoning"))
        if reasoning:
            return reasoning

    details: list[dict[str, Any]] = []
    for idx, question in enumerate(workflow_questions):
        details.append(
            {
                "step": int(question.get("questionNumber", idx + 1)),
                "source": question.get("stageName") or "workflow",
                "inference": question.get("finding")
                or question.get("actionDetail")
                or "Step in progress...",
                "evidence": question.get("finding")
                or question.get("actionDetail")
                or "Waiting for evidence...",
                "confidence_delta": question.get("confidenceDelta", 0),
            }
        )
    return details


@dataclass
class ClassificationSnapshot:
    status: str = "idle"
    events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    record_id: str | None = None
    error: str | None = None
    elapsed_seconds: float = 0.0
    started_at: float = 0.0
    confidence_history: list[dict[str, Any]] = field(default_factory=list)
    evidence_list: list[dict[str, Any]] = field(default_factory=list)
    workflow_questions: list[dict[str, Any]] = field(default_factory=list)
    workflow_stages: list[dict[str, Any]] = field(default_factory=list)
    execution_details: list[dict[str, Any]] = field(default_factory=list)


class ClassificationStateMachine:
    """Pure state transitions used by the Streamlit controller and tests."""

    @staticmethod
    def start(snapshot: ClassificationSnapshot) -> ClassificationSnapshot:
        snapshot.status = "streaming"
        snapshot.events = []
        snapshot.result = None
        snapshot.record_id = None
        snapshot.error = None
        snapshot.elapsed_seconds = 0.0
        snapshot.started_at = perf_counter()
        snapshot.confidence_history = []
        snapshot.evidence_list = []
        snapshot.workflow_questions = []
        snapshot.workflow_stages = []
        snapshot.execution_details = []
        return snapshot

    @staticmethod
    def apply_event(
        snapshot: ClassificationSnapshot,
        event: dict[str, Any],
    ) -> ClassificationSnapshot:
        snapshot.events.append(event)

        timestamp = event.get("timestamp")
        if isinstance(timestamp, (int, float)):
            snapshot.elapsed_seconds = float(timestamp)

        event_type = event.get("event_type")
        data = event.get("data", {})

        if event_type == "result" and isinstance(data, dict):
            snapshot.result = data
        elif event_type == "saved" and isinstance(data, dict):
            record_id = data.get("record_id")
            snapshot.record_id = str(record_id) if record_id is not None else None
        elif event_type == "error" and isinstance(data, dict):
            snapshot.status = "error"
            snapshot.error = str(data.get("error", "Classification failed"))

        snapshot.confidence_history = build_confidence_history(snapshot.events)
        snapshot.evidence_list = build_evidence_list(snapshot.events)
        snapshot.workflow_questions = build_workflow_questions(snapshot.events, snapshot.status)
        snapshot.workflow_stages = build_workflow_stages(snapshot.workflow_questions)
        snapshot.execution_details = build_execution_details(
            snapshot.result, snapshot.workflow_questions
        )

        return snapshot

    @staticmethod
    def finalize(
        snapshot: ClassificationSnapshot,
        cancelled: bool,
    ) -> ClassificationSnapshot:
        if cancelled:
            return ClassificationSnapshot(status="idle")

        if snapshot.status == "error":
            if snapshot.error is None:
                snapshot.error = "Classification failed"
            return snapshot

        if snapshot.result is not None:
            snapshot.status = "complete"
            snapshot.workflow_questions = build_workflow_questions(snapshot.events, "complete")
            snapshot.workflow_stages = build_workflow_stages(snapshot.workflow_questions)
            snapshot.execution_details = build_execution_details(
                snapshot.result, snapshot.workflow_questions
            )
            return snapshot

        snapshot.status = "error"
        snapshot.error = "Stream ended without a result"
        return snapshot

