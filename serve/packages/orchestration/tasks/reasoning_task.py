"""CrossPaperReasoningTask — multi-hop QA via decompose / per-sub retrieve / aggregate.

Pipeline:
    1. Decompose the question into 2-5 narrower sub-questions (LLM, JSON output).
    2. For each sub-question, retrieve evidence (planner) and answer it
       with cited chunk_ids — runs in parallel under an asyncio.Semaphore.
    3. Aggregate the sub-answers into a final coherent answer (LLM),
       preserving the [chunk_id] citations.
    4. Citations are extracted by regex and validated against the union of
       chunk_ids actually retrieved across all sub-steps.

Failure modes (graceful):
    - Decompose call fails or returns invalid JSON → fallback to a single
      sub-question equal to the original question.
    - A per-sub LLM call fails → that ReasoningStep is recorded with empty
      answer; remaining sub-steps are preserved.
    - Final aggregate call fails → the final answer is the concatenation of
      the per-sub answers (still cited).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.core.models import Query
from packages.llm.protocols import LLMClient, LLMResponse, Message
from packages.orchestration.protocols import (
    Citation,
    CrossPaperReasoningResult,
    ReasoningPath,
    ReasoningStep,
    TaskBudget,
    TaskCost,
)
from packages.retrieval.protocols import RetrievalPlanner, RetrievedEvidence

# Optional async stage emitter; same shape as ReviewGenerationTask. The
# task itself never imports Redis — the worker job injects this.
type StageEmitter = Callable[[str, str, dict[str, object]], Awaitable[None]]

# === Prompts =================================================================

_DECOMPOSE_SYSTEM_PROMPT = """You decompose complex research questions for a multi-hop \
retrieval pipeline. Break the question into 2-4 narrower sub-questions, each \
answerable with a focused retrieval. Return JSON {"sub_questions": [...]}. Don't \
repeat the original question."""

_DECOMPOSE_USER_PROMPT_TEMPLATE = """Question: {question}

Return ONLY JSON, no prose, no markdown fences:
{{"sub_questions": ["...", "..."]}}"""

_SUB_SYSTEM_PROMPT = """Answer the sub-question in 2-3 sentences using ONLY the \
evidence. Cite chunk_ids inline [chunk_id]. If the evidence is insufficient, say so \
explicitly. Do not invent facts."""

_SUB_USER_PROMPT_TEMPLATE = """Sub-question: {sub_question}

Evidence (each prefixed with its chunk_id):

{context}

Answer the sub-question now, citing chunk_ids inline."""

_FINAL_SYSTEM_PROMPT = """Combine the sub-answers below into one coherent final answer \
to the original question. Preserve [chunk_id] citations. 4-8 sentences. Do not \
invent facts beyond the sub-answers."""

_FINAL_USER_PROMPT_TEMPLATE = """Original question: {question}

Sub-answers:

{sub_answers}

Write the final aggregated answer now, preserving [chunk_id] citations."""

# === Constants ===============================================================

_MIN_SUB_QUESTIONS = 2
_MAX_SUB_QUESTIONS_HARD = 5
_CITATION_PATTERN = re.compile(r"\[([a-zA-Z0-9:_\-/.]+)\]")
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


# === Config + internal models ===============================================


@dataclass(frozen=True, slots=True)
class CrossPaperReasoningTaskConfig:
    """Tunables for CrossPaperReasoningTask."""

    max_sub_questions: int = 4
    chunks_per_sub: int = 6
    llm_temperature: float = 0.0
    llm_max_tokens_decompose: int = 300
    llm_max_tokens_sub: int = 400
    llm_max_tokens_final: int = 600
    llm_timeout_s: float = 120.0
    sub_concurrency: int = 3


class _DecomposePayload(BaseModel):
    """Schema-validated decompose JSON output."""

    model_config = ConfigDict(extra="ignore")

    sub_questions: list[str] = Field(default_factory=list)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class _SubResult:
    """Internal: per-sub-step result used to assemble the final response."""

    step: ReasoningStep
    llm_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


# === Task ===================================================================


