from __future__ import annotations

from streamlit_ui.controller import run_classification_stream


class FakeClient:
    def __init__(self, events: list[dict[str, object]]) -> None:
        self._events = events

    def stream_classification(
        self,
        description: str,
        additional_context: str | None = None,
        confidence_threshold: float = 0.82,
        demo: bool = False,
    ):
        assert description == "Atlas notes"
        assert confidence_threshold == 0.82
        assert demo is True
        _ = additional_context
        for event in self._events:
            yield event


def test_run_classification_stream_builds_complete_snapshot() -> None:
    client = FakeClient(
        events=[
            {
                "event_type": "node_start",
                "timestamp": 0.1,
                "data": {
                    "question_number": 1,
                    "stage": "II",
                    "stage_name": "Research",
                    "action_detail": "query data",
                },
            },
            {
                "event_type": "confidence_update",
                "timestamp": 0.2,
                "data": {"step": 1, "score": 0.65, "top_category": "debt"},
            },
            {
                "event_type": "evidence_found",
                "timestamp": 0.3,
                "data": {
                    "question_number": 1,
                    "finding": "Found filing",
                    "source_type": "sec_filing",
                    "source_detail": "Form D",
                    "content": "Details",
                    "relevance": "high",
                },
            },
            {
                "event_type": "result",
                "timestamp": 1.1,
                "data": {"category": "debt", "confidence": 0.95},
            },
            {
                "event_type": "saved",
                "timestamp": 1.2,
                "data": {"record_id": "rec-1"},
            },
        ]
    )

    snapshot = run_classification_stream(
        client=client,
        description="Atlas notes",
        demo=True,
    )

    assert snapshot.status == "complete"
    assert snapshot.result is not None
    assert snapshot.result["category"] == "debt"
    assert snapshot.record_id == "rec-1"
    assert snapshot.confidence_history[0]["score"] == 0.65
    assert snapshot.evidence_list[0]["finding"] == "Found filing"
    assert snapshot.workflow_stages[0]["stage"] == "II"


def test_run_classification_stream_sets_error_when_result_missing() -> None:
    client = FakeClient(
        events=[
            {"event_type": "node_start", "timestamp": 0.1, "data": {}},
        ]
    )

    snapshot = run_classification_stream(
        client=client,
        description="Atlas notes",
        demo=True,
    )

    assert snapshot.status == "error"
    assert snapshot.error == "Stream ended without a result"

