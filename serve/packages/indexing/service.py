"""HybridRetrievalCoordinator — three-route fusion + reranking.

ADR-0018 §2 pipeline:

    vector(top_n) ─┐
    bm25(top_n)   ─┼─ RRF(k=60) ─→ top_30 ─→ Rerank ─→ top_K
    graph(top_n)  ─┘                                  ↑ default K=8

The three routes run concurrently with per-route timeout (5 s default).
Single-route failure or timeout is logged and degraded to an empty
contribution; the remaining routes still produce a result. Only when
ALL three return empty (or all raise) do we surface an empty result.

We use ``asyncio.gather(return_exceptions=True)`` rather than
``TaskGroup`` because TaskGroup cancels sibling tasks on the first
unhandled exception, which would defeat the partial-degrade goal of the
hybrid retriever (ADR-0018 §3 graceful degradation).

Backward compatibility: the legacy ``search(library_id, query, k)`` →
``list[tuple[Chunk, float]]`` signature is preserved for callers that
predate ADR-0018 (existing tests + ReActPlanner tools). The
``hybrid_retrieve(library_id, query, k=10)`` method returns the richer
``RerankedHit`` tuple expected by ADR-0017 strategies.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

import structlog

from packages.core.models import Chunk
from packages.embedding.protocols import Embedder
from packages.embedding.protocols import Reranker as LegacyReranker
from packages.indexing._internal.rrf import rrf_fuse, runs_from_legacy
from packages.indexing.protocols import (
    BM25Index,
    FusedHit,
    GraphIndex,
    RerankedHit,
    RetrievalSource,
    VectorIndex,
)
from packages.indexing.protocols import Reranker as NewReranker

DEFAULT_K_PER_ROUTE: int = 30
DEFAULT_RRF_K: int = 60
DEFAULT_TOP_FUSED: int = 30
DEFAULT_K_FINAL: int = 8
# Rerank pays for itself even on small candidate sets when the cross-encoder
# is local; skipping it only saves a single forward pass. We still keep a
# threshold so the chain can be bypassed for trivially small results
# (e.g. a single hit), but it must be small enough that two-result fixtures
# still run through rerank — otherwise existing unit tests (M0-M5) regress.
SKIP_RERANK_THRESHOLD: int = 2
DEFAULT_ROUTE_TIMEOUT_S: float = 5.0

GraphSearchFn = Callable[[str, str, int], Awaitable[list[tuple[Chunk, float]]]]

_logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class HybridRetrievalConfig:
    """Tunables for hybrid retrieval (ADR-0018 §2)."""

    k_vector: int = DEFAULT_K_PER_ROUTE
    k_bm25: int = DEFAULT_K_PER_ROUTE
    k_graph: int = DEFAULT_K_PER_ROUTE
    rrf_k: int = DEFAULT_RRF_K
    top_fused: int = DEFAULT_TOP_FUSED
    k_final: int = DEFAULT_K_FINAL
    rerank: bool = True
    skip_rerank_threshold: int = SKIP_RERANK_THRESHOLD
    route_timeout_s: float = DEFAULT_ROUTE_TIMEOUT_S


class HybridRetrievalCoordinator:
    """Vector + BM25 + (optional) Graph → RRF → Rerank, scoped per library."""

    def __init__(
        self,
        *,
        embedder: Embedder,
        vector: VectorIndex,
        bm25: BM25Index,
        graph: GraphIndex | None = None,
        graph_search: GraphSearchFn | None = None,
        reranker: NewReranker | LegacyReranker | None = None,
        config: HybridRetrievalConfig | None = None,
    ) -> None:
        self._embedder = embedder
        self._vector = vector
        self._bm25 = bm25
        self._graph = graph
        self._graph_search = graph_search
        self._reranker = reranker
        self._config = config or HybridRetrievalConfig()

    async def search(
        self,
        library_id: str,
        query: str,
        k: int = 10,
    ) -> list[tuple[Chunk, float]]:
        """Legacy API — returns top-k as ``(chunk, fused_or_rerank_score)``.

        Preserves the M0-M5 signature so existing callers (ReAct tools,
        eval runners) keep working. Internally uses the new RRF + new
        Reranker pipeline whenever a new-style reranker is wired; falls
        back to the legacy passages-based reranker when only that is
        available, matching pre-ADR-0018 behaviour.
        """
        ranked = await self._fused_pipeline(library_id, query, k=k)
        return [(hit.chunk, hit.score) for hit in ranked]

    async def hybrid_search_v2(
        self,
        library_id: str,
        query: str,
        *,
        k: int | None = None,
    ) -> tuple[RerankedHit, ...]:
        """ADR-0018 API — returns reranked hits with full ranking metadata."""
        target_k = k if k is not None else self._config.k_final
        return await self._fused_pipeline(library_id, query, k=target_k)

    async def hybrid_retrieve(
        self,
        library_id: str,
        query: str,
        k: int = 10,
    ) -> tuple[RerankedHit, ...]:
        """Strategy-facing API — same as ``hybrid_search_v2`` with default k=10.

        ADR-0017 §1 strategies expect a structured ``RerankedHit`` tuple so
        they can carry rerank scores into evidence assembly. This is the
        public entry point exposed to those strategies.
        """
        return await self._fused_pipeline(library_id, query, k=k)

    async def _fused_pipeline(
        self,
        library_id: str,
        query: str,
        *,
        k: int,
    ) -> tuple[RerankedHit, ...]:
        runs = await self._gather_runs(library_id, query)
        fused = rrf_fuse(runs, k=self._config.rrf_k, top_n=self._config.top_fused)
        if not fused:
            return ()

        if self._should_skip_rerank(fused):
            return _fused_to_reranked(fused[:k])

        try:
            return await self._apply_rerank(query, fused, top_k=k)
        except Exception as e:  # graceful degrade per ADR-0018 §3
            await _logger.awarning(
                "rerank.failed_fallback_to_rrf",
                library_id=library_id,
                error=type(e).__name__,
                message=str(e),
            )
            return _fused_to_reranked(fused[:k])

    async def _gather_runs(
        self,
        library_id: str,
        query: str,
    ) -> list[list[tuple[Chunk, float, RetrievalSource]]]:
        """Run vector / BM25 / graph concurrently with per-route timeout.

        We use ``asyncio.gather(return_exceptions=True)`` rather than
        ``TaskGroup`` so a single-route failure (network, timeout) is
        absorbed instead of cancelling the siblings — partial degrade is
        a hard requirement of ADR-0018 §3.
        """
        cfg = self._config
        loop_results: dict[RetrievalSource, list[tuple[Chunk, float]]] = {}

        async def _vector_run() -> None:
            vectors = await self._embedder.embed([query])
            if not vectors:
                loop_results["vector"] = []
                return
            loop_results["vector"] = await self._vector.search(
                library_id, vectors[0], k=cfg.k_vector
            )

        async def _bm25_run() -> None:
            loop_results["bm25"] = await self._bm25.search(library_id, query, k=cfg.k_bm25)

        async def _graph_run() -> None:
            if self._graph_search is None:
                loop_results["graph"] = []
                return
            loop_results["graph"] = await self._graph_search(library_id, query, cfg.k_graph)

        async def _bounded(source: RetrievalSource, coro: Awaitable[None]) -> None:
            try:
                async with asyncio.timeout(cfg.route_timeout_s):
                    await coro
            except TimeoutError:
                await _logger.awarning(
                    "hybrid.route_timeout",
                    library_id=library_id,
                    source=source,
                    timeout_s=cfg.route_timeout_s,
                )
                loop_results.setdefault(source, [])
                # Re-raise so gather captures it; we still log at the
                # outer error site for consistency with non-timeout fails.
                raise

        bounded = [
            _bounded("vector", _vector_run()),
            _bounded("bm25", _bm25_run()),
            _bounded("graph", _graph_run()),
        ]
        gathered = await asyncio.gather(*bounded, return_exceptions=True)
        for source, outcome in zip(("vector", "bm25", "graph"), gathered, strict=True):
            if isinstance(outcome, BaseException):
                await _logger.awarning(
                    "hybrid.route_failed",
                    library_id=library_id,
                    source=source,
                    error=type(outcome).__name__,
                )
                loop_results.setdefault(cast(RetrievalSource, source), [])

        legacy_pairs: list[tuple[Sequence[tuple[Chunk, float]], RetrievalSource]] = [
            (loop_results.get("vector", []), "vector"),
            (loop_results.get("bm25", []), "bm25"),
            (loop_results.get("graph", []), "graph"),
        ]
        return runs_from_legacy(legacy_pairs)

    def _should_skip_rerank(self, fused: list[FusedHit]) -> bool:
        cfg = self._config
        if not cfg.rerank or self._reranker is None:
            return True
        return len(fused) < cfg.skip_rerank_threshold

    async def _apply_rerank(
        self,
        query: str,
        fused: list[FusedHit],
        *,
        top_k: int,
    ) -> tuple[RerankedHit, ...]:
        reranker = self._reranker
        if reranker is None:
            return _fused_to_reranked(fused[:top_k])
        if _is_new_reranker(reranker):
            return await cast(NewReranker, reranker).rerank(query, fused, top_k=top_k)
        return await _legacy_rerank(cast(LegacyReranker, reranker), query, fused, top_k=top_k)


def _is_new_reranker(reranker: NewReranker | LegacyReranker) -> bool:
    """Distinguish new ``Reranker`` (FusedHit/RerankedHit) from legacy.

    The legacy Protocol takes ``passages: list[str]`` and returns
    ``list[tuple[int, float]]``. We feature-detect by signature shape;
    runtime_checkable Protocols are unreliable here because the legacy
    one also exports ``rerank``.
    """
    rerank_attr = getattr(reranker, "rerank", None)
    if rerank_attr is None:
        return False
    # New Reranker has ``timeout_ms`` attribute; legacy does not.
    return hasattr(reranker, "timeout_ms")


async def _legacy_rerank(
    reranker: LegacyReranker,
    query: str,
    fused: list[FusedHit],
    *,
    top_k: int,
) -> tuple[RerankedHit, ...]:
    passages = [hit.chunk.text for hit in fused]
    raw = await reranker.rerank(query, passages, top_k)
    out: list[RerankedHit] = []
    for new_rank, (orig_idx, score) in enumerate(raw, start=1):
        if orig_idx < 0 or orig_idx >= len(fused):
            continue
        hit = fused[orig_idx]
        out.append(
            RerankedHit(
                chunk=hit.chunk,
                score=max(0.0, float(score)),
                pre_rerank_rank=hit.pre_rerank_rank,
                post_rerank_rank=new_rank,
                sources=hit.sources,
            )
        )
    return tuple(out)


def _fused_to_reranked(hits: Sequence[FusedHit]) -> tuple[RerankedHit, ...]:
    """Map FusedHit → RerankedHit identity (post == pre rank)."""
    return tuple(
        RerankedHit(
            chunk=hit.chunk,
            score=hit.score,
            pre_rerank_rank=hit.pre_rerank_rank,
            post_rerank_rank=hit.pre_rerank_rank,
            sources=hit.sources,
        )
        for hit in hits
    )


# Backward-compat: legacy `_rrf_fuse` is still imported by
# `tests/unit/test_hybrid_coordinator.py`. Keep a thin wrapper.
# pyright: ignore[reportUnusedFunction] because the import lives in tests.
def _rrf_fuse(  # pyright: ignore[reportUnusedFunction]
    *,
    ranked_lists: list[list[tuple[Chunk, float]]],
    k: int = DEFAULT_RRF_K,
) -> list[tuple[Chunk, float]]:
    """Deprecated thin wrapper — prefer ``packages.indexing._internal.rrf``.

    Retained for the M0-M5 unit test surface; new code should call
    :func:`packages.indexing._internal.rrf.rrf_fuse` directly.
    """
    legacy: list[tuple[Sequence[tuple[Chunk, float]], RetrievalSource]] = [
        (ranked, "vector") for ranked in ranked_lists
    ]
    runs = runs_from_legacy(legacy)
    fused = rrf_fuse(runs, k=k)
    return [(hit.chunk, hit.score) for hit in fused]


# Silence ruff PLW0603 imports we keep for type-checking only.
_ = (Mapping,)
