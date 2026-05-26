"""Tests for the sqlite-backed ingest state store."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.ingestion.state import IngestRecord, IngestStateStore


def _record(library_id: str = "lib", sha: str = "a" * 64, status: str = "done") -> IngestRecord:
    now = datetime.now(tz=UTC).isoformat()
    return IngestRecord(
        library_id=library_id,
        file_sha256=sha,
        file_name="paper.pdf",
        doc_id="doc-1" if status == "done" else None,
        title="A Paper",
        status=status,
        chunks_created=42 if status == "done" else 0,
        chunks_upserted=42 if status == "done" else 0,
        last_error=None if status != "failed" else "boom",
        created_at=now,
        updated_at=now,
    )


class TestIngestStateStore:
    def test_round_trip(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        store = IngestStateStore(tmp_path / "ingest.sqlite")
        try:
            assert store.get("lib", "a" * 64) is None
            store.put(_record())
            got = store.get("lib", "a" * 64)
            assert got is not None
            assert got.doc_id == "doc-1"
            assert got.chunks_created == 42
        finally:
            store.close()

    def test_put_overwrites(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        store = IngestStateStore(tmp_path / "ingest.sqlite")
        try:
            store.put(_record(status="pending"))
            store.put(_record(status="done"))
            got = store.get("lib", "a" * 64)
            assert got is not None
            assert got.status == "done"
            assert got.chunks_created == 42
        finally:
            store.close()

    def test_list_for_library_filters(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        store = IngestStateStore(tmp_path / "ingest.sqlite")
        try:
            store.put(_record(library_id="alpha", sha="a" * 64))
            store.put(_record(library_id="alpha", sha="b" * 64))
            store.put(_record(library_id="beta", sha="c" * 64))
            assert len(store.list_for_library("alpha")) == 2
            assert len(store.list_for_library("beta")) == 1
            assert len(store.list_for_library("missing")) == 0
        finally:
            store.close()


@pytest.mark.parametrize(
    "status",
    ["pending", "done", "failed"],
)
def test_status_persists(tmp_path, status: str) -> None:  # type: ignore[no-untyped-def]
    store = IngestStateStore(tmp_path / "ingest.sqlite")
    try:
        store.put(_record(status=status))
        got = store.get("lib", "a" * 64)
        assert got is not None
        assert got.status == status
    finally:
        store.close()
