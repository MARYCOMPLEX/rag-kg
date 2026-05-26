"""HypothesisTask — propose mechanistic hypotheses connecting two KG entities.

Pipeline:
1. Path mining (no LLM) — fetch neighborhoods of head and tail from the KG,
   build a small in-memory MultiDiGraph, and enumerate simple paths from
   head to tail up to a configured cutoff.
2. LLM hypothesis generation (single call) — provide the discovered paths
   as context and ask for 1-3 plausible mechanistic hypotheses, each tied
   to one or more path indices, returned as JSON.
3. Aggregate cost.

Failures:
- No paths discovered → return a synthetic low-confidence "no path"
  hypothesis.
- LLM failure → return empty hypotheses with the LLM cost (zero).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, cast

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.core.models import Entity, Triple
from packages.indexing.protocols import GraphIndex
from packages.llm.protocols import LLMClient, LLMResponse, Message
from packages.orchestration.protocols import (
    Hypothesis,
    HypothesisResult,
    ReasoningPath,
    TaskBudget,
    TaskCost,
)
from packages.orchestration.scorers import (
    MIN_PATHS_REQUIRED,
    hypothesis_sort_key,
    score_hypothesis,
)

# Optional async stage emitter; injected by the worker job so the task
# layer never has to import Redis.
type StageEmitter = Callable[[str, str, dict[str, object]], Awaitable[None]]

_SYSTEM_PROMPT = """You are a hypothesis-generation assistant for scientific KGs. \
Given two entities and KG paths between them, propose 1-3 plausible mechanistic \
hypotheses. Each must reference at least one path index. Return JSON with \
`hypotheses`. Be conservative — confidence should reflect how directly the paths \
support the claim. Counter-evidence should mention any conflicting or weak path.

Return strict JSON with this shape:
{
  "hypotheses": [
    {
      "statement": "Concise mechanistic claim connecting the two entities.",
      "rationale": "Why the cited paths support the claim.",
      "supporting_path_indices": [0, 2],
      "counter_evidence": "Any conflicting or weak path; empty string if none.",
      "confidence": 0.7
    }
  ]
}

Rules:
- 1 to 3 hypotheses.
- Every hypothesis MUST cite at least one path index from the supplied list.
- `supporting_path_indices` must be integers in range [0, num_paths - 1].
- `confidence` is a float in [0.0, 1.0].
- Return ONLY JSON, no prose, no markdown fences."""

_USER_PROMPT_TEMPLATE = """Head entity: {head_id}
Tail entity: {tail_id}

KG paths from head to tail (numbered):

{paths}

Propose 1 to {max_hypotheses} mechanistic hypotheses now."""

_NO_PATH_HYPOTHESIS_STATEMENT = (
    "No KG path connects the head and tail entities; any mechanistic link "
    "between them is not supported by the current knowledge graph."
)
_NO_PATH_CONFIDENCE = 0.1
_MIN_PATH_NODE_COUNT = 2

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_block(text: str) -> str | None:
    """Best-effort: pull the largest balanced JSON object from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = _JSON_BLOCK_RE.search(text)
    if match is None:
        return None
    return match.group(0)


class _LLMHypothesis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    statement: str = ""
    rationale: str = ""
    supporting_path_indices: list[int] = Field(default_factory=list)  # type: ignore[arg-type]
    counter_evidence: str = ""
    confidence: float = 0.5


class _LLMHypothesisPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    hypotheses: list[_LLMHypothesis] = Field(default_factory=list)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class HypothesisTaskConfig:
    """Tunables for HypothesisTask."""

    max_hypotheses: int = 3
    max_path_depth: int = 3
    max_paths_to_explore: int = 10
    llm_temperature: float = 0.4
    llm_max_tokens: int = 600
    llm_timeout_s: float = 120.0


