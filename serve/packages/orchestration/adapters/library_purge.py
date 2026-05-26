"""Library purge saga (ADR-0022).

Coordinates idempotent per-backend `purge_library` calls in fixed order:
qdrant → bm25 → neo4j → minio → postgres. Each step records a
`PurgeReceipt`; partial failures transition the library to
`partial_purged` and bubble out so a worker hook can re-run later.

Why a saga (not 2PC):
- None of Qdrant / Neo4j / OpenSearch / MinIO support cross-system XA.
- Idempotent purges on each backend make replay cheap and safe.
- The Postgres step is one local ACID transaction (the cheapest atomic
  guarantee we actually have).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, Protocol, runtime_checkable

import structlog
from pydantic import BaseModel, ConfigDict, Field

from packages.core.library_admin import LibraryAware, LibraryRepository
from packages.observability import with_span
from packages.orchestration._internal.ulid import new_ulid

logger = structlog.get_logger(__name__)


# Order matches ADR-0022 §3 Saga: vectors → BM25 → KG → blob storage → metadata
PURGE_ORDER: tuple[Literal["qdrant", "bm25", "neo4j", "minio", "postgres"], ...] = (
    "qdrant",
    "bm25",
    "neo4j",
    "minio",
    "postgres",
)


type Backend = Literal["qdrant", "bm25", "neo4j", "minio", "postgres"]
type PurgeStatus = Literal["purged", "partial_purged", "purging"]


class PurgeReceipt(BaseModel):
    """One per-backend purge receipt (ADR-0022 §2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    backend: Backend
    found: bool = False
    deleted: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    error: str | None = None


class LibraryPurgeResult(BaseModel):
    """Final saga outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    status: PurgeStatus
    receipts: tuple[PurgeReceipt, ...] = ()
    requested_by: str | None = None
    completed_at: datetime | None = None
    audit_id: str | None = None
    failed_backends: tuple[Backend, ...] = ()


@runtime_checkable
class PostgresPurgeAdapter(Protocol):
    """Single-transaction Postgres saga step (ADR-0022 §3 step 5)."""

    async def purge(
        self,
        library_id: str,
        *,
        requested_by: str | None,
        receipts_payload: tuple[dict[str, object], ...],
    ) -> tuple[int, str]:
        """Execute the FK-safe DELETE chain inside one transaction.

        Returns: `(rows_deleted, audit_id)` — `audit_id` is the ULID of
        the row written to `library_purge_audit`.
        """
        ...


@runtime_checkable
class PurgeAuditWriter(Protocol):
    """Lightweight 'audit only' adapter used when no Postgres engine is wired.

    The real implementation in production goes through `PostgresPurgeAdapter.purge`
    which writes the audit row inline with the other DELETEs. This Protocol
    exists so the FilesystemLibraryRepository path (M1 dev mode) can still
    record an audit footprint somewhere without cracking open a database.
    """

    async def write(
        self,
        *,
        audit_id: str,
        library_id: str,
        slug: str,
        purged_at: datetime,
        purged_by: str | None,
        partial_resume_state: str | None,
        receipts_payload: tuple[dict[str, object], ...],
    ) -> None: ...


class NoopAuditWriter:
    """Default audit writer used when no Postgres adapter is wired in (dev)."""

    async def write(
        self,
        *,
        audit_id: str,
        library_id: str,
        slug: str,
        purged_at: datetime,
        purged_by: str | None,
        partial_resume_state: str | None,
        receipts_payload: tuple[dict[str, object], ...],
    ) -> None:
        await logger.ainfo(
            "library_purge_audit_noop",
            audit_id=audit_id,
            library_id=library_id,
            slug=slug,
            purged_at=purged_at.isoformat(),
            purged_by=purged_by,
            partial_resume_state=partial_resume_state,
            backends=[r.get("backend") for r in receipts_payload],
        )


# ---------------------------------------------------------------------------
# Adapter resolver
# ---------------------------------------------------------------------------


async def _call_purge(
    backend: Backend,
    adapter: LibraryAware,
    library_id: str,
) -> PurgeReceipt:
    """Call `adapter.purge_library(library_id)` and translate to a receipt.

    Adapters are expected to be idempotent (ADR-0022 §2). Any exception is
    captured and surfaced as a non-found receipt with `error` populated so
    the saga continues to the next backend instead of aborting.
    """
    started = time.monotonic()
    try:
        async with with_span(f"library_purge.{backend}", library_id=library_id):
            await adapter.purge_library(library_id)
        duration_ms = int((time.monotonic() - started) * 1000)
        return PurgeReceipt(
            library_id=library_id,
            backend=backend,
            found=True,
            deleted=1,
            duration_ms=duration_ms,
            error=None,
        )
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        await logger.awarning(
            "library_purge_backend_failed",
            backend=backend,
            library_id=library_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return PurgeReceipt(
            library_id=library_id,
            backend=backend,
            found=False,
            deleted=0,
            duration_ms=duration_ms,
            error=str(exc) or type(exc).__name__,
        )


class LibraryPurgeSaga:
    """Coordinates the 5-step purge.

    Adapter slots are optional — missing adapters are treated as a clean
    no-op (idempotent contract), which lets local-only dev environments
    still exercise the saga without Qdrant/Neo4j/etc.
    """

    def __init__(
        self,
        *,
        repo: LibraryRepository,
        qdrant: LibraryAware | None = None,
        bm25: LibraryAware | None = None,
        neo4j: LibraryAware | None = None,
        minio: LibraryAware | None = None,
        postgres_adapter: PostgresPurgeAdapter | None = None,
        audit_writer: PurgeAuditWriter | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repo = repo
        self._adapters: dict[Backend, LibraryAware | None] = {
            "qdrant": qdrant,
            "bm25": bm25,
            "neo4j": neo4j,
            "minio": minio,
        }
        self._postgres_adapter = postgres_adapter
        self._audit = audit_writer or NoopAuditWriter()
        self._clock = clock

    async def purge(
        self,
        library_id: str,
        *,
        requested_by: str | None = None,
    ) -> LibraryPurgeResult:
        """Run the saga. Idempotent on retry."""
        async with with_span("library_purge.saga", library_id=library_id):
            return await self._run(library_id, requested_by=requested_by)

    async def _run(
        self,
        library_id: str,
        *,
        requested_by: str | None,
    ) -> LibraryPurgeResult:
        receipts: list[PurgeReceipt] = []
        failed: list[Backend] = []

        for backend in ("qdrant", "bm25", "neo4j", "minio"):
            adapter = self._adapters.get(backend)
            if adapter is None:
                receipts.append(
                    PurgeReceipt(
                        library_id=library_id,
                        backend=backend,
                        found=False,
                        deleted=0,
                        duration_ms=0,
                        error=None,
                    )
                )
                continue
            receipt = await _call_purge(backend, adapter, library_id)
            receipts.append(receipt)
            if receipt.error is not None:
                failed.append(backend)

        if failed:
            await logger.awarning(
                "library_purge_partial",
                library_id=library_id,
                failed_backends=list(failed),
            )
            return LibraryPurgeResult(
                library_id=library_id,
                status="partial_purged",
                receipts=tuple(receipts),
                requested_by=requested_by,
                failed_backends=tuple(failed),
            )

        # All non-pg adapters cleared — proceed to Postgres step.
        pg_started = time.monotonic()
        audit_id = new_ulid()
        try:
            if self._postgres_adapter is not None:
                payload = tuple(r.model_dump(mode="json") for r in receipts)
                rows_deleted, audit_id = await self._postgres_adapter.purge(
                    library_id,
                    requested_by=requested_by,
                    receipts_payload=payload,
                )
            else:
                rows_deleted = 0
                # Best-effort filesystem repo cleanup as fallback (ADR-0022 R-PURGE-1).
                try:
                    await self._repo.delete(library_id)
                    rows_deleted = 1
                except Exception:
                    rows_deleted = 0
                await self._audit.write(
                    audit_id=audit_id,
                    library_id=library_id,
                    slug=library_id,
                    purged_at=self._clock(),
                    purged_by=requested_by,
                    partial_resume_state=None,
                    receipts_payload=tuple(r.model_dump(mode="json") for r in receipts),
                )
            pg_duration_ms = int((time.monotonic() - pg_started) * 1000)
            receipts.append(
                PurgeReceipt(
                    library_id=library_id,
                    backend="postgres",
                    found=True,
                    deleted=rows_deleted,
                    duration_ms=pg_duration_ms,
                    error=None,
                )
            )
        except Exception as exc:
            pg_duration_ms = int((time.monotonic() - pg_started) * 1000)
            await logger.aerror(
                "library_purge_postgres_failed",
                library_id=library_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            receipts.append(
                PurgeReceipt(
                    library_id=library_id,
                    backend="postgres",
                    found=False,
                    deleted=0,
                    duration_ms=pg_duration_ms,
                    error=str(exc) or type(exc).__name__,
                )
            )
            return LibraryPurgeResult(
                library_id=library_id,
                status="partial_purged",
                receipts=tuple(receipts),
                requested_by=requested_by,
                failed_backends=("postgres",),
            )

        completed_at = self._clock()
        await logger.ainfo(
            "library_purged",
            library_id=library_id,
            requested_by=requested_by,
            audit_id=audit_id,
            backends=[r.backend for r in receipts],
        )
        return LibraryPurgeResult(
            library_id=library_id,
            status="purged",
            receipts=tuple(receipts),
            requested_by=requested_by,
            completed_at=completed_at,
            audit_id=audit_id,
        )
