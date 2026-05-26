"""Library CRUD endpoints + QA + KG views.

Per-library ingest moved to `apps/api/routes/ingest.py` (ADR-0019);
review moved to `apps/api/routes/review.py`. This module owns library
lifecycle, stats/schema views, and the existing QA / hypothesis surfaces.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer
from apps._shared.persistence.library_fs import make_library
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from apps.api.sse import SSE_HEADERS, SSE_MEDIA_TYPE, encode_event
from packages.core.errors import LibraryNotFoundError
from packages.core.library_admin import LibraryAdmins, init_library, purge_library
from packages.orchestration.protocols import AnsweredQuery
from packages.structuring.schema import load_schema

router = APIRouter(prefix="/v1/libraries", tags=["libraries"])

_MAX_NEIGHBORHOOD_DEPTH = 3
_SSE_TOKEN_CHUNK = 48
_SSE_TOKEN_DELAY_S = 0.02
_PALETTE: tuple[str, ...] = (
    "#2563eb",
    "#16a34a",
    "#d97706",
    "#dc2626",
    "#7c3aed",
    "#0891b2",
    "#ea580c",
    "#0d9488",
    "#be123c",
    "#65a30d",
    "#9333ea",
    "#0284c7",
)


def _color_for(label: str) -> str:
    h = hashlib.sha1(label.encode("utf-8")).digest()[0]
    return _PALETTE[h % len(_PALETTE)]


class LibraryCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    library_id: str = Field(min_length=3, max_length=31)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    language: Literal["en", "zh", "mixed"] | None = None


class LibraryResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    library_id: str
    name: str
    description: str | None
    created_at: datetime
    language: Literal["en", "zh", "mixed"] | None = None


class QAResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    library_id: str
    question: str
    answer: str
    citations: list[dict[str, object]]
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int


@router.post("", response_model=LibraryResponse, status_code=status.HTTP_201_CREATED)
async def create_library(
    body: LibraryCreateRequest,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> LibraryResponse:
    try:
        lib = make_library(
            library_id=body.library_id,
            name=body.name,
            description=body.description,
            language=body.language,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await container.library_repo.create(lib)  # exception_handler maps 409

    await init_library(body.library_id, adapters=[container.vector_index])
    return LibraryResponse(
        library_id=lib.library_id,
        name=lib.name,
        description=lib.description,
        created_at=lib.created_at,
        language=lib.language,
    )


@router.get("", response_model=list[LibraryResponse])
async def list_libraries(
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> list[LibraryResponse]:
    libs = await container.library_repo.list_all()
    return [
        LibraryResponse(
            library_id=lib.library_id,
            name=lib.name,
            description=lib.description,
            created_at=lib.created_at,
            language=lib.language,
        )
        for lib in libs
    ]


@router.get("/{library_id}", response_model=LibraryResponse)
async def get_library(
    library_id: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> LibraryResponse:
    lib = await container.library_repo.get(library_id)
    if lib is None:
        raise LibraryNotFoundError(library_id)
    return LibraryResponse(
        library_id=lib.library_id,
        name=lib.name,
        description=lib.description,
        created_at=lib.created_at,
        language=lib.language,
    )


@router.delete("/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_library(
    library_id: str,
    purge: bool = Query(default=False),
    confirmation_slug: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    principal: Principal = Depends(get_current_principal),
) -> None:
    """Delete a library — soft (metadata only) or hard purge via saga.

    `purge=1` triggers `library_admin.purge_library` which runs the
    cross-storage saga (ADR-0022). The frontend MUST send
    `confirmation_slug=<library_id>` (PRD §14.2 DeleteConfirmModal); if
    the slug doesn't match, return `PURGE_SLUG_MISMATCH` 400 — the
    backend never trusts the client-side gating.
    """
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)

    if purge:
        if confirmation_slug != library_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"PURGE_SLUG_MISMATCH: confirmation_slug must equal library_id '{library_id}'"
                ),
            )
        admins = LibraryAdmins(
            repo=container.library_repo,
            qdrant=container.vector_index,
            bm25=container.bm25_index,
            neo4j=container.graph_index,
            minio=getattr(container, "minio_index", None),
        )
        await purge_library(
            library_id,
            registries=admins,
            requested_by=principal.id,
        )
        return

    # Soft delete path: metadata-only purge for the dev/M1 flow.
    await purge_library(
        library_id,
        adapters=[container.vector_index],
    )
    await container.library_repo.delete(library_id)


class QARequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    question: str = Field(min_length=1, max_length=2000)


@router.post("/{library_id}/qa", response_model=QAResponse)
async def qa(
    library_id: str,
    body: QARequest,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> QAResponse:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)

    answered: AnsweredQuery = await container.qa_task.answer(library_id, body.question)

    return QAResponse(
        library_id=answered.library_id,
        question=answered.question,
        answer=answered.answer,
        citations=[
            {
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "page": c.page,
                "snippet": c.snippet,
            }
            for c in answered.citations
        ],
        model=answered.model,
        input_tokens=answered.tokens.input_tokens,
        output_tokens=answered.tokens.output_tokens,
        duration_ms=answered.duration_ms,
    )


class TripleResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    head: str
    relation: str
    tail: str
    confidence: float
    evidence_count: int


class NeighborhoodResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    library_id: str
    entity_id: str
    depth: int
    triples: list[TripleResponse]


@router.get(
    "/{library_id}/entities/{entity_id}/neighborhood",
    response_model=NeighborhoodResponse,
)
async def entity_neighborhood(
    library_id: str,
    entity_id: str,
    depth: int = 1,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> NeighborhoodResponse:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)
    if depth < 1 or depth > _MAX_NEIGHBORHOOD_DEPTH:
        raise HTTPException(
            status_code=400,
            detail=f"depth must be between 1 and {_MAX_NEIGHBORHOOD_DEPTH}",
        )

    triples = await container.graph_index.get_neighbors(library_id, entity_id, depth=depth)
    return NeighborhoodResponse(
        library_id=library_id,
        entity_id=entity_id,
        depth=depth,
        triples=[
            TripleResponse(
                head=t.head,
                relation=t.relation,
                tail=t.tail,
                confidence=t.confidence,
                evidence_count=len(t.evidence),
            )
            for t in triples
        ],
    )


# === M7: Stats / Schema / SSE QA / Review / Hypothesis =====================


class LibraryStatsResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    library_id: str
    documents: int
    chunks: int
    entities: int
    triples: int
    communities: int
    summary_freshness_iso: str | None


@router.get("/{library_id}/stats", response_model=LibraryStatsResponse)
async def library_stats(
    library_id: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> LibraryStatsResponse:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)

    async def _safe_count(coro_func: Callable[..., Awaitable[Any]], *args: Any, **kw: Any) -> int:
        try:
            value = await coro_func(*args, **kw)
        except Exception:
            return 0
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    documents = 0
    list_docs = getattr(container.library_repo, "list_documents", None)
    if list_docs is not None:
        try:
            docs = await list_docs(library_id)
            documents = len(list(docs))
        except Exception:
            documents = 0

    chunks = 0
    chunk_count = getattr(container.vector_index, "count", None)
    if chunk_count is not None:
        chunks = await _safe_count(chunk_count, library_id)

    entities = 0
    triples = 0
    list_triples = getattr(container.graph_index, "list_all_triples", None)
    if list_triples is not None:
        try:
            all_triples = await list_triples(library_id)
            seen: set[str] = set()
            triple_count = 0
            for t in all_triples:
                seen.add(t.head)
                seen.add(t.tail)
                triple_count += 1
            entities = len(seen)
            triples = triple_count
        except Exception:
            pass

    communities = 0
    community_count = getattr(container.community_index, "count", None)
    if community_count is not None:
        communities = await _safe_count(community_count, library_id)

    return LibraryStatsResponse(
        library_id=library_id,
        documents=documents,
        chunks=chunks,
        entities=entities,
        triples=triples,
        communities=communities,
        summary_freshness_iso=None,
    )


class TypeColorResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    type: str
    color: str


class LibrarySchemaResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    library_id: str
    entity_types: list[TypeColorResponse]
    relation_types: list[str]


@router.get("/{library_id}/schema", response_model=LibrarySchemaResponse)
async def library_schema(
    library_id: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> LibrarySchemaResponse:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)

    schema = container.schema
    if schema is None:
        try:
            schema = load_schema(library_id, Path("docs/ontology"))
        except FileNotFoundError:
            schema = None

    entity_types: list[TypeColorResponse] = []
    relation_types: list[str] = []
    if schema is not None:
        for et in getattr(schema, "entity_types", ()):
            label = getattr(et, "name", str(et))
            entity_types.append(TypeColorResponse(type=label, color=_color_for(label)))
        for rt in getattr(schema, "relation_types", ()):
            label = getattr(rt, "name", str(rt))
            relation_types.append(label)
    return LibrarySchemaResponse(
        library_id=library_id,
        entity_types=entity_types,
        relation_types=relation_types,
    )


@router.get("/{library_id}/qa/stream")
async def qa_stream(
    library_id: str,
    request: Request,
    question: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> StreamingResponse:
    """SSE stream: meta → tokens → citations → done. (Token chunking is
    client-side fan-out for now; will become real LLM streaming when the
    LLM adapter exposes streaming completions.)"""
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)
    if not question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    async def _gen() -> AsyncIterator[bytes]:
        try:
            answered: AnsweredQuery = await container.qa_task.answer(library_id, question)
        except Exception as exc:
            yield encode_event(
                "error",
                {"code": "INTERNAL_ERROR", "message": str(exc) or exc.__class__.__name__},
            )
            return

        yield encode_event(
            "meta",
            {"library_id": library_id, "model": answered.model},
        )

        text = answered.answer
        for i in range(0, len(text), _SSE_TOKEN_CHUNK):
            if await request.is_disconnected():
                return
            chunk = text[i : i + _SSE_TOKEN_CHUNK]
            yield encode_event("token", {"text": chunk})
            await asyncio.sleep(_SSE_TOKEN_DELAY_S)

        yield encode_event(
            "citations",
            [
                {
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "page": c.page,
                    "snippet": c.snippet,
                }
                for c in answered.citations
            ],
        )
        yield encode_event(
            "done",
            {
                "duration_ms": answered.duration_ms,
                "model": answered.model,
                "input_tokens": answered.tokens.input_tokens,
                "output_tokens": answered.tokens.output_tokens,
            },
        )

    return StreamingResponse(_gen(), media_type=SSE_MEDIA_TYPE, headers=SSE_HEADERS)


class HypothesisRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    head_entity_id: str = Field(min_length=1, max_length=200)
    tail_entity_id: str = Field(min_length=1, max_length=200)


class HypothesisItemResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    statement: str
    rationale: str
    confidence: float
    counter_evidence: str = ""


class HypothesisResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    library_id: str
    head_entity_id: str
    tail_entity_id: str
    hypotheses: list[HypothesisItemResponse]


@router.post("/{library_id}/hypothesis", response_model=HypothesisResponse)
async def generate_hypothesis(
    library_id: str,
    body: HypothesisRequest,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> HypothesisResponse:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)

    result = await container.hypothesis_task.run(
        library_id,
        body.head_entity_id,
        body.tail_entity_id,
    )
    return HypothesisResponse(
        library_id=result.library_id,
        head_entity_id=result.head_entity_id,
        tail_entity_id=result.tail_entity_id,
        hypotheses=[
            HypothesisItemResponse(
                statement=h.statement,
                rationale=h.rationale,
                confidence=h.confidence,
                counter_evidence=h.counter_evidence,
            )
            for h in result.hypotheses
        ],
    )
