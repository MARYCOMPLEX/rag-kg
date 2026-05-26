"""ReActPlanner — Thought-Action-Observation loop over retrieval tools.

Implements the ReAct paradigm (Yao et al. 2022): the LLM iteratively
emits a `Thought`, picks an `Action` (one of the registered tools), and
consumes the resulting `Observation` until it emits `finish[reason]` or
the bound `RetrievalBudget` is exhausted.

Available tools:
- vector_search[query] — semantic similarity search via VectorIndex
- bm25_search[query]   — keyword search via BM25Index
- kg_neighborhood[entity_id] — graph traversal via GraphIndex
- finish[reason]       — terminate the loop

Aggregated chunk evidence (deduped by chunk_id, max score) is returned
in the resulting RetrievalResult, accompanied by the full RetrievalTrace
for observability/debugging.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Literal

from packages.core.models import Chunk, Query, Triple
from packages.embedding.protocols import Embedder
from packages.indexing.protocols import BM25Index, GraphIndex, VectorIndex
from packages.llm.protocols import LLMClient, LLMResponse, Message
from packages.retrieval.protocols import (
    BudgetUsage,
    RetrievalBudget,
    RetrievalResult,
    RetrievalStep,
    RetrievalTrace,
    RetrievedEvidence,
    StepCost,
)

PLANNER_NAME: str = "react"

DEFAULT_VECTOR_K: int = 5
DEFAULT_BM25_K: int = 5
DEFAULT_KG_DEPTH: int = 1
DEFAULT_LLM_TEMPERATURE: float = 0.0
DEFAULT_LLM_MAX_TOKENS: int = 400

CHUNK_SNIPPET_MAX_CHARS: int = 160
CHUNK_SNIPPET_HEAD_CHARS: int = 157

VECTOR_SOURCE: str = "vector"
BM25_SOURCE: str = "bm25"

ACTION_VECTOR_SEARCH: str = "vector_search"
ACTION_BM25_SEARCH: str = "bm25_search"
ACTION_KG_NEIGHBORHOOD: str = "kg_neighborhood"
ACTION_FINISH: str = "finish"

TerminationReason = Literal["answer_ready", "budget_exceeded", "no_evidence", "error", "timeout"]

SYSTEM_PROMPT: str = (
    "You are a research assistant searching a scientific knowledge base.\n"
    "\n"
    "You have these TOOLS:\n"
    "- vector_search[query] — semantic similarity search over text chunks\n"
    "- bm25_search[query] — keyword search over text chunks\n"
    "- kg_neighborhood[entity_id] — graph traversal "
    '(entity_id format: "type:slug", e.g. "method:react")\n'
    "- finish[reason] — done; reason summarizes what you found\n"
    "\n"
    "Format EXACTLY:\n"
    "Thought: <your reasoning>\n"
    "Action: <tool name>\n"
    "Action Input: <single argument>\n"
    "\n"
    "After each Action you'll see:\n"
    "Observation: <tool output>\n"
    "\n"
    "Iterate until you have enough evidence, then emit Action: finish[reason].\n"
    "Be concise. Do NOT emit final answers — just gather evidence."
)

_THOUGHT_RE = re.compile(r"Thought:\s*(.+?)(?=\n\s*Action:|\Z)", re.DOTALL | re.IGNORECASE)
_ACTION_RE = re.compile(r"Action:\s*([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_ACTION_INPUT_RE = re.compile(
    r"Action\s*Input:\s*(.+?)(?=\n\s*(?:Observation|Thought|Action):|\Z)",
    re.DOTALL | re.IGNORECASE,
)
# Bracket-style "Action: tool[arg]" → also captures inline argument.
_ACTION_BRACKET_RE = re.compile(
    r"Action:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\[(.*?)\]",
    re.DOTALL | re.IGNORECASE,
)


@dataclass(frozen=True)
class ReActPlannerConfig:
    """Static configuration for the ReAct planner."""

    vector_k: int = DEFAULT_VECTOR_K
    bm25_k: int = DEFAULT_BM25_K
    kg_depth: int = DEFAULT_KG_DEPTH
    llm_temperature: float = DEFAULT_LLM_TEMPERATURE
    llm_max_tokens: int = DEFAULT_LLM_MAX_TOKENS


@dataclass(frozen=True)
class _ParsedAction:
    """Parsed LLM reply into ReAct tokens."""

    thought: str
    action: str
    action_input: str
    raw: str
    parse_error: str = ""


@dataclass(frozen=True)
class _ToolOutcome:
    """Output of executing a single tool call."""

    observation: str
    chunks: tuple[tuple[Chunk, float, str], ...] = ()
    finished: bool = False
    finish_reason: str = ""


class ReActPlanner:
    """Iterative ReAct retrieval planner."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        embedder: Embedder,
        vector_index: VectorIndex,
        bm25_index: BM25Index,
        graph_index: GraphIndex,
        budget: RetrievalBudget | None = None,
        config: ReActPlannerConfig | None = None,
    ) -> None:
        self._llm = llm
        self._embedder = embedder
        self._vector_index = vector_index
        self._bm25_index = bm25_index
        self._graph_index = graph_index
        self._budget = budget or RetrievalBudget()
        self._config = config or ReActPlannerConfig()

    # Read-only accessors — let strategy adapters (e.g.
    # `react_strategy.ReActStrategy`) clone the planner with a new
    # budget without violating private-attribute encapsulation
    # (pyright `reportPrivateUsage`). See ADR_REVIEW §11.2.

    @property
    def llm(self) -> LLMClient:
        """Underlying LLM client (read-only)."""
        return self._llm

    @property
    def embedder(self) -> Embedder:
        """Embedder used for vector search (read-only)."""
        return self._embedder

    @property
    def vector_index(self) -> VectorIndex:
        """Vector index used for semantic search (read-only)."""
        return self._vector_index

    @property
    def bm25_index(self) -> BM25Index:
        """BM25 index used for keyword search (read-only)."""
        return self._bm25_index

    @property
    def graph_index(self) -> GraphIndex:
        """KG index used for entity neighborhood traversal (read-only)."""
        return self._graph_index

    @property
    def config(self) -> ReActPlannerConfig:
        """Static planner configuration (read-only, frozen dataclass)."""
        return self._config

    async def plan_and_retrieve(
        self,
        library_id: str,
        query: Query,
    ) -> RetrievalResult:
        if query.library_id != library_id:
            msg = (
                f"Query library_id '{query.library_id}' does not match "
                f"requested library_id '{library_id}'"
            )
            raise ValueError(msg)

        started = time.perf_counter()
        conversation: list[Message] = [
            Message(role="system", content=SYSTEM_PROMPT),
            Message(role="user", content=f"Question: {query.text}"),
        ]

        steps: list[RetrievalStep] = []
        evidence_acc: dict[str, tuple[Chunk, float, str]] = {}
        terminated_reason: TerminationReason = "answer_ready"
        usage = _UsageAccumulator()

        for step_idx in range(self._budget.max_steps):
            if usage.llm_calls >= self._budget.max_llm_calls:
                terminated_reason = "budget_exceeded"
                break

            elapsed_s = time.perf_counter() - started
            if elapsed_s >= self._budget.timeout_s:
                terminated_reason = "timeout"
                break

            step_started = time.perf_counter()
            llm_resp = await self._call_llm(conversation)
            usage.add_llm(llm_resp)

            parsed = _parse_llm_reply(llm_resp.text)
            outcome = await self._dispatch_tool(library_id, parsed)

            duration_ms = int((time.perf_counter() - step_started) * 1000)
            step_cost = StepCost(
                llm_calls=1,
                input_tokens=llm_resp.input_tokens,
                output_tokens=llm_resp.output_tokens,
                cost_usd=llm_resp.cost_usd,
                duration_ms=duration_ms,
            )
            steps.append(
                RetrievalStep(
                    step_idx=step_idx,
                    thought=parsed.thought,
                    action=parsed.action,
                    action_input=parsed.action_input,
                    observation=outcome.observation,
                    cost=step_cost,
                )
            )

            for chunk, score, source in outcome.chunks:
                _merge_chunk(evidence_acc, chunk, score, source)

            conversation.append(Message(role="assistant", content=parsed.raw))
            conversation.append(Message(role="user", content=f"Observation: {outcome.observation}"))

            if outcome.finished:
                terminated_reason = "answer_ready"
                break
        else:
            terminated_reason = "budget_exceeded"

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        evidence = _build_evidence(evidence_acc)
        trace = RetrievalTrace(
            library_id=library_id,
            query=query.text,
            planner=PLANNER_NAME,
            steps=tuple(steps),
            budget_used=usage.snapshot(steps_count=len(steps), duration_ms=elapsed_ms),
            terminated_reason=terminated_reason,
        )
        return RetrievalResult(
            library_id=library_id,
            query=query.text,
            evidence=evidence,
            duration_ms=elapsed_ms,
            trace=trace,
        )

    async def _call_llm(self, conversation: list[Message]) -> LLMResponse:
        return await self._llm.complete(
            conversation,
            temperature=self._config.llm_temperature,
            max_tokens=self._config.llm_max_tokens,
        )

    async def _dispatch_tool(
        self,
        library_id: str,
        parsed: _ParsedAction,
    ) -> _ToolOutcome:
        if parsed.parse_error:
            return _ToolOutcome(
                observation=(
                    f"Could not parse action: {parsed.parse_error}. "
                    "Reply with 'Thought:', 'Action:', 'Action Input:'."
                )
            )

        action = parsed.action.lower()
        action_input = parsed.action_input

        if action == ACTION_FINISH:
            reason = action_input or "no reason given"
            return _ToolOutcome(
                observation=f"Finished: {reason}",
                finished=True,
                finish_reason=reason,
            )
        if action == ACTION_VECTOR_SEARCH:
            return await self._tool_vector_search(library_id, action_input)
        if action == ACTION_BM25_SEARCH:
            return await self._tool_bm25_search(library_id, action_input)
        if action == ACTION_KG_NEIGHBORHOOD:
            return await self._tool_kg_neighborhood(library_id, action_input)
        return _ToolOutcome(
            observation=(
                f"Unknown action '{parsed.action}'. Available: "
                f"{ACTION_VECTOR_SEARCH}, {ACTION_BM25_SEARCH}, "
                f"{ACTION_KG_NEIGHBORHOOD}, {ACTION_FINISH}."
            )
        )

    async def _tool_vector_search(
        self,
        library_id: str,
        query_text: str,
    ) -> _ToolOutcome:
        if not query_text.strip():
            return _ToolOutcome(observation="vector_search requires a non-empty query.")
        vectors = await self._embedder.embed([query_text])
        if not vectors:
            return _ToolOutcome(observation="vector_search produced no embedding.")
        results = await self._vector_index.search(library_id, vectors[0], k=self._config.vector_k)
        chunks = tuple((chunk, score, VECTOR_SOURCE) for chunk, score in results)
        return _ToolOutcome(
            observation=_format_chunk_observation("vector_search", results),
            chunks=chunks,
        )

    async def _tool_bm25_search(
        self,
        library_id: str,
        query_text: str,
    ) -> _ToolOutcome:
        if not query_text.strip():
            return _ToolOutcome(observation="bm25_search requires a non-empty query.")
        results = await self._bm25_index.search(library_id, query_text, k=self._config.bm25_k)
        chunks = tuple((chunk, score, BM25_SOURCE) for chunk, score in results)
        return _ToolOutcome(
            observation=_format_chunk_observation("bm25_search", results),
            chunks=chunks,
        )

    async def _tool_kg_neighborhood(
        self,
        library_id: str,
        entity_id: str,
    ) -> _ToolOutcome:
        if not entity_id.strip():
            return _ToolOutcome(observation="kg_neighborhood requires a non-empty entity_id.")
        triples = await self._graph_index.get_neighbors(
            library_id, entity_id, depth=self._config.kg_depth
        )
        return _ToolOutcome(observation=_format_triples_observation(entity_id, triples))


