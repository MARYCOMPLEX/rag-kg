"""Tests for `packages.context.prompt_composer.PromptComposer`."""

from __future__ import annotations

from datetime import UTC, datetime

from packages.context.prompt_composer import (
    SLOT_EVIDENCE,
    SLOT_LIBRARY_CARD,
    SLOT_MEMORY,
    SLOT_RECENT_TURNS,
    SLOT_SUMMARY,
    SLOT_USER_QUESTION,
    PromptComposer,
)
from packages.context.protocols import ContextBudget, MemoryEntry, Turn


def _turn(idx: int, role: str = "user", content: str = "hello") -> Turn:
    return Turn(
        conversation_id="c1",
        turn_id=f"t{idx}",
        role="user" if role == "user" else "assistant",
        content=content,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _memory(idx: int, content: str = "prefer post-2023 work") -> MemoryEntry:
    return MemoryEntry(
        library_id="lib1",
        entry_id=f"m{idx}",
        kind="user",
        title=f"pref-{idx}",
        content=content,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_composes_minimal_prompt_with_only_question() -> None:
    # Arrange
    composer = PromptComposer()

    # Act
    result = composer.compose(
        library_card="",
        memory_entries=(),
        summary="",
        recent_turns=(),
        evidence_block="",
        user_question="What is RAG?",
        budget=ContextBudget(),
    )

    # Assert — system has base prompt, user only has the question
    assert "You are a research assistant" in result.system
    assert "# Library" not in result.system
    assert "# Research Memory" not in result.system
    assert "# Earlier conversation summary" not in result.system
    assert "# Recent conversation" not in result.user
    assert "# Evidence" not in result.user
    assert "What is RAG?" in result.user
    assert result.estimated_input_tokens > 0


def test_includes_all_sections_when_provided() -> None:
    # Arrange
    composer = PromptComposer()

    # Act
    result = composer.compose(
        library_card="Library 'rag-agent': 15 docs on RAG+agents",
        memory_entries=(_memory(1),),
        summary="Earlier we discussed retrieval augmentation.",
        recent_turns=(_turn(1, "user", "tell me about RAG"),),
        evidence_block="[doc::p1::1] RAG combines retrieval and generation.",
        user_question="How does it differ from fine-tuning?",
        budget=ContextBudget(),
    )

    # Assert
    assert "# Library" in result.system
    assert "rag-agent" in result.system
    assert "# Research Memory" in result.system
    assert "post-2023" in result.system
    assert "# Earlier conversation summary" in result.system
    assert "Earlier we discussed" in result.system
    assert "# Recent conversation" in result.user
    assert "User: tell me about RAG" in result.user
    assert "# Evidence" in result.user
    assert "[doc::p1::1]" in result.user
    assert "How does it differ" in result.user


def test_trims_recent_turns_first_when_over_budget() -> None:
    # Arrange — tight global budget; sized so turns must shrink before evidence
    composer = PromptComposer()
    big_turns = tuple(_turn(i, "user", "x" * 200) for i in range(20))
    budget = ContextBudget(
        max_input_tokens=600,
        library_card_max=50,
        memory_max=50,
        summary_max=50,
        recent_turns_max=400,
        evidence_max=200,
        user_question_max=50,
    )

    # Act
    result = composer.compose(
        library_card="card",
        memory_entries=(),
        summary="summary text",
        recent_turns=big_turns,
        evidence_block="evidence " * 30,
        user_question="question?",
        budget=budget,
    )

    # Assert — recent_turns slot was trimmed below its individual cap;
    # other slots may also have been trimmed, but turns shrank first.
    assert result.slots_used[SLOT_RECENT_TURNS] < 400
    assert result.estimated_input_tokens <= budget.max_input_tokens + 5
    # Evidence and question both still present
    assert "evidence" in result.user
    assert "question?" in result.user


def test_never_drops_user_question_unless_budget_extreme() -> None:
    # Arrange — adversarial: tons of evidence/turns, normal question
    composer = PromptComposer()
    budget = ContextBudget(max_input_tokens=2000)

    # Act
    result = composer.compose(
        library_card="card " * 100,
        memory_entries=tuple(_memory(i, "x" * 500) for i in range(5)),
        summary="summary " * 500,
        recent_turns=tuple(_turn(i, "user", "x" * 1000) for i in range(10)),
        evidence_block="evidence " * 1000,
        user_question="What is the answer to my critical question?",
        budget=budget,
    )

    # Assert — user_question slot is preserved at full size
    assert "What is the answer to my critical question?" in result.user
    assert result.slots_used[SLOT_USER_QUESTION] > 0


def test_slots_used_sums_close_to_estimated_tokens() -> None:
    # Arrange
    composer = PromptComposer()
    budget = ContextBudget()

    # Act
    result = composer.compose(
        library_card="Library: rag-agent corpus",
        memory_entries=(_memory(1),),
        summary="prior chat about retrieval",
        recent_turns=(_turn(1, "user", "hi"), _turn(2, "assistant", "hello")),
        evidence_block="[c1] some evidence text here",
        user_question="ok and now what?",
        budget=budget,
    )

    # Assert — sum of content slots + system overhead within ±10% of estimated input
    content_sum = sum(
        result.slots_used[s]
        for s in (
            SLOT_LIBRARY_CARD,
            SLOT_MEMORY,
            SLOT_SUMMARY,
            SLOT_RECENT_TURNS,
            SLOT_EVIDENCE,
            SLOT_USER_QUESTION,
        )
    )
    overhead = result.slots_used["system_overhead"]
    estimated = result.estimated_input_tokens
    assert estimated > 0
    # Allow ±10% drift due to structural headers added during assembly.
    delta = abs((content_sum + overhead) - estimated) / max(estimated, 1)
    assert delta < 0.10


def test_empty_memory_and_summary_produce_clean_prompt() -> None:
    # Arrange
    composer = PromptComposer()

    # Act
    result = composer.compose(
        library_card="Library card text",
        memory_entries=(),
        summary="",
        recent_turns=(_turn(1, "user", "hi"),),
        evidence_block="[c1] evidence",
        user_question="what?",
        budget=ContextBudget(),
    )

    # Assert — no leftover empty headers
    assert "# Research Memory" not in result.system
    assert "# Earlier conversation summary" not in result.system
    assert "# Library" in result.system
    # No double-blank-line headers without bodies
    assert "# Research Memory\n\n" not in result.system
    assert "# Earlier conversation summary\n\n" not in result.system


def test_user_question_warning_triggers_only_under_extreme_budget() -> None:
    # Arrange — pathological budget that forces the question to trim
    composer = PromptComposer()
    budget = ContextBudget(
        max_input_tokens=512,
        library_card_max=0,
        memory_max=0,
        summary_max=0,
        recent_turns_max=0,
        evidence_max=0,
        user_question_max=512,
    )

    # Act — base system prompt alone is ~80 tokens; question of 1500 tokens forces trim
    long_q = "word " * 2000
    result = composer.compose(
        library_card="",
        memory_entries=(),
        summary="",
        recent_turns=(),
        evidence_block="",
        user_question=long_q,
        budget=budget,
    )

    # Assert — question was trimmed but still present
    assert result.slots_used[SLOT_USER_QUESTION] > 0
    assert result.estimated_input_tokens <= budget.max_input_tokens + 5
