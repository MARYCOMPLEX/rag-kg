"""Wrap `CrossPaperReasoningTask` for the worker.

Adds JobContext lifecycle + SSE stage events; the task layer itself does
the decompose / per-sub / aggregate pipeline. KG-path search is a v1.1
nice-to-have — the wrapper currently passes an empty `paths=()` tuple,
which the task records on the result so frontend renders the sub-step
view. When a path-search adapter is wired into ``ctx``, this wrapper
calls it between decompose and aggregate.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import structlog

from apps.worker.jobs._stages import StageEmitter, make_stage_emitter
from apps.worker.jobs.base import JobContext, job_lifecycle
from packages.llm.protocols import LLMClient
from packages.observability import with_span
from packages.orchestration.protocols import ReasoningPath
from packages.orchestration.queue import TaskEvent, TaskEventType
from packages.orchestration.tasks.reasoning_task import (
    CrossPaperReasoningTask,
    CrossPaperReasoningTaskConfig,
)
from packages.retrieval.protocols import RetrievalPlanner

logger = structlog.get_logger(__name__)

_REASON_TIMEOUT_S = 900.0


class _PathSearcherLike(Protocol):
    """Optional pluggable KG path-search service (ADR-0010 stage `kg_path_search`).

    Implementations live in `packages/retrieval/` once landed; the worker
    only consumes the pre-computed paths and feeds them into the task.
    """

    async def search(self, library_id: str, question: str) -> tuple[ReasoningPath, ...]: ...


async def run(
    ctx: dict[str, Any],
    *,
    library_id: str,
    task_id: str,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    """Run a multi-hop cross-paper reasoning task."""
    jc = JobContext.from_arq(ctx, library_id=library_id, task_id=task_id, task_type="run_reason")
    emitter = make_stage_emitter(jc)
    question = str(input_payload["question"])

    async with job_lifecycle(jc):
        async with asyncio.timeout(_REASON_TIMEOUT_S):
            return await _run_inner(jc, ctx, emitter, question)


async def _run_inner(
    jc: JobContext,
    ctx: dict[str, Any],
    emitter: StageEmitter,
    question: str,
) -> dict[str, Any]:
    planner = cast(RetrievalPlanner, ctx["retrieval_planner"])
    llm = cast(LLMClient, ctx["llm_client"])
    config = cast(CrossPaperReasoningTaskConfig | None, ctx.get("reasoning_task_config"))
    path_searcher = cast(_PathSearcherLike | None, ctx.get("kg_path_searcher"))

    task = CrossPaperReasoningTask(planner=planner, llm=llm, config=config)

    async with with_span(
        "worker.run_reason",
        library_id=jc.library_id,
        task_id=jc.task_id,
    ):
        paths = await _maybe_search_paths(path_searcher, jc.library_id, question)
        result = await task.run(
            jc.library_id,
            question,
            stage_emitter=emitter,
            paths=paths,
        )

        await jc.store.update_status(
            jc.library_id,
            jc.task_id,
            status="running",
            cost_usd=float(result.cost.cost_usd),
        )

        await jc.events.emit(
            TaskEvent(
                library_id=jc.library_id,
                task_id=jc.task_id,
                seq=0,
                timestamp=datetime.now(UTC),
                type=TaskEventType.COST_UPDATED,
                payload={
                    "tokens_in": int(result.cost.input_tokens),
                    "tokens_out": int(result.cost.output_tokens),
                    "cost_usd": float(result.cost.cost_usd),
                },
            )
        )

    return {
        "question": question,
        "sub_step_count": len(result.sub_steps),
        "path_count": len(result.paths),
        "citation_count": len(result.citations),
        "cost_usd": float(result.cost.cost_usd),
    }


async def _maybe_search_paths(
    searcher: _PathSearcherLike | None,
    library_id: str,
    question: str,
) -> tuple[ReasoningPath, ...]:
    """Run the optional path searcher; on failure return an empty tuple.

    Path search is observability-grade — it must never block the actual
    reasoning answer (which the LLM produces from sub-step retrieval).
    """
    if searcher is None:
        return ()
    try:
        return await searcher.search(library_id, question)
    except Exception as exc:
        await logger.awarning("kg_path_search_failed", error=str(exc))
        return ()


__all__ = ["run"]
