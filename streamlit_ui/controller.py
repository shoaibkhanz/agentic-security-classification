"""Controller that consumes stream events into a view snapshot."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

try:
    from streamlit_ui.state import ClassificationSnapshot, ClassificationStateMachine
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    from state import ClassificationSnapshot, ClassificationStateMachine


def run_classification_stream(
    client: Any,
    description: str,
    additional_context: str | None = None,
    confidence_threshold: float = 0.82,
    demo: bool = False,
    on_event: Callable[[ClassificationSnapshot, dict[str, Any]], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> ClassificationSnapshot:
    """
    Execute one classification stream and return final snapshot state.

    `client` must expose `stream_classification(...)` yielding parsed SSE events.
    """

    snapshot = ClassificationStateMachine.start(ClassificationSnapshot())
    started_at = time.perf_counter()
    cancelled = False

    try:
        stream = client.stream_classification(
            description=description,
            additional_context=additional_context,
            confidence_threshold=confidence_threshold,
            demo=demo,
        )
        for event in stream:
            if should_cancel and should_cancel():
                cancelled = True
                break
            snapshot = ClassificationStateMachine.apply_event(snapshot, event)
            if on_event:
                on_event(snapshot, event)
    except Exception as exc:
        elapsed = time.perf_counter() - started_at
        error_event = {
            "event_type": "error",
            "timestamp": elapsed,
            "data": {"error": str(exc)},
        }
        snapshot = ClassificationStateMachine.apply_event(snapshot, error_event)

    return ClassificationStateMachine.finalize(snapshot, cancelled=cancelled)
