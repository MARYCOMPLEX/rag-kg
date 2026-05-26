"""Redis-backed `TaskEventBus` (ADR-0010 §4).

Two Redis structures, **deliberately**:

- **Pub/sub channel** ``task:{task_id}``: live broadcast for connected SSE
  subscribers.
- **Stream** ``taskhist:{task_id}``: append-only history used by
  ``replay(since_seq)`` on EventSource reconnect.

The two writes are atomic via a Lua script so a subscriber attaching mid-publish
never sees a divergent (live, replay) view. ``seq`` is allocated by ``INCR
taskseq:{task_id}`` so concurrent producers cannot collide.

The event protocol implements ``packages.orchestration.queue.TaskEventBus``.

This module relies on the ``redis.asyncio`` client. Tests inject a fake via
duck typing — the only methods we touch are `eval`, `publish`, `xrange`,
`xadd`, `xread`, `incr`, `expire`, `pubsub`, and `aclose`.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog

from packages.observability import with_span
from packages.orchestration.errors import TaskHistoryExpiredError
from packages.orchestration.queue import TaskEvent, TaskEventType, TaskId

logger = structlog.get_logger(__name__)

# 24 h replay window (ADR-0010 §4: stream TTL after terminal events).
_HISTORY_TTL_S = 86_400
# Subscriber buffer cap (ADR-0010 §E-R2). Beyond this the subscriber is dropped.
_SUBSCRIBER_BUFFER = 500
# How often to poll Redis Stream when a pure XREAD-BLOCK isn't available.
_POLL_INTERVAL_S = 0.5

# Atomic dual-publish:
#   1. INCR seq counter to allocate the next monotonic seq
#   2. XADD to the history stream
#   3. PUBLISH to the live channel
# Returns the newly assigned seq number so the caller can mint TaskEvent.seq.
_PUBLISH_LUA = """
local seq_key = KEYS[1]
local stream_key = KEYS[2]
local channel = KEYS[3]
local payload_template = ARGV[1]
local stream_maxlen = tonumber(ARGV[2])

