"""Embedding and reranker protocol definitions.

These are stateless compute — no library_id needed.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

type Vector = list[float]


@runtime_checkable
class Embedder(Protocol):
    """Text-to-vector embedding service."""

    async def embed(self, texts: list[str]) -> list[Vector]: ...

    @property
    def dim(self) -> int: ...


@runtime_checkable
class Reranker(Protocol):
    """Rerank candidate passages given a query."""

    async def rerank(
        self,
        query: str,
        passages: list[str],
        k: int,
    ) -> list[tuple[int, float]]: ...
