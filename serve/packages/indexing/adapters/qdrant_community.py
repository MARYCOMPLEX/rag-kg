"""Qdrant-backed CommunityIndex adapter.

One collection per library: communities_<library_id>.
Stores Community summaries + their embedding vectors so that downstream
global-search workflows can both retrieve by similarity and enumerate the
full community catalogue (e.g. by hierarchy level).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from packages.core.models import Community
from packages.observability.instrumentation import instrumented
from packages.observability.metrics import RETRIEVAL_DURATION_SECONDS

type Vector = list[float]

# Scroll batch size — large enough for typical libraries (hundreds-to-low-thousands
# of communities), small enough to avoid huge response payloads.
_SCROLL_BATCH_SIZE = 256


@dataclass(frozen=True, slots=True)
class QdrantCommunityIndexConfig:
    """Qdrant connection + indexing tunables for community summaries."""

    url: str = "http://localhost:6333"
    dim: int = 1536
    distance: str = "Cosine"  # Cosine | Euclid | Dot


def _collection_name(library_id: str) -> str:
    return f"communities_{library_id.replace('-', '_')}"


def _community_to_point_id(library_id: str, community_id: str) -> str:
    """Qdrant requires UUID or int IDs — derive a deterministic UUID."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"community::{library_id}::{community_id}"))


class QdrantCommunityIndex:
    """CommunityIndex adapter backed by Qdrant.

    Each library gets its own collection so purge is a single API call
    and per-library tuning is isolated, matching ``QdrantVectorIndex``.
    """

    def __init__(self, config: QdrantCommunityIndexConfig) -> None:
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
        op_name="community.upsert",
        component="community",
        histogram=RETRIEVAL_DURATION_SECONDS,
        histogram_labels={"component": "community", "op": "upsert"},
        label_from_arg={"library_id": "library_id"},
    )
    async def upsert(
        self,
        library_id: str,
        items: list[tuple[Community, Vector]],
    ) -> None:
        if not items:
            return
        name = _collection_name(library_id)
        points = [
            qmodels.PointStruct(
                id=_community_to_point_id(library_id, community.community_id),
                vector=vector,
                payload={
                    "library_id": community.library_id,
                    "community_id": community.community_id,
                    "level": community.level,
                    "title": community.title,
                    "summary": community.summary,
                    "summary_model": community.summary_model,
                    "member_entity_ids": list(community.member_entity_ids),
                    "representative_entities": list(community.representative_entities),
                },
            )
            for community, vector in items
        ]
        await self._client.upsert(collection_name=name, points=points)

    @instrumented(
        op_name="community.search",
        component="community",
        histogram=RETRIEVAL_DURATION_SECONDS,
        histogram_labels={"component": "community", "op": "search"},
        label_from_arg={"library_id": "library_id"},
    )
    async def search(
        self,
        library_id: str,
        vector: Vector,
        k: int,
    ) -> list[tuple[Community, float]]:
        name = _collection_name(library_id)
        if not await self._client.collection_exists(name):
            return []
        results = await self._client.query_points(
            collection_name=name,
            query=vector,
            limit=k,
            with_payload=True,
        )
        out: list[tuple[Community, float]] = []
        for point in results.points:
            community = _payload_to_community(point.payload)
            if community is None:
                continue
            out.append((community, float(point.score)))
        return out

    async def list_all(
        self,
        library_id: str,
        *,
        level: int | None = None,
    ) -> list[Community]:
        name = _collection_name(library_id)
        if not await self._client.collection_exists(name):
            return []
        qfilter = _level_filter(level) if level is not None else None
        out: list[Community] = []
        # Qdrant's scroll offset is an opaque continuation token (int | str | UUID
        # | grpc PointId). The grpc variant isn't easily importable, so we treat
        # it as Any — we only ever pass it back to scroll() unchanged.
        next_offset: Any = None
        while True:
            records, next_offset = await self._client.scroll(
                collection_name=name,
                scroll_filter=qfilter,
                limit=_SCROLL_BATCH_SIZE,
                offset=next_offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                community = _payload_to_community(record.payload)
                if community is not None:
                    out.append(community)
            if next_offset is None:
                break
        return out

    async def close(self) -> None:
        await self._client.close()


def _level_filter(level: int) -> qmodels.Filter:
    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="level",
                match=qmodels.MatchValue(value=level),
            )
        ]
    )


def _payload_to_community(payload: dict[str, object] | None) -> Community | None:
    if not payload:
        return None
    try:
        return Community(
            library_id=str(payload["library_id"]),
            community_id=str(payload["community_id"]),
            level=int(payload["level"]),  # type: ignore[arg-type]
            title=str(payload.get("title", "")),
            summary=str(payload.get("summary", "")),
            summary_model=str(payload.get("summary_model", "")),
            member_entity_ids=_as_str_tuple(payload.get("member_entity_ids")),
            representative_entities=_as_str_tuple(payload.get("representative_entities")),
        )
    except (KeyError, ValueError, TypeError):
        return None


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)  # type: ignore[arg-type]
    return ()
