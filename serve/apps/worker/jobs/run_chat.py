"""Worker wrapper for the frontend chat question lifecycle."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

from apps.worker.jobs.base import JobContext, job_lifecycle
from packages.context.compactor import TurnCompactor
from packages.context.memory import ResearchMemory
from packages.context.prompt_composer import PromptComposer
from packages.context.protocols import ContextBudget, Conversation
from packages.context.query_rewriter import QueryRewriter
from packages.context.service import ContextService
from packages.orchestration.protocols import AnsweredQuery
from packages.orchestration.queue import TaskEvent, TaskEventType
from packages.orchestration.tasks.qa_task import ContextRuntimeSettings

_CHAT_TIMEOUT_S = 1800.0
_TOKEN_CHUNK_SIZE = 48
_TOKEN_DELAY_S = 0.02


async def run(
    ctx: dict[str, Any],
    *,
    library_id: str,
    task_id: str,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    """Run a chat question against the durable QA pipeline."""
    jc = JobContext.from_arq(ctx, library_id=library_id, task_id=task_id, task_type="run_chat")
    question = str(input_payload["question"])
    conversation_id = str(input_payload["conversation_id"])

    async with job_lifecycle(jc):
        async with asyncio.timeout(_CHAT_TIMEOUT_S):
            return await _run_inner(jc, ctx, question, conversation_id)


async def _run_inner(
    jc: JobContext,
    ctx: dict[str, Any],
    question: str,
    conversation_id: str,
) -> dict[str, Any]:
    qa_task = ctx["qa_task"]
    context_service = cast(ContextService, ctx["context_service"])
    rewriter = cast(QueryRewriter | None, ctx.get("query_rewriter"))
    compactor = cast(TurnCompactor | None, ctx.get("turn_compactor"))
    memory = cast(ResearchMemory | None, ctx.get("research_memory"))
    composer = cast(PromptComposer | None, ctx.get("prompt_composer"))
    budget = cast(ContextBudget | None, ctx.get("context_budget")) or ContextBudget()
    settings = ctx["settings"]

    conversation = await _open_conversation(context_service, jc.library_id, conversation_id)
    answered: AnsweredQuery = await qa_task.answer_in_conversation(
        library_id=jc.library_id,
        conversation=conversation,
        question=question,
        context_service=context_service,
        rewriter=rewriter,
        compactor=compactor,
        memory=memory,
        composer=composer,
        settings_snapshot=_settings_snapshot(settings),
        library_card=f"library_id={jc.library_id}",
        budget=budget,
    )

    for chunk in _chunk_text(answered.answer):
        await jc.events.emit(
            TaskEvent(
                library_id=jc.library_id,
                task_id=jc.task_id,
                seq=0,
                timestamp=datetime.now(UTC),
                type=TaskEventType.TOKEN,
                payload={"token": chunk},
            )
        )
        await asyncio.sleep(_TOKEN_DELAY_S)

    evidence = _evidence_records(answered)
    if evidence:
        await jc.events.emit(
            TaskEvent(
                library_id=jc.library_id,
                task_id=jc.task_id,
                seq=0,
                timestamp=datetime.now(UTC),
                type=TaskEventType.STAGE_COMPLETED,
                stage_name="evidence",
                payload={"evidence": evidence},
            )
        )

    citation_ids = [citation.chunk_id for citation in answered.citations]
    if citation_ids:
        await jc.events.emit(
            TaskEvent(
                library_id=jc.library_id,
                task_id=jc.task_id,
                seq=0,
                timestamp=datetime.now(UTC),
                type=TaskEventType.CITATION_ADDED,
                payload={"citation_ids": citation_ids},
            )
        )

    return {
        "conversation_id": conversation.conversation_id,
        "citation_count": len(citation_ids),
        "evidence_count": len(evidence),
    }


async def _open_conversation(
    context_service: ContextService,
    library_id: str,
    conversation_id: str,
) -> Conversation:
    return await context_service.open(library_id=library_id, conversation_id=conversation_id)


def _settings_snapshot(settings: Any) -> ContextRuntimeSettings:
    return ContextRuntimeSettings(
        recent_turns_window=settings.context_recent_turns_window,
        memory_max_entries_in_prompt=settings.context_memory_max_entries_in_prompt,
        compact_summary_max_tokens=settings.context_compact_summary_max_tokens,
        rewrite_enabled=settings.rewrite_enabled,
    )


def _evidence_records(answered: AnsweredQuery) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for index, evidence in enumerate(answered.retrieved, start=1):
        page = evidence.chunk.page
        records.append(
            {
                "id": evidence.chunk.chunk_id,
                "label": f"[{index}]",
                "type": "chunk",
                "title": evidence.chunk.doc_id,
                "meta": f"p.{page}" if page is not None else "Page unknown",
                "score": f"{evidence.score:.3f}",
                "snippet": evidence.chunk.text[:500],
            }
        )
    if records:
        return records
    for index, citation in enumerate(answered.citations, start=1):
        records.append(
            {
                "id": citation.chunk_id,
                "label": f"[{index}]",
                "type": "chunk",
                "title": citation.doc_id,
                "meta": f"p.{citation.page}" if citation.page is not None else "Page unknown",
                "score": "cited",
                "snippet": citation.snippet,
            }
        )
    return records


def _chunk_text(text: str) -> list[str]:
    if not text:
        return []
    return [text[i : i + _TOKEN_CHUNK_SIZE] for i in range(0, len(text), _TOKEN_CHUNK_SIZE)]
