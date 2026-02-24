"""
JSON file-based persistence for classification history.

Thread-safe via asyncio.Lock. Stores classification results
and user corrections so the frontend can display history
and the feedback loop works across sessions.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from web.api.schemas import ClassificationRecord, CorrectionRecord, OperatorReview


DATA_DIR = Path(__file__).parent / "data"
HISTORY_FILE = DATA_DIR / "classifications.json"


class ClassificationStore:
    """Async-safe JSON file store for classification records."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._ensure_data_dir()

    def _ensure_data_dir(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not HISTORY_FILE.exists():
            HISTORY_FILE.write_text("[]")

    def _read_all(self) -> list[dict[str, Any]]:
        try:
            return json.loads(HISTORY_FILE.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_all(self, records: list[dict[str, Any]]) -> None:
        HISTORY_FILE.write_text(json.dumps(records, indent=2, default=str))

    async def save_classification(
        self,
        description: str,
        result: dict[str, Any],
        additional_context: str | None = None,
    ) -> str:
        """Save a new classification result. Returns the record ID."""
        record_id = str(uuid.uuid4())[:8]
        record = ClassificationRecord(
            id=record_id,
            description=description,
            additional_context=additional_context,
            result=result,
            corrections=[],
            created_at=datetime.now(timezone.utc),
        )

        async with self._lock:
            records = self._read_all()
            records.append(record.model_dump(mode="json"))
            self._write_all(records)

        return record_id

    async def get_all(self) -> list[ClassificationRecord]:
        """Get all classification records, newest first."""
        async with self._lock:
            raw = self._read_all()
        records = [ClassificationRecord.model_validate(r) for r in raw]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records

    async def get_by_id(self, record_id: str) -> ClassificationRecord | None:
        """Get a single record by ID."""
        async with self._lock:
            raw = self._read_all()
        for r in raw:
            if r.get("id") == record_id:
                return ClassificationRecord.model_validate(r)
        return None

    async def add_correction(
        self,
        record_id: str,
        feedback: str,
        correct_category: str | None = None,
        new_result_id: str | None = None,
    ) -> bool:
        """Add a correction to an existing record. Returns True if found."""
        correction = CorrectionRecord(
            feedback=feedback,
            correct_category=correct_category,
            new_result_id=new_result_id,
            created_at=datetime.now(timezone.utc),
        )

        async with self._lock:
            records = self._read_all()
            for record in records:
                if record.get("id") == record_id:
                    record.setdefault("corrections", []).append(
                        correction.model_dump(mode="json")
                    )
                    self._write_all(records)
                    return True
        return False

    async def add_operator_review(
        self,
        record_id: str,
        action: str,
        override_category: str | None = None,
        comment: str | None = None,
    ) -> bool:
        """Add an operator review to a record. Returns True if found."""
        review = OperatorReview(
            action=action,
            override_category=override_category,
            comment=comment,
            reviewed_at=datetime.now(timezone.utc),
        )

        async with self._lock:
            records = self._read_all()
            for record in records:
                if record.get("id") == record_id:
                    record.setdefault("operator_reviews", []).append(
                        review.model_dump(mode="json")
                    )
                    # Mark result as reviewed
                    if "result" in record and isinstance(record["result"], dict):
                        record["result"]["operator_reviewed"] = True
                        if action == "override" and override_category:
                            record["result"]["category"] = override_category
                    self._write_all(records)
                    return True
        return False

    async def delete(self, record_id: str) -> bool:
        """Delete a record by ID. Returns True if found."""
        async with self._lock:
            records = self._read_all()
            filtered = [r for r in records if r.get("id") != record_id]
            if len(filtered) == len(records):
                return False
            self._write_all(filtered)
            return True


# Singleton instance
store = ClassificationStore()