local seq = redis.call('INCR', seq_key)
local payload = string.gsub(payload_template, '__SEQ__', tostring(seq))
redis.call('XADD', stream_key, 'MAXLEN', '~', stream_maxlen, '*', 'event', payload)
redis.call('PUBLISH', channel, payload)
return seq
"""


class _RedisLike(Protocol):
    """Minimum surface area of redis.asyncio.Redis we depend on."""

    async def eval(self, script: str, numkeys: int, *args: Any) -> Any: ...

    async def incr(self, key: str) -> int: ...

    async def xrange(
        self, name: str, min: str = "-", max: str = "+", count: int | None = None
    ) -> list[Any]: ...

    async def xread(
        self, streams: dict[str, str], count: int | None = None, block: int | None = None
    ) -> list[Any]: ...

    async def expire(self, key: str, time: int) -> int: ...

    async def exists(self, *keys: str) -> int: ...

    def pubsub(self) -> Any: ...

    async def publish(self, channel: str, message: str) -> int: ...

    async def aclose(self) -> None: ...


def _stream_key(task_id: TaskId) -> str:
    return f"taskhist:{task_id}"


def _channel_key(task_id: TaskId) -> str:
    return f"task:{task_id}"


def _seq_key(task_id: TaskId) -> str:
    return f"taskseq:{task_id}"


def _deserialise(payload: str) -> TaskEvent:
    return TaskEvent.model_validate_json(payload)


class RedisTaskEventBus:
    """Production `TaskEventBus` against ``redis.asyncio.Redis``.

    Per ADR-0010 §6 the wire shape is versioned: producers emit
    ``schema_version=1`` events; new fields can be added but never removed.
    """

    def __init__(
        self,
        redis: _RedisLike,
        *,
        history_ttl_s: int = _HISTORY_TTL_S,
        stream_maxlen: int = 10_000,
    ) -> None:
        self._redis = redis
        self._history_ttl_s = history_ttl_s
        self._stream_maxlen = stream_maxlen

    async def emit(self, event: TaskEvent) -> None:
        """Atomically allocate `seq`, append to stream, broadcast on channel.

        The caller's `event.seq` value is **overwritten** by the Lua-allocated
        seq so that concurrent producers can't collide (ADR-0010 §E-R1).
        """
        async with with_span(
            "orchestration.event_bus.emit",
            library_id=event.library_id,
            task_id=event.task_id,
            event_type=str(event.type),
        ):
            placeholder = event.model_copy(update={"seq": 0}).model_dump(mode="json")
            placeholder["seq"] = "__SEQ__"
            template = json.dumps(placeholder, default=str)
            seq = await self._redis.eval(
                _PUBLISH_LUA,
                3,
                _seq_key(event.task_id),
                _stream_key(event.task_id),
                _channel_key(event.task_id),
                template,
                str(self._stream_maxlen),
            )
            seq_int = int(seq) if seq is not None else 0
            # Refresh the stream TTL on terminal events only (ADR-0010 §E-R3).
            if event.type in {
                TaskEventType.TASK_COMPLETED,
                TaskEventType.TASK_FAILED,
                TaskEventType.TASK_CANCELLED,
            }:
                await self._redis.expire(_stream_key(event.task_id), self._history_ttl_s)
                await self._redis.expire(_seq_key(event.task_id), self._history_ttl_s)
            await logger.adebug(
                "task_event_emitted",
                library_id=event.library_id,
                task_id=event.task_id,
                event_type=str(event.type),
                seq=seq_int,
            )

    async def replay(
        self,
        library_id: str,
        task_id: TaskId,
        since_seq: int,
    ) -> tuple[TaskEvent, ...]:
        """Read all archived events with `seq > since_seq` from the stream.

        Raises `TaskHistoryExpiredError` if the stream is missing entirely
        (TTL'd or never existed for this task_id).
        """
        async with with_span(
            "orchestration.event_bus.replay",
            library_id=library_id,
            task_id=task_id,
            since_seq=since_seq,
        ):
            exists = await self._redis.exists(_stream_key(task_id))
            if not exists:
                raise TaskHistoryExpiredError(library_id, task_id)
            entries = await self._redis.xrange(_stream_key(task_id), "-", "+")
            events: list[TaskEvent] = []
            for _stream_id, fields in entries:
                # redis returns either str-keyed or bytes-keyed dict depending on decode_responses.
                payload = fields.get("event") if isinstance(fields, dict) else None
                if payload is None and isinstance(fields, dict):
                    payload = fields.get(b"event")
                if payload is None:
                    continue
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                event = _deserialise(payload)
                if event.library_id != library_id:
                    # Defence in depth: a guessed task_id from a different library.
                    continue
                if event.seq > since_seq:
                    events.append(event)
        return tuple(events)

    async def stream(
        self,
        library_id: str,
        task_id: TaskId,
        *,
        since_seq: int | None = None,
    ) -> AsyncIterator[TaskEvent]:
        """Async iterator producing past + live events.

        Implements the reconnect protocol from ADR-0010 §5: on connect we
        first replay any history beyond `since_seq`, then attach to the
        live pub/sub channel.

        The caller is expected to consume events promptly; if the underlying
        subscriber buffer fills past `_SUBSCRIBER_BUFFER` the iterator emits
        nothing further and returns (slow-consumer protection, ADR-0010
        §E-R2).
        """
        from_seq = since_seq if since_seq is not None else -1
        # Step 1: replay
        try:
            history = await self.replay(library_id, task_id, from_seq)
        except TaskHistoryExpiredError:
            history = ()
        for event in history:
            yield event
            from_seq = max(from_seq, event.seq)

        # Step 2: live subscription (XREAD with BLOCK so we don't busy-wait).
        last_id = "$"  # listen for entries appended after this point
        # If the stream already has entries, last_id should be the latest stream id.
        try:
            tail = await self._redis.xrange(
                _stream_key(task_id), "-", "+", count=1
            )  # cheapest probe
            if tail:
                # Use last received seq to anchor; XREAD wants a stream id, not a seq.
                # For new entries we just use "$" — XREAD with BLOCK returns only future entries.
                pass
        except Exception:
            last_id = "$"

        buffered = 0
        while True:
            try:
                response = await self._redis.xread(
                    {_stream_key(task_id): last_id}, count=100, block=int(_POLL_INTERVAL_S * 1000)
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await logger.awarning(
                    "task_event_stream_error",
                    library_id=library_id,
                    task_id=task_id,
                    error=str(exc),
                )
                return
            if not response:
                # block timeout; loop again so disconnect detection upstream can run
                continue
            for _stream_name, entries in response:
                for stream_id, fields in entries:
                    last_id = (
                        stream_id.decode("utf-8") if isinstance(stream_id, bytes) else stream_id
                    )
                    payload = fields.get("event") if isinstance(fields, dict) else None
                    if payload is None and isinstance(fields, dict):
                        payload = fields.get(b"event")
                    if payload is None:
                        continue
                    if isinstance(payload, bytes):
                        payload = payload.decode("utf-8")
                    event = _deserialise(payload)
                    if event.library_id != library_id:
                        continue
                    if event.seq <= from_seq:
                        continue
                    from_seq = event.seq
                    buffered += 1
                    if buffered > _SUBSCRIBER_BUFFER:
                        await logger.awarning(
                            "task_event_subscriber_overflow",
                            library_id=library_id,
                            task_id=task_id,
                        )
                        return
                    yield event


def now_utc() -> datetime:
    """UTC now — kept here so producers don't sprinkle `datetime.now()`."""
    return datetime.now(UTC)
