"""Query rewriter for anaphora resolution (ADR-0008 §5).

Before retrieval, every user turn after the first goes through a small LLM
call that rewrites anaphoric / elliptical questions into a self-contained
form. The rewritten query is what hits the retrieval planner; the original
is preserved alongside so downstream code can show the user's literal
phrasing in the answer's tone.

Heuristic guard: we skip the LLM call entirely when there is no plausible
need for a rewrite — empty history, or no anaphor markers and ≤1 prior
turns. This keeps token cost flat for the common single-shot case.

LLM contract: STRICT JSON output `{"rewritten", "confidence", "explanation"}`
parsed via Pydantic. Confidence below `min_confidence` falls back to the
original query (still marked `used_history=False`).
"""

from __future__ import annotations

import json
import re
from typing import Final

import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.context.protocols import RewriteResult, Turn
from packages.llm.protocols import LLMClient, Message

logger = structlog.get_logger(__name__)

# Threshold below which we still try the LLM call even without an anaphor
# match — implicit ellipsis tends to surface once the conversation has
# at least two prior turns of context.
_MIN_TURNS_FOR_IMPLICIT_REWRITE: Final[int] = 2

# Anaphor markers — cheap regex check covering common English pronouns,
# definite descriptions ("the method/approach/paper/model/dataset"), and
# Chinese follow-up cues ("再讲", "继续", "改写", "对比", and the bare
# pronoun "它" / its derivatives).
_ANAPHOR_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(it|its|this|that|these|those|"
    r"the\s+(method|approach|paper|model|dataset))\b"
    r"|改写|继续|再讲|对比|它",
    re.IGNORECASE,
)

_REWRITER_SYSTEM_PROMPT: Final[str] = (
    "You rewrite a user's follow-up question into a self-contained form.\n"
    "\n"
    "You receive the last 1-2 turns of a research conversation and the current\n"
    "question. Resolve any anaphora (it / this / that / 它 / 这个 / etc.) and\n"
    "implicit ellipsis using the prior turns. Keep the user's language and\n"
    "intent; do NOT add new constraints or invent topics.\n"
    "\n"
    "Respond with STRICT JSON ONLY (no prose, no code fences). Schema:\n"
    '{"rewritten": "<self-contained question>", '
    '"confidence": <0.0-1.0>, '
    '"explanation": "<one short sentence>"}\n'
    "\n"
    "Confidence guidance:\n"
    "- 0.9+ : prior turns clearly determine the referent\n"
    "- 0.7-0.9 : minor ambiguity but a sensible rewrite exists\n"
    "- <0.6 : you are guessing — return original verbatim with low confidence"
)


_USER_TEMPLATE: Final[str] = """Recent turns (oldest first):
{history}

Current question: {question}

Return JSON only."""


class _RewritePayload(BaseModel):
    """Strict-JSON payload returned by the rewriter LLM call."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    rewritten: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = ""


class QueryRewriter:
    """Anaphora-resolving query rewriter backed by a small LLM call.

    Stateless — safe to share across requests. Callers should consult
    `Settings.rewrite_enabled` to bypass the rewriter entirely; this class
    does not read settings itself.
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        model: str | None = None,
        min_confidence: float = 0.6,
        max_tokens_out: int = 80,
        timeout_s: float = 30.0,
    ) -> None:
        self._llm = llm
        self._model = model
        self._min_confidence = min_confidence
        self._max_tokens_out = max_tokens_out
        self._timeout_s = timeout_s

    @property
    def is_disabled(self) -> bool:
        """Always False — disablement is a Settings-level concern."""
        return False

    async def rewrite(self, *, question: str, recent_turns: tuple[Turn, ...]) -> RewriteResult:
        """Rewrite `question` to be self-contained using `recent_turns`.

        Returns the original (with `used_history=False`) when:
        - history is empty
        - no anaphor markers AND fewer than 2 prior turns
        - the LLM response fails to parse
        - the LLM-reported confidence is below `min_confidence`
        """
        if not recent_turns:
            return _passthrough(question, confidence=1.0)

        has_anaphor = bool(_ANAPHOR_PATTERN.search(question))
        if not has_anaphor and len(recent_turns) < _MIN_TURNS_FOR_IMPLICIT_REWRITE:
            return _passthrough(question, confidence=1.0)

        payload = await self._call_llm(question=question, recent_turns=recent_turns)
        if payload is None:
            return _passthrough(question, confidence=0.0)
        if payload.confidence < self._min_confidence:
            logger.info(
                "query_rewriter_low_confidence",
                confidence=payload.confidence,
                threshold=self._min_confidence,
            )
            return _passthrough(question, confidence=payload.confidence)

        return RewriteResult(
            original=question,
            rewritten=payload.rewritten,
            confidence=payload.confidence,
            used_history=True,
        )

    async def _call_llm(
        self, *, question: str, recent_turns: tuple[Turn, ...]
    ) -> _RewritePayload | None:
        """Issue the rewriter LLM call and parse the JSON payload.

        Returns None on transport error or malformed JSON. The caller is
        responsible for falling back to the original question.
        """
        history_text = _render_history(recent_turns)
        messages = [
            Message(role="system", content=_REWRITER_SYSTEM_PROMPT),
            Message(
                role="user",
                content=_USER_TEMPLATE.format(history=history_text, question=question),
            ),
        ]
        try:
            response = await self._llm.complete(
                messages,
                model=self._model,
                temperature=0.0,
                max_tokens=self._max_tokens_out,
                timeout_s=self._timeout_s,
            )
        except Exception as exc:
            # Fall back on any LLM-side error (transport, timeout, 5xx).
            logger.warning("query_rewriter_llm_error", error=str(exc))
            return None

        return _parse_payload(response.text)


def _render_history(recent_turns: tuple[Turn, ...]) -> str:
    """Render the (up to) last 2 turns into a compact transcript block."""
    tail = recent_turns[-_MIN_TURNS_FOR_IMPLICIT_REWRITE:]
    lines: list[str] = []
    for turn in tail:
        role = "User" if turn.role == "user" else "Assistant"
        lines.append(f"{role}: {turn.content}")
    return "\n".join(lines)


def _parse_payload(text: str) -> _RewritePayload | None:
    """Parse the LLM response as strict JSON; return None on any failure."""
    stripped = text.strip()
    if not stripped:
        logger.warning("query_rewriter_empty_response")
        return None
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as exc:
        logger.warning("query_rewriter_json_error", error=str(exc), text=stripped[:200])
        return None
    try:
        return _RewritePayload.model_validate(raw)
    except ValidationError as exc:
        logger.warning("query_rewriter_validation_error", error=str(exc))
        return None


def _passthrough(question: str, *, confidence: float) -> RewriteResult:
    """Build a no-op `RewriteResult` preserving the original question."""
    return RewriteResult(
        original=question,
        rewritten=question,
        confidence=confidence,
        used_history=False,
    )
