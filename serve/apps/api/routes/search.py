"""⌘K cross-resource search endpoint (ADR-0023).

`GET /v1/search` is the only HTTP surface for the command palette. It fans
out to four searchers (entity / document / library / action) in parallel
and returns a merged ranked list. Every path has its own 300 ms p95
budget and degrades to an empty set on timeout — never breaks the
request.

Why a route module instead of a service: routing concerns (auth, query
validation, timing-ms reporting) are HTTP-specific and don't belong in
`packages/orchestration/`. The actual fan-out lives in
`CrossResourceSearchService`.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Query

from apps._shared.factories import AppContainer
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from apps.api.schemas.search import SearchHitResponse, SearchResponse
from packages.observability import with_span
from packages.orchestration._internal.search_actions import search_actions
from packages.orchestration.adapters.search_service import (
    DEFAULT_TIMEOUT_S,
    RepoLibraryMetadataSearcher,
    time_path,
)
from packages.orchestration.search import SearchHit

router = APIRouter(prefix="/v1/search", tags=["search"])

_log = structlog.get_logger(__name__)

_MIN_QUERY_LEN = 2
_MAX_QUERY_LEN = 200
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 50

_TYPE_WEIGHT_ACTION = 1.10
_TYPE_WEIGHT_LIBRARY = 1.00
_TYPE_WEIGHT_ENTITY = 0.95
_TYPE_WEIGHT_DOCUMENT = 0.90

type SearchTypeArg = Literal["entity", "document", "library", "action"]


def _split_types(raw: str | None) -> tuple[SearchTypeArg, ...]:
    if not raw:
        return ("entity", "document", "library", "action")
    valid: tuple[SearchTypeArg, ...] = ("entity", "document", "library", "action")
    out: list[SearchTypeArg] = []
    for piece in raw.split(","):
        token = piece.strip().lower()
        for v in valid:
            if token == v:
                out.append(v)
                break
    return tuple(out) if out else valid


def _resolve_library_id(raw: str | None) -> str | None:
    """`library_id=current` is a UI affordance; the backend treats it as
    "no specific library", same as omitting the parameter."""
    if not raw:
        return None
    if raw == "current":
        return None
    return raw


def _type_weight(kind: str) -> float:
    if kind == "action":
        return _TYPE_WEIGHT_ACTION
    if kind == "library":
        return _TYPE_WEIGHT_LIBRARY
    if kind == "entity":
        return _TYPE_WEIGHT_ENTITY
    return _TYPE_WEIGHT_DOCUMENT


def _hit_to_response(hit: SearchHit) -> SearchHitResponse:
    deeplink = ""
    payload = dict(hit.payload)
    raw_link = payload.pop("deeplink", None)
    if isinstance(raw_link, str):
        deeplink = raw_link
    return SearchHitResponse(
        type=hit.type,
        id=hit.id,
        title=hit.title,
        subtitle=hit.subtitle,
        library_id=hit.library_id,
        score=hit.score,
        deeplink=deeplink,
        payload=payload,
    )


@router.get("", response_model=SearchResponse)
async def search(
    q: Annotated[str, Query(min_length=_MIN_QUERY_LEN, max_length=_MAX_QUERY_LEN)],
    library_id: Annotated[str | None, Query()] = None,
    types: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = _DEFAULT_LIMIT,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> SearchResponse:
    """4-way parallel cross-resource search."""
    requested_types = _split_types(types)
    types_set = set(requested_types)
    resolved_lib = _resolve_library_id(library_id)

    timing_ms: dict[str, int] = {}
    degraded: list[str] = []

    async with with_span(
        "api.search",
        library_id=resolved_lib or "global",
    ):
        # asyncio.TaskGroup gives structured concurrency for the 4 paths;
        # each path's coroutine itself enforces the 300 ms timeout via
        # `time_path`, so a slow path NEVER cancels the siblings.
        running: dict[str, asyncio.Task[tuple[str, tuple[SearchHit, ...], int, str | None]]] = {}
        async with asyncio.TaskGroup() as tg:
            if "entity" in types_set and resolved_lib is not None:
                lib_for_entity: str = resolved_lib
                running["entity"] = tg.create_task(
                    time_path(
                        "entity",
                        lambda: _entity_path(container, lib_for_entity, q, limit),
                        timeout_s=DEFAULT_TIMEOUT_S,
                    )
                )
            if "document" in types_set and resolved_lib is not None:
                lib_for_doc: str = resolved_lib
                running["document"] = tg.create_task(
                    time_path(
                        "document",
                        lambda: _document_path(container, lib_for_doc, q, limit),
                        timeout_s=DEFAULT_TIMEOUT_S,
                    )
                )
            if "library" in types_set:
                running["library"] = tg.create_task(
                    time_path(
                        "library",
                        lambda: _library_path(container, q, limit),
                        timeout_s=DEFAULT_TIMEOUT_S,
                    )
                )
            if "action" in types_set:
                running["action"] = tg.create_task(
                    time_path(
                        "action",
                        lambda: _action_path(q, resolved_lib, limit),
                        timeout_s=DEFAULT_TIMEOUT_S,
                    )
                )

        merged: list[SearchHit] = []
        for label, task in running.items():
            _, hits, duration_ms, error = task.result()
            timing_ms[label] = duration_ms
            if error is not None:
                degraded.append(label)
            merged.extend(hits)

        ranked = _rank(merged, limit)
        return SearchResponse(
            query=q,
            library_id=resolved_lib,
            hits=[_hit_to_response(h) for h in ranked],
            timing_ms=timing_ms,
            degraded=degraded,
        )


def _rank(hits: list[SearchHit], limit: int) -> list[SearchHit]:
    weighted = [
        hit.model_copy(update={"score": hit.score * _type_weight(hit.type)}) for hit in hits
    ]
    weighted.sort(key=lambda h: h.score, reverse=True)
    return weighted[:limit]


async def _entity_path(
    container: AppContainer, library_id: str, q: str, limit: int
) -> tuple[SearchHit, ...]:
    """Entity name+alias fuzzy search via the graph index, when supported."""
    fn = getattr(container.graph_index, "search_entities", None)
    if fn is None:
        return ()
    try:
        result = await fn(library_id, q, limit=limit)
    except Exception as exc:
        await _log.awarning(
            "search_entity_failed",
            library_id=library_id,
            error_type=type(exc).__name__,
        )
        return ()
    return tuple(result)


async def _document_path(
    container: AppContainer, library_id: str, q: str, limit: int
) -> tuple[SearchHit, ...]:
    """BM25 title search via the BM25 index, when supported."""
    fn = getattr(container.bm25_index, "search_documents", None)
    if fn is None:
        return ()
    try:
        result = await fn(library_id, q, limit=limit)
    except Exception as exc:
        await _log.awarning(
            "search_document_failed",
            library_id=library_id,
            error_type=type(exc).__name__,
        )
        return ()
    return tuple(result)


async def _library_path(container: AppContainer, q: str, limit: int) -> tuple[SearchHit, ...]:
    """Library metadata ILIKE-equivalent search (cross-library by design)."""
    searcher = RepoLibraryMetadataSearcher(container.library_repo)
    try:
        return await searcher.search_libraries(q, limit=limit)
    except Exception as exc:
        await _log.awarning(
            "search_library_failed",
            error_type=type(exc).__name__,
        )
        return ()


async def _action_path(q: str, library_id: str | None, limit: int) -> tuple[SearchHit, ...]:
    hits, _duration = search_actions(q, library_id=library_id, limit=limit)
    return hits
