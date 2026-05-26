"""Self-RAG strategy — prompt-based reflection loop wrapping ``SelfRAGCritic``.

Implements ADR-0017 §2: simulate the four reflection-token roles via
prompts (Retrieve / IsRel / IsSup / IsUse) without fine-tuning the base
LLM. The existing ``SelfRAGCritic`` implements the IsSup grader; we
reuse it as the post-draft alignment check and wire decompose +
re-retrieve via the ``LLMQueryRewriter``.

Event emission (ADR-0010): each loop iteration writes a ``RetrievalStep``
to the trace; the surrounding facade emits SSE
``strategy_self_rag_step_<n>`` using those steps.

Budget plumbing (ADR-0017 §2 + ADR_REVIEW R4): every reflection round
counts as ``llm_calls += 1``; we short-circuit the loop the moment
``has_headroom_for`` returns False.
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
from packages.retrieval.critics import GradeLabel, SelfRAGCritic
from packages.retrieval.protocols import (
    BudgetUsage,
    RetrievalBudget,
    RetrievalStep,
    RetrievalTrace,
    RetrievedEvidence,
    StepCost,
)
from packages.retrieval.rewriter import LLMQueryRewriter, RewriteSet

SELF_RAG_STRATEGY_NAME: Literal["self_rag"] = "self_rag"
SELF_RAG_DEFAULT_K: int = 8
DEFAULT_SUPPORT_THRESHOLD: float = 0.5

CoordinatorSearchFn = Callable[[str, str, int], Awaitable[list[tuple[Chunk, float]]]]


@dataclass(frozen=True, slots=True)
class SelfRAGStrategyConfig:
    """Tunables for the Self-RAG retrieval loop."""

    candidate_k: int = SELF_RAG_DEFAULT_K
    support_threshold: float = DEFAULT_SUPPORT_THRESHOLD


class SelfRAGStrategy:
    """``RetrievalStrategy`` implementation of ADR-0017 §2 Self-RAG."""

    name: Literal["self_rag"] = SELF_RAG_STRATEGY_NAME

    def __init__(
        self,
        *,
        critic: SelfRAGCritic,
        rewriter: LLMQueryRewriter,
        coordinator_search: CoordinatorSearchFn,
        config: SelfRAGStrategyConfig | None = None,
    ) -> None:
        self._critic = critic
        self._rewriter = rewriter
        self._coordinator_search = coordinator_search
        self._config = config or SelfRAGStrategyConfig()

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

        # ---- Step 1: initial retrieve --------------------------------------
        snapshot = BudgetSnapshot(budget=budget, usage=usage, started_at_monotonic=started)
        if not has_headroom_for(snapshot, llm_calls=0):
            return _terminated(library_id, query, steps, usage, started, "budget_exceeded")

        initial_hits = await self._coordinator_search(
            library_id, query.text, self._config.candidate_k
        )
        evidence = _to_evidence(initial_hits)
        steps.append(
            RetrievalStep(
                step_idx=0,
                thought="self_rag.retrieve initial candidate set",
                action="self_rag.retrieve",
                action_input=query.text,
                observation=f"retrieved {len(evidence)} candidates",
            )
        )
        usage = _add_step(usage, llm_calls=0)

        # ---- Step 2: IsSup reflection on first draft -----------------------
        snapshot = BudgetSnapshot(budget=budget, usage=usage, started_at_monotonic=started)
        if not has_headroom_for(snapshot, llm_calls=1):
            return _terminated(library_id, query, steps, usage, started, "budget_exceeded")

        first_draft = _draft_text(query, evidence)
        assessment = await self._critic.critique(first_draft, list(evidence))
        steps.append(
            RetrievalStep(
                step_idx=len(steps),
                thought="self_rag.is_sup reflection on initial draft",
                action="self_rag.is_sup",
                action_input="<draft>",
                observation=(
                    f"overall_support={assessment.overall_support:.2f} "
                    f"unsupported={assessment.unsupported_claim_count}"
                ),
                cost=StepCost(llm_calls=1),
            )
        )
        usage = _add_step(usage, llm_calls=1)

        if assessment.overall_support >= self._config.support_threshold:
            return _trace(library_id, query, steps, usage, started, "answer_ready")

        # ---- Step 3: rewrite + re-retrieve ---------------------------------
        snapshot = BudgetSnapshot(budget=budget, usage=usage, started_at_monotonic=started)
        if not has_headroom_for(snapshot, llm_calls=2):
            return _terminated(library_id, query, steps, usage, started, "budget_exceeded")

        rewrite_set = await self._rewriter.rewrite(query.text)
        rewritten = _select_rewrite(rewrite_set, original=query.text)
        if rewritten is None:
            return _trace(library_id, query, steps, usage, started, "answer_ready")

        steps.append(
            RetrievalStep(
                step_idx=len(steps),
                thought="self_rag.rewrite produced step-back / decompose query",
                action="self_rag.rewrite",
                action_input=rewritten,
                observation="ready for re-retrieve",
                cost=StepCost(llm_calls=1),
            )
        )
        usage = _add_step(usage, llm_calls=1)

        retry_hits = await self._coordinator_search(library_id, rewritten, self._config.candidate_k)
        retry_evidence = _to_evidence(retry_hits)
        merged_evidence = _merge_evidence(evidence, retry_evidence)

        steps.append(
            RetrievalStep(
                step_idx=len(steps),
                thought="self_rag.re_retrieve with rewritten query",
                action="self_rag.re_retrieve",
                action_input=rewritten,
                observation=f"retrieved {len(retry_evidence)} additional candidates",
            )
        )
        usage = _add_step(usage, llm_calls=0)

        # ---- Step 4: final IsSup reflection --------------------------------
        snapshot = BudgetSnapshot(budget=budget, usage=usage, started_at_monotonic=started)
        if not has_headroom_for(snapshot, llm_calls=1):
            return _terminated(library_id, query, steps, usage, started, "budget_exceeded")

        final_draft = _draft_text(query, merged_evidence)
        final_assessment = await self._critic.critique(final_draft, list(merged_evidence))
        steps.append(
            RetrievalStep(
                step_idx=len(steps),
                thought="self_rag.is_sup final reflection after re-retrieve",
                action="self_rag.is_sup",
                action_input="<final_draft>",
                observation=(f"overall_support={final_assessment.overall_support:.2f}"),
                cost=StepCost(llm_calls=1),
            )
        )
        usage = _add_step(usage, llm_calls=1)

        return _trace(library_id, query, steps, usage, started, "answer_ready")


def _select_rewrite(rewrite_set: RewriteSet, *, original: str) -> str | None:
    """Pick the first non-passthrough, non-trivial rewrite from the set."""
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
    """Dedupe by chunk_id, keeping the higher score."""
    by_id: dict[str, RetrievedEvidence] = {ev.chunk.chunk_id: ev for ev in existing}
    for ev in new:
        prior = by_id.get(ev.chunk.chunk_id)
        if prior is None or ev.score > prior.score:
            by_id[ev.chunk.chunk_id] = ev
    return tuple(sorted(by_id.values(), key=lambda e: e.score, reverse=True))


def _draft_text(query: Query, evidence: tuple[RetrievedEvidence, ...]) -> str:
    """Stub draft used for the IsSup reflection round.

    Self-RAG's IsSup gate critiques *answers*; we don't run the answer
    LLM inside the strategy (synthesis lives at the orchestration layer
    per CODING_STANDARDS §3). The stub provides a minimal draft of the
    form ``<query> -> [chunk_ids]`` so the critic has something to
    decompose into claims. When the critic short-circuits on empty
    drafts, that's still a faithful "no support" signal.
    """
    chunk_ids = [ev.chunk.chunk_id for ev in evidence[:5]]
    return f"Question: {query.text}\nCited chunks: {', '.join(chunk_ids) or 'none'}"


def _add_step(usage: BudgetUsage, *, llm_calls: int) -> BudgetUsage:
    """Return new BudgetUsage with one step appended (immutable)."""
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
        planner=SELF_RAG_STRATEGY_NAME,
        steps=tuple(steps),
        budget_used=final_usage,
        terminated_reason=reason,
    )


def _terminated(
    library_id: str,
    query: Query,
    steps: list[RetrievalStep],
    usage: BudgetUsage,
    started: float,
    reason: Literal["budget_exceeded", "timeout", "error", "no_evidence"],
) -> RetrievalTrace:
    return _trace(library_id, query, steps, usage, started, reason)


# Keep imported for potential future per-grade aggregation tightening.
_ = (GradeLabel,)