class _UsageAccumulator:
    """Mutable helper for tallying budget usage across steps."""

    def __init__(self) -> None:
        self.llm_calls: int = 0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.cost_usd: float = 0.0

    def add_llm(self, resp: LLMResponse) -> None:
        self.llm_calls += 1
        self.input_tokens += resp.input_tokens
        self.output_tokens += resp.output_tokens
        self.cost_usd += resp.cost_usd

    def snapshot(self, *, steps_count: int, duration_ms: int) -> BudgetUsage:
        return BudgetUsage(
            steps=steps_count,
            llm_calls=self.llm_calls,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cost_usd=self.cost_usd,
            duration_ms=duration_ms,
        )


def _parse_llm_reply(raw: str) -> _ParsedAction:
    """Parse a ReAct-formatted LLM reply.

    Supports both ``Action: tool`` + ``Action Input: arg`` and the more
    compact ``Action: tool[arg]`` forms. On total parse failure, returns
    a parsed action with ``parse_error`` populated so the loop can record
    the step and ask the LLM to reformat.
    """
    text = raw.strip()
    if not text:
        return _ParsedAction(
            thought="",
            action="",
            action_input="",
            raw=raw,
            parse_error="empty response",
        )

    thought_match = _THOUGHT_RE.search(text)
    thought = thought_match.group(1).strip() if thought_match else ""

    bracket_match = _ACTION_BRACKET_RE.search(text)
    if bracket_match:
        return _ParsedAction(
            thought=thought,
            action=bracket_match.group(1).strip(),
            action_input=bracket_match.group(2).strip(),
            raw=raw,
        )

    action_match = _ACTION_RE.search(text)
    if not action_match:
        return _ParsedAction(
            thought=thought,
            action="",
            action_input="",
            raw=raw,
            parse_error="missing 'Action:' line",
        )
    input_match = _ACTION_INPUT_RE.search(text)
    return _ParsedAction(
        thought=thought,
        action=action_match.group(1).strip(),
        action_input=input_match.group(1).strip() if input_match else "",
        raw=raw,
    )


