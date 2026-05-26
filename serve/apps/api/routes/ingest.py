"""Ingest endpoint with `kind=pdf|zip|folder` discriminator (ADR-0019).

`POST /v1/libraries/{library_id}/ingest` is the single ingestion entry
point for the Web UI. The form must carry a `kind` field which selects
one of three pipelines:

| kind   | payload          | flow                                    |
|--------|------------------|------------------------------------------|
| pdf    | one .pdf upload  | synchronous in-process ingest (M1 path)  |
| zip    | one .zip upload  | enqueue `ingest_batch` worker job        |
| folder | many files       | enqueue `ingest_batch` after server stage |

The single-PDF path is preserved verbatim from
`apps/api/routes/libraries.py:ingest_document` so existing M1 tests keep
passing; the `zip`/`folder` paths return a TaskHandle for the parent
batch job.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi import (
    Path as PathParam,
)
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer, ingest_pdf
from apps.api._task_deps import get_task_queue
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from packages.core.errors import LibraryNotFoundError
from packages.core.library_admin import init_library
from packages.observability import with_span
from packages.orchestration.queue import TaskQueue, TaskSpec

router = APIRouter(prefix="/v1/libraries/{library_id}/ingest", tags=["ingest"])

type IngestKind = Literal["pdf", "zip", "folder"]


class IngestPdfResponse(BaseModel):
    """Response shape for a synchronous single-PDF ingest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["pdf"] = "pdf"
    library_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    title: str
    chunks_created: int = Field(ge=0)
    chunks_upserted: int = Field(ge=0)


class IngestBatchResponse(BaseModel):
    """Response shape for an async batch ingest (zip or folder)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["zip", "folder"]
    library_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    enqueued_at: datetime
    discovered_files: int = Field(ge=0, default=0)


@router.post("")
async def ingest(
    library_id: Annotated[str, PathParam()],
    kind: Annotated[IngestKind, Form()],
    file: Annotated[UploadFile | None, File()] = None,
    files: Annotated[list[UploadFile] | None, File()] = None,
    parser: Annotated[str, Form()] = "auto",
    force: Annotated[bool, Form()] = False,
    container: AppContainer = Depends(get_container),
    queue: TaskQueue = Depends(get_task_queue),
    _principal: Principal = Depends(get_current_principal),
) -> IngestPdfResponse | IngestBatchResponse:
    """Multipart ingest with `kind` discriminator (ADR-0019)."""
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)

    async with with_span("api.ingest", library_id=library_id):
        if kind == "pdf":
            if file is None:
                raise HTTPException(status_code=400, detail="Missing 'file' field for kind=pdf")
            return await _ingest_pdf(container, library_id=library_id, file=file, force=force)
        if kind == "zip":
            if file is None:
                raise HTTPException(status_code=400, detail="Missing 'file' field for kind=zip")
            return await _ingest_zip(
                container, queue, library_id=library_id, file=file, parser=parser
            )
        # kind == "folder"
        items = files or []
        if not items:
            raise HTTPException(
                status_code=400,
                detail="kind=folder requires at least one entry in 'files'",
            )
        return await _ingest_folder(
            container, queue, library_id=library_id, files=items, parser=parser
        )


# === handlers ================================================================


async def _ingest_pdf(
    container: AppContainer,
    *,
    library_id: str,
    file: UploadFile,
    force: bool,
) -> IngestPdfResponse:
    """Single PDF — synchronous M1 path."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    await init_library(library_id, adapters=[container.vector_index])

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        with file.file as src:
            shutil.copyfileobj(src, tmp)

    try:
        result = await ingest_pdf(container, library_id=library_id, pdf_path=tmp_path, force=force)
    finally:
        tmp_path.unlink(missing_ok=True)

    return IngestPdfResponse(
        library_id=library_id,
        doc_id=result.doc_id,
        title=result.title,
        chunks_created=result.chunks_created,
        chunks_upserted=result.chunks_upserted,
    )


async def _ingest_zip(
    container: AppContainer,
    queue: TaskQueue,
    *,
    library_id: str,
    file: UploadFile,
    parser: str,
) -> IngestBatchResponse:
    """ZIP archive — stage to disk and enqueue an ingest_batch job."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Expected a .zip upload")

    sandbox = _make_sandbox(container, library_id, "zip")
    inbox = sandbox / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    archive_path = inbox / file.filename
    with archive_path.open("wb") as dst, file.file as src:
        shutil.copyfileobj(src, dst)

    spec = TaskSpec(
        library_id=library_id,
        task_type="ingest_batch",
        input_payload={
            "kind": "zip",
            "archive_path": str(archive_path),
            "sandbox_path": str(sandbox),
            "parser": parser,
        },
    )
    handle = await queue.enqueue(library_id, spec)
    return IngestBatchResponse(
        kind="zip",
        library_id=library_id,
        task_id=handle.task_id,
        enqueued_at=handle.enqueued_at,
        discovered_files=0,
    )


async def _ingest_folder(
    container: AppContainer,
    queue: TaskQueue,
    *,
    library_id: str,
    files: list[UploadFile],
    parser: str,
) -> IngestBatchResponse:
    """Multi-file folder upload — drop everything into a sandbox and enqueue."""
    sandbox = _make_sandbox(container, library_id, "folder")
    inbox = sandbox / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    discovered = 0
    for upload in files:
        if not upload.filename:
            continue
        rel = Path(upload.filename).name  # flatten to defeat path traversal
        target = inbox / rel
        with target.open("wb") as dst, upload.file as src:
            shutil.copyfileobj(src, dst)
        discovered += 1

    if discovered == 0:
        raise HTTPException(status_code=400, detail="No usable files found in folder upload")

    spec = TaskSpec(
        library_id=library_id,
        task_type="ingest_batch",
        input_payload={
            "kind": "folder",
            "sandbox_path": str(sandbox),
            "parser": parser,
            "discovered_files": discovered,
        },
    )
    handle = await queue.enqueue(library_id, spec)
    return IngestBatchResponse(
        kind="folder",
        library_id=library_id,
        task_id=handle.task_id,
        enqueued_at=handle.enqueued_at,
        discovered_files=discovered,
    )


def _make_sandbox(container: AppContainer, library_id: str, kind: str) -> Path:
    """Create a fresh per-request sandbox under `<data_dir>/sandbox/...`."""
    base = Path(container.settings.data_dir) / "sandbox" / library_id
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{kind}-", dir=str(base)))
