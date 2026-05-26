"""OpenAI-compatible /v1/rerank reranker adapter.

Works with SiliconFlow (BAAI/bge-reranker-v2-m3), Jina, Cohere /rerank,
and any provider exposing this endpoint shape:

    POST /v1/rerank
    { "model": "...", "query": "...", "documents": [...], "top_n": N }

Returns ranked indices with scores.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict

from packages.embedding._retry import make_retrying
from packages.observability.instrumentation import instrumented
from packages.observability.metrics import EMBEDDING_DURATION_SECONDS


class _RerankResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    index: int
    relevance_score: float


class _RerankResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    results: list[_RerankResult]


@dataclass(frozen=True, slots=True)
class OpenAICompatRerankerConfig:
    """Configuration for the OpenAI-compatible reranker."""

    api_base: str = "https://api.siliconflow.cn/v1"
    api_key: str = ""
    model: str = "BAAI/bge-reranker-v2-m3"
    timeout_s: int = 30
    max_attempts: int = 3
    retry_initial_wait_s: float = 1.5


class OpenAICompatReranker:
    """Reranker that calls /v1/rerank on any compatible endpoint."""

    def __init__(self, config: OpenAICompatRerankerConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.api_base.rstrip("/"),
            headers=self._build_headers(config.api_key),
            timeout=httpx.Timeout(config.timeout_s),
        )

    @staticmethod
    def _build_headers(api_key: str) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @instrumented(
        op_name="openai_compat.rerank",
        component="embedding",
        histogram=EMBEDDING_DURATION_SECONDS,
        histogram_labels={"op": "rerank", "model": "openai_compat"},
    )
    async def rerank(
        self,
        query: str,
        passages: list[str],
        k: int,
    ) -> list[tuple[int, float]]:
        """Return [(original_index, score), ...] sorted by relevance desc."""
        if not passages:
            return []

        payload: dict[str, object] = {
            "model": self._config.model,
            "query": query,
            "documents": passages,
            "top_n": min(k, len(passages)),
        }

        retrying = make_retrying(
            max_attempts=self._config.max_attempts,
            initial_wait=self._config.retry_initial_wait_s,
        )
        response: httpx.Response | None = None

        async for attempt in retrying:
            with attempt:
                response = await self._client.post("/rerank", json=payload)
                response.raise_for_status()

        if response is None:
            msg = "Reranker call returned no response after retries"
            raise RuntimeError(msg)

        parsed = _RerankResponse.model_validate(response.json())
        return [(r.index, r.relevance_score) for r in parsed.results]

    async def close(self) -> None:
        await self._client.aclose()
