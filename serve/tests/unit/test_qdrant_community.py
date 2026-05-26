"""Tests for the Qdrant-backed CommunityIndex adapter.

Tests use AsyncMock for AsyncQdrantClient — no running Qdrant required.
"""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from packages.core.models import Community
from packages.indexing.adapters.qdrant_community import (
    QdrantCommunityIndex,
    QdrantCommunityIndexConfig,
    _collection_name,
    _community_to_point_id,
)


def _make_community(
    *,
    community_id: str = "c1",
    library_id: str = "test-lib",
    level: int = 0,
    title: str = "Cluster A",
    summary: str = "Summary of cluster A.",
    summary_model: str = "gpt-4",
    member_entity_ids: tuple[str, ...] = ("e1", "e2"),
    representative_entities: tuple[str, ...] = ("e1",),
) -> Community:
    return Community(
        library_id=library_id,
        community_id=community_id,
        level=level,
        title=title,
        summary=summary,
        summary_model=summary_model,
        member_entity_ids=member_entity_ids,
        representative_entities=representative_entities,
    )


def _make_index() -> QdrantCommunityIndex:
    config = QdrantCommunityIndexConfig(url="http://localhost:6333", dim=3)
    index = QdrantCommunityIndex(config)
    index._client = AsyncMock()  # type: ignore[assignment]
    return index


class TestCollectionName:
    def test_replaces_hyphens_with_underscores(self) -> None:
        assert _collection_name("my-library-001") == "communities_my_library_001"

    def test_no_hyphens(self) -> None:
        assert _collection_name("alpha") == "communities_alpha"

    def test_distinct_from_chunks_prefix(self) -> None:
        # Sanity: must not collide with QdrantVectorIndex's `chunks_` prefix.
        assert _collection_name("foo").startswith("communities_")


class TestPointIdDerivation:
    def test_is_deterministic(self) -> None:
        a = _community_to_point_id("lib", "c1")
        b = _community_to_point_id("lib", "c1")
        assert a == b

    def test_is_uuid(self) -> None:
        pid = _community_to_point_id("lib", "c1")
        # Will raise if not a valid UUID
        uuid.UUID(pid)

    def test_differs_between_libraries(self) -> None:
        a = _community_to_point_id("lib1", "c1")
        b = _community_to_point_id("lib2", "c1")
        assert a != b

    def test_differs_between_communities(self) -> None:
        a = _community_to_point_id("lib", "c1")
        b = _community_to_point_id("lib", "c2")
        assert a != b


class TestConfig:
    def test_defaults(self) -> None:
        config = QdrantCommunityIndexConfig()
        assert config.url == "http://localhost:6333"
        assert config.dim == 1536
        assert config.distance == "Cosine"

    def test_is_frozen(self) -> None:
        config = QdrantCommunityIndexConfig()
        with pytest.raises(AttributeError):
            config.dim = 2048  # type: ignore[misc]


class TestInitLibrary:
    @pytest.mark.asyncio
    async def test_creates_collection_when_missing(self) -> None:
        index = _make_index()
        index._client.collection_exists = AsyncMock(return_value=False)
        index._client.create_collection = AsyncMock()

        await index.init_library("lib-1")

        index._client.create_collection.assert_called_once()
        kwargs = index._client.create_collection.call_args.kwargs
        assert kwargs["collection_name"] == "communities_lib_1"

    @pytest.mark.asyncio
    async def test_skips_when_collection_exists(self) -> None:
        index = _make_index()
        index._client.collection_exists = AsyncMock(return_value=True)
        index._client.create_collection = AsyncMock()

        await index.init_library("lib-1")

        index._client.create_collection.assert_not_called()


class TestPurgeLibrary:
    @pytest.mark.asyncio
    async def test_deletes_when_collection_exists(self) -> None:
        index = _make_index()
        index._client.collection_exists = AsyncMock(return_value=True)
        index._client.delete_collection = AsyncMock()

        await index.purge_library("lib-1")

        index._client.delete_collection.assert_called_once_with(collection_name="communities_lib_1")

    @pytest.mark.asyncio
    async def test_noop_when_collection_missing(self) -> None:
        index = _make_index()
        index._client.collection_exists = AsyncMock(return_value=False)
        index._client.delete_collection = AsyncMock()

        await index.purge_library("lib-1")

        index._client.delete_collection.assert_not_called()


class TestUpsert:
    @pytest.mark.asyncio
    async def test_empty_items_is_noop(self) -> None:
        index = _make_index()
        index._client.upsert = AsyncMock()

        await index.upsert("lib-1", [])

        index._client.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_builds_correct_point_struct_payload(self) -> None:
        index = _make_index()
        index._client.upsert = AsyncMock()

        community = _make_community(
            community_id="c1",
            library_id="test-lib",
            level=2,
            title="Methods",
            summary="A cluster of methods.",
            summary_model="gpt-4o",
            member_entity_ids=("e1", "e2", "e3"),
            representative_entities=("e1",),
        )
        vector = [0.1, 0.2, 0.3]

        await index.upsert("test-lib", [(community, vector)])

        index._client.upsert.assert_called_once()
        kwargs = index._client.upsert.call_args.kwargs
        assert kwargs["collection_name"] == "communities_test_lib"
        points = kwargs["points"]
        assert len(points) == 1

        point = points[0]
        assert point.vector == vector
        assert point.id == _community_to_point_id("test-lib", "c1")

        payload = point.payload
        assert payload["library_id"] == "test-lib"
        assert payload["community_id"] == "c1"
        assert payload["level"] == 2
        assert payload["title"] == "Methods"
        assert payload["summary"] == "A cluster of methods."
        assert payload["summary_model"] == "gpt-4o"
        assert payload["member_entity_ids"] == ["e1", "e2", "e3"]
        assert payload["representative_entities"] == ["e1"]