class HypothesisTask:
    """Propose KG-grounded hypotheses connecting two entities."""

    def __init__(
        self,
        *,
        graph_index: GraphIndex,
        llm: LLMClient,
        budget: TaskBudget | None = None,
        config: HypothesisTaskConfig | None = None,
    ) -> None:
        self._graph_index = graph_index
        self._llm = llm
        self._budget = budget or TaskBudget()
        self._config = config or HypothesisTaskConfig()

    async def run(
        self,
        library_id: str,
        head_entity_id: str,
        tail_entity_id: str,
        *,
        stage_emitter: StageEmitter | None = None,
    ) -> HypothesisResult:
        started = time.perf_counter()
        emitter = _coerce_emitter(stage_emitter)

        await emitter(
            "path_mining",
            "stage_started",
            {"head": head_entity_id, "tail": tail_entity_id},
        )
        paths, structured = await self._mine_paths(library_id, head_entity_id, tail_entity_id)
        await emitter(
            "path_mining",
            "stage_completed",
            {"path_count": len(paths)},
        )

        if not paths:
            return HypothesisResult(
                library_id=library_id,
                head_entity_id=head_entity_id,
                tail_entity_id=tail_entity_id,
                hypotheses=(
                    Hypothesis(
                        statement=_NO_PATH_HYPOTHESIS_STATEMENT,
                        rationale="Path mining returned no simple paths within the depth cutoff.",
                        supporting_paths=(),
                        counter_evidence="",
                        confidence=_NO_PATH_CONFIDENCE,
                    ),
                ),
                cost=self._aggregate_cost([], started),
            )

        await emitter("llm_generate", "stage_started", {})
        llm_response = await self._call_llm(head_entity_id, tail_entity_id, paths)
        await emitter(
            "llm_generate",
            "stage_completed",
            {"llm_call": llm_response is not None},
        )

        hypotheses = self._build_hypotheses(llm_response, paths)

        # ADR-0020: filter (≥ MIN_PATHS_REQUIRED supporting paths) → score
        # three axes via `score_hypothesis` → sort by `novelty × confidence`.
        await emitter("score", "stage_started", {})
        scored = self._score_and_filter(library_id, hypotheses, paths, structured)
        await emitter(
            "score",
            "stage_completed",
            {"scored": len(scored), "filtered_out": len(hypotheses) - len(scored)},
        )

        await emitter("rank", "stage_started", {})
        ranked = tuple(sorted(scored, key=hypothesis_sort_key, reverse=True))
        await emitter("rank", "stage_completed", {"final_count": len(ranked)})

        return HypothesisResult(
            library_id=library_id,
            head_entity_id=head_entity_id,
            tail_entity_id=tail_entity_id,
            hypotheses=ranked,
            cost=self._aggregate_cost(
                [llm_response] if llm_response is not None else [],
                started,
            ),
        )

    # === path mining ===

    async def _mine_paths(
        self, library_id: str, head_entity_id: str, tail_entity_id: str
    ) -> tuple[tuple[tuple[str, ...], ...], tuple[ReasoningPath, ...]]:
        """Fetch head/tail neighborhoods, build an in-memory MultiDiGraph, and
        enumerate simple paths from head to tail up to ``max_path_depth`` hops.

        Returns a pair of parallel tuples:

        - ``flat_paths``: flat tuples ``(entity_id, relation, entity_id, ...)``
          consumed by the LLM prompt rendering helpers.
        - ``structured``: matching ``ReasoningPath`` objects feeding the
          three-axis scorer (ADR-0020). Each path's ``confidence`` is the
          mean of its underlying triple confidences.
        """
        head_neighbors = await self._graph_index.get_neighbors(
            library_id, head_entity_id, depth=self._config.max_path_depth
        )
        tail_neighbors = await self._graph_index.get_neighbors(
            library_id, tail_entity_id, depth=self._config.max_path_depth
        )

        graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
        seen_edges: set[tuple[str, str, str]] = set()
        triple_by_edge: dict[tuple[str, str, str], Triple] = {}
        for triple in list(head_neighbors) + list(tail_neighbors):
            edge_key = (triple.head, triple.relation, triple.tail)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            triple_by_edge[edge_key] = triple
            graph.add_edge(triple.head, triple.tail, relation=triple.relation)

        if head_entity_id not in graph or tail_entity_id not in graph:
            return (), ()

        node_paths_iter = cast(
            "Any",
            nx.all_simple_paths(  # type: ignore[no-untyped-call]
                graph,
                source=head_entity_id,
                target=tail_entity_id,
                cutoff=self._config.max_path_depth,
            ),
        )

        flat_out: list[tuple[str, ...]] = []
        structured_out: list[ReasoningPath] = []
        for node_path in node_paths_iter:
            nodes = cast("list[str]", list(node_path))
            for flat in _expand_node_path_to_edge_paths(graph, nodes):
                flat_out.append(flat)
                structured_out.append(_build_reasoning_path(library_id, flat, triple_by_edge))
                if len(flat_out) >= self._config.max_paths_to_explore:
                    return tuple(flat_out), tuple(structured_out)
        return tuple(flat_out), tuple(structured_out)

    # === LLM call ===

    async def _call_llm(
        self,
        head_entity_id: str,
        tail_entity_id: str,
        paths: tuple[tuple[str, ...], ...],
    ) -> LLMResponse | None:
        rendered = "\n".join(f"{i}: {_render_path(p)}" for i, p in enumerate(paths))
        messages = [
            Message(role="system", content=_SYSTEM_PROMPT),
            Message(
                role="user",
                content=_USER_PROMPT_TEMPLATE.format(
                    head_id=head_entity_id,
                    tail_id=tail_entity_id,
                    paths=rendered,
                    max_hypotheses=self._config.max_hypotheses,
                ),
            ),
        ]
        try:
            return await self._llm.complete(
                messages,
                temperature=self._config.llm_temperature,
                max_tokens=self._config.llm_max_tokens,
                timeout_s=self._config.llm_timeout_s,
            )
        except Exception:
            return None

    # === hypothesis assembly ===

    def _build_hypotheses(
        self,
        response: LLMResponse | None,
        paths: tuple[tuple[str, ...], ...],
    ) -> tuple[Hypothesis, ...]:
        if response is None:
            return ()
        block = _extract_json_block(response.text)
        if block is None:
            return ()
        try:
            payload = _LLMHypothesisPayload.model_validate_json(block)
        except (json.JSONDecodeError, ValidationError):
            return ()

        cap = max(1, self._config.max_hypotheses)
        out: list[Hypothesis] = []
        for item in payload.hypotheses:
            statement = item.statement.strip()
            if not statement:
                continue
            supporting = tuple(
                paths[idx] for idx in item.supporting_path_indices if 0 <= idx < len(paths)
            )
            if not supporting:
                # spec requires every hypothesis cite at least one path
                continue
            confidence = max(0.0, min(1.0, item.confidence))
            out.append(
                Hypothesis(
                    statement=statement,
                    rationale=item.rationale.strip(),
                    supporting_paths=supporting,
                    counter_evidence=item.counter_evidence.strip(),
                    confidence=confidence,
                )
            )
            if len(out) >= cap:
                break
        return tuple(out)

    # === scoring + filtering (ADR-0020) ===

    def _score_and_filter(
        self,
        library_id: str,
        hypotheses: tuple[Hypothesis, ...],
        flat_paths: tuple[tuple[str, ...], ...],
        structured_paths: tuple[ReasoningPath, ...],
    ) -> tuple[Hypothesis, ...]:
        """Score each hypothesis and drop those with too few supporting paths.

        Mapping flat → structured is positional (parallel tuples produced
        by `_mine_paths`). Hypotheses whose `supporting_paths` cannot be
        located in `flat_paths` (e.g. LLM-fabricated path) are dropped
        rather than scored.
        """
        flat_index = {p: i for i, p in enumerate(flat_paths)}
        kept: list[Hypothesis] = []
        for hypothesis in hypotheses:
            indices: list[int] = []
            for support in hypothesis.supporting_paths:
                idx = flat_index.get(support)
                if idx is not None:
                    indices.append(idx)
            if len(indices) < MIN_PATHS_REQUIRED:
                continue
            paths_for_h = tuple(structured_paths[i] for i in indices)
            scored = score_hypothesis(library_id, hypothesis, paths_for_h)
            kept.append(scored)
        return tuple(kept)

    # === cost ===

    @staticmethod
    def _aggregate_cost(responses: list[LLMResponse], started: float) -> TaskCost:
        return TaskCost(
            llm_calls=len(responses),
            input_tokens=sum(r.input_tokens for r in responses),
            output_tokens=sum(r.output_tokens for r in responses),
            cost_usd=sum(r.cost_usd for r in responses),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )


