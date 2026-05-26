"""Reranker fallback chain — composes BGE → Cohere → Noop per ADR-0018 §4.

The chain itself implements the ``Reranker`` Protocol so callers can drop
it in anywhere a single reranker is expected. Each entry has its own
``timeout_ms`` (per ADR-0018 §3 latency contract); the chain advances on
``RerankerNotAvailableError`` or ``RerankerTimeoutError`` and never on
unrelated exceptions (those propagate so we don't silently mask bugs).

The Noop tail is mandatory — without it, an unhealthy chain would raise
all the way to the QA route, regressing P95 worse than just dropping the
rerank stage.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import structlog

from packages.indexing.adapters.noop_reranker import NoopReranker
from packages.indexing.errors import RerankerNotAvailableError, RerankerTimeoutError
from packages.indexing.protocols import FusedHit, RerankedHit, Reranker

CHAIN_NAME: str = "fallback-chain"
DEFAULT_CHAIN_TIMEOUT_MS: int = 1000

_logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class FallbackReranker:
    """Walks an ordered list of rerankers; first to succeed wins."""

    name: str = CHAIN_NAME

    def __init__(
        self,
        chain: Sequence[Reranker],
        *,
        ensure_noop_tail: bool = True,
    ) -> None:
        if not chain:
            msg = "FallbackReranker requires at least one reranker in the chain"
            raise ValueError(msg)
        ordered = list(chain)
        if ensure_noop_tail and not isinstance(ordered[-1], NoopReranker):
            ordered.append(NoopReranker())
        self._chain: tuple[Reranker, ...] = tuple(ordered)

    @property
    def timeout_ms(self) -> int:
        # The chain itself does not impose an outer timeout; each entry
        # has its own. We surface the longest as a diagnostic value.
        return max(r.timeout_ms for r in self._chain) or DEFAULT_CHAIN_TIMEOUT_MS

    @property
    def chain(self) -> tuple[Reranker, ...]:
        return self._chain

    async def rerank(
        self,
        query: str,
        candidates: Sequence[FusedHit],
        *,
        top_k: int | None = None,
    ) -> tuple[RerankedHit, ...]:
        last_error: BaseException | None = None
        for reranker in self._chain:
            try:
                result = await reranker.rerank(query, candidates, top_k=top_k)
            except (
                RerankerNotAvailableError,
                RerankerTimeoutError,
                TimeoutError,
                asyncio.CancelledError,
            ) as e:
                last_error = e
                await _logger.awarning(
                    "reranker.fallback_advance",
                    failed=reranker.name,
                    error=type(e).__name__,
                )
                if isinstance(e, asyncio.CancelledError):
                    raise
                continue
            return result

        # All entries failed — the Noop tail (if present) cannot fail, so
        # this branch is only reached when ensure_noop_tail=False.
        msg = f"All rerankers in fallback chain failed; last error: {last_error!s}"
        raise RerankerNotAvailableError(msg)
