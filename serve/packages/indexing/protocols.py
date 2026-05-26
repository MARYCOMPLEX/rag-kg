"""Indexing layer protocol definitions.

All data-touching methods take library_id as first positional argument.
Each index adapter must implement init_library / purge_library for
physical partition lifecycle.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from packages.core.models import Chunk, Community, Entity, Triple

type Vector = list[float]
type RetrievalSource = Literal["vector", "graph", "bm25", "community"]


@runtime_checkable
class VectorIndex(Protocol):
    """Dense vector index scoped by library."""

    async def init_library(self, library_id: str) -> None: ...
    async def purge_library(self, library_id: str) -> None: ...

    async def upsert(
        self,
        library_id: str,
        items: list[tuple[Chunk, Vector]],
    ) -> None: ...

    async def search(
        self,
        library_id: str,
        vector: Vector,
        k: int,
        *,
        filter: Mapping[str, object] | None = None,
    ) -> list[tuple[Chunk, float]]: ...


@runtime_checkable
class GraphIndex(Protocol):
    """Knowledge graph index scoped by library."""

    async def init_library(self, library_id: str) -> None: ...
    async def purge_library(self, library_id: str) -> None: ...

    async def upsert_entities(self, library_id: str, entities: list[Entity]) -> None: ...
    async def upsert_triples(self, library_id: str, triples: list[Triple]) -> None: ...

    async def get_neighbors(
        self,
        library_id: str,
        entity_id: str,
        depth: int = 1,
    ) -> list[Triple]: ...


@runtime_checkable
class BM25Index(Protocol):
    """Sparse keyword index scoped by library."""

    async def init_library(self, library_id: str) -> None: ...
    async def purge_library(self, library_id: str) -> None: ...

    async def upsert(self, library_id: str, chunks: list[Chunk]) -> None: ...

    async def search(
        self,
        library_id: str,
        query: str,
        k: int,
    ) -> list[tuple[Chunk, float]]: ...


@runtime_checkable
class RetrievalCoordinator(Protocol):
    """Orchestrates multi-index retrieval within a single library."""

    async def search(
        self,
        library_id: str,
        query: str,
        k: int = 10,
    ) -> list[tuple[Chunk, float]]: ...


@runtime_checkable
class CommunityDetector(Protocol):
    """Detects communities (densely-connected subgraphs) in a library KG."""

    async def detect(
        self,
        library_id: str,
        edges: list[tuple[str, str, float]],
    ) -> list[Community]:
        """Return communities (without summaries) from a list of weighted edges.

        Each tuple is (head_entity_id, tail_entity_id, weight).
        """
        ...


# ----------------------------------------------------------------------
# M7: Hybrid fusion + reranker (ADR-0017 + ADR-0018)
# ----------------------------------------------------------------------


class FusedHit(BaseModel):
    """One candidate after RRF fusion across (vector, graph, bm25) runs.

    `pre_rerank_rank` is the post-RRF position (1-based); `score` is the
    fused score before reranking.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk: Chunk
    score: float = Field(ge=0.0)
    pre_rerank_rank: int = Field(ge=1)
    sources: tuple[RetrievalSource, ...] = ()


class RerankedHit(BaseModel):
    """A `FusedHit` after reranking, carrying both pre/post ranks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk: Chunk
    score: float = Field(ge=0.0)
    pre_rerank_rank: int = Field(ge=1)
    post_rerank_rank: int = Field(ge=1)
    sources: tuple[RetrievalSource, ...] = ()


@runtime_checkable
class Reranker(Protocol):
    """Cross-encoder reranker (ADR-0018).

    Library-agnostic: pure scoring service. Implementations:
    - `BGERerankerV2Adapter` (local, primary)
    - `CohereRerankAdapter` (API fallback)
    - `NoopReranker` (passthrough, used when disabled)
    """

    name: str
    timeout_ms: int

    async def rerank(
        self,
        query: str,
        candidates: Sequence[FusedHit],
        *,
        top_k: int | None = None,
    ) -> tuple[RerankedHit, ...]: ...


@runtime_checkable
class CommunityIndex(Protocol):
    """Per-library store for community summaries (vector + metadata)."""

    async def init_library(self, library_id: str) -> None: ...
    async def purge_library(self, library_id: str) -> None: ...

    async def upsert(
        self,
        library_id: str,
        items: list[tuple[Community, Vector]],
    ) -> None: ...

    async def search(
        self,
        library_id: str,
        vector: Vector,
        k: int,
    ) -> list[tuple[Community, float]]: ...

    async def list_all(
        self,
        library_id: str,
        *,
        level: int | None = None,
    ) -> list[Community]: ...
