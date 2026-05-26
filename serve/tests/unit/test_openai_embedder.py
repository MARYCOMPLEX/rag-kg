"""Tests for the OpenAI-compatible embedding adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from packages.embedding.adapters.openai_compat import (
    OpenAICompatEmbedder,
    OpenAICompatEmbedderConfig,
)


def _fake_embedding_response(vectors: list[list[float]]) -> httpx.Response:
    body = {
        "object": "list",
        "data": [
            {"object": "embedding", "index": i, "embedding": vec} for i, vec in enumerate(vectors)
        ],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    }
    return httpx.Response(200, json=body, request=httpx.Request("POST", "/embeddings"))


class TestOpenAICompatEmbedderConfig:
    def test_defaults(self) -> None:
        config = OpenAICompatEmbedderConfig()
        assert config.api_base == "https://api.openai.com/v1"
        assert config.model == "text-embedding-3-small"
        assert config.dim == 1536

    def test_custom_values(self) -> None:
        config = OpenAICompatEmbedderConfig(
            api_base="http://localhost:8080/v1",
            api_key="test-key",
            model="bge-m3",
            dim=1024,
            batch_size=32,
        )
        assert config.api_base == "http://localhost:8080/v1"
        assert config.dim == 1024

    def test_is_frozen(self) -> None:
        config = OpenAICompatEmbedderConfig()
        with pytest.raises(AttributeError):
            config.model = "other"  # type: ignore[misc]


class TestOpenAICompatEmbedder:
    def test_dim_property(self) -> None:
        config = OpenAICompatEmbedderConfig(dim=768)
        embedder = OpenAICompatEmbedder(config)
        assert embedder.dim == 768

    @pytest.mark.asyncio
    async def test_embed_empty_list(self) -> None:
        config = OpenAICompatEmbedderConfig()
        embedder = OpenAICompatEmbedder(config)
        result = await embedder.embed([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_single_text(self) -> None:
        config = OpenAICompatEmbedderConfig(dim=3)
        embedder = OpenAICompatEmbedder(config)

        fake_resp = _fake_embedding_response([[0.1, 0.2, 0.3]])
        embedder._client = AsyncMock(spec=httpx.AsyncClient)
        embedder._client.post = AsyncMock(return_value=fake_resp)

        result = await embedder.embed(["hello world"])

        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]
        embedder._client.post.assert_called_once_with(
            "/embeddings",
            json={"input": ["hello world"], "model": "text-embedding-3-small"},
        )

    @pytest.mark.asyncio
    async def test_embed_multiple_texts(self) -> None:
        config = OpenAICompatEmbedderConfig(dim=2)
        embedder = OpenAICompatEmbedder(config)

        fake_resp = _fake_embedding_response([[1.0, 0.0], [0.0, 1.0]])
        embedder._client = AsyncMock(spec=httpx.AsyncClient)
        embedder._client.post = AsyncMock(return_value=fake_resp)

        result = await embedder.embed(["text a", "text b"])

        assert len(result) == 2
        assert result[0] == [1.0, 0.0]
        assert result[1] == [0.0, 1.0]

    @pytest.mark.asyncio
    async def test_embed_batching(self) -> None:
        config = OpenAICompatEmbedderConfig(dim=2, batch_size=2)
        embedder = OpenAICompatEmbedder(config)

        batch1_resp = _fake_embedding_response([[1.0, 0.0], [0.0, 1.0]])
        batch2_resp = _fake_embedding_response([[0.5, 0.5]])

        embedder._client = AsyncMock(spec=httpx.AsyncClient)
        embedder._client.post = AsyncMock(side_effect=[batch1_resp, batch2_resp])

        result = await embedder.embed(["a", "b", "c"])

        assert len(result) == 3
        assert embedder._client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_embed_handles_unordered_response(self) -> None:
        config = OpenAICompatEmbedderConfig(dim=2)
        embedder = OpenAICompatEmbedder(config)

        body = {
            "object": "list",
            "data": [
                {"object": "embedding", "index": 1, "embedding": [0.0, 1.0]},
                {"object": "embedding", "index": 0, "embedding": [1.0, 0.0]},
            ],
            "model": "test",
            "usage": {"prompt_tokens": 10, "total_tokens": 10},
        }
        fake_resp = httpx.Response(200, json=body, request=httpx.Request("POST", "/embeddings"))
        embedder._client = AsyncMock(spec=httpx.AsyncClient)
        embedder._client.post = AsyncMock(return_value=fake_resp)

        result = await embedder.embed(["first", "second"])

        assert result[0] == [1.0, 0.0]
        assert result[1] == [0.0, 1.0]

    def test_headers_with_api_key(self) -> None:
        headers = OpenAICompatEmbedder._build_headers("sk-test")
        assert headers["Authorization"] == "Bearer sk-test"

    def test_headers_without_api_key(self) -> None:
        headers = OpenAICompatEmbedder._build_headers("")
        assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        config = OpenAICompatEmbedderConfig()
        embedder = OpenAICompatEmbedder(config)
        embedder._client = AsyncMock(spec=httpx.AsyncClient)
        await embedder.close()
        embedder._client.aclose.assert_called_once()
