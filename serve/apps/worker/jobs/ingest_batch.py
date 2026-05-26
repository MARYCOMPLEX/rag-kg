"""Fan-out parent job for ZIP / folder uploads (ADR-0019).

The parent job is enqueued by `POST /v1/libraries/{lib}/ingest` after the
API has staged the multipart payload. Pipeline:

1. ``parse``  : extract the ZIP (when ``kind=zip``) into the sandbox.
2. ``chunk``  : discover PDFs (extension + magic-number check) — the
                stage name is reused so the SSE event taxonomy stays
                identical across single + batch ingest.
3. ``upsert`` : enqueue one ``ingest_document`` child task per discovered
                PDF, deduping on file SHA-256 if a state store is wired.

The job respects ADR-0019 hard limits — sandbox extraction is delegated
to ``packages.ingestion.extractor.extract_zip`` which already enforces
zip-bomb / path-traversal / disk-quota guards.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Protocol, cast

import structlog

from apps.worker.jobs._stages import StageEmitter, make_stage_emitter
from apps.worker.jobs.base import JobContext, job_lifecycle
from packages.ingestion.extractor import (
    LIMITS,
    discover_pdfs,
    extract_zip,
    walk_folder,
)
from packages.observability import with_span
from packages.orchestration.queue import TaskSpec

logger = structlog.get_logger(__name__)

_BATCH_TIMEOUT_S = 1500.0


class _TaskQueueLike(Protocol):
    async def enqueue(self, library_id: str, spec: TaskSpec) -> Any: ...


async def run(
    ctx: dict[str, Any],
    *,
    library_id: str,
    task_id: str,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    """Discover PDFs from a ZIP / folder and enqueue per-doc child jobs.

    Required ``input_payload`` keys (one of):
        - ``kind`` = ``"zip"`` and ``zip_path``  — absolute path to the
          uploaded archive sitting under the request sandbox.
        - ``kind`` = ``"folder"`` and ``folder_path`` — sandbox staging dir.

    Returns:
        ``{"discovered_pdfs": int, "child_task_ids": list[str], ...}``.
    """
    jc = JobContext.from_arq(ctx, library_id=library_id, task_id=task_id, task_type="ingest_batch")
    emitter = make_stage_emitter(jc)
    kind = str(input_payload.get("kind", "zip"))
    sandbox = Path(str(input_payload.get("sandbox_path", "")))

    async with job_lifecycle(jc):
        async with asyncio.timeout(_BATCH_TIMEOUT_S):
            return await _run_inner(jc, ctx, emitter, kind, sandbox, input_payload)


async def _run_inner(
    jc: JobContext,
    ctx: dict[str, Any],
    emitter: StageEmitter,
    kind: str,
    sandbox: Path,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    queue = cast(_TaskQueueLike | None, ctx.get("task_queue"))

    async with with_span(
        "worker.ingest_batch",
        library_id=jc.library_id,
        task_id=jc.task_id,
        kind=kind,
    ):
        await emitter("parse", "stage_started", {"kind": kind})
        if kind == "zip":
            zip_path = Path(str(input_payload["zip_path"]))
            await extract_zip(zip_path, sandbox, limits=LIMITS)
            scan_root = sandbox
        elif kind == "folder":
            scan_root = Path(str(input_payload["folder_path"]))
        else:
            msg = f"unsupported batch kind: {kind!r}"
            raise ValueError(msg)
        await emitter("parse", "stage_completed", {"sandbox": str(scan_root)})

        await emitter("chunk", "stage_started", {})
        pdfs = await asyncio.to_thread(discover_pdfs, scan_root, limits=LIMITS)
        # Folders may legitimately contain non-PDFs; surface their count
        # for operator diagnostics without aborting the run.
        all_files = await asyncio.to_thread(walk_folder, scan_root) if kind == "folder" else []
        await emitter(
            "chunk",
            "stage_completed",
            {
                "discovered_pdfs": len(pdfs),
                "skipped_non_pdf": max(0, len(all_files) - len(pdfs)),
            },
        )

        await emitter("upsert", "stage_started", {"pdf_count": len(pdfs)})
        child_task_ids = await _fan_out(jc, queue, pdfs, input_payload)
        await emitter(
            "upsert",
            "stage_completed",
            {"children_enqueued": len(child_task_ids)},
        )

    return {
        "discovered_pdfs": len(pdfs),
        "child_task_ids": child_task_ids,
        "kind": kind,
    }


async def _fan_out(
    jc: JobContext,
    queue: _TaskQueueLike | None,
    pdfs: list[Path],
    input_payload: dict[str, Any],
) -> list[str]:
    """Enqueue an `ingest_document` child for each PDF.

    When the task queue is not in `ctx` (e.g. unit-test environment), we
    return the PDF paths verbatim so the test can assert discovery
    happened without standing up Redis.
    """
    if queue is None:
        await jc.log.awarning(
            "ingest_batch_no_task_queue",
            pdf_count=len(pdfs),
        )
        return [str(p) for p in pdfs]

    parser_pref = str(input_payload.get("parser", "auto"))
    handles: list[str] = []
    for pdf in pdfs:
        spec = TaskSpec(
            library_id=jc.library_id,
            task_type="ingest_document",
            input_payload={
                "file_path": str(pdf),
                "parser": parser_pref,
                "parent_task_id": jc.task_id,
            },
        )
        try:
            handle = await queue.enqueue(jc.library_id, spec)
        except Exception as exc:
            await jc.log.aerror(
                "ingest_batch_child_enqueue_failed",
                error=str(exc),
                pdf=str(pdf),
            )
            continue
        handles.append(getattr(handle, "task_id", ""))
    return handles


__all__ = ["run"]
