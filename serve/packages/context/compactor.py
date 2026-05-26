"""Turn compaction — fits prior conversation history into the budget.

Strategy (mirrors ADR-0008 §4):
  1. **count**: the per-turn token cost is `content` + light citation metadata
     (chunk_id + snippet, which the Citation contract caps at 200 chars). We
     never embed full evidence text here — that lives in the retrieval index
     and is re-fetched on demand.
  2. **walk-back**: starting from the newest turn, keep turns until adding the
     next would exceed `budget.recent_turns_max`. The collected suffix becomes
     `kept_turns`, preserved in original chronological order.
  3. **summarize-rest**: anything older + the prior accumulated `summary` is
     fed to one deterministic LLM call which returns a fresh ≤summary_max prose
     paragraph. On LLM failure we fall back to `prior_summary` so we never
     lose data — the kept-turns suffix is still correct.

`fit_auto` short-circuits the LLM call when nothing needs compacting, which
is the common case during normal conversation flow.
"""

from __future__ import annotations

import logging
import time

from pydantic import BaseModel, ConfigDict, Field

from packages.context.protocols import ContextBudget, TokenCounter, Turn
from packages.llm.protocols import LLMClient, Message
from packages.observability.metrics import TASK_DURATION_SECONDS

logger = logging.getLogger(__name__)

_SUMMARY_SYSTEM_PROMPT = (
    "You are a research-conversation summarizer. Your output must be plain "
    "prose (no bullet markdown, no headings) suitable for re-injection into a "
    "later turn's context window. Be terse but information-dense."
)

_SUMMARY_USER_TEMPLATE = """Summarize the following research conversation, preserving:
  - Topic of investigation
  - Key claims established
  - Open questions
  - Important named entities (methods, datasets, models)

Output at most {summary_max_tokens} tokens of plain prose. No bullet markdown.

{body}"""

_SECTION_SEPARATOR = "\n\n---\n\n"
_TASK_LABEL = "context.compact"


