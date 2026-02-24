from __future__ import annotations

import json

import httpx
import pytest

from streamlit_ui.api_client import StreamlitAPIClient


def test_fetch_history_returns_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/history"
        return httpx.Response(
            200,
            json=[{"id": "1", "description": "d", "result": {"confidence": 0.9}}],
        )

    client = StreamlitAPIClient(
        base_url="http://test", transport=httpx.MockTransport(handler)
    )

    history = client.fetch_history()

    assert history[0]["id"] == "1"


def test_submit_operator_review_posts_expected_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/operator-review/abc123"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["action"] == "override"
        assert payload["override_category"] == "debt"
        return httpx.Response(200, json={"status": "ok", "record_id": "abc123"})

    client = StreamlitAPIClient(
        base_url="http://test", transport=httpx.MockTransport(handler)
    )

    result = client.submit_operator_review(
        "abc123", action="override", override_category="debt", comment="manual"
    )

    assert result["status"] == "ok"


def test_stream_classification_parses_sse_events() -> None:
    sse_payload = "\n".join(
        [
            'data: {"event_type":"node_start","timestamp":0.1,"data":{"question_number":1}}',
            "",
            'data: {"event_type":"result","timestamp":1.2,"data":{"category":"debt","confidence":0.95}}',
            "",
            'data: {"event_type":"saved","timestamp":1.3,"data":{"record_id":"rec-1"}}',
            "",
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/classify"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["description"] == "Atlas notes"
        assert payload["demo"] is True
        return httpx.Response(
            200,
            text=sse_payload,
            headers={"content-type": "text/event-stream"},
        )

    client = StreamlitAPIClient(
        base_url="http://test", transport=httpx.MockTransport(handler)
    )

    events = list(client.stream_classification(description="Atlas notes", demo=True))

    assert [event["event_type"] for event in events] == ["node_start", "result", "saved"]


def test_delete_history_raises_on_not_found() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    client = StreamlitAPIClient(
        base_url="http://test", transport=httpx.MockTransport(handler)
    )

    with pytest.raises(httpx.HTTPStatusError):
        client.delete_history_record("missing")

