"""Smoke test for the per-Library export/import flow.

Uses pure-Python in-memory stub adapters; no Qdrant/Neo4j required.
"""

from __future__ import annotations

import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from packages.core.backup import export_library, import_library
from packages.core.models import Library


class _StubRepo:
    def __init__(self) -> None:
        self._libs: dict[str, Library] = {}

    async def get(self, library_id: str) -> Library | None:
        return self._libs.get(library_id)

    async def create(self, lib: Library) -> None:
        self._libs[lib.library_id] = lib

    async def exists(self, library_id: str) -> bool:
        return library_id in self._libs


class _StubVector:
    """Adapter without scroll_all to exercise the graceful-skip path."""


class _StubGraph:
    async def list_all_triples(self, library_id: str):  # type: ignore[no-untyped-def]
        return []


class _StubCommunity:
    async def scroll_all(self, library_id: str):  # type: ignore[no-untyped-def]
        if False:
            yield {}


def _make_library(library_id: str = "alpha") -> Library:
    return Library(
        library_id=library_id,
        name="Alpha",
        description="test",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_export_then_import_round_trip(tmp_path: Path) -> None:
    libraries_root = tmp_path / "libraries"
    out_dir = tmp_path / "backups"

    repo = _StubRepo()
    src_lib = _make_library("alpha")
    await repo.create(src_lib)

    # Pretend the library has a corpus
    (libraries_root / "alpha" / "corpus" / "spike").mkdir(parents=True)
    (libraries_root / "alpha" / "corpus" / "spike" / "a.pdf").write_bytes(b"%PDF-1.4")

    report = await export_library(
        library_id="alpha",
        out_dir=out_dir,
        library_repo=repo,
        vector_index=_StubVector(),
        graph_index=_StubGraph(),
        community_index=_StubCommunity(),
        state_store=None,
        libraries_root=libraries_root,
    )
    assert report.archive_path.exists()
    assert report.documents == 1
    assert report.chunks == 0  # _StubVector lacks scroll_all
    assert any("qdrant" in n for n in report.notes)

    # Verify manifest is well-formed
    with tarfile.open(report.archive_path, "r:gz") as tar:
        names = tar.getnames()
    assert "alpha/manifest.json" in names

    # Import as a different ID
    target_root = tmp_path / "restored" / "libraries"
    target_root.mkdir(parents=True)
    target_repo = _StubRepo()
    result = await import_library(
        archive_path=report.archive_path,
        target_library_id="alpha-clone",
        library_repo=target_repo,
        libraries_root=target_root,
    )
    assert result["library_id"] == "alpha-clone"
    assert result["restored_meta"] is True
    assert result["restored_corpus"] is True
    assert (target_root / "alpha-clone" / "corpus" / "spike" / "a.pdf").exists()

    # Verify the meta was rewritten
    restored = await target_repo.get("alpha-clone")
    assert restored is not None
    assert restored.library_id == "alpha-clone"
    assert restored.name == "Alpha"


@pytest.mark.asyncio
async def test_export_unknown_library_raises(tmp_path: Path) -> None:
    repo = _StubRepo()
    with pytest.raises(FileNotFoundError):
        await export_library(
            library_id="missing",
            out_dir=tmp_path / "backups",
            library_repo=repo,
            vector_index=_StubVector(),
            graph_index=_StubGraph(),
            community_index=_StubCommunity(),
            state_store=None,
            libraries_root=tmp_path / "libraries",
        )


@pytest.mark.asyncio
async def test_manifest_payload_shape(tmp_path: Path) -> None:
    libraries_root = tmp_path / "libraries"
    out_dir = tmp_path / "backups"
    repo = _StubRepo()
    await repo.create(_make_library("beta"))

    report = await export_library(
        library_id="beta",
        out_dir=out_dir,
        library_repo=repo,
        vector_index=_StubVector(),
        graph_index=_StubGraph(),
        community_index=_StubCommunity(),
        state_store=None,
        libraries_root=libraries_root,
    )
    manifest_path = out_dir / "beta" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in (
        "library_id",
        "started_at",
        "finished_at",
        "documents",
        "chunks",
        "triples",
        "communities",
        "notes",
    ):
        assert key in payload
    assert payload["library_id"] == "beta"
    assert report.notes == tuple(payload["notes"])
