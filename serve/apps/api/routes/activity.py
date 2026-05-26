"""Activity log endpoints (ADR-0014, BACKEND_ROADMAP §2.6).

| Method | Path                                              | Purpose                            |
|--------|---------------------------------------------------|------------------------------------|
| GET    | /v1/activity                                      | cross-library feed (L5 §16.6)      |
| GET    | /v1/libraries/{library_id}/activity               | per-library feed                   |

Per ADR-0014 §1, the cross-library `GET /v1/activity` is the canonical
"L5 read-only meta-view exception" to PRD §16.6. The Protocol layer
(`packages/orchestration/activity.py`) stays strictly per-library; the
SQL `library_id = ANY(?)` aggregation lives in
`apps/api/_activity_reader.py`.
"""

from __future__ import annotations

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, Path, Query

from apps._shared.factories import AppContainer
from apps.api._activity_reader import ActivityCrossReader
from apps.api._orchestration_deps import (
    get_activity_logger,
    get_activity_reader,
)
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from apps.api.schemas.activity import ActivityEventResponse, ActivityListResponse
from packages.core.errors import LibraryNotFoundError
from packages.orchestration.activity import ActivityEvent, ActivityType
from packages.orchestration.adapters.postgres_activity import PostgresActivityLogger

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["activity"])

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200
_MAX_LIBRARY_IDS = 32


def _to_response(event: ActivityEvent) -> ActivityEventResponse:
    return ActivityEventResponse(
        id=event.id,
        library_id=event.library_id,
        type=event.type.value,
        title=event.title,
        summary=event.summary,
        payload=dict(event.payload),
        actor=event.actor,
        created_at=event.created_at,
    )


def _parse_types(types: list[str] | None) -> tuple[ActivityType, ...] | None:
    if not types:
        return None
    parsed: list[ActivityType] = []
    for raw in types:
        try:
            parsed.append(ActivityType(raw))
        except ValueError:
            # Silently skip unknown types — keeps the endpoint forward-compatible
            # when frontend sends an enum value the backend has not deployed yet.
            continue
    return tuple(parsed) if parsed else None


async def _resolve_scope(container: AppContainer, library_ids: list[str] | None) -> list[str]:
    if library_ids:
        return list(library_ids)
    libs = await container.library_repo.list_all()
    return [lib.library_id for lib in libs]


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


@router.get(
    "/v1/activity",
    response_model=ActivityListResponse,
    summary="Cross-library activity feed (L5 read-only meta-view)",
)
async def list_activity(
    library_ids: list[str] | None = Query(
        default=None,
        alias="library_ids",
        max_length=_MAX_LIBRARY_IDS,
        description=(
            "Filter to a subset of libraries. Omit to scope to every library "
            "the principal can read (v1 single-tenant: all libraries)."
        ),
    ),
    types: list[str] | None = Query(
        default=None,
        description="Filter to specific activity types (see `ActivityType`).",
    ),
    since: datetime | None = Query(default=None, description="created_at >= since"),
    until: datetime | None = Query(default=None, description="created_at <= until"),
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    container: AppContainer = Depends(get_container),
    reader: ActivityCrossReader = Depends(get_activity_reader),
    _principal: Principal = Depends(get_current_principal),
) -> ActivityListResponse:
    scope = await _resolve_scope(container, library_ids)
    parsed_types = _parse_types(types)
    events = await reader.list_for_libraries(
        library_ids=scope,
        since=since,
        until=until,
        types=parsed_types,
        limit=limit,
    )
    await logger.ainfo(
        "activity_listed",
        library_count=len(scope),
        returned=len(events),
    )
    return ActivityListResponse(items=tuple(_to_response(e) for e in events))


@router.get(
    "/v1/libraries/{library_id}/activity",
    response_model=ActivityListResponse,
    summary="Per-library activity feed",
)
async def list_library_activity(
    library_id: str = Path(..., description="Library slug"),
    types: list[str] | None = Query(default=None),
    since: datetime | None = Query(default=None),
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    container: AppContainer = Depends(get_container),
    activity_logger: PostgresActivityLogger = Depends(get_activity_logger),
    _principal: Principal = Depends(get_current_principal),
) -> ActivityListResponse:
    await _ensure_library(container, library_id)
    parsed_types = _parse_types(types)
    events = await activity_logger.list_for_library(
        library_id,
        since=since,
        types=parsed_types,
        limit=limit,
    )
    return ActivityListResponse(items=tuple(_to_response(e) for e in events))
