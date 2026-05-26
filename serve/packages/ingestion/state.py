"""Sqlite-backed processed-doc tracker for ingest idempotency."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingest_state (
    library_id      TEXT NOT NULL,
    file_sha256     TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    doc_id          TEXT,
    title           TEXT,
    status          TEXT NOT NULL,         -- pending | done | failed
    chunks_created  INTEGER DEFAULT 0,
    chunks_upserted INTEGER DEFAULT 0,
    last_error      TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    PRIMARY KEY (library_id, file_sha256)
)
"""


@dataclass(frozen=True, slots=True)
class IngestRecord:
    library_id: str
    file_sha256: str
    file_name: str
    doc_id: str | None
    title: str | None
    status: str  # 'pending' | 'done' | 'failed'
    chunks_created: int
    chunks_upserted: int
    last_error: str | None
    created_at: str
    updated_at: str


class IngestStateStore:
    """Thread-safe sqlite-backed key-value store keyed by (library_id, sha256)."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def get(self, library_id: str, file_sha256: str) -> IngestRecord | None:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM ingest_state WHERE library_id = ? AND file_sha256 = ?",
                (library_id, file_sha256),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def put(self, record: IngestRecord) -> None:
        data = asdict(record)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO ingest_state (
                    library_id, file_sha256, file_name, doc_id, title,
                    status, chunks_created, chunks_upserted,
                    last_error, created_at, updated_at
                ) VALUES (
                    :library_id, :file_sha256, :file_name, :doc_id, :title,
                    :status, :chunks_created, :chunks_upserted,
                    :last_error, :created_at, :updated_at
                )
                ON CONFLICT(library_id, file_sha256) DO UPDATE SET
                    file_name=excluded.file_name,
                    doc_id=excluded.doc_id,
                    title=excluded.title,
                    status=excluded.status,
                    chunks_created=excluded.chunks_created,
                    chunks_upserted=excluded.chunks_upserted,
                    last_error=excluded.last_error,
                    updated_at=excluded.updated_at
                """,
                data,
            )
            self._conn.commit()

    def list_for_library(self, library_id: str) -> tuple[IngestRecord, ...]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM ingest_state WHERE library_id = ? ORDER BY created_at",
                (library_id,),
            )
            rows = cur.fetchall()
        return tuple(_row_to_record(r) for r in rows)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def to_json_export(self, library_id: str) -> str:
        records = [asdict(r) for r in self.list_for_library(library_id)]
        return json.dumps(records, ensure_ascii=False, indent=2)


def _row_to_record(row: sqlite3.Row) -> IngestRecord:
    return IngestRecord(
        library_id=row["library_id"],
        file_sha256=row["file_sha256"],
        file_name=row["file_name"],
        doc_id=row["doc_id"],
        title=row["title"],
        status=row["status"],
        chunks_created=row["chunks_created"] or 0,
        chunks_upserted=row["chunks_upserted"] or 0,
        last_error=row["last_error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
