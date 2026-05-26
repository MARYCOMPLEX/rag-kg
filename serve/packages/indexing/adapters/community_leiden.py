"""Louvain-based hierarchical community detector.

Despite the class name (`LeidenCommunityDetector`), the implementation
uses the **Louvain** algorithm via `python-louvain`. The name keeps the
public interface stable for downstream consumers; we can swap in a true
Leiden implementation (e.g. `igraph` / `leidenalg`) later without
touching call sites.

Hierarchy is built bottom-up:
  - level 0: Louvain partition over the input graph
  - level 1+: re-partition the meta-graph whose nodes are level-(l-1)
    communities and whose edge weights are the sum of inter-community
    edge weights from the original graph

Detection is CPU-bound and synchronous in the underlying library, so it
runs inside `asyncio.to_thread` to keep the event loop responsive.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any, cast

import networkx as nx
from community import community_louvain  # type: ignore[import-untyped]

from packages.core.models import Community

_RANDOM_SEED_MAX = 2**31 - 1
_MIN_NODES_TO_AGGREGATE = 2


@dataclass(frozen=True, slots=True)
class LeidenCommunityDetectorConfig:
    """Tunables for the Louvain/Leiden detector."""

    random_seed: int = 42
    min_community_size: int = 3
    max_levels: int = 2
    resolution: float = 1.0


class LeidenCommunityDetector:
    """Hierarchical community detector implementing the CommunityDetector protocol."""

    def __init__(self, config: LeidenCommunityDetectorConfig) -> None:
        self._config = config

    async def detect(
        self,
        library_id: str,
        edges: list[tuple[str, str, float]],
    ) -> list[Community]:
        if not edges:
            return []
        return await asyncio.to_thread(self._detect_sync, library_id, edges)

    def _detect_sync(
        self,
        library_id: str,
        edges: list[tuple[str, str, float]],
    ) -> list[Community]:
        self._seed_rngs()
        graph = _build_graph(edges)
        if graph.number_of_edges() == 0:
            return []

        level0 = self._partition_level(graph, level=0, library_id=library_id)
        if not level0:
            return []

        if self._config.max_levels <= 1:
            return level0

        higher = self._build_higher_levels(graph, level0, library_id)
        return level0 + higher

    def _seed_rngs(self) -> None:
        seed = self._config.random_seed
        random.seed(seed)
        try:
            import numpy as np  # noqa: PLC0415

            np.random.seed(seed % _RANDOM_SEED_MAX)
        except ImportError:
            pass

    def _partition_level(
        self,
        graph: nx.Graph[str],
        *,
        level: int,
        library_id: str,
        child_members: dict[str, tuple[str, ...]] | None = None,
    ) -> list[Community]:
        """Run Louvain on `graph` and return communities at the given level.

        `child_members` maps node-id (in this graph) -> entity ids that
        node represents. For level 0, identity mapping is used.
        """
        partition = cast(
            "dict[Any, int]",
            community_louvain.best_partition(  # type: ignore[no-untyped-call]
                graph,
                weight="weight",
                resolution=self._config.resolution,
                random_state=self._config.random_seed,
            ),
        )

        groups: dict[int, list[Any]] = {}
        for node, comm_idx in partition.items():
            groups.setdefault(comm_idx, []).append(node)

        out: list[Community] = []
        for new_idx, (_, nodes) in enumerate(sorted(groups.items())):
            if child_members is None:
                members = tuple(sorted(str(n) for n in nodes))
            else:
                merged: set[str] = set()
                for n in nodes:
                    merged.update(child_members.get(str(n), ()))
                members = tuple(sorted(merged))
            if len(members) < self._config.min_community_size:
                continue
            out.append(
                Community(
                    library_id=library_id,
                    community_id=f"c{level}:{new_idx}",
                    level=level,
                    member_entity_ids=members,
                )
            )
        return out

    def _build_higher_levels(
        self,
        base_graph: nx.Graph[str],
        level0: list[Community],
        library_id: str,
    ) -> list[Community]:
        """Aggregate level-0 communities into a meta-graph and re-partition.

        Returns flattened communities for levels 1..max_levels-1.
        """
        results: list[Community] = []
        prev_level = level0
        for next_level in range(1, self._config.max_levels):
            if len(prev_level) < _MIN_NODES_TO_AGGREGATE:
                break  # nothing to aggregate
            meta_graph, child_members = _build_meta_graph(base_graph, prev_level)
            if meta_graph.number_of_edges() == 0:
                break
            communities = self._partition_level(
                meta_graph,
                level=next_level,
                library_id=library_id,
                child_members=child_members,
            )
            if not communities:
                break
            results.extend(communities)
            prev_level = communities
        return results


def _build_graph(edges: list[tuple[str, str, float]]) -> nx.Graph[str]:
    """Build an undirected weighted graph; collapse duplicate edges by summing weight."""
    graph: nx.Graph[str] = nx.Graph()
    for head, tail, weight in edges:
        if head == tail:
            continue  # ignore self-loops
        if graph.has_edge(head, tail):
            graph[head][tail]["weight"] += float(weight)
        else:
            graph.add_edge(head, tail, weight=float(weight))
    return graph


def _build_meta_graph(
    base_graph: nx.Graph[str],
    communities: list[Community],
) -> tuple[nx.Graph[str], dict[str, tuple[str, ...]]]:
    """Project `base_graph` onto a meta-graph keyed by community_id.

    Edge (A, B) weight = sum of weights of base edges crossing
    community A and community B. Returns the meta-graph and a mapping
    community_id -> contained entity_ids.
    """
    entity_to_comm: dict[str, str] = {}
    child_members: dict[str, tuple[str, ...]] = {}
    for comm in communities:
        child_members[comm.community_id] = comm.member_entity_ids
        for entity_id in comm.member_entity_ids:
            entity_to_comm[entity_id] = comm.community_id

    meta: nx.Graph[str] = nx.Graph()
    for cid in child_members:
        meta.add_node(cid)

    for u, v, data in base_graph.edges(data=True):
        cu = entity_to_comm.get(str(u))
        cv = entity_to_comm.get(str(v))
        if cu is None or cv is None or cu == cv:
            continue
        weight = float(data.get("weight", 1.0))
        if meta.has_edge(cu, cv):
            meta[cu][cv]["weight"] += weight
        else:
            meta.add_edge(cu, cv, weight=weight)
    return meta, child_members
