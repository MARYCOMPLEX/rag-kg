"""Wrap `HypothesisTask` for the worker.

The task layer (M5) does path mining + LLM hypothesis generation; this
wrapper:

- Runs the task inside `JobContext` so status / events / notifications
  land in the standard pipeline.
- Forwards stage events from the task into the SSE bus (path_mining /
  llm_generate / score / rank).
- Persists a `cost_updated` event after the run.

Three-axis scoring (ADR-0020) lives inside the task — this wrapper does
not duplicate the formula.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

import structlog

from apps.worker.jobs._stages import StageEmitter, make_stage_emitter
from apps.worker.jobs.base import JobContext, job_lifecycle
from packages.indexing.protocols import GraphIndex
from packages.llm.protocols import LLMClient
from packages.observability import with_span
from packages.orchestration.queue import TaskEvent, TaskEventType
from packages.orchestration.tasks.hypothesis_task import (
    HypothesisTask,
    HypothesisTaskConfig,
)

logger = structlog.get_logger(__name__)

_HYPOTHESIZE_TIMEOUT_S = 600.0


async def run(
    ctx: dict[str, Any],
    *,
    library_id: str,
    task_id: str,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    """Generate KG-grounded hypotheses for a (head, tail) entity pair."""
    jc = JobContext.from_arq(
        ctx, library_id=library_id, task_id=task_id, task_type="run_hypothesize"
    )
    emitter = make_stage_emitter(jc)
    head_entity_id = str(input_payload["head_entity_id"])
    tail_entity_id = str(input_payload["tail_entity_id"])

    async with job_lifecycle(jc):
        async with asyncio.timeout(_HYPOTHESIZE_TIMEOUT_S):
            return await _run_inner(jc, ctx, emitter, head_entity_id, tail_entity_id)


async def _run_inner(
    jc: JobContext,
    ctx: dict[str, Any],
    emitter: StageEmitter,
    head_entity_id: str,
    tail_entity_id: str,
) -> dict[str, Any]:
    graph_index = cast(GraphIndex, ctx["graph_index"])
    llm = cast(LLMClient, ctx["llm_client"])
    config = cast(HypothesisTaskConfig | None, ctx.get("hypothesis_task_config"))

    task = HypothesisTask(graph_index=graph_index, llm=llm, config=config)

    async with with_span(
        "worker.run_hypothesize",
        library_id=jc.library_id,
        task_id=jc.task_id,
        head=head_entity_id,
        tail=tail_entity_id,
    ):
        result = await task.run(
            jc.library_id,
            head_entity_id,
            tail_entity_id,
            stage_emitter=emitter,
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
        "head_entity_id": head_entity_id,
        "tail_entity_id": tail_entity_id,
        "hypothesis_count": len(result.hypotheses),
        "cost_usd": float(result.cost.cost_usd),
    }


__all__ = ["run"]
