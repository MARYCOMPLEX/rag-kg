"""QATask — minimal RAG QA pipeline.

retrieve → stuff context → LLM answer → extract citations.

Conversation-aware variant `answer_in_conversation()` adds the M8 layered
context pipeline on top of `answer()`:
  rewrite → compact prior turns → compose layered prompt → llm → persist
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from packages.core.models import Query
from packages.llm.protocols import LLMClient, Message
from packages.observability.instrumentation import instrumented
from packages.observability.metrics import TASK_DURATION_SECONDS
from packages.orchestration.protocols import (
    AnsweredQuery,
    Citation,
    TokenUsage,
)
from packages.retrieval.protocols import RetrievalPlanner, RetrievedEvidence

# Context-management deps are imported lazily to avoid a circular import:
# `packages.context.protocols` re-exports `Citation` from this package, so
# loading the context subsystem at top-level here would trigger an
# orchestration↔context cycle during package init. Tests still type-check
# fine because all references below sit behind `TYPE_CHECKING`.
if TYPE_CHECKING:
    from packages.context.compactor import CompactionResult, TurnCompactor
    from packages.context.memory import ResearchMemory
    from packages.context.prompt_composer import PromptComposer
    from packages.context.protocols import (
        ComposedPrompt,
        ContextBudget,
        Conversation,
        MemoryEntry,
        RewriteResult,
        Turn,
    )
    from packages.context.query_rewriter import QueryRewriter
    from packages.context.service import ContextService

_SYSTEM_PROMPT = """You are a research assistant. Answer the user's question using ONLY the
provided evidence. Every factual claim MUST cite at least one evidence item
using [id] markers, where `id` is the chunk_id shown in brackets next to the
evidence text (e.g., "GraphRAG uses Leiden clustering [doc::p2::3]" or
"This corpus covers RAG variants [community::c0:5]").

Rules:
- If the evidence does not support a confident answer, say so explicitly.
- Do not invent facts not present in the evidence.
- Cite evidence inline, not at the end.
- Be concise — 2 to 5 sentences unless the question demands more depth."""

_USER_PROMPT_TEMPLATE = """Question: {question}

Evidence chunks (each prefixed with its chunk_id):

{context}

Answer the question, citing chunk_ids inline."""

# Permissive: capture anything inside [...] that looks like an identifier.
# We then validate it against the actual evidence chunk_ids (which are the
# only authoritative source). This handles both:
#   - chunk-level: [2210.03629::p3::18]
#   - community-level: [community::c0:5]
_CITATION_PATTERN = re.compile(r"\[([a-zA-Z0-9:_\-/.]+)\]")

_DEFAULT_MAX_TOKENS = 800


class ContextRuntimeSettings(BaseModel):
    """Per-call snapshot of context-management settings.

    Captured at the route layer so a single conversation turn sees a
    consistent set of values even if Settings are reloaded mid-flight.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    recent_turns_window: int = Field(default=4, ge=0, le=50)
    memory_max_entries_in_prompt: int = Field(default=5, ge=0, le=50)
    compact_summary_max_tokens: int = Field(default=512, ge=64, le=4096)
    rewrite_enabled: bool = True


