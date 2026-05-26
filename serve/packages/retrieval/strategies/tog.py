"""ToG (Think-on-Graph) strategy — KG beam search planner.

ADR-0017 §4 implementation. Walks the knowledge graph outward from a set
of seed entities, expanding each beam path one hop per round, until
either the answer is producible (``answer_ready``), the budget runs out
(``budget_exceeded``), no further evidence is found (``no_evidence``),
or the hard depth cap (``MAX_DEPTH``) is reached.

Constraints (PRD §11.2 + ADR-0017 §4):
- depth ≤ 3 (hard cap; truncation if deeper)
- beam ≤ 4 (hard cap on retained paths per round)
- branching factor ≤ 8 (cap on neighbours fetched per leaf node)
- ``library_id`` is mandatory on every graph call (PRD §16.6).

Implementation notes:
- The strategy is *path-based*: a beam carries an ordered list of
  triples plus an aggregated confidence (product of edge confidences).
- Beam pruning keeps the top-``beam_size`` paths by confidence; ties are
  broken by the path's tail entity id for reproducibility.
- The strategy emits one ``RetrievalStep`` per expansion (action =
  ``"expand_neighbor"``), as required by ADR-0017 §6.

Budget plumbing follows the same convention as Self-RAG / CRAG: every
LLM-equivalent op (graph round-trip) is one ``llm_calls`` increment so
the existing ``has_headroom_for`` helper can short-circuit cleanly.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from packages.core.models import Query, Triple
from packages.indexing.protocols import GraphIndex
from packages.retrieval._internal.budget_check import (
    BudgetSnapshot,
    has_headroom_for,
)
from packages.retrieval.protocols import (
    BudgetUsage,
    RetrievalBudget,
    RetrievalStep,
    RetrievalTrace,
    StepCost,
)

TOG_STRATEGY_NAME: Literal["tog"] = "tog"
MAX_DEPTH: int = 3
MAX_BEAM_SIZE: int = 4
DEFAULT_BRANCHING_FACTOR: int = 8
SEED_TOP_K: int = MAX_BEAM_SIZE

# Step idx 0 is reserved for "tog.seed"; expansion steps start at 1.
SEED_STEP_IDX: int = 0

SeedEntityFn = Callable[[str, Query], Awaitable[list[str]]]
"""Resolves a query to seed entity ids within ``library_id``.

Signature: ``(library_id, query) -> list[entity_id]``.
"""

AnswerCheckFn = Callable[[Query, "tuple[BeamPath, ...]"], Awaitable[bool]]
"""Optional probe that decides whether the current beam set already
covers the answer. Defaults to ``False`` until depth runs out.

