"""Bridge a Redis-backed `TaskEventBus` stream to an SSE response.

ADR-0010 §4 specifies the wire format:

```
id: <seq>
event: <type>
data: <JSON of TaskEvent>

```

This module is the only place that handles the `Last-Event-ID` reconnect
header (ADR-0010 §5) — every route that wants task-event streaming should
call `stream_task_events(...)` rather than re-implementing the loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator

import structlog
from fastapi import Request

from apps.api.sse import encode_event
from packages.orchestration.errors import TaskHistoryExpiredError
from packages.orchestration.queue import TaskEvent, TaskEventBus, TaskId

logger = structlog.get_logger(__name__)

_HEARTBEAT_S = 15.0


def parse_last_event_id(request: Request) -> int | None:
    """Read the `Last-Event-ID` HTTP header into an integer seq.

    Returns None if absent or unparsable so the caller treats it as a
    fresh subscription.
    """
    raw = request.headers.get("last-event-id")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _encode_task_event(event: TaskEvent) -> bytes:
    """Serialize a `TaskEvent` to the SSE on-wire frame.

    `id:` is the monotonic seq (ADR-0010); `event:` is the type
    discriminator; `data:` is the full JSON envelope.
    """
    payload = json.loads(event.model_dump_json())
    body = encode_event(str(event.type), payload)
    # Splice the `id:` header into the frame. encode_event yields
    # "event: T\ndata: ...\n\n" so we prepend `id: N\n` for SSE conformance.
    return f"id: {event.seq}\n".encode() + body


async def stream_task_events(
    request: Request,
    bus: TaskEventBus,
    *,
    library_id: str,
    task_id: TaskId,
    since_seq: int | None = None,
) -> AsyncIterator[bytes]:
    """Yield SSE-encoded byte frames from the task event bus.

    Behaviour:
    - On enter: emit history with seq > `since_seq`, then attach to live
      stream.
    - Every `_HEARTBEAT_S` seconds without traffic, emit a `:keep-alive`
      comment frame so reverse proxies don't time the connection out.
    - Exits cleanly when the client disconnects (`request.is_disconnected`).
    - On `TaskHistoryExpiredError` emits a single `error` event then
      returns; client falls back to the snapshot endpoint.
    """
    last_seq = since_seq
    queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=512)

    async def producer() -> None:
        try:
            stream_iter = bus.stream(library_id, task_id, since_seq=last_seq)
            assert isinstance(stream_iter, AsyncIterator) or hasattr(stream_iter, "__aiter__")
            async for event in stream_iter:
                await queue.put(_encode_task_event(event))
        except TaskHistoryExpiredError:
            await queue.put(
                encode_event(
                    "error",
                    {
                        "code": "TASK_HISTORY_EXPIRED",
                        "message": "Stream history has expired; fall back to snapshot.",
                    },
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await logger.awarning(
                "sse_bridge_producer_error",
                library_id=library_id,
                task_id=task_id,
                error=str(exc),
            )
            await queue.put(
                encode_event(
                    "error",
                    {"code": "INTERNAL_ERROR", "message": "Stream error"},
                )
            )
        finally:
            await queue.put(None)  # sentinel — close the consumer loop

    producer_task = asyncio.create_task(producer())
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_S)
            except TimeoutError:
                yield b": keep-alive\n\n"
                continue
            if frame is None:
                break
            yield frame
    finally:
        producer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await producer_task
