"""Tests for CachedEmbedder — cost-critical caching layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.embedding.adapters.cached import CachedEmbedder


class FakeEmbedder:
    def __init__(self, dim: int = 4) -> None:
        self._dim = dim
        self.call_count = 0
        self.last_inputs: list[str] = []

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        self.last_inputs = list(texts)
        return [[float(len(t)), 0.0, 0.0, 0.0] for t in texts]


@pytest.fixture
def cache_path(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "embeddings.sqlite"


class TestCachedEmbedder:
    @pytest.mark.asyncio
    async def test_dim_passthrough(self, cache_path: Path) -> None:
        inner = FakeEmbedder(dim=128)
        cached = CachedEmbedder(inner=inner, cache_path=cache_path, model_id="m")
        assert cached.dim == 128

    @pytest.mark.asyncio
    async def test_first_call_invokes_inner(self, cache_path: Path) -> None:
        inner = FakeEmbedder()
        cached = CachedEmbedder(inner=inner, cache_path=cache_path, model_id="m")
        result = await cached.embed(["hello"])
        assert len(result) == 1
        assert inner.call_count == 1

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self, cache_path: Path) -> None:
        inner = FakeEmbedder()
        cached = CachedEmbedder(inner=inner, cache_path=cache_path, model_id="m")
        await cached.embed(["hello"])
        await cached.embed(["hello"])
        assert inner.call_count == 1

    @pytest.mark.asyncio
    async def test_partial_cache_hit_only_embeds_missing(self, cache_path: Path) -> None:
        inner = FakeEmbedder()
        cached = CachedEmbedder(inner=inner, cache_path=cache_path, model_id="m")
        await cached.embed(["a", "b"])
        # Now request a, b, c — only c should hit the inner embedder
        inner.call_count = 0
        result = await cached.embed(["a", "b", "c"])
        assert inner.call_count == 1
        assert inner.last_inputs == ["c"]
        assert len(result) == 3
        # Order preserved
        assert result[0][0] == 1.0  # len("a")
        assert result[1][0] == 1.0  # len("b")
        assert result[2][0] == 1.0  # len("c")

    @pytest.mark.asyncio
    async def test_different_model_id_invalidates_cache(self, cache_path: Path) -> None:
        inner = FakeEmbedder()
        c1 = CachedEmbedder(inner=inner, cache_path=cache_path, model_id="model-a")
        await c1.embed(["hello"])
        c2 = CachedEmbedder(inner=inner, cache_path=cache_path, model_id="model-b")
        await c2.embed(["hello"])
        assert inner.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_texts_no_inner_call(self, cache_path: Path) -> None:
        inner = FakeEmbedder()
        cached = CachedEmbedder(inner=inner, cache_path=cache_path, model_id="m")
        result = await cached.embed([])
        assert result == []
        assert inner.call_count == 0

    @pytest.mark.asyncio
    async def test_cache_persists_across_instances(self, cache_path: Path) -> None:
        inner1 = FakeEmbedder()
        c1 = CachedEmbedder(inner=inner1, cache_path=cache_path, model_id="m")
        await c1.embed(["hello"])

        inner2 = FakeEmbedder()
        c2 = CachedEmbedder(inner=inner2, cache_path=cache_path, model_id="m")
        await c2.embed(["hello"])
        assert inner2.call_count == 0

    @pytest.mark.asyncio
    async def test_cache_stats(self, cache_path: Path) -> None:
        inner = FakeEmbedder()
        cached = CachedEmbedder(inner=inner, cache_path=cache_path, model_id="m")
        await cached.embed(["a", "b", "c"])
        count, size = await cached.cache_stats()
        assert count == 3
        assert size > 0
