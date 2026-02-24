from __future__ import annotations

from streamlit_ui.sse_parser import parse_sse_events


def test_parse_single_event() -> None:
    lines = [
        'event: message',
        'data: {"event_type":"node_start","timestamp":0.1,"data":{}}',
        "",
    ]

    events = list(parse_sse_events(lines))

    assert len(events) == 1
    assert events[0]["event_type"] == "node_start"


def test_parse_multiline_data_event() -> None:
    lines = [
        'data: {"event_type":"result",',
        'data: "timestamp":1.2,',
        'data: "data":{"category":"debt"}}',
        "",
    ]

    events = list(parse_sse_events(lines))

    assert len(events) == 1
    assert events[0]["event_type"] == "result"
    assert events[0]["data"]["category"] == "debt"


def test_skips_malformed_json() -> None:
    lines = [
        "data: not-json",
        "",
        'data: {"event_type":"saved","timestamp":2.0,"data":{"record_id":"abc123"}}',
        "",
    ]

    events = list(parse_sse_events(lines))

    assert len(events) == 1
    assert events[0]["event_type"] == "saved"

