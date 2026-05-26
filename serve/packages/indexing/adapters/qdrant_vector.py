"""Qdrant-backed VectorIndex adapter.

One collection per library: chunks_<library_id>.
Library purge = delete collection. Library init = create collection
with the configured embedding dimension.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from packages.core.models import Chunk
from packages.observability.instrumentation import instrumented
from packages.observability.metrics import RETRIEVAL_DURATION_SECONDS

type Vector = list[float]


@dataclass(frozen=True, slots=True)
class QdrantVectorIndexConfig:
    """Qdrant connection + indexing tunables."""

    url: str = "http://localhost:6333"
    dim: int = 1536
    distance: str = "Cosine"  # Cosine | Euclid | Dot


def _collection_name(library_id: str) -> str:
    return f"chunks_{library_id.replace('-', '_')}"


def _chunk_to_point_id(chunk_id: str) -> str:
    """Qdrant requires UUID or int IDs — derive a deterministic UUID from chunk_id."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"chunk::{chunk_id}"))


class QdrantVectorIndex:
    """VectorIndex adapter backed by Qdrant.

    Each library gets its own collection so purge is a single API call
    and per-library ANN tuning is isolated.
    """

    def __init__(self, config: QdrantVectorIndexConfig) -> None:
        self._config = config
        # check_compatibility=False — we accept the client/server version skew
        # (server is the docker image we control; client floats with deps).
        self._client = AsyncQdrantClient(url=config.url, check_compatibility=False)

    async def init_library(self, library_id: str) -> None:
        name = _collection_name(library_id)
        if await self._client.collection_exists(name):
            return
        await self._client.create_collection(
            collection_name=name,
            vectors_config=qmodels.VectorParams(
                size=self._config.dim,
                distance=qmodels.Distance(self._config.distance),
            ),
        )

    async def purge_library(self, library_id: str) -> None:
        name = _collection_name(library_id)
        if await self._client.collection_exists(name):
            await self._client.delete_collection(collection_name=name)

    @instrumented(
        op_name="qdrant.upsert",
        component="qdrant",
        histogram=RETRIEVAL_DURATION_SECONDS,
        histogram_labels={"component": "qdrant", "op": "upsert"},
        label_from_arg={"library_id": "library_id"},
    )
    async def upsert(
        self,
        library_id: str,
        items: list[tuple[Chunk, Vector]],
    ) -> None:
        if not items:
            return
        name = _collection_name(library_id)
        points = [
            qmodels.PointStruct(
                id=_chunk_to_point_id(chunk.chunk_id),
                vector=vector,
                payload={
                    "library_id": chunk.library_id,
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "text": chunk.text,
                    "page": chunk.page,
                    "section": chunk.section,
                    "kind": chunk.kind,
                    "offset_start": chunk.offset[0],
                    "offset_end": chunk.offset[1],
                },
            )
            for chunk, vector in items
        ]
        await self._client.upsert(collection_name=name, points=points)

    @instrumented(
        op_name="qdrant.search",
        component="qdrant",
        histogram=RETRIEVAL_DURATION_SECONDS,
        histogram_labels={"component": "qdrant", "op": "search"},
        label_from_arg={"library_id": "library_id"},
    )
    async def search(
        self,
        library_id: str,
        vector: Vector,
        k: int,
        *,
        filter: Mapping[str, object] | None = None,
    ) -> list[tuple[Chunk, float]]:
        name = _collection_name(library_id)
        if not await self._client.collection_exists(name):
            return []
        qfilter = self._build_filter(filter) if filter else None
        results = await self._client.query_points(
            collection_name=name,
            query=vector,
            limit=k,
            query_filter=qfilter,
            with_payload=True,
        )
        out: list[tuple[Chunk, float]] = []
        for point in results.points:
            payload = point.payload or {}
            try:
                chunk = Chunk(
                    library_id=str(payload["library_id"]),
                    chunk_id=str(payload["chunk_id"]),
                    doc_id=str(payload["doc_id"]),
                    text=str(payload["text"]),
                    page=_as_optional_int(payload.get("page")),
                    section=_as_optional_str(payload.get("section")),
                    kind=str(payload.get("kind", "text")),  # type: ignore[arg-type]
                    offset=(
                        int(payload.get("offset_start", 0) or 0),
                        int(payload.get("offset_end", 0) or 0),
                    ),
                )
            except (KeyError, ValueError, TypeError):
                continue
            out.append((chunk, float(point.score)))
        return out

    @staticmethod
    def _build_filter(filt: Mapping[str, object]) -> qmodels.Filter:
        conditions: list[qmodels.FieldCondition] = []
        for key, value in filt.items():
            conditions.append(
                qmodels.FieldCondition(
                    key=key,
                    match=qmodels.MatchValue(value=value),  # type: ignore[arg-type]
                )
            )
        return qmodels.Filter(must=conditions)  # type: ignore[arg-type]

    async def close(self) -> None:
        await self._client.close()


def _as_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value) if value != "" else None
