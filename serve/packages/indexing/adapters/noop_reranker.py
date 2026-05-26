"""NoopReranker — passthrough that preserves RRF order.

Used as the mandatory tail of the reranker fallback chain (ADR-0018 §4):
when both the local BGE adapter and the Cohere fallback fail or are
disabled, the QA pipe still has to return *something*. The Noop reranker
just slices ``top_k`` and converts ``FusedHit`` → ``RerankedHit`` with
``post_rerank_rank == pre_rerank_rank``.

Library-agnostic: no library_id parameter (matches the new ``Reranker``
Protocol in ``packages/indexing/protocols.py``).
"""

from __future__ import annotations

from collections.abc import Sequence

from packages.indexing.protocols import FusedHit, RerankedHit

NOOP_NAME: str = "noop"
DEFAULT_NOOP_TIMEOUT_MS: int = 0


class NoopReranker:
    """Passthrough reranker — preserves the fused order verbatim."""

    name: str = NOOP_NAME
    timeout_ms: int = DEFAULT_NOOP_TIMEOUT_MS

    async def rerank(
        self,
        query: str,
        candidates: Sequence[FusedHit],
        *,
        top_k: int | None = None,
    ) -> tuple[RerankedHit, ...]:
        """Return ``candidates`` unchanged, capped to ``top_k``."""
        del query  # unused — intentional passthrough
        if not candidates:
            return ()
        sliced = candidates if top_k is None else candidates[:top_k]
        return tuple(
            RerankedHit(
                chunk=hit.chunk,
                score=hit.score,
                pre_rerank_rank=hit.pre_rerank_rank,
                post_rerank_rank=idx,
                sources=hit.sources,
            )
            for idx, hit in enumerate(sliced, start=1)
        )
