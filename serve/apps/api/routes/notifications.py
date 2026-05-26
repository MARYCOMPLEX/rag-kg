"""Notification center endpoints (ADR-0011, BACKEND_ROADMAP §2.3).

Routes:
- GET  /v1/notifications                            cross-library list (L5 §16.6)
- GET  /v1/notifications/stream                     SSE; LISTEN/NOTIFY relay
- POST /v1/notifications/{id}/read                  mark one read (idempotent)
- GET  /v1/libraries/{library_id}/notifications     per-library list

Cross-library reads go through `apps/api/_notification_reader.py`, which
is the single sanctioned place for `library_id = ANY(...)` (PRD §16.6
L5 read-only meta-view exception).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import StreamingResponse

from apps._shared.factories import AppContainer
from apps.api._notification_reader import NotificationCrossReader
from apps.api._orchestration_deps import (
    get_notification_reader,
    get_notification_store,
)
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from apps.api.schemas.notifications import (
    NotificationListResponse,
    NotificationMarkReadResponse,
    NotificationResponse,
)
from apps.api.sse import SSE_HEADERS, SSE_MEDIA_TYPE, encode_event
from packages.core.errors import LibraryNotFoundError
from packages.observability import with_span
from packages.orchestration.adapters.postgres_notifications import (
    PostgresNotificationStore,
)
from packages.orchestration.notifications import Notification

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["notifications"])

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200
_SSE_HEARTBEAT_S = 15.0


def _to_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        library_id=notification.library_id,
        type=notification.type.value,
        severity=notification.severity,
        title=notification.title,
        body=notification.body,
        payload=dict(notification.payload),
        read=notification.read,
        read_at=notification.read_at,
        created_at=notification.created_at,
        expires_at=notification.expires_at,
        dedup_key=notification.dedup_key,
    )


async def _resolve_library_ids(
    container: AppContainer,
    library_ids: list[str] | None,
) -> list[str]:
    """Resolve the principal's library scope.

    v1 single-tenant: no `library_ids` filter ⇒ all known libraries.
    Multi-tenancy in M8+ will replace this with an ACL lookup.
    """
    if library_ids:
        return list(library_ids)
    libs = await container.library_repo.list_all()
    return [lib.library_id for lib in libs]


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


@router.get(
    "/v1/notifications",
    response_model=NotificationListResponse,
    summary="Cross-library notification feed (L5 read-only meta-view)",
)
async def list_notifications(
    library_ids: list[str] | None = Query(
        default=None,
        alias="library_ids",
        description=(
            "Filter to a subset of libraries. Omit to scope to every library "
            "the principal can read. Globals (library_id=NULL) are always "
            "included per ADR-0011 §6."
        ),
    ),
    unread: bool = Query(default=False, description="Only return unread rows"),
    since: datetime | None = Query(default=None, description="Created at >= since"),
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    container: AppContainer = Depends(get_container),
    reader: NotificationCrossReader = Depends(get_notification_reader),
    _principal: Principal = Depends(get_current_principal),
) -> NotificationListResponse:
    scope = await _resolve_library_ids(container, library_ids)
    items = await reader.list_for_libraries(
        library_ids=scope,
        unread_only=unread,
        since=since,
        limit=limit,
    )
    unread_count = await reader.count_unread(library_ids=scope)
    await logger.ainfo(
        "notifications_listed",
        library_count=len(scope),
        returned=len(items),
        unread_only=unread,
    )
    return NotificationListResponse(
        items=tuple(_to_response(n) for n in items),
        unread_count=unread_count,
    )


@router.get(
    "/v1/libraries/{library_id}/notifications",
    response_model=NotificationListResponse,
    summary="Per-library notification feed",
)
async def list_library_notifications(
    library_id: str = Path(..., description="Library slug"),
    unread: bool = Query(default=False),
    since: datetime | None = Query(default=None),
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    container: AppContainer = Depends(get_container),
    store: PostgresNotificationStore = Depends(get_notification_store),
    _principal: Principal = Depends(get_current_principal),
) -> NotificationListResponse:
    await _ensure_library(container, library_id)
    items = await store.list_for_library(
        library_id,
        unread_only=unread,
        since=since,
        limit=limit,
    )
    unread_items = (
        items
        if unread
        else await store.list_for_library(library_id, unread_only=True, limit=_MAX_LIMIT)
    )
    return NotificationListResponse(
        items=tuple(_to_response(n) for n in items),
        unread_count=len(unread_items),
    )


@router.post(
    "/v1/notifications/{notification_id}/read",
    response_model=NotificationMarkReadResponse,
    summary="Mark a notification as read (idempotent)",
)
async def mark_notification_read(
    notification_id: str = Path(..., min_length=1, description="ULID"),
    library_id: str | None = Query(
        default=None,
        description=(
            "Optional library scope. When set, only flips rows that match "
            "(library_id, id) — keeps non-owners from read-marking another "
            "library's row in M8+ multi-tenant mode."
        ),
    ),
    store: PostgresNotificationStore = Depends(get_notification_store),
    _principal: Principal = Depends(get_current_principal),
) -> NotificationMarkReadResponse:
    async with with_span(
        "api.notifications.mark_read",
        notification_id=notification_id,
        library_id=library_id or "",
    ):
        await store.mark_read(library_id, notification_id)
    await logger.ainfo(
        "notification_marked_read",
        notification_id=notification_id,
        library_id=library_id,
    )
    return NotificationMarkReadResponse(id=notification_id, marked=True)


async def _sse_iterator(
    request: Request,
    store: PostgresNotificationStore,
) -> AsyncIterator[bytes]:
    """Forward Postgres LISTEN events as SSE frames.

    Disconnect detection runs between yields. Heartbeats are emitted every
    `_SSE_HEARTBEAT_S` to keep reverse proxies from idle-killing the
    socket.
    """
    queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=256)

    async def producer() -> None:
        try:
            async for notification_id in store.listen():
                notification = await store.get(notification_id)
                if notification is None:
                    continue
                payload = json.loads(
                    NotificationResponse.model_validate(
                        _to_response(notification).model_dump()
                    ).model_dump_json()
                )
                frame = encode_event("notification_created", payload)
                await queue.put(frame)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await logger.awarning("notifications_sse_producer_error", error=str(exc))
            await queue.put(
                encode_event(
                    "error",
                    {"code": "INTERNAL_ERROR", "message": "Stream error"},
                )
            )
        finally:
            await queue.put(None)

    producer_task = asyncio.create_task(producer())
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=_SSE_HEARTBEAT_S)
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


@router.get(
    "/v1/notifications/stream",
    summary="SSE stream of newly created notifications",
)
async def stream_notifications(
    request: Request,
    store: PostgresNotificationStore = Depends(get_notification_store),
    _principal: Principal = Depends(get_current_principal),
) -> StreamingResponse:
    return StreamingResponse(
        _sse_iterator(request, store),
        media_type=SSE_MEDIA_TYPE,
        headers=SSE_HEADERS,
    )