class CrossPaperReasoningTask:
    """Answers multi-hop questions via decompose → per-sub retrieve → aggregate."""

    def __init__(
        self,
        *,
        planner: RetrievalPlanner,
        llm: LLMClient,
        budget: TaskBudget | None = None,
        config: CrossPaperReasoningTaskConfig | None = None,
    ) -> None:
        self._planner = planner
        self._llm = llm
        self._budget = budget or TaskBudget()
        self._config = config or CrossPaperReasoningTaskConfig()

    async def run(
        self,
        library_id: str,
        question: str,
        *,
        stage_emitter: StageEmitter | None = None,
        paths: tuple[ReasoningPath, ...] = (),
    ) -> CrossPaperReasoningResult:
        started = time.perf_counter()
        cost = _MutableCost()
        emitter = _coerce_emitter(stage_emitter)

        await emitter("decompose", "stage_started", {"question": question})
        sub_questions = await self._decompose(question, cost)
        await emitter(
            "decompose",
            "stage_completed",
            {"sub_question_count": len(sub_questions)},
        )

        await emitter(
            "parallel_retrieve",
            "stage_started",
            {"sub_question_count": len(sub_questions)},
        )
        sub_results = await self._answer_sub_questions(library_id, sub_questions, cost)
        steps = tuple(sr.step for sr in sub_results)
        for sr in sub_results:
            cost.add(sr.llm_calls, sr.input_tokens, sr.output_tokens, sr.cost_usd)
        await emitter(
            "parallel_retrieve",
            "stage_completed",
            {"answered": sum(1 for s in steps if s.answer)},
        )

        # KG path search is supplied by the caller (worker job). When
        # absent the result simply omits structured paths — the Reasoning
        # UI then falls back to the sub-step view.
        await emitter("kg_path_search", "stage_started", {})
        await emitter("kg_path_search", "stage_completed", {"path_count": len(paths)})

        await emitter("aggregate", "stage_started", {})
        final_answer = await self._aggregate(question, steps, cost)
        citations = self._extract_citations(final_answer, steps)
        await emitter(
            "aggregate",
            "stage_completed",
            {"answer_chars": len(final_answer), "citation_count": len(citations)},
        )

        duration_ms = int((time.perf_counter() - started) * 1000)
        return CrossPaperReasoningResult(
            library_id=library_id,
            question=question,
            sub_steps=steps,
            paths=paths,
            final_answer=final_answer,
            citations=tuple(citations),
            cost=cost.to_task_cost(duration_ms),
        )

    # --- Decompose ----------------------------------------------------------

    async def _decompose(self, question: str, cost: _MutableCost) -> tuple[str, ...]:
        """LLM decomposes the question; on any failure falls back to [question]."""
        messages = [
            Message(role="system", content=_DECOMPOSE_SYSTEM_PROMPT),
            Message(
                role="user",
                content=_DECOMPOSE_USER_PROMPT_TEMPLATE.format(question=question),
            ),
        ]
        try:
            resp = await self._llm.complete(
                messages,
                temperature=self._config.llm_temperature,
                max_tokens=self._config.llm_max_tokens_decompose,
                timeout_s=self._config.llm_timeout_s,
            )
        except Exception:
            return (question,)

        cost.add_response(resp)

        parsed = _parse_decompose(resp.text)
        if not parsed:
            return (question,)

        cap = min(self._config.max_sub_questions, _MAX_SUB_QUESTIONS_HARD)
        clipped = parsed[:cap]
        if len(clipped) < _MIN_SUB_QUESTIONS:
            return (question,)
        return tuple(clipped)

    # --- Per-sub answer (parallel) -----------------------------------------

    async def _answer_sub_questions(
        self,
        library_id: str,
        sub_questions: tuple[str, ...],
        cost: _MutableCost,
    ) -> list[_SubResult]:
        sem = asyncio.Semaphore(max(1, self._config.sub_concurrency))

        async def _run_one(idx: int, sub_q: str) -> tuple[int, _SubResult]:
            async with sem:
                result = await self._answer_one_sub(library_id, sub_q)
                return idx, result

        tasks = [_run_one(i, q) for i, q in enumerate(sub_questions)]
        gathered = await asyncio.gather(*tasks)
        gathered.sort(key=lambda pair: pair[0])
        # cost accumulation done in caller via returned _SubResult fields
        _ = cost  # kept for symmetry / future use
        return [pair[1] for pair in gathered]

    async def _answer_one_sub(self, library_id: str, sub_q: str) -> _SubResult:
        # Retrieve evidence for this sub-question
        query = Query(
            library_id=library_id,
            text=sub_q,
            type="single-hop",
            max_results=self._config.chunks_per_sub,
        )
        try:
            retrieval = await self._planner.plan_and_retrieve(library_id, query)
        except Exception:
            step = ReasoningStep(sub_question=sub_q, answer="", evidence=())
            return _SubResult(step=step, llm_calls=0, input_tokens=0, output_tokens=0, cost_usd=0.0)

        evidence = retrieval.evidence[: self._config.chunks_per_sub]
        if not evidence:
            step = ReasoningStep(sub_question=sub_q, answer="", evidence=())
            return _SubResult(step=step, llm_calls=0, input_tokens=0, output_tokens=0, cost_usd=0.0)

        context = _format_context(evidence)
        messages = [
            Message(role="system", content=_SUB_SYSTEM_PROMPT),
            Message(
                role="user",
                content=_SUB_USER_PROMPT_TEMPLATE.format(sub_question=sub_q, context=context),
            ),
        ]
        try:
            resp = await self._llm.complete(
                messages,
                temperature=self._config.llm_temperature,
                max_tokens=self._config.llm_max_tokens_sub,
                timeout_s=self._config.llm_timeout_s,
            )
        except Exception:
            step = ReasoningStep(sub_question=sub_q, answer="", evidence=evidence)
            return _SubResult(step=step, llm_calls=0, input_tokens=0, output_tokens=0, cost_usd=0.0)

        step = ReasoningStep(sub_question=sub_q, answer=resp.text, evidence=evidence)
        return _SubResult(
            step=step,
            llm_calls=1,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cost_usd=resp.cost_usd,
        )

    # --- Aggregate ---------------------------------------------------------

    async def _aggregate(
        self,
        question: str,
        steps: tuple[ReasoningStep, ...],
        cost: _MutableCost,
    ) -> str:
        if not steps:
            return ""

        sub_answers_text = _format_sub_answers(steps)
        messages = [
            Message(role="system", content=_FINAL_SYSTEM_PROMPT),
            Message(
                role="user",
                content=_FINAL_USER_PROMPT_TEMPLATE.format(
                    question=question, sub_answers=sub_answers_text
                ),
            ),
        ]
        try:
            resp = await self._llm.complete(
                messages,
                temperature=self._config.llm_temperature,
                max_tokens=self._config.llm_max_tokens_final,
                timeout_s=self._config.llm_timeout_s,
            )
        except Exception:
            return _concat_sub_answers(steps)

        cost.add_response(resp)
        return resp.text

    # --- Citations ---------------------------------------------------------

    @staticmethod
    def _extract_citations(final_answer: str, steps: tuple[ReasoningStep, ...]) -> list[Citation]:
        """Validate cited chunk_ids against the union of evidence across all steps."""
        cited_ids = {m.group(1) for m in _CITATION_PATTERN.finditer(final_answer)}
        if not cited_ids:
            return []

        by_chunk_id: dict[str, RetrievedEvidence] = {}
        for step in steps:
            for ev in step.evidence:
                by_chunk_id.setdefault(ev.chunk.chunk_id, ev)

        citations: list[Citation] = []
        for chunk_id in cited_ids:
            ev = by_chunk_id.get(chunk_id)
            if ev is None:
                continue
            citations.append(
                Citation(
                    chunk_id=ev.chunk.chunk_id,
                    doc_id=ev.chunk.doc_id,
                    page=ev.chunk.page,
                    snippet=ev.chunk.text[:200],
                )
            )
        return citations


