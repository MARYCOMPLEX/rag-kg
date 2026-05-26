"""OpenAI-compatible embedding adapter.

Works with any provider exposing the /v1/embeddings endpoint:
OpenAI, Azure OpenAI, vLLM, Ollama, LiteLLM, etc.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict

from packages.observability.instrumentation import instrumented
from packages.observability.metrics import EMBEDDING_DURATION_SECONDS


class _EmbeddingItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    index: int
    embedding: list[float]


class _EmbeddingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data: list[_EmbeddingItem]


@dataclass(frozen=True, slots=True)
class OpenAICompatEmbedderConfig:
    """Configuration for the OpenAI-compatible embedder."""

    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "text-embedding-3-small"
    dim: int = 1536
    batch_size: int = 64
    timeout_s: int = 30


class OpenAICompatEmbedder:
    """Embedder that calls any OpenAI-compatible /v1/embeddings endpoint."""

    def __init__(self, config: OpenAICompatEmbedderConfig) -> None:
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

    @property
    def dim(self) -> int:
        """Return the configured embedding dimension."""
        return self._config.dim

    @instrumented(
        op_name="openai_compat.embed",
        component="embedding",
        histogram=EMBEDDING_DURATION_SECONDS,
        histogram_labels={"op": "embed", "model": "openai_compat"},
    )
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via the OpenAI-compatible /v1/embeddings endpoint.

        Automatically batches requests according to config.batch_size.
        """
        if not texts:
            return []

        all_vectors: list[list[float]] = []
        batch_size = self._config.batch_size

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vectors = await self._embed_batch(batch)
            all_vectors.extend(vectors)

        return all_vectors

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Send a single batch to the embeddings endpoint."""
        payload: dict[str, object] = {
            "input": texts,
            "model": self._config.model,
        }

        response = await self._client.post("/embeddings", json=payload)
        response.raise_for_status()

        parsed = _EmbeddingResponse.model_validate(response.json())
        sorted_items = sorted(parsed.data, key=lambda item: item.index)
        return [item.embedding for item in sorted_items]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
