"""Layered prompt assembly for the context subsystem (ADR-0008 §3).

The composer takes pre-computed inputs (caller is responsible for memory
selection / evidence formatting / turn filtering) and stitches them into a
two-message (system + user) prompt that fits inside `ContextBudget`.

Trim priority — when total > `max_input_tokens`, we shrink slots in this
order (lowest priority first):

    1. recent_turns
    2. summary
    3. evidence
    4. memory
    5. library_card
    6. user_question  (only as a last resort; logger.warning)

The `slots_used` dict in the returned `ComposedPrompt` records the actual
token count per slot — useful for callers that want to record observability
without re-counting.
"""

from __future__ import annotations

import structlog

from packages.context.budget import CharCountTokenCounter, trim_to_tokens
from packages.context.protocols import (
    ComposedPrompt,
    ContextBudget,
    MemoryEntry,
    TokenCounter,
    Turn,
)

logger = structlog.get_logger(__name__)

BASE_SYSTEM_PROMPT = """You are a research assistant. Answer the user's question using ONLY the
provided evidence. Every factual claim MUST cite at least one evidence item
using [id] markers, where `id` is the chunk_id shown in brackets next to the
evidence text.

Rules:
- If the evidence does not support a confident answer, say so explicitly.
- Do not invent facts not present in the evidence.
- Cite evidence inline, not at the end.
- Be concise — 2 to 5 sentences unless the question demands more depth.
- Use prior conversation turns and research memory only as guidance for
  tone, scope, and continuity; do not treat them as factual evidence."""

# Slot identifiers used in `ComposedPrompt.slots_used`. Centralized so
# downstream metrics code can import them.
SLOT_LIBRARY_CARD = "library_card"
SLOT_MEMORY = "memory"
SLOT_SUMMARY = "summary"
SLOT_RECENT_TURNS = "recent_turns"
SLOT_EVIDENCE = "evidence"
SLOT_USER_QUESTION = "user_question"
SLOT_SYSTEM_OVERHEAD = "system_overhead"

# Order: lowest priority first. The composer drops/trims earlier entries
# before later ones when over budget.
_TRIM_PRIORITY: tuple[str, ...] = (
    SLOT_RECENT_TURNS,
    SLOT_SUMMARY,
    SLOT_EVIDENCE,
    SLOT_MEMORY,
    SLOT_LIBRARY_CARD,
    SLOT_USER_QUESTION,
)


