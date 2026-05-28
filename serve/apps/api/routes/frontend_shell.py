"""Frontend command search and shell metadata endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from packages.core.errors import LibraryNotFoundError
from packages.ingestion.state import IngestStateStore
from packages.orchestration.adapters.search_service import (
    CrossResourceSearchService,
    DocumentTitleSearcher,
    EntityNameSearcher,
    RepoLibraryMetadataSearcher,
)
from packages.orchestration.search import SearchHit, SearchQuery, SearchType

router = APIRouter(prefix="/api/libraries/{library_id}", tags=["libraries"])

type FrontendSearchScope = Literal["documents", "entities", "libraries", "actions"]
type FrontendSearchResultType = Literal["document", "entity", "library", "action"]
type FrontendScreen = Literal["dashboard", "chat", "graph", "docs", "review", "eval"]

_DEFAULT_SEARCH_LIMIT = 12
_MAX_SEARCH_LIMIT = 50
_MAX_QUERY_LEN = 200
_DEFAULT_SCOPES: tuple[FrontendSearchScope, ...] = (
    "documents",
    "entities",
    "libraries",
    "actions",
)
_SCOPE_TO_SEARCH_TYPE: dict[FrontendSearchScope, SearchType] = {
    "documents": "document",
    "entities": "entity",
    "libraries": "library",
    "actions": "action",
}
_ACTION_SCREEN_BY_ID: dict[str, FrontendScreen] = {
    "open_chat": "chat",
    "generate_review": "review",
    "open_kg": "graph",
    "open_eval": "eval",
    "open_documents": "docs",
}


class FrontendSearchTarget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    library_id: str | None = Field(default=None, alias="libraryId")
    document_id: str | None = Field(default=None, alias="documentId")
    entity_id: str | None = Field(default=None, alias="entityId")
    session_id: str | None = Field(default=None, alias="sessionId")
    review_run_id: str | None = Field(default=None, alias="reviewRunId")
    query: str | None = None


class FrontendSearchResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    type: FrontendSearchResultType
    label: str
    meta: str
    screen: FrontendScreen
    icon: str | None = None
    shortcut: str | None = None
    tone: str | None = None
    target: FrontendSearchTarget | None = None


class FrontendSearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str
    results: list[FrontendSearchResult]


class FrontendRecentSession(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    time: str
    screen: FrontendScreen
    active: bool | None = None
    target: FrontendSearchTarget | None = None


class FrontendLibraryStat(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    value: str


class FrontendShellNotifications(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    active_background_streams: int = Field(alias="activeBackgroundStreams", ge=0)
    label: str | None = None


class FrontendShellProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    initials: str
    display_name: str = Field(alias="displayName")
    plan_label: str | None = Field(default=None, alias="planLabel")


class FrontendShellMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    recent_sessions: list[FrontendRecentSession] = Field(alias="recentSessions")
    library_stats: list[FrontendLibraryStat] = Field(alias="libraryStats")
    notifications: FrontendShellNotifications | None = None
    profile: FrontendShellProfile | None = None


@router.get(
    "/search",
    response_model=FrontendSearchResponse,
    response_model_exclude_none=True,
)
async def search_frontend_library(
    library_id: str,
    q: str = Query(default="", max_length=_MAX_QUERY_LEN),
    scope: str | None = Query(default=None),
    limit: int = Query(default=_DEFAULT_SEARCH_LIMIT, ge=1, le=_MAX_SEARCH_LIMIT),
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> FrontendSearchResponse:
    await _ensure_library(container, library_id)
    query = q.strip()
    if len(query) < 2:
        return FrontendSearchResponse(query=q, results=[])

    scopes = _parse_scopes(scope)
    service = CrossResourceSearchService(
        entity_searcher=_entity_searcher(container),
        document_searcher=_document_searcher(container),
        library_searcher=RepoLibraryMetadataSearcher(container.library_repo),
    )
    hits = await service.search(
        SearchQuery(
            q=query,
            library_id=library_id,
            types=tuple(_SCOPE_TO_SEARCH_TYPE[item] for item in scopes),
            limit=limit,
        )
    )
    return FrontendSearchResponse(
        query=q,
        results=[_search_result_from_hit(hit, library_id, query) for hit in hits],
    )


@router.get(
    "/shell/metadata",
    response_model=FrontendShellMetadata,
    response_model_exclude_none=True,
)
async def get_frontend_shell_metadata(
    library_id: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> FrontendShellMetadata:
    await _ensure_library(container, library_id)
    return FrontendShellMetadata(
        recentSessions=await _recent_sessions(container, library_id),
        libraryStats=_library_stats(container, library_id),
    )


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


def _parse_scopes(raw: str | None) -> tuple[FrontendSearchScope, ...]:
    if raw is None or raw.strip() == "":
        return _DEFAULT_SCOPES

    valid = set(_DEFAULT_SCOPES)
    scopes: list[FrontendSearchScope] = []
    invalid: list[str] = []
    for piece in raw.split(","):
        token = piece.strip().lower()
        if not token:
            continue
        if token not in valid:
            invalid.append(token)
            continue
        scopes.append(token)  # type: ignore[arg-type]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported search scope: {', '.join(invalid)}",
        )
    return tuple(scopes) if scopes else _DEFAULT_SCOPES


def _entity_searcher(container: AppContainer) -> EntityNameSearcher | None:
    searcher = container.graph_index
    if isinstance(searcher, EntityNameSearcher):
        return searcher
    return None


def _document_searcher(container: AppContainer) -> DocumentTitleSearcher | None:
    searcher = container.bm25_index
    if isinstance(searcher, DocumentTitleSearcher):
        return searcher
    return None


def _search_result_from_hit(
    hit: SearchHit,
    library_id: str,
    query: str,
) -> FrontendSearchResult:
    result_type = _frontend_type(hit.type)
    screen = _screen_for_hit(hit)
    return FrontendSearchResult(
        id=hit.id,
        type=result_type,
        label=hit.title,
        meta=hit.subtitle or _default_meta(result_type),
        screen=screen,
        target=_target_for_hit(hit, library_id, query),
    )


def _frontend_type(kind: SearchType) -> FrontendSearchResultType:
    if kind == "document":
        return "document"
    if kind == "entity":
        return "entity"
    if kind == "library":
        return "library"
    return "action"


def _screen_for_hit(hit: SearchHit) -> FrontendScreen:
    if hit.type == "document":
        return "docs"
    if hit.type == "entity":
        return "graph"
    if hit.type == "action":
        return _ACTION_SCREEN_BY_ID.get(hit.id, "dashboard")
    return "dashboard"


def _target_for_hit(
    hit: SearchHit,
    library_id: str,
    query: str,
) -> FrontendSearchTarget:
    if hit.type == "document":
        return FrontendSearchTarget(libraryId=hit.library_id or library_id, documentId=hit.id)
    if hit.type == "entity":
        return FrontendSearchTarget(libraryId=hit.library_id or library_id, entityId=hit.id)
    if hit.type == "library":
        return FrontendSearchTarget(libraryId=hit.id)
    return FrontendSearchTarget(libraryId=library_id, query=query)


def _default_meta(kind: FrontendSearchResultType) -> str:
    if kind == "document":
        return "Document"
    if kind == "entity":
        return "Entity"
    if kind == "library":
        return "Library"
    return "Action"


async def _recent_sessions(
    container: AppContainer,
    library_id: str,
) -> list[FrontendRecentSession]:
    list_conversations = getattr(container.context_service, "list", None)
    if list_conversations is None:
        return []
    try:
        conversations = await list_conversations(library_id, limit=5)
    except Exception:
        return []

    sessions: list[FrontendRecentSession] = []
    for conversation in conversations:
        conversation_id = getattr(conversation, "conversation_id", "")
        if not conversation_id:
            continue
        updated_at = _coerce_datetime(getattr(conversation, "updated_at", None))
        sessions.append(
            FrontendRecentSession(
                id=conversation_id,
                title=getattr(conversation, "title", "") or "Untitled conversation",
                time=_time_label(updated_at),
                screen="chat",
                target=FrontendSearchTarget(libraryId=library_id, sessionId=conversation_id),
            )
        )
    return sessions


def _library_stats(container: AppContainer, library_id: str) -> list[FrontendLibraryStat]:
    records = _ingest_records(container, library_id)
    documents = sum(1 for record in records if record.doc_id is not None)
    chunks = sum(record.chunks_upserted for record in records)
    return [
        FrontendLibraryStat(label="Documents", value=str(documents)),
        FrontendLibraryStat(label="Chunks", value=str(chunks)),
    ]


def _ingest_records(container: AppContainer, library_id: str):
    store = IngestStateStore(Path(container.settings.ingest_state_dir) / "ingest.sqlite")
    try:
        return store.list_for_library(library_id)
    finally:
        store.close()


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    return datetime.now(UTC)


def _time_label(value: datetime) -> str:
    return value.date().isoformat()
