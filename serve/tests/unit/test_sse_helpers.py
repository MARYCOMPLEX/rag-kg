"""Tests for the small SSE helper module."""

from __future__ import annotations

import json

from apps.api.sse import SSE_HEADERS, SSE_MEDIA_TYPE, encode_event


def test_encode_event_shape() -> None:
    raw = encode_event("token", {"text": "hi"})
    text = raw.decode("utf-8")
    assert text.startswith("event: token\n")
    assert "data: " in text
    payload_line = next(line for line in text.splitlines() if line.startswith("data: "))
    assert json.loads(payload_line[6:]) == {"text": "hi"}
    assert text.endswith("\n\n")


def test_media_and_headers() -> None:
    assert SSE_MEDIA_TYPE == "text/event-stream"
    assert SSE_HEADERS["Cache-Control"].startswith("no-cache")
    assert SSE_HEADERS["X-Accel-Buffering"] == "no"


def test_encode_event_handles_unicode() -> None:
    raw = encode_event("meta", {"name": "你好"})
    assert "你好".encode() in raw
