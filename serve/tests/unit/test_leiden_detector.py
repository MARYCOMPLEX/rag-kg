"""Tests for the Louvain/Leiden hierarchical community detector."""

from __future__ import annotations

import pytest

from packages.indexing.adapters.community_leiden import (
    LeidenCommunityDetector,
    LeidenCommunityDetectorConfig,
)


def _clique_edges(prefix: str, size: int) -> list[tuple[str, str, float]]:
    nodes = [f"{prefix}{i}" for i in range(size)]
    edges: list[tuple[str, str, float]] = []
    for i in range(size):
        for j in range(i + 1, size):
            edges.append((nodes[i], nodes[j], 1.0))
    return edges


def _three_cliques_with_bridges() -> list[tuple[str, str, float]]:
    """3 cliques of 5 nodes each, joined by single weak bridge edges."""
    edges: list[tuple[str, str, float]] = []
    edges.extend(_clique_edges("a", 5))
    edges.extend(_clique_edges("b", 5))
    edges.extend(_clique_edges("c", 5))
    # Weak bridges so Louvain still keeps the cliques apart
    edges.append(("a0", "b0", 0.05))
    edges.append(("b0", "c0", 0.05))
    return edges


class TestLeidenCommunityDetector:
    @pytest.mark.asyncio
    async def test_empty_edges_returns_empty(self) -> None:
        detector = LeidenCommunityDetector(LeidenCommunityDetectorConfig())
        assert await detector.detect("test-lib", []) == []

    @pytest.mark.asyncio
    async def test_three_cliques_yield_three_level0_communities(self) -> None:
        detector = LeidenCommunityDetector(
            LeidenCommunityDetectorConfig(min_community_size=3, max_levels=1)
        )
        edges = _three_cliques_with_bridges()

        communities = await detector.detect("test-lib", edges)
        level0 = [c for c in communities if c.level == 0]

        assert len(level0) == 3
        assert all(c.library_id == "test-lib" for c in level0)
        # Each clique's nodes co-locate
        for prefix in ("a", "b", "c"):
            owner = next(
                c for c in level0 if any(m.startswith(prefix) for m in c.member_entity_ids)
            )
            assert {m for m in owner.member_entity_ids if m.startswith(prefix)} == {
                f"{prefix}{i}" for i in range(5)
            }
        # community_id format c{level}:{idx}
        assert all(c.community_id.startswith("c0:") for c in level0)

    @pytest.mark.asyncio
    async def test_min_community_size_drops_small_clusters(self) -> None:
        # A triangle (3 nodes) plus an isolated 2-node component
        edges: list[tuple[str, str, float]] = [
            ("x0", "x1", 1.0),
            ("x1", "x2", 1.0),
            ("x0", "x2", 1.0),
            ("y0", "y1", 1.0),  # tiny 2-node community — should be filtered
        ]
        detector = LeidenCommunityDetector(
            LeidenCommunityDetectorConfig(min_community_size=3, max_levels=1)
        )

        communities = await detector.detect("test-lib", edges)

        # Only the triangle survives
        assert len(communities) == 1
        assert set(communities[0].member_entity_ids) == {"x0", "x1", "x2"}

    @pytest.mark.asyncio
    async def test_deterministic_with_same_seed(self) -> None:
        edges = _three_cliques_with_bridges()
        detector_a = LeidenCommunityDetector(
            LeidenCommunityDetectorConfig(random_seed=42, max_levels=2)
        )
        detector_b = LeidenCommunityDetector(
            LeidenCommunityDetectorConfig(random_seed=42, max_levels=2)
        )

        result_a = await detector_a.detect("test-lib", edges)
        result_b = await detector_b.detect("test-lib", edges)

        assert [(c.community_id, c.level, c.member_entity_ids) for c in result_a] == [
            (c.community_id, c.level, c.member_entity_ids) for c in result_b
        ]

    @pytest.mark.asyncio
    async def test_hierarchy_aggregates_level0_into_level1(self) -> None:
        # Two pairs of tightly-coupled cliques, each pair bridged strongly,
        # the two pairs bridged weakly. Expect 4 level-0 communities and
        # at least one level-1 community that merges some of them.
        edges: list[tuple[str, str, float]] = []
        edges.extend(_clique_edges("a", 4))
        edges.extend(_clique_edges("b", 4))
        edges.extend(_clique_edges("c", 4))
        edges.extend(_clique_edges("d", 4))
        # Strong bridges within pairs (a<->b) and (c<->d)
        edges.append(("a0", "b0", 0.5))
        edges.append(("a1", "b1", 0.5))
        edges.append(("c0", "d0", 0.5))
        edges.append(("c1", "d1", 0.5))
        # Weak bridge between pairs
        edges.append(("b0", "c0", 0.01))

        detector = LeidenCommunityDetector(
            LeidenCommunityDetectorConfig(min_community_size=3, max_levels=2)
        )
        communities = await detector.detect("test-lib", edges)

        level0 = [c for c in communities if c.level == 0]
        level1 = [c for c in communities if c.level == 1]

        assert len(level0) >= 2
        assert len(level1) >= 1
        # Every level-1 community's members are the union of one or more
        # level-0 communities' members.
        level0_member_sets = [set(c.member_entity_ids) for c in level0]
        for upper in level1:
            upper_members = set(upper.member_entity_ids)
            covered: set[str] = set()
            for child_set in level0_member_sets:
                if child_set <= upper_members:
                    covered |= child_set
            assert covered == upper_members
        # community_id naming
        assert all(c.community_id.startswith("c1:") for c in level1)
