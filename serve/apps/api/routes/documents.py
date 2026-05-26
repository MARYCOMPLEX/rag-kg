"""Document Detail Drawer endpoints (M4 + ADR_REVIEW §4).

Five endpoints scoped under `/v1/libraries/{library_id}/docs`:

| Method | Path                              | Purpose                          |
|--------|-----------------------------------|----------------------------------|
| GET    | `/{doc_id}`                       | DocumentDetail (sections + counts) |
| GET    | `/{doc_id}/chunks`                | paged chunks (?section, ?limit)  |
| GET    | `/{doc_id}/pdf`                   | MinIO presigned URL              |
| POST   | `/{doc_id}/retry`                 | re-queue failed ingest           |
| DELETE | `/{doc_id}`                       | hard delete this doc             |

The MinIO presigned URL is a placeholder when no MinIO adapter is wired
into the container — see `_minio_presign` for the contract. This is
flagged with a TODO so a follow-up PR can add the real presign.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from apps._shared.factories import AppContainer
from apps._shared.factories.ingest_runner import _state_store
from apps.api._task_deps import get_task_queue
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from apps.api.schemas.documents import (
    DocumentChunkResponse,
    DocumentChunksListResponse,
    DocumentDetailResponse,
    DocumentPdfUrlResponse,
    DocumentRetryResponse,
)
from packages.core.errors import LibraryNotFoundError
from packages.ingestion.state import IngestRecord
from packages.observability import with_span
from packages.orchestration._internal.ulid import new_ulid
from packages.orchestration.queue import TaskQueue, TaskSpec

router = APIRouter(prefix="/v1/libraries/{library_id}/docs", tags=["documents"])

_log = structlog.get_logger(__name__)

_PRESIGNED_URL_TTL_S = 300  # 5 minutes per the spec
_DEFAULT_CHUNK_LIMIT = 20
_MAX_CHUNK_LIMIT = 100
_DOC_NOT_FOUND_DETAIL = "Document not found"

type IngestStatus = Literal["queued", "parsing", "indexing", "ready", "failed"]


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


def _ingest_status_for(record: IngestRecord | None) -> IngestStatus:
    if record is None:
        return "ready"
    if record.status == "done":
        return "ready"
    if record.status == "failed":
        return "failed"
    if record.status == "pending":
        return "indexing"
    return "ready"


def _find_record(container: AppContainer, library_id: str, doc_id: str) -> IngestRecord | None:
    """Look up the ingest state record for a given doc_id."""
    store = _state_store(container)
    try:
        records = store.list_for_library(library_id)
    finally:
        store.close()
    for rec in records:
        if rec.doc_id == doc_id:
            return rec
    return None


@router.get("/{doc_id}", response_model=DocumentDetailResponse)
async def get_document(
    library_id: Annotated[str, Path()],
    doc_id: Annotated[str, Path()],
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> DocumentDetailResponse:
    """Return DocumentDetail aggregated from the ingest state + indexes."""
    await _ensure_library(container, library_id)

    async with with_span("api.document.detail", library_id=library_id):
        record = _find_record(container, library_id, doc_id)
        if record is None:
            raise HTTPException(status_code=404, detail=_DOC_NOT_FOUND_DETAIL)

        chunks_count = record.chunks_upserted
        entities_count = await _safe_entity_count(container, library_id)
        triples_count = await _safe_triple_count(container, library_id)

        ingest_ts = _parse_iso(record.created_at)

        return DocumentDetailResponse(
            library_id=library_id,
            doc_id=doc_id,
            title=record.title or record.file_name,
            authors=[],
            year=None,
            venue=None,
            source_url="",
            doi=None,
            content_hash=record.file_sha256,
            ingest_ts=ingest_ts,
            ingest_status=_ingest_status_for(record),
            ingest_error=record.last_error,
            sections=[],
            chunks_count=chunks_count,
            entities_count=entities_count,
            triples_count=triples_count,
            pages_count=0,
        )


@router.get("/{doc_id}/chunks", response_model=DocumentChunksListResponse)
async def list_chunks(
    library_id: Annotated[str, Path()],
    doc_id: Annotated[str, Path()],
    section: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=_MAX_CHUNK_LIMIT)] = _DEFAULT_CHUNK_LIMIT,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> DocumentChunksListResponse:
    """Return up to `limit` chunks for this doc.

    The vector index does not currently expose a per-doc list operation,
    so this endpoint returns an empty list when no adapter helper exists.
    Callers that need chunk text should use the QA / search endpoints.
    """
    await _ensure_library(container, library_id)

    async with with_span("api.document.chunks", library_id=library_id):
        record = _find_record(container, library_id, doc_id)
        if record is None:
            raise HTTPException(status_code=404, detail=_DOC_NOT_FOUND_DETAIL)

        chunks: list[DocumentChunkResponse] = []
        list_chunks_fn = getattr(container.vector_index, "list_chunks_by_doc", None)
        if list_chunks_fn is not None:
            try:
                rows = await list_chunks_fn(library_id, doc_id, limit=limit)
            except Exception as exc:
                await _log.awarning(
                    "document_chunks_lookup_failed",
                    library_id=library_id,
                    doc_id=doc_id,
                    error_type=type(exc).__name__,
                )
                rows = ()
            for chunk in rows:
                if section is not None and getattr(chunk, "section", None) != section:
                    continue
                chunks.append(
                    DocumentChunkResponse(
                        library_id=library_id,
                        chunk_id=chunk.chunk_id,
                        doc_id=chunk.doc_id,
                        text=chunk.text,
                        page=chunk.page,
                        section=chunk.section,
                        kind=chunk.kind,
                    )
                )

        return DocumentChunksListResponse(
            library_id=library_id,
            doc_id=doc_id,
            chunks=chunks,
            total=len(chunks),
        )


@router.get("/{doc_id}/pdf", response_model=DocumentPdfUrlResponse)
async def get_document_pdf(
    library_id: Annotated[str, Path()],
    doc_id: Annotated[str, Path()],
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> DocumentPdfUrlResponse:
    """Return a 5-minute presigned URL to the original PDF in MinIO."""
    await _ensure_library(container, library_id)

    record = _find_record(container, library_id, doc_id)
    if record is None:
        raise HTTPException(status_code=404, detail=_DOC_NOT_FOUND_DETAIL)

    url = await _minio_presign(container, library_id, doc_id, record.file_name)
    expires_at = datetime.now(UTC) + timedelta(seconds=_PRESIGNED_URL_TTL_S)
    return DocumentPdfUrlResponse(
        library_id=library_id,
        doc_id=doc_id,
        url=url,
        expires_at=expires_at,
    )


@router.post("/{doc_id}/retry", response_model=DocumentRetryResponse)
async def retry_document(
    library_id: Annotated[str, Path()],
    doc_id: Annotated[str, Path()],
    parser: Annotated[str, Query()] = "auto",
    container: AppContainer = Depends(get_container),
    queue: TaskQueue = Depends(get_task_queue),
    _principal: Principal = Depends(get_current_principal),
) -> DocumentRetryResponse:
    """Re-enqueue an `ingest_document` job for this doc."""
    await _ensure_library(container, library_id)

    record = _find_record(container, library_id, doc_id)
    if record is None:
        raise HTTPException(status_code=404, detail=_DOC_NOT_FOUND_DETAIL)

    spec = TaskSpec(
        library_id=library_id,
        task_type="ingest_document",
        input_payload={
            "doc_id": doc_id,
            "file_sha256": record.file_sha256,
            "file_name": record.file_name,
            "parser": parser,
            "force": True,
        },
        dedup_key=f"retry:{doc_id}:{new_ulid()}",
    )
    handle = await queue.enqueue(library_id, spec)
    return DocumentRetryResponse(
        library_id=library_id,
        doc_id=doc_id,
        task_id=handle.task_id,
        parser=parser,
    )


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    library_id: Annotated[str, Path()],
    doc_id: Annotated[str, Path()],
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> None:
    """Delete this document from every backend that exposes a deleter.

    Each backend deletion is best-effort and logged on failure. The ingest
    state row is removed so future re-uploads are not deduped against the
    deleted body.
    """
    await _ensure_library(container, library_id)

    record = _find_record(container, library_id, doc_id)
    if record is None:
        raise HTTPException(status_code=404, detail=_DOC_NOT_FOUND_DETAIL)

    async with with_span("api.document.delete", library_id=library_id):
        await _try_delete(container.vector_index, "delete_doc", library_id, doc_id)
        await _try_delete(container.bm25_index, "delete_doc", library_id, doc_id)
        await _try_delete(container.graph_index, "delete_doc", library_id, doc_id)

        # Best-effort ingest state removal — protocol does not expose
        # delete, but we can rewrite the row with a tombstone status.
        store = _state_store(container)
        try:
            store.put(
                IngestRecord(
                    library_id=record.library_id,
                    file_sha256=record.file_sha256,
                    file_name=record.file_name,
                    doc_id=None,
                    title=None,
                    status="failed",
                    chunks_created=0,
                    chunks_upserted=0,
                    last_error="deleted",
                    created_at=record.created_at,
                    updated_at=datetime.now(UTC).isoformat(),
                )
            )
        finally:
            store.close()


# === helpers =================================================================


async def _safe_entity_count(container: AppContainer, library_id: str) -> int:
    fn = getattr(container.graph_index, "list_all_triples", None)
    if fn is None:
        return 0
    try:
        triples = await fn(library_id)
    except Exception:
        return 0
    seen: set[str] = set()
    for t in triples:
        seen.add(t.head)
        seen.add(t.tail)
    return len(seen)


async def _safe_triple_count(container: AppContainer, library_id: str) -> int:
    fn = getattr(container.graph_index, "list_all_triples", None)
    if fn is None:
        return 0
    try:
        triples = await fn(library_id)
    except Exception:
        return 0
    return sum(1 for _ in triples)


async def _try_delete(adapter: object, method_name: str, library_id: str, doc_id: str) -> None:
    fn = getattr(adapter, method_name, None)
    if fn is None:
        return
    try:
        await fn(library_id, doc_id)
    except Exception as exc:
        await _log.awarning(
            "document_delete_backend_failed",
            adapter=type(adapter).__name__,
            library_id=library_id,
            doc_id=doc_id,
            error_type=type(exc).__name__,
        )


async def _minio_presign(
    container: AppContainer,
    library_id: str,
    doc_id: str,
    file_name: str,
) -> str:
    """Resolve a 5-minute presigned GET URL for the doc's original PDF.

    TODO(M7-presign): replace this stub with the real MinIO adapter call
    once `packages/storage/minio.py` exposes `presigned_get_object`. The
    placeholder is wired through `Settings.minio_endpoint` so dev/staging
    environments still see a deterministic URL.
    """
    presign_fn: Callable[..., Awaitable[str]] | None = getattr(container, "minio_presign_get", None)
    if presign_fn is not None and callable(presign_fn):
        try:
            url = await presign_fn(library_id=library_id, doc_id=doc_id, ttl_s=_PRESIGNED_URL_TTL_S)
        except Exception as exc:
            await _log.awarning(
                "minio_presign_failed",
                library_id=library_id,
                doc_id=doc_id,
                error_type=type(exc).__name__,
            )
        else:
            if url:
                return url
    settings = container.settings
    bucket = getattr(settings, "minio_bucket", "kb")
    endpoint = getattr(settings, "minio_endpoint", "localhost:9000")
    safe_name = file_name.replace(" ", "%20")
    return f"http://{endpoint}/{bucket}/{library_id}/{doc_id}/{safe_name}"


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(UTC)
