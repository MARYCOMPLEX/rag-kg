"""Cohere Rerank API adapter — secondary entry of the reranker chain.

ADR-0018 §1+§4: when the local BGE adapter is unavailable or times out,
the fallback chain advances to Cohere Rerank v3. Network-bound and per-
call billed; daily cost cap (ADR-0015) gates the meter.

API contract (Cohere /v1/rerank):
    POST https://api.cohere.com/v1/rerank
    Authorization: Bearer ${COHERE_API_KEY}
    {
      "model": "rerank-v3.5",
      "query": "...",
      "documents": ["text", ...],
      "top_n": 8
    }
    →
    { "results": [{"index": int, "relevance_score": float}, ...] }

Failure semantics:
- Missing ``api_key`` at construction → ``RerankerNotAvailableError``
  (the chain skips this adapter without a network round-trip).
- HTTP error / timeout → ``RerankerTimeoutError`` so the chain advances
  to the Noop tail.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import httpx
import structlog
from pydantic import BaseModel, ConfigDict

from packages.indexing.errors import RerankerNotAvailableError, RerankerTimeoutError
from packages.indexing.protocols import FusedHit, RerankedHit

COHERE_NAME: str = "cohere-rerank-v3"
DEFAULT_COHERE_API_BASE: str = "https://api.cohere.com"
DEFAULT_COHERE_MODEL: str = "rerank-v3.5"
DEFAULT_COHERE_TIMEOUT_MS: int = 500

_logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CohereRerankerConfig:
    """Connection + model selection for the Cohere Rerank API."""

    api_key: str
    api_base: str = DEFAULT_COHERE_API_BASE
    model: str = DEFAULT_COHERE_MODEL
    timeout_ms: int = DEFAULT_COHERE_TIMEOUT_MS


class _CohereResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    index: int
    relevance_score: float


class _CohereResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    results: list[_CohereResult]


class CohereRerankAdapter:
    """Cohere Rerank v3.x reranker for the fallback chain."""

    name: str = COHERE_NAME

    def __init__(
        self,
        config: CohereRerankerConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not config.api_key:
            msg = "Cohere reranker requires non-empty api_key"
            raise RerankerNotAvailableError(msg)
        self._config = config
        timeout_s = config.timeout_ms / 1000.0
        self._client = client or httpx.AsyncClient(
            base_url=config.api_base.rstrip("/"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.api_key}",
            },
            timeout=httpx.Timeout(timeout_s),
        )

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
        if not candidates:
            return ()

        documents = [hit.chunk.text for hit in candidates]
        payload: dict[str, object] = {
            "model": self._config.model,
            "query": query,
            "documents": documents,
            "top_n": top_k if top_k is not None else len(candidates),
        }

        try:
            response = await self._client.post("/v1/rerank", json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            await _logger.awarning(
                "cohere_reranker.timeout",
                timeout_ms=self._config.timeout_ms,
                n_candidates=len(candidates),
            )
            msg = f"Cohere rerank timed out after {self._config.timeout_ms} ms"
            raise RerankerTimeoutError(msg) from e
        except httpx.HTTPError as e:
            msg = f"Cohere rerank HTTP error: {e!s}"
            raise RerankerTimeoutError(msg) from e

        parsed = _CohereResponse.model_validate(response.json())
        return _convert(candidates, parsed.results)

    async def close(self) -> None:
        await self._client.aclose()


def _convert(
    candidates: Sequence[FusedHit],
    results: list[_CohereResult],
) -> tuple[RerankedHit, ...]:
    """Map Cohere index/score pairs back to RerankedHit tuples."""
    out: list[RerankedHit] = []
    for new_rank, item in enumerate(results, start=1):
        if item.index < 0 or item.index >= len(candidates):
            continue
        hit = candidates[item.index]
        score = max(0.0, float(item.relevance_score))
        out.append(
            RerankedHit(
                chunk=hit.chunk,
                score=score,
                pre_rerank_rank=hit.pre_rerank_rank,
                post_rerank_rank=new_rank,
                sources=hit.sources,
            )
        )
    return tuple(out)
