"""Server-Sent Events (SSE) helper.

Encodes events in the standard `event: <type>\\ndata: <json>\\n\\n` form and
yields bytes for `StreamingResponse`. Disconnect detection is the caller's
responsibility (await `request.is_disconnected()` between yields).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator


def encode_event(event: str, data: object) -> bytes:
    """Encode a single SSE frame."""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    lines = [f"event: {event}", f"data: {payload}", "", ""]
    return "\n".join(lines).encode("utf-8")


async def heartbeat_stream(seconds: float = 15.0) -> AsyncIterator[bytes]:
    """Emit comment-only frames to keep the connection warm."""
    while True:
        await asyncio.sleep(seconds)
        yield b": keepalive\n\n"


SSE_MEDIA_TYPE = "text/event-stream"
SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