def _expand_node_path_to_edge_paths(
    graph: nx.MultiDiGraph[str], nodes: list[str]
) -> list[tuple[str, ...]]:
    """Expand a node-only path into one flat path per relation combination.

    A ``MultiDiGraph`` may have multiple parallel edges between the same
    (u, v) pair (different relations). We enumerate the cartesian product
    of relation labels along the path and emit each as a flat tuple
    ``(node, relation, node, relation, ..., node)``.
    """
    if len(nodes) < _MIN_PATH_NODE_COUNT:
        return [tuple(nodes)]

    edge_relations_per_step: list[list[str]] = []
    for u, v in pairwise(nodes):
        edge_dict = cast("dict[Any, dict[str, Any]]", graph.get_edge_data(u, v) or {})
        relations = sorted({str(data.get("relation", "")) for data in edge_dict.values()})
        if not relations:
            return []
        edge_relations_per_step.append(relations)

    out: list[tuple[str, ...]] = []
    for combo in _cartesian(edge_relations_per_step):
        flat: list[str] = [nodes[0]]
        for idx, rel in enumerate(combo):
            flat.append(rel)
            flat.append(nodes[idx + 1])
        out.append(tuple(flat))
    return out


def _cartesian(seqs: list[list[str]]) -> list[list[str]]:
    """Tiny iterative cartesian product without importing itertools.product."""
    acc: list[list[str]] = [[]]
    for seq in seqs:
        acc = [[*prev, item] for prev in acc for item in seq]
    return acc