class CompactionResult(BaseModel):
    """Result of one compaction pass over a turn list."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str = ""
    kept_turns: tuple[Turn, ...] = ()
    dropped_turns: int = Field(default=0, ge=0)
    summary_tokens: int = Field(default=0, ge=0)
    kept_tokens: int = Field(default=0, ge=0)


class TurnCompactor:
    """Fits prior turns + summary into ContextBudget slots.

    Deterministic: temperature=0 on the summary call; identical inputs
    produce identical outputs (modulo LLM provider determinism).
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        counter: TokenCounter,
        budget: ContextBudget,
        summary_max_tokens: int = 512,
        llm_timeout_s: float = 60.0,
        llm_model: str | None = None,
    ) -> None:
        self._llm = llm
        self._counter = counter
        self._budget = budget
        self._summary_max_tokens = summary_max_tokens
        self._llm_timeout_s = llm_timeout_s
        self._llm_model = llm_model

    async def fit(self, prior_summary: str, turns: tuple[Turn, ...]) -> CompactionResult:
        """Always-compacting fit: kept_turns from newest backward, rest summarized."""
        started = time.perf_counter()
        try:
            return await self._fit_inner(prior_summary, turns, force_summary=True)
        finally:
            self._observe_duration(started)

    async def fit_auto(self, prior_summary: str, turns: tuple[Turn, ...]) -> CompactionResult:
        """Skip LLM when prior_summary + all turns already fit in budget."""
        started = time.perf_counter()
        try:
            if self._fits_without_compaction(prior_summary, turns):
                return self._noop_result(prior_summary, turns)
            return await self._fit_inner(prior_summary, turns, force_summary=True)
        finally:
            self._observe_duration(started)

    async def _fit_inner(
        self,
        prior_summary: str,
        turns: tuple[Turn, ...],
        *,
        force_summary: bool,
    ) -> CompactionResult:
        if not turns:
            return CompactionResult(
                summary=prior_summary,
                summary_tokens=self._counter.count(prior_summary),
            )

        kept, dropped = self._select_kept_suffix(turns)
        kept_tokens = sum(self._turn_tokens(turn) for turn in kept)

        new_summary = await self._build_summary(prior_summary, dropped, force=force_summary)
        return CompactionResult(
            summary=new_summary,
            kept_turns=kept,
            dropped_turns=len(dropped),
            summary_tokens=self._counter.count(new_summary),
            kept_tokens=kept_tokens,
        )

    def _fits_without_compaction(self, prior_summary: str, turns: tuple[Turn, ...]) -> bool:
        kept_tokens = sum(self._turn_tokens(turn) for turn in turns)
        summary_tokens = self._counter.count(prior_summary)
        return (
            kept_tokens <= self._budget.recent_turns_max
            and summary_tokens <= self._budget.summary_max
        )

    def _noop_result(self, prior_summary: str, turns: tuple[Turn, ...]) -> CompactionResult:
        kept_tokens = sum(self._turn_tokens(turn) for turn in turns)
        return CompactionResult(
            summary=prior_summary,
            kept_turns=turns,
            dropped_turns=0,
            summary_tokens=self._counter.count(prior_summary),
            kept_tokens=kept_tokens,
        )

    def _select_kept_suffix(
        self, turns: tuple[Turn, ...]
    ) -> tuple[tuple[Turn, ...], tuple[Turn, ...]]:
        """Walk newest→oldest; collect turns until next would overflow."""
        budget = self._budget.recent_turns_max
        kept_reversed: list[Turn] = []
        running = 0
        cutoff_idx = len(turns)  # everything kept by default
        for idx in range(len(turns) - 1, -1, -1):
            cost = self._turn_tokens(turns[idx])
            if running + cost > budget:
                cutoff_idx = idx + 1
                break
            running += cost
            kept_reversed.append(turns[idx])
            cutoff_idx = idx
        kept = tuple(reversed(kept_reversed))
        dropped = turns[:cutoff_idx]
        return kept, dropped

    async def _build_summary(
        self, prior_summary: str, dropped: tuple[Turn, ...], *, force: bool
    ) -> str:
        if not dropped and not prior_summary:
            return ""
        if not dropped:
            return prior_summary
        if not force:
            return prior_summary

        body = self._format_summary_body(prior_summary, dropped)
        try:
            response = await self._llm.complete(
                [
                    Message(role="system", content=_SUMMARY_SYSTEM_PROMPT),
                    Message(
                        role="user",
                        content=_SUMMARY_USER_TEMPLATE.format(
                            summary_max_tokens=self._summary_max_tokens,
                            body=body,
                        ),
                    ),
                ],
                model=self._llm_model,
                temperature=0.0,
                max_tokens=self._summary_max_tokens,
                timeout_s=self._llm_timeout_s,
            )
        except Exception:
            logger.exception("compactor_llm_failed")
            return prior_summary
        text = response.text.strip()
        return text or prior_summary

    @staticmethod
    def _format_summary_body(prior_summary: str, dropped: tuple[Turn, ...]) -> str:
        parts: list[str] = []
        if prior_summary:
            parts.append(f"Prior summary:\n{prior_summary}")
        transcript = "\n".join(f"{turn.role.upper()}: {turn.content}" for turn in dropped)
        parts.append(f"Older turns:\n{transcript}")
        return _SECTION_SEPARATOR.join(parts)

    def _turn_tokens(self, turn: Turn) -> int:
        """Count: turn.content + per-citation chunk_id + snippet preview."""
        total = self._counter.count(turn.content)
        for citation in turn.citations:
            total += self._counter.count(citation.chunk_id)
            total += self._counter.count(citation.snippet)
        return total

    @staticmethod
    def _observe_duration(started: float) -> None:
        elapsed = time.perf_counter() - started
        TASK_DURATION_SECONDS.labels(task=_TASK_LABEL, library_id="").observe(elapsed)
