"""Frontend-facing document read endpoints under `/api/libraries/*/documents`."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer
from apps.api._task_deps import get_task_bundle
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from packages.core.errors import LibraryNotFoundError
from packages.ingestion.extractor import LIMITS
from packages.ingestion.state import IngestRecord, IngestStateStore
from packages.orchestration._internal.ulid import new_ulid
from packages.orchestration.errors import QueueFullError
from packages.orchestration.queue import TaskSpec

router = APIRouter(prefix="/api/libraries/{library_id}/documents", tags=["documents"])

type FrontendDocumentStatusKind = Literal["ready", "indexing", "parsing", "failed"]

_PDF_MAGIC = b"%PDF-"
_UPLOAD_CHUNK_SIZE = 1024 * 1024
_ALLOWED_PDF_MEDIA_TYPES = {"application/pdf", "application/x-pdf"}


@dataclass(frozen=True, slots=True)
class _StagedPdfUpload:
    file_name: str
    file_path: Path
    file_sha256: str
    doc_id: str
    size_bytes: int


class FrontendDocumentStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: FrontendDocumentStatusKind
    label: str
    title: str
    message: str
    meta: str
    progress: int | None = Field(default=None, ge=0, le=100)
    progress_text: str | None = Field(default=None, alias="progressText")
    action_label: str | None = Field(default=None, alias="actionLabel")


class FrontendDocumentsSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    library_id: str = Field(alias="libraryId")
    document_count_label: str = Field(alias="documentCountLabel")
    chunk_count_label: str = Field(alias="chunkCountLabel")
    last_sync_label: str = Field(alias="lastSyncLabel")


class FrontendLibraryDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str
    library_id: str = Field(alias="libraryId")
    title: str
    authors: str
    source: str
    year: int
    status: FrontendDocumentStatus
    chunks: int | None
    entities: int | None
    ingested_label: str = Field(alias="ingestedLabel")


class FrontendDocumentStatistic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    value: str


class FrontendDocumentSection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str
    order_label: str = Field(alias="orderLabel")
    title: str
    page_label: str = Field(alias="pageLabel")


class FrontendDocumentChunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str
    location_label: str = Field(alias="locationLabel")
    text: str


class FrontendDocumentDetail(FrontendLibraryDocument):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    file_format: str = Field(alias="fileFormat")
    file_size_label: str = Field(alias="fileSizeLabel")
    ingested_at_label: str = Field(alias="ingestedAtLabel")
    page_count: int = Field(alias="pageCount", ge=0)
    selected_page: int = Field(alias="selectedPage", ge=1)
    statistics: list[FrontendDocumentStatistic]
    sections: list[FrontendDocumentSection]
    chunks_preview: list[FrontendDocumentChunk] = Field(alias="chunksPreview")


class FrontendDocumentsWorkspace(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: FrontendDocumentsSummary
    documents: list[FrontendLibraryDocument]


class FrontendDocumentMutationFeedback(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tone: Literal["success", "info", "warning", "danger"]
    title: str
    detail: str
    action: str | None = None


@router.get(
    "",
    response_model=FrontendDocumentsWorkspace,
)
async def list_frontend_documents(
    library_id: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> FrontendDocumentsWorkspace:
    await _ensure_library(container, library_id)
    records = _document_records(container, library_id)
    documents = [_document_from_record(record, entities=None) for record in records]
    return FrontendDocumentsWorkspace(
        summary=_summary_from_records(library_id, records),
        documents=documents,
    )


@router.get(
    "/{document_id}",
    response_model=FrontendDocumentDetail,
)
async def get_frontend_document(
    library_id: str,
    document_id: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> FrontendDocumentDetail:
    await _ensure_library(container, library_id)
    record = _find_record(container, library_id, document_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    chunks_preview = await _chunks_preview(container, library_id, document_id)
    page_count = _max_page_from_chunks(chunks_preview)
    entities_count = await _safe_entity_count(container, library_id)
    triples_count = await _safe_triple_count(container, library_id)
    base = _document_from_record(record, entities=entities_count)
    return FrontendDocumentDetail(
        **base.model_dump(by_alias=True),
        fileFormat=_file_format(record.file_name),
        fileSizeLabel="Unknown",
        ingestedAtLabel=_format_ingested_at(_parse_iso(record.updated_at)),
        pageCount=page_count,
        selectedPage=1,
        statistics=[
            FrontendDocumentStatistic(label="chunks", value=str(record.chunks_upserted)),
            FrontendDocumentStatistic(label="entities", value=str(entities_count)),
            FrontendDocumentStatistic(label="triples", value=str(triples_count)),
            FrontendDocumentStatistic(label="pages", value=str(page_count)),
        ],
        sections=[],
        chunksPreview=chunks_preview,
    )


@router.post(
    ":upload",
    response_model=FrontendDocumentMutationFeedback,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_frontend_documents(
    library_id: str,
    files: list[UploadFile] | None = File(default=None),
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> FrontendDocumentMutationFeedback:
    await _ensure_library(container, library_id)
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one PDF file is required in multipart field 'files'",
        )

    staged: list[_StagedPdfUpload] = []
    queued = False
    try:
        for upload in files:
            staged.append(await _stage_pdf_upload(container, library_id, upload))
        _ensure_unique_uploads(staged)
        _ensure_uploads_are_new(container, library_id, staged)
        await _queue_uploaded_documents(container, library_id, staged)
        queued = True
        _record_pending_uploads(container, library_id, staged)
    except Exception:
        if not queued:
            _cleanup_staged_uploads(staged)
        raise

    return FrontendDocumentMutationFeedback(
        tone="info",
        title="Upload queued",
        detail=_upload_feedback_detail(staged),
        action="View documents",
    )


@router.post(
    "/{document_id}:retry",
    response_model=FrontendDocumentMutationFeedback,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_frontend_document_ingestion(
    library_id: str,
    document_id: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> FrontendDocumentMutationFeedback:
    await _ensure_library(container, library_id)
    record = _find_record(container, library_id, document_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )
    if record.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document ingestion is already running: {document_id}",
        )
    if record.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is already ready: {document_id}",
        )

    spec = TaskSpec(
        library_id=library_id,
        task_type="ingest_document",
        input_payload={
            "doc_id": document_id,
            "file_sha256": record.file_sha256,
            "file_name": record.file_name,
            "parser": "auto",
            "force": True,
        },
        dedup_key=f"frontend-retry:{document_id}:{new_ulid()}",
    )
    try:
        task_bundle = await get_task_bundle(container)
        await task_bundle.queue.enqueue(library_id, spec)
    except QueueFullError:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document retry queue unavailable",
        ) from exc
    return FrontendDocumentMutationFeedback(
        tone="warning",
        title="Retry queued",
        detail=f"{record.file_name} ingestion retry queued.",
        action="Logs",
    )


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


def _document_records(container: AppContainer, library_id: str) -> tuple[IngestRecord, ...]:
    store = _state_store(container)
    try:
        records = store.list_for_library(library_id)
    finally:
        store.close()
    return tuple(record for record in records if record.doc_id is not None)


def _find_record(
    container: AppContainer,
    library_id: str,
    document_id: str,
) -> IngestRecord | None:
    for record in _document_records(container, library_id):
        if record.doc_id == document_id:
            return record
    return None


def _state_store(container: AppContainer) -> IngestStateStore:
    return IngestStateStore(Path(container.settings.ingest_state_dir) / "ingest.sqlite")


async def _stage_pdf_upload(
    container: AppContainer,
    library_id: str,
    upload: UploadFile,
) -> _StagedPdfUpload:
    file_name = _safe_upload_name(upload.filename)
    if file_name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a file name",
        )
    media_type = upload.content_type or ""
    if media_type and media_type not in _ALLOWED_PDF_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type for {file_name}: {media_type}",
        )
    if PurePath(file_name).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Only PDF files are supported: {file_name}",
        )

    upload_root = Path(container.settings.data_dir) / "uploads" / library_id
    upload_root.mkdir(parents=True, exist_ok=True)
    temp_path = upload_root / f".upload-{new_ulid()}.tmp"
    sha256 = hashlib.sha256()
    total = 0
    saw_magic = False

    try:
        with temp_path.open("wb") as dst:
            while True:
                chunk = await upload.read(_UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                if not saw_magic:
                    if len(chunk) < len(_PDF_MAGIC) or not chunk.startswith(_PDF_MAGIC):
                        raise HTTPException(
                            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail=f"Only PDF files are supported: {file_name}",
                        )
                    saw_magic = True
                total += len(chunk)
                if total > LIMITS.max_pdf_size_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"Uploaded PDF exceeds max size "
                            f"{LIMITS.max_pdf_size_bytes} bytes: {file_name}"
                        ),
                    )
                sha256.update(chunk)
                dst.write(chunk)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    if total == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file is empty: {file_name}",
        )

    digest = sha256.hexdigest()
    doc_id = digest[:12]
    target_dir = upload_root / digest
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / file_name
    temp_path.replace(target_path)
    return _StagedPdfUpload(
        file_name=file_name,
        file_path=target_path,
        file_sha256=digest,
        doc_id=doc_id,
        size_bytes=total,
    )


def _safe_upload_name(filename: str | None) -> str | None:
    if not filename:
        return None
    safe_name = PurePath(filename).name
    if not safe_name or safe_name in {".", ".."}:
        return None
    return safe_name


def _ensure_unique_uploads(staged: list[_StagedPdfUpload]) -> None:
    seen: set[str] = set()
    for item in staged:
        if item.file_sha256 in seen:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate upload in request: {item.file_name}",
            )
        seen.add(item.file_sha256)


def _ensure_uploads_are_new(
    container: AppContainer,
    library_id: str,
    staged: list[_StagedPdfUpload],
) -> None:
    store = _state_store(container)
    try:
        for item in staged:
            existing = store.get(library_id, item.file_sha256)
            if existing is None or existing.doc_id is None:
                continue
            if existing.status == "pending":
                detail = f"Document ingestion is already running: {existing.doc_id}"
            else:
                detail = f"Document already exists: {existing.doc_id}"
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    finally:
        store.close()


async def _queue_uploaded_documents(
    container: AppContainer,
    library_id: str,
    staged: list[_StagedPdfUpload],
) -> None:
    try:
        task_bundle = await get_task_bundle(container)
        for item in staged:
            spec = TaskSpec(
                library_id=library_id,
                task_type="ingest_document",
                input_payload={
                    "file_path": str(item.file_path),
                    "doc_id": item.doc_id,
                    "file_sha256": item.file_sha256,
                    "file_name": item.file_name,
                    "parser": "auto",
                    "force": False,
                },
                dedup_key=f"frontend-upload:{item.file_sha256}",
            )
            await task_bundle.queue.enqueue(library_id, spec)
    except QueueFullError:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document upload queue unavailable",
        ) from exc


def _record_pending_uploads(
    container: AppContainer,
    library_id: str,
    staged: list[_StagedPdfUpload],
) -> None:
    store = _state_store(container)
    now = datetime.now(UTC).isoformat()
    try:
        for item in staged:
            store.put(
                IngestRecord(
                    library_id=library_id,
                    file_sha256=item.file_sha256,
                    file_name=item.file_name,
                    doc_id=item.doc_id,
                    title=PurePath(item.file_name).stem,
                    status="pending",
                    chunks_created=0,
                    chunks_upserted=0,
                    last_error=None,
                    created_at=now,
                    updated_at=now,
                )
            )
    finally:
        store.close()


def _cleanup_staged_uploads(staged: list[_StagedPdfUpload]) -> None:
    for item in staged:
        item.file_path.unlink(missing_ok=True)


def _upload_feedback_detail(staged: list[_StagedPdfUpload]) -> str:
    if len(staged) == 1:
        return f"{staged[0].file_name} queued for ingestion."
    return f"{len(staged)} documents queued for ingestion."


def _summary_from_records(
    library_id: str,
    records: tuple[IngestRecord, ...],
) -> FrontendDocumentsSummary:
    total_chunks = sum(record.chunks_upserted for record in records)
    latest_update = max((_parse_iso(record.updated_at) for record in records), default=None)
    return FrontendDocumentsSummary(
        libraryId=library_id,
        documentCountLabel=_plural(len(records), "document"),
        chunkCountLabel=_plural(total_chunks, "chunk"),
        lastSyncLabel=_last_sync_label(latest_update),
    )


def _document_from_record(
    record: IngestRecord,
    *,
    entities: int | None,
) -> FrontendLibraryDocument:
    parsed_created = _parse_iso(record.created_at)
    status_value = _status_from_record(record)
    return FrontendLibraryDocument(
        id=record.doc_id or record.file_sha256,
        libraryId=record.library_id,
        title=record.title or PurePath(record.file_name).stem or record.file_name,
        authors="",
        source=record.file_name,
        year=parsed_created.year,
        status=status_value,
        chunks=record.chunks_upserted if status_value.kind == "ready" else None,
        entities=entities if status_value.kind == "ready" else None,
        ingestedLabel=_ingested_label(parsed_created),
    )


def _status_from_record(record: IngestRecord) -> FrontendDocumentStatus:
    if record.status == "done":
        return FrontendDocumentStatus(
            kind="ready",
            label="Ready",
            title="Document ready",
            message="Indexed and available for search, chat citations, and review generation.",
            meta=f"Chunks: {record.chunks_upserted}",
        )
    if record.status == "failed":
        return FrontendDocumentStatus(
            kind="failed",
            label="Failed",
            title="Ingestion failed",
            message=record.last_error or "Document ingestion failed.",
            meta=f"File: {record.file_name}",
            actionLabel="Retry ingestion",
        )
    return FrontendDocumentStatus(
        kind="indexing",
        label="Indexing",
        title="Ingestion in progress",
        message="The document is being parsed, chunked, and indexed.",
        meta=f"File: {record.file_name}",
        progress=0,
        progressText="Queued",
    )


async def _chunks_preview(
    container: AppContainer,
    library_id: str,
    document_id: str,
) -> list[FrontendDocumentChunk]:
    list_chunks = getattr(container.vector_index, "list_chunks_by_doc", None)
    if list_chunks is None:
        return []
    try:
        rows = await list_chunks(library_id, document_id, limit=3)
    except Exception:
        return []

    chunks: list[FrontendDocumentChunk] = []
    for row in rows:
        chunk_id = getattr(row, "chunk_id", "")
        text = getattr(row, "text", "")
        if not chunk_id or not text:
            continue
        chunks.append(
            FrontendDocumentChunk(
                id=chunk_id,
                locationLabel=_chunk_location_label(
                    getattr(row, "section", None),
                    getattr(row, "page", None),
                ),
                text=text,
            )
        )
    return chunks


async def _safe_entity_count(container: AppContainer, library_id: str) -> int:
    list_triples = getattr(container.graph_index, "list_all_triples", None)
    if list_triples is None:
        return 0
    try:
        triples = await list_triples(library_id)
    except Exception:
        return 0
    seen: set[str] = set()
    for triple in triples:
        seen.add(triple.head)
        seen.add(triple.tail)
    return len(seen)


async def _safe_triple_count(container: AppContainer, library_id: str) -> int:
    list_triples = getattr(container.graph_index, "list_all_triples", None)
    if list_triples is None:
        return 0
    try:
        triples = await list_triples(library_id)
    except Exception:
        return 0
    return sum(1 for _ in triples)


def _max_page_from_chunks(chunks: list[FrontendDocumentChunk]) -> int:
    # The current chunk preview shape is display-first, so page metadata is not
    # retained after formatting. Until a structured section source is available,
    # return one selected preview page for frontend layout stability.
    if chunks:
        return 1
    return 0


def _chunk_location_label(section: str | None, page: int | None) -> str:
    parts: list[str] = []
    if section:
        parts.append(section)
    if page is not None:
        parts.append(f"p.{page}")
    if not parts:
        return "Document"
    return " / ".join(parts)


def _file_format(file_name: str) -> str:
    suffix = PurePath(file_name).suffix.lstrip(".")
    if not suffix:
        return "Unknown"
    return suffix.upper()


def _parse_iso(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _plural(value: int, noun: str) -> str:
    suffix = "" if value == 1 else "s"
    return f"{value:,} {noun}{suffix}"


def _last_sync_label(value: datetime | None) -> str:
    if value is None:
        return "No documents"
    return f"Last sync {value.date().isoformat()}"


def _ingested_label(value: datetime) -> str:
    return f"Ingested {value.date().isoformat()}"


def _format_ingested_at(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")
