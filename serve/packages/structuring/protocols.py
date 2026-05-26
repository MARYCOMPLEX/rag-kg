"""Structuring layer protocol definitions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from packages.core.models import Chunk, Community, Entity, Triple


@runtime_checkable
class EntityExtractor(Protocol):
    """Extract named entities from text chunks."""

    async def extract(self, library_id: str, chunks: list[Chunk]) -> list[Entity]: ...


@runtime_checkable
class RelationExtractor(Protocol):
    """Extract relations (triples) between entities."""

    async def extract(
        self, library_id: str, chunks: list[Chunk], entities: list[Entity]
    ) -> list[Triple]: ...


@runtime_checkable
class EntityLinker(Protocol):
    """Link and disambiguate entities within a library."""

    async def link(self, library_id: str, entities: list[Entity]) -> list[Entity]: ...


@runtime_checkable
class CommunitySummarizer(Protocol):
    """Generate human-readable summaries for KG communities.

    Receives a community and the set of entities and triples that belong
    to it; emits a Community with `summary` + `title` + `representative_entities`
    populated.
    """

    async def summarize(
        self,
        library_id: str,
        community: Community,
        entities: list[Entity],
        triples: list[Triple],
    ) -> Community: ...
