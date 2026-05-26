"""Tests for OpenAICompatReranker."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from packages.embedding.adapters.openai_compat_rerank import (
    OpenAICompatReranker,
    OpenAICompatRerankerConfig,
)


def _fake_response(scores: list[float]) -> httpx.Response:
    body = {
        "results": [
            {"index": i, "relevance_score": s, "document": {"text": f"d{i}"}}
            for i, s in enumerate(scores)
        ]
    }
    return httpx.Response(200, json=body, request=httpx.Request("POST", "/rerank"))


class TestOpenAICompatReranker:
    def test_default_config(self) -> None:
        c = OpenAICompatRerankerConfig()
        assert c.model == "BAAI/bge-reranker-v2-m3"

    def test_headers_with_key(self) -> None:
        h = OpenAICompatReranker._build_headers("sk-x")
        assert h["Authorization"] == "Bearer sk-x"

    def test_headers_no_key(self) -> None:
        h = OpenAICompatReranker._build_headers("")
        assert "Authorization" not in h

    @pytest.mark.asyncio
    async def test_empty_passages(self) -> None:
        r = OpenAICompatReranker(OpenAICompatRerankerConfig())
        assert await r.rerank("q", [], k=5) == []

    @pytest.mark.asyncio
    async def test_returns_indexed_scores(self) -> None:
        r = OpenAICompatReranker(OpenAICompatRerankerConfig(retry_initial_wait_s=0.01))
        r._client = AsyncMock(spec=httpx.AsyncClient)
        r._client.post = AsyncMock(return_value=_fake_response([0.9, 0.5, 0.7]))
        result = await r.rerank("q", ["a", "b", "c"], k=3)
        assert len(result) == 3
        assert result == [(0, 0.9), (1, 0.5), (2, 0.7)]

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self) -> None:
        r = OpenAICompatReranker(
            OpenAICompatRerankerConfig(max_attempts=2, retry_initial_wait_s=0.01)
        )
        r._client = AsyncMock(spec=httpx.AsyncClient)
        r._client.post = AsyncMock(side_effect=[httpx.ReadTimeout("slow"), _fake_response([0.9])])
        result = await r.rerank("q", ["a"], k=1)
        assert result == [(0, 0.9)]
        assert r._client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        r = OpenAICompatReranker(OpenAICompatRerankerConfig())
        r._client = AsyncMock(spec=httpx.AsyncClient)
        await r.close()
        r._client.aclose.assert_called_once()