class QATask:
    """RAG QA: retrieve → stuff → answer with inline citations."""

    def __init__(
        self,
        *,
        planner: RetrievalPlanner,
        llm: LLMClient,
        max_context_chunks: int = 8,
        llm_timeout_s: float = 120.0,
    ) -> None:
        self._planner = planner
        self._llm = llm
        self._max_context_chunks = max_context_chunks
        self._llm_timeout_s = llm_timeout_s

    @instrumented(
        op_name="task.qa.answer",
        component="task",
        histogram=TASK_DURATION_SECONDS,
        histogram_labels={"task": "qa"},
        label_from_arg={"library_id": "library_id"},
    )
    async def answer(self, library_id: str, question: str) -> AnsweredQuery:
        started = time.perf_counter()

        retrieval = await self._retrieve(library_id, question)
        if not retrieval:
            return self._no_evidence_answer(library_id, question, started)

        evidence = retrieval[: self._max_context_chunks]
        context = self._format_context(evidence)
        messages = [
            Message(role="system", content=_SYSTEM_PROMPT),
            Message(
                role="user",
                content=_USER_PROMPT_TEMPLATE.format(question=question, context=context),
            ),
        ]

        llm_resp = await self._llm.complete(
            messages,
            temperature=0.0,
            max_tokens=_DEFAULT_MAX_TOKENS,
            timeout_s=self._llm_timeout_s,
        )
        citations = self._extract_citations(llm_resp.text, evidence)

        return AnsweredQuery(
            library_id=library_id,
            question=question,
            answer=llm_resp.text,
            citations=tuple(citations),
            retrieved=evidence,
            model=llm_resp.model,
            tokens=TokenUsage(
                input_tokens=llm_resp.input_tokens,
                output_tokens=llm_resp.output_tokens,
                cost_usd=llm_resp.cost_usd,
            ),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    async def answer_in_conversation(
        self,
        *,
        library_id: str,
        conversation: Conversation,
        question: str,
        context_service: ContextService,
        rewriter: QueryRewriter | None,
        compactor: TurnCompactor | None,
        memory: ResearchMemory | None,
        composer: PromptComposer | None,
        settings_snapshot: ContextRuntimeSettings,
        library_card: str = "",
        budget: ContextBudget | None = None,
    ) -> AnsweredQuery:
        """Conversation-aware variant: rewrite → compact → compose → answer.

        See ADR-0008 §3 for the full pipeline diagram. The single-shot
        `answer()` remains the supported back-compat surface.
        """
        # Lazy import to break the orchestration↔context package cycle.
        from packages.context.protocols import ContextBudget as _ContextBudget

        started = time.perf_counter()
        budget = budget or _ContextBudget()

        prior_turns = await context_service.history(conversation.conversation_id)
        recent = self._select_recent_turns(prior_turns, settings_snapshot)
        rewrite_result = await self._rewrite_question(
            question=question,
            recent_turns=recent,
            rewriter=rewriter,
            settings_snapshot=settings_snapshot,
        )

        compaction = await self._compact_history(
            conversation=conversation,
            prior_turns=prior_turns,
            recent=recent,
            compactor=compactor,
            settings_snapshot=settings_snapshot,
        )
        if compaction.summary != conversation.summary:
            conversation = await context_service.update_summary(
                conversation=conversation, summary=compaction.summary
            )

        retrieval = await self._retrieve(library_id, rewrite_result.rewritten)
        await context_service.append_user_turn(
            conversation=conversation,
            content=question,
            rewritten_query=(rewrite_result.rewritten if rewrite_result.used_history else None),
        )

        if not retrieval:
            return await self._no_evidence_in_conversation(
                library_id=library_id,
                question=question,
                conversation=conversation,
                context_service=context_service,
                started=started,
            )

        evidence = retrieval[: self._max_context_chunks]
        messages = self._build_messages_for_conversation(
            question=question,
            evidence=evidence,
            memory_entries=await self._select_memory(
                library_id=library_id,
                memory=memory,
                rewritten=rewrite_result.rewritten,
                settings_snapshot=settings_snapshot,
            ),
            summary=compaction.summary,
            recent_turns=compaction.kept_turns,
            composer=composer,
            library_card=library_card,
            budget=budget,
        )

        llm_resp = await self._llm.complete(
            messages,
            temperature=0.0,
            max_tokens=_DEFAULT_MAX_TOKENS,
            timeout_s=self._llm_timeout_s,
        )
        citations = self._extract_citations(llm_resp.text, evidence)

        await context_service.append_assistant_turn(
            conversation=conversation,
            content=llm_resp.text,
            citations=tuple(citations),
            model=llm_resp.model,
            input_tokens=llm_resp.input_tokens,
            output_tokens=llm_resp.output_tokens,
        )

        return AnsweredQuery(
            library_id=library_id,
            question=question,
            answer=llm_resp.text,
            citations=tuple(citations),
            retrieved=evidence,
            model=llm_resp.model,
            tokens=TokenUsage(
                input_tokens=llm_resp.input_tokens,
                output_tokens=llm_resp.output_tokens,
                cost_usd=llm_resp.cost_usd,
            ),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    async def _retrieve(self, library_id: str, query_text: str) -> tuple[RetrievedEvidence, ...]:
        query = Query(
            library_id=library_id,
            text=query_text,
            type="single-hop",
            max_results=self._max_context_chunks,
        )
        result = await self._planner.plan_and_retrieve(library_id, query)
        return result.evidence

    @staticmethod
    def _select_recent_turns(
        prior_turns: tuple[Turn, ...],
        settings_snapshot: ContextRuntimeSettings,
    ) -> tuple[Turn, ...]:
        window = settings_snapshot.recent_turns_window
        if window <= 0:
            return ()
        return tuple(prior_turns[-window:])

    @staticmethod
    async def _rewrite_question(
        *,
        question: str,
        recent_turns: tuple[Turn, ...],
        rewriter: QueryRewriter | None,
        settings_snapshot: ContextRuntimeSettings,
    ) -> RewriteResult:
        # Lazy import — see top-of-file note about the package cycle.
        from packages.context.protocols import RewriteResult as _RewriteResult

        if rewriter is None or not settings_snapshot.rewrite_enabled or not recent_turns:
            return _RewriteResult(
                original=question,
                rewritten=question,
                confidence=1.0,
                used_history=False,
            )
        return await rewriter.rewrite(question=question, recent_turns=recent_turns)

    @staticmethod
    async def _compact_history(
        *,
        conversation: Conversation,
        prior_turns: tuple[Turn, ...],
        recent: tuple[Turn, ...],
        compactor: TurnCompactor | None,
        settings_snapshot: ContextRuntimeSettings,
    ) -> CompactionResult:
        # Lazy import — see top-of-file note about the package cycle.
        from packages.context.compactor import (
            CompactionResult as _CompactionResult,
        )

        if compactor is None or len(prior_turns) <= settings_snapshot.recent_turns_window:
            return _CompactionResult(
                summary=conversation.summary,
                kept_turns=recent,
                dropped_turns=0,
                summary_tokens=0,
                kept_tokens=0,
            )
        return await compactor.fit_auto(conversation.summary, prior_turns)

    @staticmethod
    async def _select_memory(
        *,
        library_id: str,
        memory: ResearchMemory | None,
        rewritten: str,
        settings_snapshot: ContextRuntimeSettings,
    ) -> tuple[MemoryEntry, ...]:
        if memory is None or settings_snapshot.memory_max_entries_in_prompt == 0:
            return ()
        return await memory.select_relevant(
            library_id,
            rewritten,
            limit=settings_snapshot.memory_max_entries_in_prompt,
        )

    @classmethod
    def _build_messages_for_conversation(
        cls,
        *,
        question: str,
        evidence: tuple[RetrievedEvidence, ...],
        memory_entries: tuple[MemoryEntry, ...],
        summary: str,
        recent_turns: tuple[Turn, ...],
        composer: PromptComposer | None,
        library_card: str,
        budget: ContextBudget,
    ) -> list[Message]:
        evidence_block = cls._format_context(evidence)
        if composer is None:
            return [
                Message(role="system", content=_SYSTEM_PROMPT),
                Message(
                    role="user",
                    content=_USER_PROMPT_TEMPLATE.format(question=question, context=evidence_block),
                ),
            ]
        composed: ComposedPrompt = composer.compose(
            library_card=library_card,
            memory_entries=memory_entries,
            summary=summary,
            recent_turns=recent_turns,
            evidence_block=evidence_block,
            user_question=question,
            budget=budget,
        )
        return [
            Message(role="system", content=composed.system),
            Message(role="user", content=composed.user),
        ]

    @staticmethod
    def _no_evidence_answer(library_id: str, question: str, started: float) -> AnsweredQuery:
        return AnsweredQuery(
            library_id=library_id,
            question=question,
            answer=(
                "I could not find any relevant evidence in this library to answer this question."
            ),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    async def _no_evidence_in_conversation(
        self,
        *,
        library_id: str,
        question: str,
        conversation: Conversation,
        context_service: ContextService,
        started: float,
    ) -> AnsweredQuery:
        no_ev = self._no_evidence_answer(library_id, question, started)
        await context_service.append_assistant_turn(
            conversation=conversation,
            content=no_ev.answer,
            citations=(),
            model="",
            input_tokens=0,
            output_tokens=0,
        )
        return no_ev

    @staticmethod
    def _format_context(evidence: tuple[RetrievedEvidence, ...]) -> str:
        parts: list[str] = [f"[{ev.chunk.chunk_id}] {ev.chunk.text}" for ev in evidence]
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _extract_citations(answer: str, evidence: tuple[RetrievedEvidence, ...]) -> list[Citation]:
        cited_ids = {m.group(1) for m in _CITATION_PATTERN.finditer(answer)}
        by_chunk_id = {ev.chunk.chunk_id: ev for ev in evidence}
        citations: list[Citation] = []
        for chunk_id in cited_ids:
            ev = by_chunk_id.get(chunk_id)
            if ev is None:
                continue
            snippet = ev.chunk.text[:200]
            citations.append(
                Citation(
                    chunk_id=ev.chunk.chunk_id,
                    doc_id=ev.chunk.doc_id,
                    page=ev.chunk.page,
                    snippet=snippet,
                )
            )
        return citations
