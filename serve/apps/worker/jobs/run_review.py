"""Wrap `ReviewGenerationTask` for the worker.

The task layer (`packages/orchestration/tasks/review_task.py`) does the
actual outline → sections → abstract pipeline. This wrapper adds:

- ``JobContext`` lifecycle (status row + terminal events).
- A stage emitter so the task fires SSE events without importing Redis.
- Result pointer write — the rendered review markdown is persisted to
  the result store when one is wired into ``ctx``; otherwise we leave the
  pointer empty and the API serves the result inline from the row.
- Cost roll-up (`cost_updated` event after the run).

The job stays small: it does not build retrieval planners or LLM clients;
those are pulled from ``ctx`` like every other adapter dependency.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, cast

import structlog

from apps.worker.jobs._stages import StageEmitter, make_stage_emitter
from apps.worker.jobs.base import JobContext, job_lifecycle
from packages.llm.protocols import LLMClient
from packages.observability import with_span
from packages.orchestration.protocols import ReviewResult
from packages.orchestration.queue import TaskEvent, TaskEventType
from packages.orchestration.tasks.review_task import (
    ReviewGenerationTask,
    ReviewGenerationTaskConfig,
)
from packages.retrieval.protocols import RetrievalPlanner

logger = structlog.get_logger(__name__)

_REVIEW_TIMEOUT_S = 1800.0


class _ResultWriterLike(Protocol):
    """Minimal contract for "write the final markdown blob somewhere".

    Production wires a MinIO-backed writer; tests can pass a callable
    that returns a fake key. Returning the storage key (e.g.
    ``s3://kb/<lib>/reviews/<task_id>.md``) lets the API render a stable
    download link from the `tasks.result_pointer` column.
    """

    async def write(
        self,
        library_id: str,
        task_id: str,
        kind: str,
        content: bytes,
    ) -> str: ...


async def run(
    ctx: dict[str, Any],
    *,
    library_id: str,
    task_id: str,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    """Run a literature-review task; persist the result pointer."""
    jc = JobContext.from_arq(ctx, library_id=library_id, task_id=task_id, task_type="run_review")
    emitter = make_stage_emitter(jc)
    topic = str(input_payload["topic"])
    citation_style = cast(
        Literal["numeric", "author_year"],
        input_payload.get("citation_style", "numeric"),
    )

    async with job_lifecycle(jc):
        async with asyncio.timeout(_REVIEW_TIMEOUT_S):
            return await _run_inner(jc, ctx, emitter, topic, citation_style)


async def _run_inner(
    jc: JobContext,
    ctx: dict[str, Any],
    emitter: StageEmitter,
    topic: str,
    citation_style: Literal["numeric", "author_year"],
) -> dict[str, Any]:
    planner = cast(RetrievalPlanner, ctx["retrieval_planner"])
    llm = cast(LLMClient, ctx["llm_client"])
    writer = cast(_ResultWriterLike | None, ctx.get("result_writer"))
    config = cast(ReviewGenerationTaskConfig | None, ctx.get("review_task_config"))

    task = ReviewGenerationTask(planner=planner, llm=llm, config=config)

    async with with_span(
        "worker.run_review",
        library_id=jc.library_id,
        task_id=jc.task_id,
    ):
        result = await task.run(
            jc.library_id,
            topic,
            citation_style=citation_style,
            stage_emitter=emitter,
        )
        await _emit_review_result_events(jc, result)

        markdown = _render_review_markdown(result)
        result_pointer = ""
        if writer is not None:
            result_pointer = await writer.write(
                jc.library_id, jc.task_id, "review", markdown.encode("utf-8")
            )

        await jc.store.update_status(
            jc.library_id,
            jc.task_id,
            status="running",
            result_pointer=result_pointer or None,
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
        "topic": topic,
        "section_count": len(result.sections),
        "result_pointer": result_pointer,
        "cost_usd": float(result.cost.cost_usd),
    }


def _render_review_markdown(result: ReviewResult) -> str:
    """Render `ReviewResult` to a top-level markdown document."""
    parts: list[str] = [f"# {result.topic}", ""]
    if result.abstract:
        parts.extend(["## Abstract", "", result.abstract, ""])
    for section in result.sections:
        parts.extend([f"## {section.heading}", "", section.body, ""])
    return "\n".join(parts)


async def _emit_review_result_events(jc: JobContext, result: ReviewResult) -> None:
    """Publish frontend review stream events derived from the real result."""
    draft_tokens = 0
    citations = _frontend_citations(result)
    for index, section in enumerate(result.sections, start=1):
        draft_tokens += _token_estimate(section.body)
        await jc.events.emit(
            TaskEvent(
                library_id=jc.library_id,
                task_id=jc.task_id,
                seq=0,
                timestamp=datetime.now(UTC),
                type=TaskEventType.STAGE_COMPLETED,
                stage_name="draft_delta",
                payload={
                    "sectionId": _section_id(section.heading, index),
                    "markdownDelta": f"## {section.heading}\n\n{section.body}",
                    "citations": [citation.chunk_id for citation in section.citations],
                    "draftTokens": draft_tokens,
                },
            )
        )
    if citations:
        await jc.events.emit(
            TaskEvent(
                library_id=jc.library_id,
                task_id=jc.task_id,
                seq=0,
                timestamp=datetime.now(UTC),
                type=TaskEventType.CITATION_ADDED,
                payload={"citations": citations},
            )
        )


def _frontend_citations(result: ReviewResult) -> list[dict[str, object]]:
    seen: set[str] = set()
    citations: list[dict[str, object]] = []
    for section in result.sections:
        for citation in section.citations:
            if citation.chunk_id in seen:
                continue
            seen.add(citation.chunk_id)
            citations.append(
                {
                    "id": citation.chunk_id,
                    "type": "chunk",
                    "author": citation.doc_id,
                    "isNew": True,
                }
            )
    return citations


def _section_id(heading: str, index: int) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in heading).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or f"section-{index}"


def _token_estimate(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


__all__ = ["run"]
