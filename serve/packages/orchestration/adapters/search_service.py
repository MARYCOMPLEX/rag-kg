"""⌘K cross-resource search service implementation (ADR-0023).

Fans out to 4 sources in parallel with per-path timeout, applies type
weighting, and returns the merged ranked list.

Why this lives in `adapters/` and not `service.py`:
- It composes other adapters (Neo4j / BM25 / Postgres library repo) and
  the static action registry — a classic facade.
- `service.py` is reserved for the in-process re-export root (per
  CODING_STANDARDS §3.3).

Type weights (ADR-0023 §6) are constants here so unit tests can assert
the ordering math without monkey-patching.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol, runtime_checkable

import structlog

from packages.core.errors import LibraryNotFoundError
from packages.core.models import Library
from packages.observability import with_span
from packages.orchestration._internal.search_actions import search_actions
from packages.orchestration.search import SearchHit, SearchQuery

logger = structlog.get_logger(__name__)

# Path-level p95 timeout per ADR-0023 §5.
DEFAULT_TIMEOUT_S: float = 0.300

# Cross-type weighting (ADR-0023 §6).
TYPE_WEIGHT_ACTION: float = 1.10
TYPE_WEIGHT_LIBRARY: float = 1.00
TYPE_WEIGHT_ENTITY: float = 0.95
TYPE_WEIGHT_DOCUMENT: float = 0.90


# ---------------------------------------------------------------------------
# Source-level Protocols (kept narrow on purpose).
# ---------------------------------------------------------------------------


@runtime_checkable
class EntityNameSearcher(Protocol):
    """Neo4j name+alias fuzzy search, scoped per library."""

    async def search_entities(
        self,
        library_id: str,
        q: str,
        *,
        limit: int,
    ) -> tuple[SearchHit, ...]: ...


@runtime_checkable
class DocumentTitleSearcher(Protocol):
    """BM25 title search, scoped per library."""

    async def search_documents(
        self,
        library_id: str,
        q: str,
        *,
        limit: int,
    ) -> tuple[SearchHit, ...]: ...


@runtime_checkable
class LibraryMetadataSearcher(Protocol):
    """Postgres ILIKE search across library metadata.

    Cross-library by design — this is the §16.6 L5 exception.
    """

    async def search_libraries(
        self,
        q: str,
        *,
        limit: int,
    ) -> tuple[SearchHit, ...]: ...


# ---------------------------------------------------------------------------
# Default LibraryMetadataSearcher built on top of LibraryRepository.list_all
# ---------------------------------------------------------------------------


class _LibraryRepoListAll(Protocol):
    async def list_all(self) -> list[Library]: ...


class RepoLibraryMetadataSearcher:
    """ILIKE-equivalent search on library metadata via repo `list_all`.

    The default `FilesystemLibraryRepository` doesn't expose a SQL ILIKE,
    so we filter the in-memory list. Postgres-backed repos may override
    by implementing `LibraryMetadataSearcher` directly.
    """

    def __init__(self, repo: _LibraryRepoListAll) -> None:
        self._repo = repo

    async def search_libraries(
        self,
        q: str,
        *,
        limit: int,
    ) -> tuple[SearchHit, ...]:
        q_lower = q.strip().lower()
        if not q_lower:
            return ()
        libraries = await self._repo.list_all()
        scored: list[tuple[float, SearchHit]] = []
        for lib in libraries:
            score = _score_library(lib, q_lower)
            if score == 0.0:
                continue
            scored.append(
                (
                    score,
                    SearchHit(
                        type="library",
                        id=lib.library_id,
                        title=lib.name,
                        subtitle=lib.description,
                        library_id=None,
                        score=score,
                        payload={
                            "deeplink": f"/lib/{lib.library_id}",
                            "slug": lib.library_id,
                        },
                    ),
                )
            )
        scored.sort(key=lambda t: t[0], reverse=True)
        return tuple(hit for _, hit in scored[:limit])


def _score_library(lib: Library, q_lower: str) -> float:
    """Cheap normalized score: max-of-fields token coverage."""
    fields = [
        lib.library_id.lower(),
        lib.name.lower(),
        (lib.description or "").lower(),
    ]
    tokens = [t for t in q_lower.split() if t]
    if not tokens:
        return 0.0
    matched = sum(1 for t in tokens if any(t in f for f in fields))
    if matched == 0:
        return 0.0
    return min(matched / len(tokens), 1.0)


# ---------------------------------------------------------------------------
# Stubs used when callers omit a backend (graceful no-op)
# ---------------------------------------------------------------------------


class _EmptyEntitySearcher:
    async def search_entities(
        self,
        library_id: str,
        q: str,
        *,
        limit: int,
    ) -> tuple[SearchHit, ...]:
        _ = library_id, q, limit
        return ()


class _EmptyDocumentSearcher:
    async def search_documents(
        self,
        library_id: str,
        q: str,
        *,
        limit: int,
    ) -> tuple[SearchHit, ...]:
        _ = library_id, q, limit
        return ()


# ---------------------------------------------------------------------------
# SearchService implementation
# ---------------------------------------------------------------------------


def _type_weight(kind: str) -> float:
    if kind == "action":
        return TYPE_WEIGHT_ACTION
    if kind == "library":
        return TYPE_WEIGHT_LIBRARY
    if kind == "entity":
        return TYPE_WEIGHT_ENTITY
    if kind == "document":
        return TYPE_WEIGHT_DOCUMENT
    return TYPE_WEIGHT_DOCUMENT


def _normalize_and_rank(hits: Sequence[SearchHit], limit: int) -> tuple[SearchHit, ...]:
    weighted = tuple(
        hit.model_copy(update={"score": hit.score * _type_weight(hit.type)}) for hit in hits
    )
    ranked = sorted(weighted, key=lambda h: h.score, reverse=True)
    return tuple(ranked[:limit])


class CrossResourceSearchService:
    """4-way parallel search facade with per-path timeout (ADR-0023)."""

    def __init__(
        self,
        *,
        entity_searcher: EntityNameSearcher | None = None,
        document_searcher: DocumentTitleSearcher | None = None,
        library_searcher: LibraryMetadataSearcher,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._entity = entity_searcher or _EmptyEntitySearcher()
        self._document = document_searcher or _EmptyDocumentSearcher()
        self._library = library_searcher
        self._timeout_s = timeout_s

    async def search(self, query: SearchQuery) -> tuple[SearchHit, ...]:
        """Run all selected sources concurrently and merge with type weights."""
        async with with_span(
            "orchestration.search",
            library_id=query.library_id or "global",
        ):
            return await self._run(query)

    async def _run(self, query: SearchQuery) -> tuple[SearchHit, ...]:
        types_set = set(query.types)
        running: dict[str, asyncio.Task[tuple[SearchHit, ...]]] = {}

        async def _wrap(
            label: str, coro: Awaitable[tuple[SearchHit, ...]]
        ) -> tuple[SearchHit, ...]:
            try:
                async with asyncio.timeout(self._timeout_s):
                    return await coro
            except (TimeoutError, Exception) as exc:
                await logger.awarning(
                    "search_path_failed",
                    path=label,
                    error_type=type(exc).__name__,
                )
                return ()

        if "entity" in types_set and query.library_id:
            running["entity"] = asyncio.create_task(
                _wrap(
                    "entity",
                    self._entity.search_entities(query.library_id, query.q, limit=query.limit),
                )
            )
        if "document" in types_set and query.library_id:
            running["document"] = asyncio.create_task(
                _wrap(
                    "document",
                    self._document.search_documents(query.library_id, query.q, limit=query.limit),
                )
            )
        if "library" in types_set:
            running["library"] = asyncio.create_task(
                _wrap("library", self._library.search_libraries(query.q, limit=query.limit))
            )
        if "action" in types_set:
            running["action"] = asyncio.create_task(
                _wrap("action", _action_coro(query)),
            )

        if not running:
            return ()
        await asyncio.gather(*running.values(), return_exceptions=True)
        merged: list[SearchHit] = []
        for task in running.values():
            merged.extend(task.result())
        return _normalize_and_rank(merged, query.limit)


async def _action_coro(query: SearchQuery) -> tuple[SearchHit, ...]:
    hits, _duration = search_actions(query.q, library_id=query.library_id, limit=query.limit)
    return hits


# ---------------------------------------------------------------------------
# Diagnostic helpers reused by the route layer for `timing_ms` reporting.
# ---------------------------------------------------------------------------


async def time_path(
    label: str,
    coro_factory: Callable[[], Awaitable[tuple[SearchHit, ...]]],
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> tuple[str, tuple[SearchHit, ...], int, str | None]:
    """Time a single search path with a hard timeout.

    Returns `(label, hits, duration_ms, error_label_or_none)` for callers
    who need to fill `SearchResponse.timing_ms` and `SearchResponse.degraded`.
    """
    started = time.monotonic()
    try:
        async with asyncio.timeout(timeout_s):
            hits = await coro_factory()
    except TimeoutError:
        duration_ms = int((time.monotonic() - started) * 1000)
        return label, (), duration_ms, "timeout"
    except LibraryNotFoundError:
        duration_ms = int((time.monotonic() - started) * 1000)
        return label, (), duration_ms, "library_not_found"
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        return label, (), duration_ms, type(exc).__name__
    duration_ms = int((time.monotonic() - started) * 1000)
    return label, hits, duration_ms, None
