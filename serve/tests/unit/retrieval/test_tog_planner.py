"""Unit tests for the ToG planner (ADR-0017 §4)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import pytest

from packages.core.models import Entity, Query, Triple
from packages.retrieval.protocols import RetrievalBudget
from packages.retrieval.strategies.tog import (
    MAX_BEAM_SIZE,
    MAX_DEPTH,
    TOG_STRATEGY_NAME,
    BeamPath,
    ToGStrategy,
    ToGStrategyConfig,
)

LIB = "test-lib"


class FakeGraphIndex:
    """In-memory ``GraphIndex`` returning canned neighbours per entity."""

    def __init__(self, neighbours: dict[str, list[Triple]]) -> None:
        self._neighbours = neighbours
        self.calls: list[tuple[str, str, int]] = []

    async def init_library(self, library_id: str) -> None:
        return None

    async def purge_library(self, library_id: str) -> None:
        return None

    async def upsert_entities(self, library_id: str, entities: list[Entity]) -> None:
        return None

    async def upsert_triples(self, library_id: str, triples: list[Triple]) -> None:
        return None

    async def get_neighbors(
        self,
        library_id: str,
        entity_id: str,
        depth: int = 1,
    ) -> list[Triple]:
        self.calls.append((library_id, entity_id, depth))
        return list(self._neighbours.get(entity_id, []))


def _triple(head: str, rel: str, tail: str, conf: float = 0.9) -> Triple:
    return Triple(
        library_id=LIB,
        head=head,
        relation=rel,
        tail=tail,
        evidence=("doc-001::p1::0",),
        confidence=conf,
        source_model="unit-test",
    )


async def _seed(_library_id: str, _query: Query) -> list[str]:
    return ["e1"]


@pytest.mark.asyncio
async def test_seed_resolution_records_step_zero() -> None:
    graph = FakeGraphIndex(neighbours={"e1": []})
    strategy = ToGStrategy(graph=graph, seed_resolver=_seed)
    query = Query(library_id=LIB, text="What is e1?", type="multi-hop")
    budget = RetrievalBudget(max_steps=10, max_llm_calls=20, timeout_s=10.0)

    trace = await strategy.run(LIB, query, budget)

    assert trace.planner == TOG_STRATEGY_NAME
    assert trace.steps[0].step_idx == 0
    assert trace.steps[0].action == "seed"
    assert "e1" in trace.steps[0].observation


@pytest.mark.asyncio
async def test_no_seeds_yields_no_evidence_termination() -> None:
    graph = FakeGraphIndex(neighbours={})

    async def _empty_seed(_library_id: str, _query: Query) -> list[str]:
        return []

    strategy = ToGStrategy(graph=graph, seed_resolver=_empty_seed)
    query = Query(library_id=LIB, text="orphan", type="multi-hop")
    trace = await strategy.run(LIB, query, RetrievalBudget())
    assert trace.terminated_reason == "no_evidence"


@pytest.mark.asyncio
async def test_depth_capped_at_three() -> None:
    """A linear chain longer than 3 hops must be truncated at depth=3."""
    graph = FakeGraphIndex(
        neighbours={
            "e1": [_triple("e1", "to", "e2")],
            "e2": [_triple("e2", "to", "e3")],
            "e3": [_triple("e3", "to", "e4")],
            "e4": [_triple("e4", "to", "e5")],
        }
    )
    strategy = ToGStrategy(graph=graph, seed_resolver=_seed)
    query = Query(library_id=LIB, text="chain", type="multi-hop")
    budget = RetrievalBudget(max_steps=20, max_llm_calls=20, timeout_s=10.0)

    trace = await strategy.run(LIB, query, budget)

    # 1 seed step + max_depth (3) expansion steps = 4 total
    assert len(trace.steps) == 1 + MAX_DEPTH
    expansion_steps = trace.steps[1:]
    for idx, step in enumerate(expansion_steps, start=1):
        assert step.action == "expand_neighbor"
        assert step.thought == f"hop {idx}"


@pytest.mark.asyncio
async def test_beam_size_capped_at_four() -> None:
    """Even with 8+ neighbours, beam keeps at most ``MAX_BEAM_SIZE`` paths."""
    big_fanout = [_triple("e1", "to", f"n{i}", conf=0.9 - i * 0.01) for i in range(10)]
    graph = FakeGraphIndex(
        neighbours={"e1": big_fanout} | {f"n{i}": [] for i in range(10)},
    )
    strategy = ToGStrategy(
        graph=graph,
        seed_resolver=_seed,
        config=ToGStrategyConfig(max_depth=1),
    )
    query = Query(library_id=LIB, text="fanout", type="multi-hop")
    trace = await strategy.run(LIB, query, RetrievalBudget())

    # The expansion step is index 1 (after seed). Its observation
    # records "{n} beams" for the post-prune beam set.
    expansion_obs = trace.steps[1].observation
    assert expansion_obs.startswith(f"{MAX_BEAM_SIZE} beams")


@pytest.mark.asyncio
async def test_branching_factor_caps_neighbour_intake() -> None:
    """``branching_factor`` truncates the neighbour list before pruning."""
    fanout = [_triple("e1", "to", f"n{i}", conf=0.5) for i in range(20)]
    graph = FakeGraphIndex(
        neighbours={"e1": fanout} | {f"n{i}": [] for i in range(20)},
    )
    strategy = ToGStrategy(
        graph=graph,
        seed_resolver=_seed,
        config=ToGStrategyConfig(max_depth=1, branching_factor=3),
    )
    query = Query(library_id=LIB, text="fanout", type="multi-hop")
    trace = await strategy.run(LIB, query, RetrievalBudget())
    obs = trace.steps[1].observation
    # branching_factor=3 means at most 3 children → beam keeps min(3, 4) = 3
    assert obs.startswith("3 beams")


@pytest.mark.asyncio
async def test_budget_exceeded_short_circuits_loop() -> None:
    """A budget too small to afford the second hop terminates ``budget_exceeded``."""
    # Three-hop chain — the strategy would normally run all three hops.
    graph = FakeGraphIndex(
        neighbours={
            "e1": [_triple("e1", "to", "e2")],
            "e2": [_triple("e2", "to", "e3")],
            "e3": [_triple("e3", "to", "e4")],
            "e4": [],
        }
    )
    strategy = ToGStrategy(graph=graph, seed_resolver=_seed)
    query = Query(library_id=LIB, text="q", type="multi-hop")

    # max_llm_calls=1 only affords ONE expansion; before hop 2 the
    # headroom check (need 1 more) fails → budget_exceeded.
    tight_budget = RetrievalBudget(max_steps=10, max_llm_calls=1, timeout_s=10.0)
    trace = await strategy.run(LIB, query, tight_budget)
    assert trace.terminated_reason == "budget_exceeded"
    # Seed + exactly one expansion landed before the cut-off.
    assert len(trace.steps) == 2

    # With ample budget the same chain reaches depth=3 and terminates normally.
    ample_budget = RetrievalBudget(max_steps=10, max_llm_calls=20, timeout_s=10.0)
    trace_ok = await strategy.run(LIB, query, ample_budget)
    assert trace_ok.terminated_reason in ("answer_ready", "no_evidence")
    assert len(trace_ok.steps) == 1 + MAX_DEPTH


@pytest.mark.asyncio
async def test_answer_check_terminates_early() -> None:
    """When the optional ``answer_check`` returns True, loop ends with answer_ready."""
    graph = FakeGraphIndex(
        neighbours={
            "e1": [_triple("e1", "to", "target", conf=0.95)],
            "target": [_triple("target", "to", "e3")],
            "e3": [],
        }
    )

    async def _hit(_q: Query, beams: tuple[BeamPath, ...]) -> bool:
        return any(p.tail == "target" for p in beams)

    strategy = ToGStrategy(
        graph=graph,
        seed_resolver=_seed,
        answer_check=_hit,
    )
    query = Query(library_id=LIB, text="find target", type="multi-hop")
    trace = await strategy.run(LIB, query, RetrievalBudget())

    assert trace.terminated_reason == "answer_ready"
    # Should stop after the FIRST expansion; depth=1 step is index 1.
    assert len(trace.steps) == 2


@pytest.mark.asyncio
async def test_query_library_id_mismatch_raises() -> None:
    graph = FakeGraphIndex(neighbours={})
    strategy = ToGStrategy(graph=graph, seed_resolver=_seed)
    query = Query(library_id="other-lib", text="q", type="multi-hop")
    with pytest.raises(ValueError, match="does not match"):
        await strategy.run(LIB, query, RetrievalBudget())


def test_config_rejects_oversized_depth_and_beam() -> None:
    graph = FakeGraphIndex(neighbours={})
    with pytest.raises(ValueError, match="max_depth"):
        ToGStrategy(
            graph=graph,
            seed_resolver=_seed,
            config=ToGStrategyConfig(max_depth=MAX_DEPTH + 1),
        )
    with pytest.raises(ValueError, match="beam_size"):
        ToGStrategy(
            graph=graph,
            seed_resolver=_seed,
            config=ToGStrategyConfig(beam_size=MAX_BEAM_SIZE + 1),
        )


def test_beam_path_extension_is_immutable() -> None:
    seed = BeamPath.seed("e1")
    triple = _triple("e1", "to", "e2", conf=0.8)
    extended = seed.extend(triple, next_tail="e2")
    assert seed.triples == ()
    assert extended.triples == (triple,)
    assert extended.tail == "e2"
    assert extended.confidence == pytest.approx(0.8)


def test_neighbours_signature_used_correctly() -> None:
    """Defensive check: ``GraphIndex.get_neighbors`` is the only graph call."""
    graph = FakeGraphIndex(neighbours={"e1": []})

    # Sanity: the strategy should walk through this without exception
    # and the only graph method invoked is ``get_neighbors``.
    async def _smoke() -> Sequence[tuple[str, str, int]]:
        strategy = ToGStrategy(graph=graph, seed_resolver=_seed)
        query = Query(library_id=LIB, text="q", type="multi-hop")
        await strategy.run(LIB, query, RetrievalBudget())
        return graph.calls

    calls = asyncio.run(_smoke())
    # All calls should be against the same library and the seed.
    for lib, _entity, depth in calls:
        assert lib == LIB
        assert depth == 1