def _merge_chunk(
    acc: dict[str, tuple[Chunk, float, str]],
    chunk: Chunk,
    score: float,
    source: str,
) -> None:
    """Insert/update chunk in accumulator, keeping the highest score."""
    existing = acc.get(chunk.chunk_id)
    if existing is None or score > existing[1]:
        acc[chunk.chunk_id] = (chunk, score, source)


def _build_evidence(
    acc: dict[str, tuple[Chunk, float, str]],
) -> tuple[RetrievedEvidence, ...]:
    """Sort accumulated chunks by descending score → tuple of evidence."""
    ordered = sorted(acc.values(), key=lambda item: item[1], reverse=True)
    return tuple(
        RetrievedEvidence(chunk=chunk, score=score, source=source)
        for chunk, score, source in ordered
    )


def _format_chunk_observation(
    tool: str,
    results: list[tuple[Chunk, float]],
) -> str:
    if not results:
        return f"{tool} returned 0 results."
    lines = [f"{tool} returned {len(results)} results:"]
    for chunk, score in results:
        snippet = chunk.text.replace("\n", " ")
        if len(snippet) > CHUNK_SNIPPET_MAX_CHARS:
            snippet = snippet[:CHUNK_SNIPPET_HEAD_CHARS] + "..."
        lines.append(f"- [{chunk.chunk_id}] (score={score:.3f}) {snippet}")
    return "\n".join(lines)


def _format_triples_observation(entity_id: str, triples: list[Triple]) -> str:
    if not triples:
        return f"kg_neighborhood({entity_id}) returned 0 triples."
    lines = [f"kg_neighborhood({entity_id}) returned {len(triples)} triples:"]
    lines.extend(f"- ({t.head}) -[{t.relation}]-> ({t.tail})" for t in triples)
    return "\n".join(lines)
