"""Small SSE parser for decoding JSON events from FastAPI streams."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any


class SSEEventParser:
    """Incremental parser for SSE `data:` lines."""

    def __init__(self) -> None:
        self._data_lines: list[str] = []

    def feed_line(self, line: str) -> list[dict[str, Any]]:
        cleaned = line.rstrip("\n")

        if cleaned == "":
            event = self._flush()
            return [event] if event is not None else []

        if cleaned.startswith(":"):
            return []

        field, _, value = cleaned.partition(":")
        if value.startswith(" "):
            value = value[1:]

        if field == "data":
            self._data_lines.append(value)

        return []

    def finish(self) -> list[dict[str, Any]]:
        event = self._flush()
        return [event] if event is not None else []

    def _flush(self) -> dict[str, Any] | None:
        if not self._data_lines:
            return None

        payload = "\n".join(self._data_lines).strip()
        self._data_lines.clear()

        if not payload:
            return None

        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None

        return parsed if isinstance(parsed, dict) else None


def parse_sse_events(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """Parse an iterable of SSE lines into decoded JSON payloads."""

    parser = SSEEventParser()
    for line in lines:
        for event in parser.feed_line(line):
            yield event
    for event in parser.finish():
        yield event