# === Helpers ================================================================


class _MutableCost:
    """Internal mutable accumulator → frozen TaskCost on read."""

    __slots__ = ("cost_usd", "input_tokens", "llm_calls", "output_tokens")

    def __init__(self) -> None:
        self.llm_calls: int = 0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.cost_usd: float = 0.0

    def add(
        self,
        llm_calls: int,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        self.llm_calls += llm_calls
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += cost_usd

    def add_response(self, resp: LLMResponse) -> None:
        self.add(1, resp.input_tokens, resp.output_tokens, resp.cost_usd)

    def to_task_cost(self, duration_ms: int) -> TaskCost:
        return TaskCost(
            llm_calls=self.llm_calls,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cost_usd=self.cost_usd,
            duration_ms=duration_ms,
        )


def _format_context(evidence: tuple[RetrievedEvidence, ...]) -> str:
    return "\n\n---\n\n".join(f"[{ev.chunk.chunk_id}] {ev.chunk.text}" for ev in evidence)


def _format_sub_answers(steps: tuple[ReasoningStep, ...]) -> str:
    parts: list[str] = []
    for i, step in enumerate(steps, start=1):
        ans = step.answer.strip() or "(no answer)"
        parts.append(f"Sub-question {i}: {step.sub_question}\nAnswer: {ans}")
    return "\n\n---\n\n".join(parts)


def _concat_sub_answers(steps: tuple[ReasoningStep, ...]) -> str:
    """Fallback final answer when aggregate LLM call fails."""
    parts = [step.answer.strip() for step in steps if step.answer.strip()]
    return "\n\n".join(parts)


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


def _parse_decompose(text: str) -> list[str]:
    """Returns the cleaned sub-questions list, or [] on parse failure."""
    json_text = _extract_json_block(text)
    if json_text is None:
        return []
    try:
        payload = _DecomposePayload.model_validate_json(json_text)
    except (json.JSONDecodeError, ValidationError):
        return []
    return [q.strip() for q in payload.sub_questions if q and q.strip()]


def _coerce_emitter(emitter: StageEmitter | None) -> StageEmitter:
    """Return a real emitter or a no-op fallback so `run()` never branches."""
    if emitter is not None:
        return emitter

    async def _noop(stage: str, event_type: str, payload: dict[str, object]) -> None:
        return None

    return _noop
