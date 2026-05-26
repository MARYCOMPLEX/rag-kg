"""Integration test for `apps.worker.jobs.ingest_batch.run`.

Exercises the ZIP and folder discovery paths end-to-end with the real
`packages.ingestion.extractor` so the safety filters stay covered.
"""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from apps.worker.jobs import ingest_batch
from packages.orchestration.queue import TaskHandle, TaskSpec


class _FakeQueue:
    """Records every enqueue call; returns a synthetic `TaskHandle`."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, TaskSpec]] = []
        self.next_id = 0

    async def enqueue(self, library_id: str, spec: TaskSpec) -> TaskHandle:
        self.calls.append((library_id, spec))
        self.next_id += 1
        return TaskHandle(
            library_id=library_id,
            task_id=f"child-{self.next_id}",
            enqueued_at=datetime.now(UTC),
        )


def _make_pdf(path: Path) -> None:
    path.write_bytes(b"%PDF-1.4\nfake-pdf-content")


@pytest.mark.asyncio
async def test_ingest_batch_folder_fans_out_one_child_per_pdf(
    base_ctx: dict[str, Any],
    fake_event_bus: Any,
    tmp_path: Path,
) -> None:
    # Arrange — two PDFs + one .txt that must be skipped.
    folder = tmp_path / "folder"
    folder.mkdir()
    _make_pdf(folder / "a.pdf")
    _make_pdf(folder / "b.pdf")
    (folder / "notes.txt").write_text("not a pdf")

    queue = _FakeQueue()
    ctx = {**base_ctx, "task_queue": queue}

    # Act
    result = await ingest_batch.run(
        ctx,
        library_id="test-lib",
        task_id="batch-1",
        input_payload={"kind": "folder", "folder_path": str(folder)},
    )

    # Assert — exactly two child tasks queued, plus stage events fired.
    assert result["discovered_pdfs"] == 2
    assert len(result["child_task_ids"]) == 2
    assert set(result["child_task_ids"]) == {"child-1", "child-2"}
    stages = [s for s, _ in fake_event_bus.stage_events() if s is not None]
    for expected in ("parse", "chunk", "upsert"):
        assert expected in stages


@pytest.mark.asyncio
async def test_ingest_batch_zip_extracts_and_fans_out(
    base_ctx: dict[str, Any],
    tmp_path: Path,
) -> None:
    # Arrange — build a small ZIP with two PDFs.
    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    _make_pdf(pdf_a)
    _make_pdf(pdf_b)
    zip_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(pdf_a, arcname="a.pdf")
        zf.write(pdf_b, arcname="sub/b.pdf")

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    queue = _FakeQueue()
    ctx = {**base_ctx, "task_queue": queue}

    # Act
    result = await ingest_batch.run(
        ctx,
        library_id="test-lib",
        task_id="batch-2",
        input_payload={
            "kind": "zip",
            "zip_path": str(zip_path),
            "sandbox_path": str(sandbox),
        },
    )

    # Assert
    assert result["discovered_pdfs"] == 2
    assert len(queue.calls) == 2
    # Each child carries the parent task id.
    for _lib, spec in queue.calls:
        assert spec.input_payload["parent_task_id"] == "batch-2"
        assert spec.task_type == "ingest_document"


@pytest.mark.asyncio
async def test_ingest_batch_no_queue_returns_paths_for_unit_tests(
    base_ctx: dict[str, Any],
    tmp_path: Path,
) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    _make_pdf(folder / "a.pdf")

    # Note: no task_queue in ctx
    result = await ingest_batch.run(
        base_ctx,
        library_id="test-lib",
        task_id="batch-3",
        input_payload={"kind": "folder", "folder_path": str(folder)},
    )

    # Without a queue the job degrades to returning the paths verbatim.
    assert result["discovered_pdfs"] == 1
    assert result["child_task_ids"] == [str(folder / "a.pdf")]
