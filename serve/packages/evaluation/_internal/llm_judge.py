"""Dual-LLM agreement gate for VAR judgment (ADR-0016 §4).

Two judge LLMs independently score `useful` and `citations_correct`
booleans plus a self-reported confidence in `[0, 1]`. The aggregate
verdict counts ONLY when:

  * both judges agree on both booleans, AND
  * each judge self-reports confidence >= JUDGE_AGREEMENT_THRESHOLD (0.6).

Disagreement returns `None` for the verdict — surfaced as `not_enough_data`
to the snapshot writer; ADR-0016 §4 explicitly forbids treating disagreement
as 0.5.

This module talks to LLMs only via `packages.llm.protocols.LLMClient` so
unit tests can swap a fake without dragging the SiliconFlow SDK along.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.evaluation._internal.var_blend import JUDGE_AGREEMENT_THRESHOLD
from packages.llm.protocols import LLMClient, Message
from packages.observability import with_span

logger = structlog.get_logger(__name__)

# Stable prompt version (ADR-0016 §4) — bump on any prompt edit.
JUDGE_PROMPT_VERSION: str = "v2026-05"

_JUDGE_PROMPT = """You are an answer-quality judge.

Given a USER QUESTION and an ASSISTANT ANSWER (with bracketed citations),
decide independently:

1. Is the answer USEFUL for the question? (true/false)
2. Are the citations CORRECT (i.e., the answer's claims match the cited sources)? (true/false)
3. Your CONFIDENCE in this verdict on [0, 1].

Output JSON only:
{{
  "useful": true,
  "citations_correct": true,
  "confidence": 0.85,
  "rationale": "short reason"
}}

QUESTION:
{question}

ANSWER:
{answer}
"""

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True, slots=True)
class JudgeVerdict:
    """One judge's binary scoring on a single answer."""

    judge_model: str
    useful: bool
    citations_correct: bool
    confidence: float
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class JudgeAggregate:
    """Two-judge agreement outcome.

    `useful` and `citations_correct` are `None` when judges disagreed or
    confidence floor was breached; the snapshot writer treats this as
    `not_enough_data` for that sample.
    """

    useful: bool | None
    citations_correct: bool | None
    agreed: bool
    judges: tuple[JudgeVerdict, ...]


class _JudgePayload(BaseModel):
    """Strict shape for a judge's JSON output."""

    model_config = ConfigDict(extra="ignore")

    useful: bool
    citations_correct: bool
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


def _extract_json(text: str) -> str | None:
    """Pull the first JSON object from LLM text, ignoring code fences."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    match = _JSON_BLOCK_RE.search(stripped)
    if match is None:
        return None
    return match.group(0)


class DualLLMJudge:
    """Two independent LLM calls; agreement-gated verdict.

    The two judges may share an `LLMClient` instance — what differentiates
    them is the `model` argument passed to `complete`. Passing two distinct
    `model` strings gives the dual-LLM property required by ADR-0016 §4.
    """

    def __init__(
        self,
        *,
        primary_llm: LLMClient,
        secondary_llm: LLMClient,
        primary_model: str = "primary",
        secondary_model: str = "secondary",
        timeout_s: float = 30.0,
        max_tokens: int = 400,
        confidence_floor: float = JUDGE_AGREEMENT_THRESHOLD,
    ) -> None:
        self._primary = primary_llm
        self._secondary = secondary_llm
        self._primary_model = primary_model
        self._secondary_model = secondary_model
        self._timeout_s = timeout_s
        self._max_tokens = max_tokens
        self._confidence_floor = confidence_floor

    async def judge(self, question: str, answer: str) -> JudgeAggregate:
        """Score one (question, answer) pair with both judges; aggregate."""
        async with with_span("evaluation.dual_judge"):
            verdicts: list[JudgeVerdict] = []
            for client, model in (
                (self._primary, self._primary_model),
                (self._secondary, self._secondary_model),
            ):
                verdict = await self._one_judge(client, model, question, answer)
                if verdict is None:
                    return JudgeAggregate(
                        useful=None,
                        citations_correct=None,
                        agreed=False,
                        judges=tuple(verdicts),
                    )
                verdicts.append(verdict)
            return _aggregate(tuple(verdicts), self._confidence_floor)

    async def _one_judge(
        self,
        llm: LLMClient,
        model: str,
        question: str,
        answer: str,
    ) -> JudgeVerdict | None:
        prompt = _JUDGE_PROMPT.format(question=question, answer=answer)
        try:
            response = await llm.complete(
                [Message(role="user", content=prompt)],
                model=model,
                temperature=0.0,
                max_tokens=self._max_tokens,
                timeout_s=self._timeout_s,
            )
        except Exception as exc:
            await logger.awarning(
                "judge_llm_call_failed",
                model=model,
                error=str(exc),
            )
            return None
        json_block = _extract_json(response.text)
        if json_block is None:
            await logger.awarning("judge_no_json", model=model, raw_len=len(response.text))
            return None
        try:
            payload = _JudgePayload.model_validate_json(json_block)
        except (json.JSONDecodeError, ValidationError) as exc:
            await logger.awarning("judge_parse_error", model=model, error=str(exc))
            return None
        return JudgeVerdict(
            judge_model=model,
            useful=payload.useful,
            citations_correct=payload.citations_correct,
            confidence=payload.confidence,
            rationale=payload.rationale,
        )


def _aggregate(
    verdicts: Sequence[JudgeVerdict],
    confidence_floor: float,
) -> JudgeAggregate:
    """Pure aggregation: two-judge agreement gate (ADR-0016 §4)."""
    if len(verdicts) < 2:
        return JudgeAggregate(
            useful=None,
            citations_correct=None,
            agreed=False,
            judges=tuple(verdicts),
        )
    a, b = verdicts[0], verdicts[1]
    agreed = (
        a.useful == b.useful
        and a.citations_correct == b.citations_correct
        and a.confidence >= confidence_floor
        and b.confidence >= confidence_floor
    )
    if not agreed:
        return JudgeAggregate(
            useful=None,
            citations_correct=None,
            agreed=False,
            judges=tuple(verdicts),
        )
    return JudgeAggregate(
        useful=a.useful,
        citations_correct=a.citations_correct,
        agreed=True,
        judges=tuple(verdicts),
    )


__all__ = [
    "JUDGE_PROMPT_VERSION",
    "DualLLMJudge",
    "JudgeAggregate",
    "JudgeVerdict",
]