def _render_path(flat: tuple[str, ...]) -> str:
    """Render a flat path tuple as ``a -[r1]-> b -[r2]-> c``."""
    if not flat:
        return ""
    parts: list[str] = [flat[0]]
    i = 1
    while i + 1 < len(flat):
        parts.append(f"-[{flat[i]}]->")
        parts.append(flat[i + 1])
        i += 2
    return " ".join(parts)


def _coerce_emitter(emitter: StageEmitter | None) -> StageEmitter:
    """Return a real emitter or a no-op fallback."""
    if emitter is not None:
        return emitter

    async def _noop(stage: str, event_type: str, payload: dict[str, object]) -> None:
        return None

    return _noop


def _build_reasoning_path(
    library_id: str,
    flat: tuple[str, ...],
    triple_by_edge: dict[tuple[str, str, str], Triple],
) -> ReasoningPath:
    """Reconstruct a structured ReasoningPath from a flat path tuple.

    The flat tuple alternates ``(entity_id, relation, entity_id, ...)``.
    Each consecutive (head, relation, tail) triple is looked up in
    ``triple_by_edge`` to recover its provenance + confidence; missing
    edges fall back to a neutral 0.5 confidence so scoring still runs.
    """
    if not flat:
        return ReasoningPath(library_id=library_id, confidence=0.0)

    entities = tuple(
        Entity(library_id=library_id, entity_id=node, name=node, type="Entity")
        for node in flat[::2]
    )

    triples: list[Triple] = []
    confidences: list[float] = []
    i = 1
    while i + 1 < len(flat):
        head = flat[i - 1]
        relation = flat[i]
        tail = flat[i + 1]
        existing = triple_by_edge.get((head, relation, tail))
        if existing is not None:
            triples.append(existing)
            confidences.append(existing.confidence)
        else:
            triples.append(
                Triple(
                    library_id=library_id,
                    head=head,
                    relation=relation,
                    tail=tail,
                    confidence=0.5,
                )
            )
            confidences.append(0.5)
        i += 2

    mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return ReasoningPath(
        library_id=library_id,
        nodes=entities,
        relations=tuple(triples),
        confidence=max(0.0, min(1.0, mean_conf)),
    )