class TestSearch:
    @pytest.mark.asyncio
    async def test_returns_empty_when_collection_missing(self) -> None:
        index = _make_index()
        index._client.collection_exists = AsyncMock(return_value=False)

        result = await index.search("lib-1", [0.1, 0.2, 0.3], k=5)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_communities_with_scores(self) -> None:
        index = _make_index()
        index._client.collection_exists = AsyncMock(return_value=True)

        # Build fake query_points response: simulate Qdrant returning 2 points.
        point_a: Any = type(
            "P",
            (),
            {
                "score": 0.95,
                "payload": {
                    "library_id": "test-lib",
                    "community_id": "c1",
                    "level": 0,
                    "title": "A",
                    "summary": "summary A",
                    "summary_model": "gpt-4",
                    "member_entity_ids": ["e1", "e2"],
                    "representative_entities": ["e1"],
                },
            },
        )()
        point_b: Any = type(
            "P",
            (),
            {
                "score": 0.80,
                "payload": {
                    "library_id": "test-lib",
                    "community_id": "c2",
                    "level": 1,
                    "title": "B",
                    "summary": "summary B",
                    "summary_model": "gpt-4",
                    "member_entity_ids": ["e3"],
                    "representative_entities": ["e3"],
                },
            },
        )()
        response: Any = type("R", (), {"points": [point_a, point_b]})()
        index._client.query_points = AsyncMock(return_value=response)

        result = await index.search("test-lib", [0.0, 1.0, 0.0], k=2)

        assert len(result) == 2
        comm_a, score_a = result[0]
        comm_b, score_b = result[1]
        assert comm_a.community_id == "c1"
        assert score_a == pytest.approx(0.95)
        assert comm_b.community_id == "c2"
        assert score_b == pytest.approx(0.80)
        # Ordering preserved (Qdrant returns sorted by score descending).
        assert score_a > score_b

    @pytest.mark.asyncio
    async def test_skips_invalid_payloads(self) -> None:
        index = _make_index()
        index._client.collection_exists = AsyncMock(return_value=True)

        good: Any = type(
            "P",
            (),
            {
                "score": 0.9,
                "payload": {
                    "library_id": "test-lib",
                    "community_id": "c1",
                    "level": 0,
                    "title": "A",
                    "summary": "s",
                    "summary_model": "m",
                    "member_entity_ids": [],
                    "representative_entities": [],
                },
            },
        )()
        bad: Any = type("P", (), {"score": 0.8, "payload": None})()
        response: Any = type("R", (), {"points": [good, bad]})()
        index._client.query_points = AsyncMock(return_value=response)

        result = await index.search("test-lib", [0.0, 1.0, 0.0], k=10)

        assert len(result) == 1
        assert result[0][0].community_id == "c1"


class TestListAll:
    @pytest.mark.asyncio
    async def test_returns_empty_when_collection_missing(self) -> None:
        index = _make_index()
        index._client.collection_exists = AsyncMock(return_value=False)

        result = await index.list_all("lib-1")

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_all_records_across_pages(self) -> None:
        index = _make_index()
        index._client.collection_exists = AsyncMock(return_value=True)

        rec1: Any = type(
            "R",
            (),
            {
                "payload": {
                    "library_id": "test-lib",
                    "community_id": "c1",
                    "level": 0,
                    "title": "A",
                    "summary": "s",
                    "summary_model": "m",
                    "member_entity_ids": ["e1"],
                    "representative_entities": ["e1"],
                }
            },
        )()
        rec2: Any = type(
            "R",
            (),
            {
                "payload": {
                    "library_id": "test-lib",
                    "community_id": "c2",
                    "level": 1,
                    "title": "B",
                    "summary": "s",
                    "summary_model": "m",
                    "member_entity_ids": ["e2"],
                    "representative_entities": ["e2"],
                }
            },
        )()
        # Simulate pagination: first call returns rec1 + offset, second returns rec2 + None.
        index._client.scroll = AsyncMock(
            side_effect=[
                ([rec1], "next-offset"),
                ([rec2], None),
            ]
        )

        result = await index.list_all("test-lib")

        assert len(result) == 2
        assert {c.community_id for c in result} == {"c1", "c2"}
        assert index._client.scroll.call_count == 2

    @pytest.mark.asyncio
    async def test_passes_level_filter_when_provided(self) -> None:
        index = _make_index()
        index._client.collection_exists = AsyncMock(return_value=True)
        index._client.scroll = AsyncMock(return_value=([], None))

        await index.list_all("test-lib", level=2)

        assert index._client.scroll.call_count == 1
        kwargs = index._client.scroll.call_args.kwargs
        assert kwargs["scroll_filter"] is not None
        # Filter must constrain on level == 2
        scroll_filter = kwargs["scroll_filter"]
        conditions = scroll_filter.must
        assert conditions is not None
        assert len(conditions) == 1
        assert conditions[0].key == "level"
        assert conditions[0].match.value == 2

    @pytest.mark.asyncio
    async def test_no_filter_when_level_none(self) -> None:
        index = _make_index()
        index._client.collection_exists = AsyncMock(return_value=True)
        index._client.scroll = AsyncMock(return_value=([], None))

        await index.list_all("test-lib", level=None)

        kwargs = index._client.scroll.call_args.kwargs
        assert kwargs["scroll_filter"] is None


class TestClose:
    @pytest.mark.asyncio
    async def test_close_calls_client_close(self) -> None:
        index = _make_index()
        index._client.close = AsyncMock()

        await index.close()

        index._client.close.assert_called_once()
