"""Synchronous API client for the Streamlit frontend."""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Any

import httpx

try:
    from streamlit_ui.sse_parser import parse_sse_events
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    from sse_parser import parse_sse_events


DEFAULT_API_BASE_URL = "http://localhost:8000"


class StreamlitAPIClient:
    """Thin sync client over the current `/api/*` surface."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        resolved_base = (
            base_url or os.getenv("CLASSIFIER_API_BASE_URL", DEFAULT_API_BASE_URL)
        )
        self.base_url = resolved_base.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self.transport,
        )

    def _request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        with self._client() as client:
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

    def fetch_examples(self) -> list[dict[str, Any]]:
        return self._request_json("GET", "/api/examples")

    def fetch_history(self) -> list[dict[str, Any]]:
        return self._request_json("GET", "/api/history")

    def fetch_history_record(self, record_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"/api/history/{record_id}")

    def delete_history_record(self, record_id: str) -> dict[str, Any]:
        return self._request_json("DELETE", f"/api/history/{record_id}")

    def submit_feedback(
        self,
        record_id: str,
        feedback: str,
        correct_category: str | None = None,
        rerun: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "feedback": feedback,
            "correct_category": correct_category,
            "rerun": rerun,
        }
        return self._request_json("POST", f"/api/feedback/{record_id}", json=payload)

    def fetch_operator_queue(self) -> list[dict[str, Any]]:
        return self._request_json("GET", "/api/operator-queue")

    def submit_operator_review(
        self,
        record_id: str,
        action: str,
        override_category: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "action": action,
            "override_category": override_category,
            "comment": comment,
        }
        return self._request_json(
            "POST",
            f"/api/operator-review/{record_id}",
            json=payload,
        )

    def submit_chat(self, record_id: str, message: str) -> dict[str, Any]:
        return self._request_json(
            "POST",
            f"/api/chat/{record_id}",
            params={"message": message},
        )

    def stream_classification(
        self,
        description: str,
        additional_context: str | None = None,
        confidence_threshold: float = 0.82,
        demo: bool = False,
    ) -> Iterable[dict[str, Any]]:
        payload = {
            "description": description,
            "additional_context": additional_context,
            "confidence_threshold": confidence_threshold,
            "demo": demo,
        }

        with self._client() as client:
            with client.stream("POST", "/api/classify", json=payload) as response:
                response.raise_for_status()
                for event in parse_sse_events(response.iter_lines()):
                    yield event
