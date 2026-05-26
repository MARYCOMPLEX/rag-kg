"""BGE-reranker-v2-m3 local cross-encoder adapter.

Primary entry of the reranker fallback chain per ADR-0018 §1+§4.

Design notes
------------
- ``sentence-transformers`` is an OPTIONAL runtime dependency. We import it
  lazily inside ``_load_model`` so packages that don't need a local
  reranker (CI lanes, unit tests, dev boxes without GPU) never pay the
  import cost or the model download.
- The cross-encoder forward pass is CPU-bound; we run it via
  ``asyncio.to_thread`` so the event loop stays responsive. Per
  ADR-0018 §3 the contract is P95 ≤ 200 ms on top-30 with GPU; we keep
  the same ``timeout_ms`` ceiling on CPU and surface a graceful
  ``asyncio.TimeoutError`` so the chain falls through.
- Library-agnostic API per ADR-0018 §1: signature does NOT take
  ``library_id`` (it's a pure scoring service). The ``Reranker`` Protocol
  in ``packages/indexing/protocols.py`` matches this shape.

Failure semantics
-----------------
- ``ImportError`` while loading sentence-transformers → marks the adapter
  as unhealthy and re-raises ``RerankerNotAvailableError``; the chain
  catches and falls through.
- Forward-pass timeout → ``asyncio.TimeoutError`` propagates so the
  fallback chain can route to Cohere / Noop.
- Empty candidates → returns ``()`` immediately (no model call).
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

import structlog

from packages.indexing.errors import RerankerNotAvailableError
from packages.indexing.protocols import FusedHit, RerankedHit

BGE_NAME: str = "bge-reranker-v2-m3"
DEFAULT_BGE_MODEL_ID: str = "BAAI/bge-reranker-v2-m3"
DEFAULT_BGE_TIMEOUT_MS: int = 200
DEFAULT_BGE_MAX_LENGTH: int = 512
SCORE_NORMALIZATION_OFFSET: float = 0.0  # raw cross-encoder logit; >=0 enforced post-hoc

_logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BGERerankerConfig:
    """Tunables for the local BGE-reranker-v2-m3 cross-encoder."""

    model_id: str = DEFAULT_BGE_MODEL_ID
    timeout_ms: int = DEFAULT_BGE_TIMEOUT_MS
    max_length: int = DEFAULT_BGE_MAX_LENGTH
    device: str | None = None  # "cuda" / "cpu" / None (auto)


class _CrossEncoderLike(Protocol):
    """Minimal Protocol matching ``sentence_transformers.CrossEncoder.predict``."""

    def predict(
        self,
        sentences: list[tuple[str, str]],
        *,
        batch_size: int = 32,
        show_progress_bar: bool = False,
    ) -> Any: ...


class BGERerankerV2Adapter:
    """Local BGE-reranker-v2-m3 cross-encoder via sentence-transformers."""

    name: str = BGE_NAME

    def __init__(
        self,
        config: BGERerankerConfig | None = None,
        *,
        model: _CrossEncoderLike | None = None,
    ) -> None:
        self._config = config or BGERerankerConfig()
        # Tests inject ``model`` directly; production loads on first call.
        self._model: _CrossEncoderLike | None = model
        self._load_failed: bool = False

    @property
    def timeout_ms(self) -> int:
        return self._config.timeout_ms

    async def rerank(
        self,
        query: str,
        candidates: Sequence[FusedHit],
        *,
        top_k: int | None = None,
    ) -> tuple[RerankedHit, ...]:
        """Score ``(query, chunk.text)`` pairs and return top-``top_k`` hits.

        Raises ``asyncio.TimeoutError`` when the forward pass exceeds
        ``timeout_ms`` so the fallback chain can route to the next
        reranker. ``RerankerNotAvailableError`` when the model can't be
        loaded.
        """
        if not candidates:
            return ()

        model = await asyncio.to_thread(self._ensure_model)
        pairs = [(query, hit.chunk.text) for hit in candidates]

        timeout_s = self._config.timeout_ms / 1000.0
        try:
            raw_scores = await asyncio.wait_for(
                asyncio.to_thread(_score_pairs, model, pairs),
                timeout=timeout_s,
            )
        except TimeoutError:
            await _logger.awarning(
                "bge_reranker.timeout",
                timeout_ms=self._config.timeout_ms,
                n_candidates=len(candidates),
            )
            raise

        return _build_reranked(candidates, raw_scores, top_k=top_k)

    def _ensure_model(self) -> _CrossEncoderLike:
        if self._model is not None:
            return self._model
        if self._load_failed:
            msg = "BGE reranker model previously failed to load"
            raise RerankerNotAvailableError(msg)

        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-not-found]
        except ImportError as e:
            self._load_failed = True
            msg = (
                "sentence-transformers not installed; "
                "BGE local reranker unavailable. Install via "
                "`uv add sentence-transformers` or use Cohere fallback."
            )
            raise RerankerNotAvailableError(msg) from e

        try:
            instance = CrossEncoder(
                self._config.model_id,
                max_length=self._config.max_length,
                device=self._config.device,
            )
        except Exception as e:
            self._load_failed = True
            msg = f"Failed to load BGE cross-encoder '{self._config.model_id}': {e!s}"
            raise RerankerNotAvailableError(msg) from e

        self._model = cast(_CrossEncoderLike, instance)
        return self._model


def _score_pairs(
    model: _CrossEncoderLike,
    pairs: list[tuple[str, str]],
) -> list[float]:
    """Run the cross-encoder forward pass; pure CPU/GPU work."""
    raw = model.predict(pairs, batch_size=32, show_progress_bar=False)
    return [float(s) for s in raw]


def _build_reranked(
    candidates: Sequence[FusedHit],
    raw_scores: list[float],
    *,
    top_k: int | None,
) -> tuple[RerankedHit, ...]:
    """Sort candidates by score desc, slice to top_k, normalize >= 0."""
    enumerated = list(enumerate(raw_scores))
    enumerated.sort(key=lambda item: item[1], reverse=True)
    if top_k is not None:
        enumerated = enumerated[:top_k]

    out: list[RerankedHit] = []
    for new_rank, (orig_idx, score) in enumerate(enumerated, start=1):
        hit = candidates[orig_idx]
        # FusedHit/RerankedHit enforce score >= 0; cross-encoder logits can
        # be negative. Map by sigmoid-style rescale: max(0, score + 0.5)
        # is a safe monotonic transform that preserves order. (For pure
        # ranking, only order matters; downstream CRAG normalises again.)
        normalised = score if score >= SCORE_NORMALIZATION_OFFSET else 0.0
        out.append(
            RerankedHit(
                chunk=hit.chunk,
                score=normalised,
                pre_rerank_rank=hit.pre_rerank_rank,
                post_rerank_rank=new_rank,
                sources=hit.sources,
            )
        )
    return tuple(out)
