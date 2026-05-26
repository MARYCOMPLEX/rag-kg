"""Tests for the string-based entity linker."""

from __future__ import annotations

import pytest

from packages.core.models import Entity
from packages.structuring.adapters.string_linker import StringEntityLinker


def _ent(entity_id: str, name: str, aliases: tuple[str, ...] = ()) -> Entity:
    return Entity(
        library_id="test-lib",
        entity_id=entity_id,
        name=name,
        aliases=aliases,
        type="Method",
    )


class TestStringEntityLinker:
    @pytest.mark.asyncio
    async def test_empty_input(self) -> None:
        linker = StringEntityLinker()
        assert await linker.link("test-lib", []) == []

    @pytest.mark.asyncio
    async def test_dedupe_by_entity_id(self) -> None:
        linker = StringEntityLinker()
        ents = [
            _ent("method:graphrag", "GraphRAG", aliases=("Graph-RAG",)),
            _ent("method:graphrag", "GraphRAG", aliases=("graph rag",)),
        ]
        out = await linker.link("test-lib", ents)
        assert len(out) == 1
        merged = out[0]
        assert merged.entity_id == "method:graphrag"
        # Aliases merged from both sources
        assert "Graph-RAG" in merged.aliases
        assert "graph rag" in merged.aliases
        # Name itself excluded from aliases
        assert "GraphRAG" not in merged.aliases

    @pytest.mark.asyncio
    async def test_filters_other_libraries(self) -> None:
        linker = StringEntityLinker()
        outside = Entity(
            library_id="other-lib",
            entity_id="method:other",
            name="Other",
            type="Method",
        )
        ents = [_ent("method:a", "A"), outside]
        out = await linker.link("test-lib", ents)
        assert len(out) == 1
        assert out[0].entity_id == "method:a"