Signature: ``(query, beams) -> bool``.
"""


@dataclass(frozen=True, slots=True)
class BeamPath:
    """One path in the beam — a chain of triples plus aggregated score.

    ``confidence`` is the product of the triples' confidences; ``tail``
    is the path's leaf entity id (next expansion target).
    """

    triples: tuple[Triple, ...]
    confidence: float
    tail: str

    @classmethod
    def seed(cls, entity_id: str) -> BeamPath:
        return cls(triples=(), confidence=1.0, tail=entity_id)

    def extend(self, triple: Triple, *, next_tail: str) -> BeamPath:
        return BeamPath(
            triples=(*self.triples, triple),
            confidence=self.confidence * max(triple.confidence, 0.0),
            tail=next_tail,
        )


@dataclass(frozen=True, slots=True)
class ToGStrategyConfig:
    """Tunables for the ToG beam search."""

    max_depth: int = MAX_DEPTH
    beam_size: int = MAX_BEAM_SIZE
    branching_factor: int = DEFAULT_BRANCHING_FACTOR
    min_edge_confidence: float = 0.0


class ToGStrategy:
    """``RetrievalStrategy`` implementation of ADR-0017 §4 Think-on-Graph."""

    name: Literal["tog"] = TOG_STRATEGY_NAME

    def __init__(
        self,
        *,
        graph: GraphIndex,
        seed_resolver: SeedEntityFn,
        answer_check: AnswerCheckFn | None = None,
        config: ToGStrategyConfig | None = None,
    ) -> None:
        cfg = config or ToGStrategyConfig()
        if cfg.max_depth > MAX_DEPTH:
            msg = f"ToG max_depth {cfg.max_depth} exceeds hard cap {MAX_DEPTH}"
            raise ValueError(msg)
        if cfg.beam_size > MAX_BEAM_SIZE:
            msg = f"ToG beam_size {cfg.beam_size} exceeds hard cap {MAX_BEAM_SIZE}"
            raise ValueError(msg)
        if cfg.max_depth < 1 or cfg.beam_size < 1:
            msg = "ToG requires max_depth >= 1 and beam_size >= 1"
            raise ValueError(msg)
        self._graph = graph
        self._seed_resolver = seed_resolver
        self._answer_check = answer_check
        self._config = cfg

    async def run(
        self,
        library_id: str,
        query: Query,
        budget: RetrievalBudget,
    ) -> RetrievalTrace:
        if query.library_id != library_id:
            msg = (
                f"Query library_id '{query.library_id}' does not match "
                f"requested library_id '{library_id}'"
            )
            raise ValueError(msg)

        started = time.perf_counter()
        steps: list[RetrievalStep] = []
        usage = BudgetUsage()

        # ---- Seed: resolve entities from query --------------------------
        seeds = await self._seed_resolver(library_id, query)
        seeds = list(dict.fromkeys(seeds))[: self._config.beam_size]
        steps.append(
            RetrievalStep(
                step_idx=SEED_STEP_IDX,
                thought="tog.seed resolve query entities",
                action="seed",
                action_input=query.text,
                observation=f"resolved {len(seeds)} seed entities: {seeds}",
            )
        )
        usage = _add_step(usage, llm_calls=0)

        if not seeds:
            return _trace(library_id, query, steps, usage, started, "no_evidence")

        beams: tuple[BeamPath, ...] = tuple(BeamPath.seed(eid) for eid in seeds)

        # ---- Beam expansion: depth 1 .. max_depth -----------------------
        for hop in range(1, self._config.max_depth + 1):
            snapshot = BudgetSnapshot(budget=budget, usage=usage, started_at_monotonic=started)
            if not has_headroom_for(snapshot, llm_calls=1):
                return _trace(library_id, query, steps, usage, started, "budget_exceeded")

            expanded = await self._expand_beams(library_id, beams, hop)
            beams = self._prune(expanded)

            steps.append(
                RetrievalStep(
                    step_idx=len(steps),
                    thought=f"hop {hop}",
                    action="expand_neighbor",
                    action_input=_format_beam_tails(beams),
                    observation=_format_beam_observation(beams),
                    cost=StepCost(llm_calls=1),
                )
            )
            usage = _add_step(usage, llm_calls=1)

            if not beams:
                return _trace(library_id, query, steps, usage, started, "no_evidence")

            if await self._is_answer_ready(query, beams):
                return _trace(library_id, query, steps, usage, started, "answer_ready")

        # Depth cap reached without conclusive answer — return what we have.
        return _trace(library_id, query, steps, usage, started, "answer_ready")

    async def _expand_beams(
        self,
        library_id: str,
        beams: Sequence[BeamPath],
        hop: int,
    ) -> list[BeamPath]:
        """Expand each beam by one hop, returning the union of children."""
        del hop  # observability only — observable via step_idx
        out: list[BeamPath] = []
        for path in beams:
            triples = await self._graph.get_neighbors(library_id, path.tail, depth=1)
            children = self._children_from_triples(path, triples)
            out.extend(children)
        return out

    def _children_from_triples(
        self,
        parent: BeamPath,
        triples: Sequence[Triple],
    ) -> list[BeamPath]:
        """Convert one-hop triples into extended beam paths.

        Caps on branching factor + minimum edge confidence mirror ADR-0017
        §4 to keep the search bounded on hub entities.
        """
        cfg = self._config
        kept: list[BeamPath] = []
        # Sort by confidence so the branching-factor cap keeps strongest edges.
        ordered = sorted(triples, key=lambda t: t.confidence, reverse=True)
        for triple in ordered[: cfg.branching_factor]:
            if triple.confidence < cfg.min_edge_confidence:
                continue
            next_tail = _opposite_endpoint(triple, parent.tail)
            if next_tail is None:
                continue
            kept.append(parent.extend(triple, next_tail=next_tail))
        return kept

    def _prune(self, candidates: Sequence[BeamPath]) -> tuple[BeamPath, ...]:
        """Keep top-``beam_size`` by confidence, deduped by tail."""
        # Dedupe by tail entity (keep the highest-confidence path to it).
        best_by_tail: dict[str, BeamPath] = {}
        for path in candidates:
            prior = best_by_tail.get(path.tail)
            if prior is None or path.confidence > prior.confidence:
                best_by_tail[path.tail] = path
        ordered = sorted(
            best_by_tail.values(),
            key=lambda p: (-p.confidence, p.tail),
        )
        return tuple(ordered[: self._config.beam_size])

    async def _is_answer_ready(
        self,
        query: Query,
        beams: tuple[BeamPath, ...],
    ) -> bool:
        if self._answer_check is None:
            return False
        return await self._answer_check(query, beams)


def _opposite_endpoint(triple: Triple, current_tail: str) -> str | None:
    """Return the entity on the other side of ``triple`` from ``current_tail``.

    ``GraphIndex.get_neighbors`` returns triples adjacent to the seed
    node; that node may be either ``head`` or ``tail`` depending on
    direction. None is returned when the triple is unrelated (defensive).
    """
    if triple.head == current_tail:
        return triple.tail
    if triple.tail == current_tail:
        return triple.head
    return None


def _format_beam_tails(beams: Sequence[BeamPath]) -> str:
    return ",".join(p.tail for p in beams) or "<empty>"


def _format_beam_observation(beams: Sequence[BeamPath]) -> str:
    if not beams:
        return "0 active beams"
    parts = [f"{p.tail}@conf={p.confidence:.3f}|edges={len(p.triples)}" for p in beams]
    return f"{len(beams)} beams: " + "; ".join(parts)


def _add_step(usage: BudgetUsage, *, llm_calls: int) -> BudgetUsage:
    return usage.model_copy(
        update={
            "steps": usage.steps + 1,
            "llm_calls": usage.llm_calls + llm_calls,
        }
    )


def _trace(
    library_id: str,
    query: Query,
    steps: list[RetrievalStep],
    usage: BudgetUsage,
    started: float,
    reason: Literal["answer_ready", "budget_exceeded", "no_evidence", "error", "timeout"],
) -> RetrievalTrace:
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    final_usage = usage.model_copy(update={"duration_ms": elapsed_ms})
    return RetrievalTrace(
        library_id=library_id,
        query=query.text,
        planner=TOG_STRATEGY_NAME,
        steps=tuple(steps),
        budget_used=final_usage,
        terminated_reason=reason,
    )