class PromptComposer:
    """Assemble a `ComposedPrompt` from pre-filtered context inputs.

    Stateless — safe to share across requests. The default token counter
    is `CharCountTokenCounter`; callers may inject a real BPE counter.
    """

    def __init__(
        self,
        *,
        counter: TokenCounter | None = None,
        base_system_prompt: str = BASE_SYSTEM_PROMPT,
    ) -> None:
        self._counter: TokenCounter = counter or CharCountTokenCounter()
        self._base_system_prompt = base_system_prompt

    def compose(
        self,
        *,
        library_card: str,
        memory_entries: tuple[MemoryEntry, ...],
        summary: str,
        recent_turns: tuple[Turn, ...],
        evidence_block: str,
        user_question: str,
        budget: ContextBudget,
    ) -> ComposedPrompt:
        """Assemble the layered prompt within `budget`.

        Returns a `ComposedPrompt` whose `system` and `user` are ready to
        send and whose `slots_used` reports the actual per-slot token cost.
        """
        rendered = self._render_initial(
            library_card=library_card,
            memory_entries=memory_entries,
            summary=summary,
            recent_turns=recent_turns,
            evidence_block=evidence_block,
            user_question=user_question,
            budget=budget,
        )
        rendered = self._fit_to_budget(rendered, budget)
        return self._assemble(rendered)

    def _render_initial(
        self,
        *,
        library_card: str,
        memory_entries: tuple[MemoryEntry, ...],
        summary: str,
        recent_turns: tuple[Turn, ...],
        evidence_block: str,
        user_question: str,
        budget: ContextBudget,
    ) -> dict[str, str]:
        """Trim each slot to its individual cap before global budget pass."""
        memory_text = _render_memory(memory_entries)
        turns_text = _render_turns(recent_turns)
        return {
            SLOT_LIBRARY_CARD: trim_to_tokens(library_card, budget.library_card_max, self._counter),
            SLOT_MEMORY: trim_to_tokens(memory_text, budget.memory_max, self._counter),
            SLOT_SUMMARY: trim_to_tokens(summary, budget.summary_max, self._counter),
            SLOT_RECENT_TURNS: trim_to_tokens(turns_text, budget.recent_turns_max, self._counter),
            SLOT_EVIDENCE: trim_to_tokens(evidence_block, budget.evidence_max, self._counter),
            SLOT_USER_QUESTION: trim_to_tokens(
                user_question, budget.user_question_max, self._counter
            ),
        }

    def _fit_to_budget(self, slots: dict[str, str], budget: ContextBudget) -> dict[str, str]:
        """Globally trim slots in `_TRIM_PRIORITY` order until total ≤ budget."""
        overhead = self._counter.count(self._base_system_prompt) + _structural_overhead_tokens()
        usable = max(budget.max_input_tokens - overhead, 0)

        result = dict(slots)
        for slot in _TRIM_PRIORITY:
            total = sum(self._counter.count(t) for t in result.values())
            if total <= usable:
                return result
            current = self._counter.count(result[slot])
            excess = total - usable
            target = max(current - excess, 0)
            if slot == SLOT_USER_QUESTION and target < current:
                logger.warning(
                    "prompt_composer_trimming_user_question",
                    target_tokens=target,
                    current_tokens=current,
                )
            result[slot] = trim_to_tokens(result[slot], target, self._counter)

        return result

    def _assemble(self, slots: dict[str, str]) -> ComposedPrompt:
        """Stitch trimmed slots into final system+user messages.

        `system_overhead` tracks every token that's NOT in a content slot:
        the base system prompt plus structural headers/separators. This
        keeps `sum(slots_used.values()) == estimated_input_tokens` exact
        modulo char/4 rounding.
        """
        system = _build_system(
            base=self._base_system_prompt,
            library_card=slots[SLOT_LIBRARY_CARD],
            memory=slots[SLOT_MEMORY],
            summary=slots[SLOT_SUMMARY],
        )
        user = _build_user(
            recent_turns=slots[SLOT_RECENT_TURNS],
            evidence=slots[SLOT_EVIDENCE],
            question=slots[SLOT_USER_QUESTION],
        )

        slots_used = {name: self._counter.count(text) for name, text in slots.items()}
        estimated = self._counter.count(system) + self._counter.count(user)
        content_total = sum(slots_used.values())
        # Overhead = everything else (base prompt + structural headers).
        # Clamp to non-negative since char/4 ceil-division can over-count
        # tiny pieces in rare cases.
        slots_used[SLOT_SYSTEM_OVERHEAD] = max(estimated - content_total, 0)

        return ComposedPrompt(
            system=system,
            user=user,
            estimated_input_tokens=estimated,
            slots_used=slots_used,
        )


def _render_memory(entries: tuple[MemoryEntry, ...]) -> str:
    """Render memory entries into a flat text block."""
    if not entries:
        return ""
    lines: list[str] = []
    for entry in entries:
        lines.append(f"- ({entry.kind}) {entry.title}: {entry.content}")
    return "\n".join(lines)


def _render_turns(turns: tuple[Turn, ...]) -> str:
    """Render recent turns into a chat-transcript-like block."""
    if not turns:
        return ""
    lines: list[str] = []
    for turn in turns:
        role = "User" if turn.role == "user" else "Assistant"
        lines.append(f"{role}: {turn.content}")
    return "\n".join(lines)


def _build_system(*, base: str, library_card: str, memory: str, summary: str) -> str:
    """Compose the system message; sections with empty bodies are omitted."""
    parts: list[str] = [base]
    if library_card:
        parts.append("# Library\n" + library_card)
    if memory:
        parts.append("# Research Memory\n" + memory)
    if summary:
        parts.append("# Earlier conversation summary\n" + summary)
    return "\n\n".join(parts)


def _build_user(*, recent_turns: str, evidence: str, question: str) -> str:
    """Compose the user message; sections with empty bodies are omitted."""
    parts: list[str] = []
    if recent_turns:
        parts.append("# Recent conversation\n" + recent_turns)
    if evidence:
        parts.append("# Evidence\n" + evidence)
    parts.append("# Current question\n" + question)
    return "\n\n".join(parts)


def _structural_overhead_tokens() -> int:
    """Constant tokens for section headers and separators we always emit.

    Empirically ~30 tokens for the worst case (all 6 sections present).
    Keep this small — overestimating just means slightly tighter budgets.
    """
    return 32
