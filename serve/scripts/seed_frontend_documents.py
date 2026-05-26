"""Seed backend document rows for frontend API-mode smoke verification.

This writes normal ingest-state records into the local sqlite store used by
`GET /api/libraries/{libraryId}/documents` and
`POST /api/libraries/{libraryId}/documents/{documentId}:retry`.
It is intentionally idempotent and only touches the selected library.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from apps._shared.persistence.library_fs import FilesystemLibraryRepository
from packages.ingestion.state import IngestRecord, IngestStateStore

_DEFAULT_LIBRARY_ID = "rag-agent"
_DEFAULT_READY_DOC_ID = "2210.03629"
_DEFAULT_FAILED_DOC_ID = "frontend-retry-failed"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", default=_DEFAULT_LIBRARY_ID)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--state-db", default="data/state/ingest.sqlite")
    return parser.parse_args()


async def _ensure_library(data_dir: Path, library_id: str) -> None:
    repo = FilesystemLibraryRepository(data_dir=data_dir)
    if not await repo.exists(library_id):
        msg = f"Library does not exist: {library_id}"
        raise SystemExit(msg)


def _read_kg_extract(data_dir: Path, library_id: str, doc_id: str) -> dict[str, object]:
    path = data_dir / "libraries" / library_id / "kg_extracts" / f"{doc_id}.json"
    if not path.is_file():
        msg = f"KG extract not found: {path}"
        raise SystemExit(msg)
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        msg = f"KG extract must be a JSON object: {path}"
        raise SystemExit(msg)
    return raw


def _count_items(raw: dict[str, object], key: str) -> int:
    value = raw.get(key)
    if isinstance(value, list):
        return len(value)
    return 0


def _seed_records(data_dir: Path, state_db: Path, library_id: str) -> tuple[IngestRecord, ...]:
    kg_extract = _read_kg_extract(data_dir, library_id, _DEFAULT_READY_DOC_ID)
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    ready_title = kg_extract.get("title")
    ready_chunks = max(_count_items(kg_extract, "triples"), 1)
    records = (
        IngestRecord(
            library_id=library_id,
            file_sha256="seed-sha-2210-03629",
            file_name="2210.03629.pdf",
            doc_id=_DEFAULT_READY_DOC_ID,
            title=ready_title if isinstance(ready_title, str) else "ReAct paper",
            status="done",
            chunks_created=ready_chunks,
            chunks_upserted=ready_chunks,
            last_error=None,
            created_at="2026-05-20T09:30:00+00:00",
            updated_at=now,
        ),
        IngestRecord(
            library_id=library_id,
            file_sha256="seed-sha-frontend-retry-failed",
            file_name="frontend-retry-failed.pdf",
            doc_id=_DEFAULT_FAILED_DOC_ID,
            title="Frontend retry failed fixture",
            status="failed",
            chunks_created=0,
            chunks_upserted=0,
            last_error="Frontend smoke fixture: parser failed before indexing.",
            created_at="2026-05-20T10:15:00+00:00",
            updated_at=now,
        ),
    )

    store = IngestStateStore(state_db)
    try:
        for record in records:
            store.put(record)
    finally:
        store.close()
    return records


async def main() -> int:
    args = _parse_args()
    data_dir = Path(args.data_dir)
    state_db = Path(args.state_db)
    library_id = str(args.library)
    await _ensure_library(data_dir, library_id)
    records = _seed_records(data_dir, state_db, library_id)
    print(f"Seeded {len(records)} frontend document records for {library_id} in {state_db}")
    for record in records:
        print(f"- {record.doc_id}: {record.status} ({record.file_name})")
    return 0


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
