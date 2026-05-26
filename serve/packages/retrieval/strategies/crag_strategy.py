"""CRAG strategy — wraps the existing ``CRAGEvaluator`` for ADR-0017 §3.

Loop shape (one or two retrieval rounds):

1. ``crag.retrieve``      — initial coordinator search.
2. ``crag.evaluate``      — LLM-based grader scores chunks; bucket into
   confident / ambiguous / incorrect.
3. ``crag.rewrite``       — when the verdict is ``ambiguous`` or
   ``incorrect``, ask the rewriter for a step-back / decompose query.
4. ``crag.re_retrieve``   — fetch a second candidate set; merge.

Budget plumbing & SSE event emission follow the same conventions as
SelfRAGStrategy. ``terminated_reason="budget_exceeded"`` short-circuits
the loop the moment headroom drops below the next round's cost.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from packages.core.models import Chunk, Query
from packages.retrieval._internal.budget_check import (
    BudgetSnapshot,
    has_headroom_for,
)
from packages.retrieval.critics import CRAGEvaluator, GradeLabel
from packages.retrieval.protocols import (
    BudgetUsage,
    RetrievalBudget,
    RetrievalStep,
    RetrievalTrace,
    RetrievedEvidence,
    StepCost,
)
from packages.retrieval.rewriter import LLMQueryRewriter, RewriteSet

CRAG_STRATEGY_NAME: Literal["crag"] = "crag"
CRAG_DEFAULT_K: int = 8

CoordinatorSearchFn = Callable[[str, str, int], Awaitable[list[tuple[Chunk, float]]]]


@dataclass(frozen=True, slots=True)
class CRAGStrategyConfig:
    """Tunables for the CRAG retrieval loop."""

    candidate_k: int = CRAG_DEFAULT_K


class CRAGStrategy:
    """``RetrievalStrategy`` implementation of ADR-0017 §3 CRAG."""

    name: Literal["crag"] = CRAG_STRATEGY_NAME

    def __init__(
        self,
        *,
        evaluator: CRAGEvaluator,
        rewriter: LLMQueryRewriter,
        coordinator_search: CoordinatorSearchFn,
        config: CRAGStrategyConfig | None = None,
    ) -> None:
        self._evaluator = evaluator
        self._rewriter = rewriter
        self._coordinator_search = coordinator_search
        self._config = config or CRAGStrategyConfig()

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

        # ---- Step 0: initial retrieve --------------------------------------
        initial_hits = await self._coordinator_search(
            library_id, query.text, self._config.candidate_k
        )
        evidence = _to_evidence(initial_hits)
        steps.append(
            RetrievalStep(
                step_idx=0,
                thought="crag.retrieve initial candidate set",
                action="crag.retrieve",
                action_input=query.text,
                observation=f"retrieved {len(evidence)} candidates",
            )
        )
        usage = _add_step(usage, llm_calls=0)

        # ---- Step 1: evaluate ---------------------------------------------
        snapshot = BudgetSnapshot(budget=budget, usage=usage, started_at_monotonic=started)
        if not has_headroom_for(snapshot, llm_calls=1):
            return _trace(library_id, query, steps, usage, started, "budget_exceeded")

        assessment = await self._evaluator.evaluate(query.text, list(evidence))
        steps.append(
            RetrievalStep(
                step_idx=len(steps),
                thought=f"crag.evaluate verdict={assessment.overall.value}",
                action="crag.evaluate",
                action_input=query.text,
                observation=(
                    f"overall={assessment.overall.value} "
                    f"trigger_rewrite={assessment.trigger_rewrite}"
                ),
                cost=StepCost(llm_calls=1),
            )
        )
        usage = _add_step(usage, llm_calls=1)

        if assessment.overall is GradeLabel.CORRECT or not assessment.trigger_rewrite:
            return _trace(library_id, query, steps, usage, started, "answer_ready")

        # ---- Step 2: rewrite -----------------------------------------------
        snapshot = BudgetSnapshot(budget=budget, usage=usage, started_at_monotonic=started)
        if not has_headroom_for(snapshot, llm_calls=2):
            return _trace(library_id, query, steps, usage, started, "budget_exceeded")

        rewrite_set = await self._rewriter.rewrite(query.text)
        rewritten = _select_rewrite(rewrite_set, original=query.text)
        if rewritten is None:
            return _trace(library_id, query, steps, usage, started, "answer_ready")

        steps.append(
            RetrievalStep(
                step_idx=len(steps),
                thought="crag.rewrite produced step-back / decompose query",
                action="crag.rewrite",
                action_input=rewritten,
                observation="ready for re-retrieve",
                cost=StepCost(llm_calls=1),
            )
        )
        usage = _add_step(usage, llm_calls=1)

        # ---- Step 3: re-retrieve ------------------------------------------
        retry_hits = await self._coordinator_search(library_id, rewritten, self._config.candidate_k)
        retry_evidence = _to_evidence(retry_hits)
        merged = _merge_evidence(evidence, retry_evidence)
        steps.append(
            RetrievalStep(
                step_idx=len(steps),
                thought="crag.re_retrieve with rewritten query",
                action="crag.re_retrieve",
                action_input=rewritten,
                observation=(f"retrieved {len(retry_evidence)} additional, total={len(merged)}"),
            )
        )
        usage = _add_step(usage, llm_calls=0)

        return _trace(library_id, query, steps, usage, started, "answer_ready")


def _select_rewrite(rewrite_set: RewriteSet, *, original: str) -> str | None:
    for rq in rewrite_set.queries:
        if rq.strategy == "passthrough":
            continue
        if rq.rewritten and rq.rewritten.strip() != original.strip():
            return rq.rewritten
    return None


def _to_evidence(
    hits: list[tuple[Chunk, float]],
) -> tuple[RetrievedEvidence, ...]:
    return tuple(
        RetrievedEvidence(chunk=chunk, score=score, source="vector") for chunk, score in hits
    )


def _merge_evidence(
    existing: tuple[RetrievedEvidence, ...],
    new: tuple[RetrievedEvidence, ...],
) -> tuple[RetrievedEvidence, ...]:
    by_id: dict[str, RetrievedEvidence] = {ev.chunk.chunk_id: ev for ev in existing}
    for ev in new:
        prior = by_id.get(ev.chunk.chunk_id)
        if prior is None or ev.score > prior.score:
            by_id[ev.chunk.chunk_id] = ev
    return tuple(sorted(by_id.values(), key=lambda e: e.score, reverse=True))


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
        planner=CRAG_STRATEGY_NAME,
        steps=tuple(steps),
        budget_used=final_usage,
        terminated_reason=reason,
    )
