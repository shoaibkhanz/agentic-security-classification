"""
API route definitions for the classification service.

Endpoints:
  POST /api/classify          - Start classification (SSE stream)
  POST /api/feedback/{id}     - Submit correction, optionally rerun
  GET  /api/history           - List past classifications
  GET  /api/history/{id}      - Get single classification
  DELETE /api/history/{id}    - Delete a record
  GET  /api/examples          - Example securities for the UI
  GET  /api/operator-queue    - Classifications needing operator review
  POST /api/operator-review/{id} - Submit operator review decision
  POST /api/chat/{id}         - Submit inline feedback message
  GET  /api/health            - Health check
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from shared.fake_data import SECURITIES_DATABASE
from web.api.memory import store
from web.api.schemas import (
    ClassifyRequest,
    ExampleSecurity,
    FeedbackRequest,
    OperatorReviewRequest,
)
from web.api.demo_streaming import stream_demo_classification
from web.api.streaming import stream_classification


router = APIRouter(prefix="/api")


# =============================================================================
# Health
# =============================================================================


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "securities-classifier"}


# =============================================================================
# Classification (SSE streaming)
# =============================================================================


@router.post("/classify")
async def classify(request: ClassifyRequest) -> EventSourceResponse:
    """
    Run the classification pipeline and stream results via SSE.

    The client receives a stream of StreamEvent objects as the
    pipeline executes each graph node.
    """

    # Use demo streaming when demo=True (no API key needed)
    streamer = stream_demo_classification if request.demo else stream_classification

    async def event_generator():
        result_data = None
        async for event_str in streamer(request):
            yield event_str

            # Capture the result event for persistence
            try:
                parsed = json.loads(event_str)
                if parsed.get("event_type") == "result":
                    result_data = parsed.get("data", {})
            except (json.JSONDecodeError, AttributeError):
                pass

        # Save to history after streaming completes
        if result_data is not None:
            record_id = await store.save_classification(
                description=request.description,
                result=result_data,
                additional_context=request.additional_context,
            )
            # Send the record ID as a final event
            yield json.dumps({"event_type": "saved", "data": {"record_id": record_id}})

    return EventSourceResponse(event_generator())


# =============================================================================
# Feedback / Corrections
# =============================================================================


@router.post("/feedback/{record_id}")
async def submit_feedback(
    record_id: str,
    request: FeedbackRequest,
) -> dict[str, object]:
    """Submit a correction for a classification."""
    record = await store.get_by_id(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")

    new_result_id = None

    # If rerun requested, we'll do a new classification with context
    if request.rerun:
        new_result_data = None
        classify_req = ClassifyRequest(
            description=record.description,
            additional_context=request.feedback,
        )
        async for event_str in stream_classification(classify_req):
            try:
                parsed = json.loads(event_str.replace("data: ", "").strip())
                if parsed.get("event_type") == "result":
                    new_result_data = parsed.get("data", {})
            except (json.JSONDecodeError, AttributeError):
                pass

        if new_result_data is not None:
            new_result_id = await store.save_classification(
                description=record.description,
                result=new_result_data,
                additional_context=request.feedback,
            )

    # Save the correction
    success = await store.add_correction(
        record_id=record_id,
        feedback=request.feedback,
        correct_category=request.correct_category,
        new_result_id=new_result_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")

    return {
        "status": "ok",
        "record_id": record_id,
        "new_result_id": new_result_id,
    }


# =============================================================================
# Operator Review
# =============================================================================


@router.get("/operator-queue")
async def get_operator_queue() -> list[dict[str, object]]:
    """Get classifications that need operator review (confidence < 100%)."""
    all_records = await store.get_all()
    queue = []
    for record in all_records:
        confidence = (
            record.result.get("confidence", 1.0)
            if isinstance(record.result, dict)
            else 1.0
        )
        reviewed = (
            record.result.get("operator_reviewed", False)
            if isinstance(record.result, dict)
            else False
        )
        if confidence < 1.0 and not reviewed:
            queue.append(record.model_dump(mode="json"))
    return queue


@router.post("/operator-review/{record_id}")
async def submit_operator_review(
    record_id: str,
    request: OperatorReviewRequest,
) -> dict[str, object]:
    """Submit operator review decision (approve/reject/override)."""
    record = await store.get_by_id(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")

    success = await store.add_operator_review(
        record_id=record_id,
        action=request.action,
        override_category=request.override_category,
        comment=request.comment,
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")

    return {"status": "ok", "record_id": record_id, "action": request.action}


@router.post("/chat/{record_id}")
async def submit_chat(record_id: str, message: str) -> dict[str, str]:
    """Submit operator chat message for a classification."""
    record = await store.get_by_id(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")

    await store.add_correction(
        record_id=record_id,
        feedback=message,
    )
    return {"status": "ok", "message": "Feedback recorded"}


# =============================================================================
# History
# =============================================================================


@router.get("/history")
async def list_history() -> list[dict[str, object]]:
    """List all past classifications, newest first."""
    records = await store.get_all()
    return [r.model_dump(mode="json") for r in records]


@router.get("/history/{record_id}")
async def get_history_record(record_id: str) -> dict[str, object]:
    """Get a single classification record with corrections."""
    record = await store.get_by_id(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")
    return record.model_dump(mode="json")


@router.delete("/history/{record_id}")
async def delete_history_record(record_id: str) -> dict[str, str]:
    """Delete a classification record."""
    success = await store.delete(record_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")
    return {"status": "deleted", "record_id": record_id}


# =============================================================================
# Examples
# =============================================================================

# Category code mappings
CATEGORY_CODES: dict[str, tuple[str, str]] = {
    "equity": ("A01", "Equity Securities"),
    "debt": ("A02", "Debt Securities"),
    "convertible_note": ("A03", "Convertible Notes"),
    "safe": ("A04", "SAFE Instruments"),
    "real_estate": ("A05", "Real Estate Securities"),
    "revenue_share": ("A06", "Revenue Participation"),
    "fund_interest": ("A08", "Private Equity Funds"),
    "other": ("A99", "Unclassified"),
}

# Curated example securities for the frontend cards
_EXAMPLE_CONFIG: dict[str, tuple[str, str]] = {
    # name: (difficulty, expected_category)
    "Atlas Senior Secured Notes 2024": ("easy", "debt"),
    "NovaTech SAFE Round": ("easy", "safe"),
    "Catalyst Convertible Note Series A": ("medium", "convertible_note"),
    "Riverview Revenue Participation": ("medium", "revenue_share"),
    "Apex Hybrid Instrument 2024": ("hard", "convertible_note"),
}


@router.get("/examples")
async def get_examples() -> list[ExampleSecurity]:
    """Return curated example securities for the frontend."""
    examples = []
    for sec in SECURITIES_DATABASE:
        if sec.name in _EXAMPLE_CONFIG:
            difficulty, category_key = _EXAMPLE_CONFIG[sec.name]
            code_info = CATEGORY_CODES.get(category_key, ("U98", "Unknown"))
            examples.append(
                ExampleSecurity(
                    name=sec.name,
                    issuer=sec.issuer,
                    description=sec.raw_description,
                    difficulty=difficulty,
                    type_hint=sec.type_hint,
                    category_code=code_info[0],
                    category_label=code_info[1],
                )
            )
    return examples
