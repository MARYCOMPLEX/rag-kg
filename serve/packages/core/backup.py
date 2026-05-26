"""Per-Library backup orchestration.

Bundles every per-Library state slice into a single archive directory:
    library_meta.json   (Library + custom config)
    documents.tar.gz    (raw corpus / spike / full)
    qdrant.jsonl        (chunks scrolled out of the vector index)
    graph.json          (entities + triples from Neo4j)
    communities.jsonl   (community summaries)
    ingest_state.json   (sqlite IngestStateStore export)
    manifest.json       (versions + counts)

The cross-store dump implementations are intentionally minimal — they call
the public Protocol surface only, so they keep working when adapters change.
Backends that don't yet expose `scroll_all` simply leave the corresponding
file empty and record a note in the manifest.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import shutil
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.models import Library


@dataclass(frozen=True, slots=True)
class BackupReport:
    library_id: str
    archive_path: Path
    documents: int
    chunks: int
    triples: int
    communities: int
    started_at: str
    finished_at: str
    notes: tuple[str, ...] = ()


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


async def _write_jsonl_async(path: Path, items: list[Any]) -> int:
    def _write() -> int:
        count = 0
        with path.open("w", encoding="utf-8") as fp:
            for item in items:
                fp.write(json.dumps(item, ensure_ascii=False, default=str))
                fp.write("\n")
                count += 1
        return count

    return await asyncio.to_thread(_write)


async def _dump_corpus(corpus_dir: Path, archive_dir: Path) -> int:
    if not corpus_dir.exists():
        return 0
    documents = 0
    tar_path = archive_dir / "documents.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for child in corpus_dir.rglob("*"):
            if child.is_file():
                tar.add(child, arcname=child.relative_to(corpus_dir))
                if child.suffix.lower() == ".pdf":
                    documents += 1
    return documents


async def _dump_chunks(
    vector_index: Any, library_id: str, archive_dir: Path, notes: list[str]
) -> int:
    path = archive_dir / "qdrant.jsonl"
    if not hasattr(vector_index, "scroll_all"):
        path.write_text("", encoding="utf-8")
        notes.append("qdrant: scroll_all not implemented — skipping chunk dump")
        return 0
    try:
        items: list[dict[str, Any]] = []
        async for item in vector_index.scroll_all(library_id):
            items.append(item)
        return await _write_jsonl_async(path, items)
    except Exception as exc:
        notes.append(f"qdrant.scroll_all: {exc}")
        path.write_text("", encoding="utf-8")
        return 0


async def _dump_graph(
    graph_index: Any, library_id: str, archive_dir: Path, notes: list[str]
) -> int:
    path = archive_dir / "graph.json"
    if not hasattr(graph_index, "list_all_triples"):
        path.write_text("[]", encoding="utf-8")
        notes.append("graph: list_all_triples not implemented — skipping triples dump")
        return 0
    try:
        triple_list = await graph_index.list_all_triples(library_id)
        payload = [
            t.model_dump(mode="json") if hasattr(t, "model_dump") else dict(t)  # type: ignore[arg-type]
            for t in triple_list
        ]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(payload)
    except Exception as exc:
        notes.append(f"graph.list_all_triples: {exc}")
        path.write_text("[]", encoding="utf-8")
        return 0


async def _dump_communities(
    community_index: Any, library_id: str, archive_dir: Path, notes: list[str]
) -> int:
    path = archive_dir / "communities.jsonl"
    if not hasattr(community_index, "scroll_all"):
        path.write_text("", encoding="utf-8")
        notes.append("community: scroll_all not implemented — skipping summaries")
        return 0
    try:
        items: list[dict[str, Any]] = []
        async for item in community_index.scroll_all(library_id):
            items.append(item)
        return await _write_jsonl_async(path, items)
    except Exception as exc:
        notes.append(f"community.scroll_all: {exc}")
        path.write_text("", encoding="utf-8")
        return 0


def _dump_state(state_store: Any, library_id: str, archive_dir: Path, notes: list[str]) -> None:
    if state_store is None:
        return
    try:
        (archive_dir / "ingest_state.json").write_text(
            state_store.to_json_export(library_id), encoding="utf-8"
        )
    except Exception as exc:
        notes.append(f"ingest_state: {exc}")


async def export_library(
    *,
    library_id: str,
    out_dir: Path,
    library_repo: Any,
    vector_index: Any,
    graph_index: Any,
    community_index: Any,
    state_store: Any | None,
    libraries_root: Path,
) -> BackupReport:
    """Dump every per-Library state slice into `out_dir / <library_id>/`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = out_dir / library_id
    if archive_dir.exists():
        shutil.rmtree(archive_dir)
    archive_dir.mkdir(parents=True)

    started = _now()
    notes: list[str] = []

    lib = await library_repo.get(library_id)
    if lib is None:
        msg = f"Library not found: {library_id}"
        raise FileNotFoundError(msg)
    (archive_dir / "library_meta.json").write_text(
        json.dumps(lib.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    documents = await _dump_corpus(libraries_root / library_id, archive_dir)
    chunks = await _dump_chunks(vector_index, library_id, archive_dir, notes)
    triples = await _dump_graph(graph_index, library_id, archive_dir, notes)
    communities = await _dump_communities(community_index, library_id, archive_dir, notes)
    _dump_state(state_store, library_id, archive_dir, notes)

    finished = _now()
    manifest = {
        "library_id": library_id,
        "started_at": started,
        "finished_at": finished,
        "documents": documents,
        "chunks": chunks,
        "triples": triples,
        "communities": communities,
        "notes": notes,
    }
    (archive_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    archive_tar = out_dir / f"{library_id}.tar.gz"
    if archive_tar.exists():
        archive_tar.unlink()
    with tarfile.open(archive_tar, "w:gz") as tar:
        tar.add(archive_dir, arcname=library_id)

    return BackupReport(
        library_id=library_id,
        archive_path=archive_tar,
        documents=documents,
        chunks=chunks,
        triples=triples,
        communities=communities,
        started_at=started,
        finished_at=finished,
        notes=tuple(notes),
    )


async def import_library(
    *,
    archive_path: Path,
    target_library_id: str,
    library_repo: Any,
    libraries_root: Path,
) -> dict[str, Any]:
    """Restore a previously-exported archive into a new library_id.

    For now this restores the corpus + meta only — re-running the
    ingest pipeline is the intended flow because the per-vector-store
    bulk-insert APIs are not part of the adapter Protocol yet.
    """
    if not archive_path.exists():
        msg = f"Archive not found: {archive_path}"
        raise FileNotFoundError(msg)

    work_dir = libraries_root.parent / "_restore_tmp"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(work_dir)

    inner = next(work_dir.iterdir())  # the {library_id}/ folder
    meta_path = inner / "library_meta.json"
    documents_tar = inner / "documents.tar.gz"

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["library_id"] = target_library_id
    lib = Library.model_validate(meta)
    await library_repo.create(lib)

    target_corpus = libraries_root / target_library_id
    restored_corpus = documents_tar.exists()
    if restored_corpus:
        with tarfile.open(documents_tar, "r:gz") as tar:
            tar.extractall(target_corpus)

    shutil.rmtree(work_dir)
    return {
        "library_id": target_library_id,
        "restored_meta": True,
        "restored_corpus": restored_corpus,
        "next_step": (
            f"Run `rkb ingest --library {target_library_id}` to repopulate "
            "vector / KG / community indices."
        ),
    }


def gzip_text(path: Path, content: str) -> None:
    """Helper used by snapshot scripts."""
    with gzip.open(path, "wt", encoding="utf-8") as fp:
        fp.write(content)
