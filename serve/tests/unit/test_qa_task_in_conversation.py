"""Unit tests for `QATask.answer_in_conversation` (M8.B1).

Drives the full pipeline against AsyncMock-injected dependencies so the
test runs in milliseconds and never touches sqlite or any LLM.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.context.compactor import CompactionResult
from packages.context.protocols import (
    ContextBudget,
    Conversation,
    RewriteResult,
    Turn,
)
from packages.core.models import Chunk
from packages.llm.protocols import LLMResponse
from packages.orchestration.tasks.qa_task import (
    ContextRuntimeSettings,
    QATask,
)
from packages.retrieval.protocols import RetrievalResult, RetrievedEvidence


def _evidence(chunk_id: str = "chunk-1") -> RetrievedEvidence:
    return RetrievedEvidence(
        chunk=Chunk(
            library_id="lib-a",
            chunk_id=chunk_id,
            doc_id="doc-1",
            text=f"text-of-{chunk_id}",
            page=1,
        ),
        score=0.9,
        source="vector",
    )


def _make_conversation(*, summary: str = "", conversation_id: str = "conv-1") -> Conversation:
    now = datetime(2026, 4, 28, tzinfo=UTC)
    return Conversation(
        library_id="lib-a",
        conversation_id=conversation_id,
        title="t",
        summary=summary,
        created_at=now,
        updated_at=now,
    )


def _make_turn(*, role: str, content: str, turn_id: str, conversation_id: str = "conv-1") -> Turn:
    return Turn(
        conversation_id=conversation_id,
        turn_id=turn_id,
        role=role,  # type: ignore[arg-type]
        content=content,
        created_at=datetime(2026, 4, 28, tzinfo=UTC),
    )


def _planner_returning(*evidence: RetrievedEvidence) -> AsyncMock:
    planner = AsyncMock()
    planner.plan_and_retrieve.return_value = RetrievalResult(
        library_id="lib-a", query="q", evidence=tuple(evidence)
    )
    return planner


def _llm_with(text: str = "Answer [chunk-1]") -> AsyncMock:
    llm = AsyncMock()
    llm.complete.return_value = LLMResponse(
        text=text, model="fake", input_tokens=10, output_tokens=20
    )
    return llm


def _settings(
    *,
    recent_turns_window: int = 4,
    rewrite_enabled: bool = True,
    memory_max_entries_in_prompt: int = 5,
) -> ContextRuntimeSettings:
    return ContextRuntimeSettings(
        recent_turns_window=recent_turns_window,
        memory_max_entries_in_prompt=memory_max_entries_in_prompt,
        compact_summary_max_tokens=512,
        rewrite_enabled=rewrite_enabled,
    )


def _context_service_stub(history: tuple[Turn, ...] = ()) -> MagicMock:
    """Magic-mock ContextService returning canned history; records calls."""
    svc = MagicMock()
    svc.history = AsyncMock(return_value=history)
    svc.append_user_turn = AsyncMock(
        return_value=_make_turn(role="user", content="q", turn_id="u1")
    )
    svc.append_assistant_turn = AsyncMock(
        return_value=_make_turn(role="assistant", content="a", turn_id="a1")
    )

    async def _update_summary(*, conversation: Conversation, summary: str) -> Conversation:
        return conversation.model_copy(update={"summary": summary})

    svc.update_summary = AsyncMock(side_effect=_update_summary)
    return svc


@pytest.mark.asyncio
async def test_first_turn_skips_rewrite_and_compaction() -> None:
    # Arrange — empty history; rewriter+compactor injected but should NOT be called.
    planner = _planner_returning(_evidence("chunk-1"))
    llm = _llm_with("Cited [chunk-1].")
    task = QATask(planner=planner, llm=llm)

    rewriter = AsyncMock()
    compactor = AsyncMock()
    composer = MagicMock()
    composer.compose.return_value = MagicMock(
        system="sys", user="usr", estimated_input_tokens=10, slots_used={}
    )
    memory = AsyncMock()
    memory.select_relevant.return_value = ()

    svc = _context_service_stub(history=())
    conversation = _make_conversation()

    # Act
    result = await task.answer_in_conversation(
        library_id="lib-a",
        conversation=conversation,
        question="What is RAG?",
        context_service=svc,
        rewriter=rewriter,
        compactor=compactor,
        memory=memory,
        composer=composer,
        settings_snapshot=_settings(),
        budget=ContextBudget(),
    )

    # Assert
    assert result.answer == "Cited [chunk-1]."
    assert {c.chunk_id for c in result.citations} == {"chunk-1"}
    rewriter.rewrite.assert_not_called()
    compactor.fit_auto.assert_not_called()
    svc.append_user_turn.assert_awaited_once()
    svc.append_assistant_turn.assert_awaited_once()
    llm.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_second_turn_invokes_rewriter_and_passes_recent_to_composer() -> None:
    # Arrange — one prior user/assistant pair so we have non-empty recent.
    history = (
        _make_turn(role="user", content="What is GraphRAG?", turn_id="u0"),
        _make_turn(role="assistant", content="A graph-based RAG.", turn_id="a0"),
    )
    planner = _planner_returning(_evidence("chunk-1"))
    llm = _llm_with("Builds on it [chunk-1].")
    task = QATask(planner=planner, llm=llm)

    rewriter = AsyncMock()
    rewriter.rewrite.return_value = RewriteResult(
        original="how does it improve?",
        rewritten="how does GraphRAG improve naive RAG?",
        confidence=0.95,
        used_history=True,
    )
    compactor = AsyncMock()
    compactor.fit_auto = AsyncMock()  # not used since len(history)<=window
    composer = MagicMock()
    composer.compose.return_value = MagicMock(
        system="sys", user="usr", estimated_input_tokens=10, slots_used={}
    )
    memory = AsyncMock()
    memory.select_relevant.return_value = ()

    svc = _context_service_stub(history=history)
    conversation = _make_conversation()

    # Act
    await task.answer_in_conversation(
        library_id="lib-a",
        conversation=conversation,
        question="how does it improve?",
        context_service=svc,
        rewriter=rewriter,
        compactor=compactor,
        memory=memory,
        composer=composer,
        settings_snapshot=_settings(recent_turns_window=4),
    )

    # Assert
    rewriter.rewrite.assert_awaited_once()
    call_kwargs = rewriter.rewrite.call_args.kwargs
    assert call_kwargs["question"] == "how does it improve?"
    assert call_kwargs["recent_turns"] == history

    # Composer received the same recent history as kept_turns.
    compose_kwargs = composer.compose.call_args.kwargs
    assert compose_kwargs["recent_turns"] == history

    # Retrieval used the rewritten query.
    planner_kwargs = planner.plan_and_retrieve.call_args.args
    assert planner_kwargs[1].text == "how does GraphRAG improve naive RAG?"

    # User turn persisted with rewritten_query (since used_history=True).
    user_call = svc.append_user_turn.call_args.kwargs
    assert user_call["rewritten_query"] == "how does GraphRAG improve naive RAG?"


@pytest.mark.asyncio
async def test_long_history_invokes_compactor_and_updates_summary() -> None:
    # Arrange — 6 turns > recent_turns_window=2, so compaction kicks in.
    history = tuple(
        _make_turn(
            role="user" if i % 2 == 0 else "assistant",
            content=f"turn {i}",
            turn_id=f"t{i}",
        )
        for i in range(6)
    )
    planner = _planner_returning(_evidence("chunk-1"))
    llm = _llm_with("Final answer [chunk-1].")
    task = QATask(planner=planner, llm=llm)

    rewriter = AsyncMock()
    rewriter.rewrite.return_value = RewriteResult(
        original="q",
        rewritten="q",
        confidence=1.0,
        used_history=False,
    )
    compactor = AsyncMock()
    compactor.fit_auto.return_value = CompactionResult(
        summary="NEW_SUMMARY",
        kept_turns=history[-2:],
        dropped_turns=4,
        summary_tokens=8,
        kept_tokens=12,
    )
    composer = MagicMock()
    composer.compose.return_value = MagicMock(
        system="sys", user="usr", estimated_input_tokens=10, slots_used={}
    )
    memory = AsyncMock()
    memory.select_relevant.return_value = ()

    svc = _context_service_stub(history=history)
    conversation = _make_conversation(summary="OLD_SUMMARY")

    # Act
    await task.answer_in_conversation(
        library_id="lib-a",
        conversation=conversation,
        question="next?",
        context_service=svc,
        rewriter=rewriter,
        compactor=compactor,
        memory=memory,
        composer=composer,
        settings_snapshot=_settings(recent_turns_window=2),
    )

    # Assert
    compactor.fit_auto.assert_awaited_once()
    svc.update_summary.assert_awaited_once()
    update_kwargs = svc.update_summary.call_args.kwargs
    assert update_kwargs["summary"] == "NEW_SUMMARY"

    compose_kwargs = composer.compose.call_args.kwargs
    assert compose_kwargs["summary"] == "NEW_SUMMARY"
    assert compose_kwargs["recent_turns"] == history[-2:]


@pytest.mark.asyncio
async def test_rewrite_disabled_in_settings_skips_rewriter() -> None:
    # Arrange — rewriter present but `rewrite_enabled=False` in snapshot.
    history = (
        _make_turn(role="user", content="prior question", turn_id="u0"),
        _make_turn(role="assistant", content="prior answer", turn_id="a0"),
    )
    planner = _planner_returning(_evidence("chunk-1"))
    llm = _llm_with("Answer [chunk-1].")
    task = QATask(planner=planner, llm=llm)

    rewriter = AsyncMock()
    compactor = AsyncMock()
    composer = MagicMock()
    composer.compose.return_value = MagicMock(
        system="sys", user="usr", estimated_input_tokens=10, slots_used={}
    )
    memory = AsyncMock()
    memory.select_relevant.return_value = ()

    svc = _context_service_stub(history=history)
    conversation = _make_conversation()

    # Act
    await task.answer_in_conversation(
        library_id="lib-a",
        conversation=conversation,
        question="follow-up",
        context_service=svc,
        rewriter=rewriter,
        compactor=compactor,
        memory=memory,
        composer=composer,
        settings_snapshot=_settings(rewrite_enabled=False),
    )

    # Assert
    rewriter.rewrite.assert_not_called()
    # Retrieval used original question.
    planner_args = planner.plan_and_retrieve.call_args.args
    assert planner_args[1].text == "follow-up"
    # User turn persisted WITHOUT rewritten_query.
    user_kwargs = svc.append_user_turn.call_args.kwargs
    assert user_kwargs["rewritten_query"] is None


@pytest.mark.asyncio
async def test_no_evidence_path_persists_assistant_turn_with_fallback_text() -> None:
    # Arrange — planner returns nothing.
    planner = _planner_returning()  # empty evidence
    llm = _llm_with("never used")
    task = QATask(planner=planner, llm=llm)

    rewriter = AsyncMock()
    compactor = AsyncMock()
    composer = MagicMock()
    memory = AsyncMock()
    memory.select_relevant.return_value = ()

    svc = _context_service_stub(history=())
    conversation = _make_conversation()

    # Act
    result = await task.answer_in_conversation(
        library_id="lib-a",
        conversation=conversation,
        question="What is X?",
        context_service=svc,
        rewriter=rewriter,
        compactor=compactor,
        memory=memory,
        composer=composer,
        settings_snapshot=_settings(),
    )

    # Assert
    assert "could not find" in result.answer.lower()
    llm.complete.assert_not_called()
    # Both turns persisted: user, then placeholder assistant.
    svc.append_user_turn.assert_awaited_once()
    svc.append_assistant_turn.assert_awaited_once()


@pytest.mark.asyncio
async def test_composer_none_falls_back_to_legacy_prompt() -> None:
    # Arrange
    planner = _planner_returning(_evidence("chunk-1"))
    llm = _llm_with("From legacy [chunk-1].")
    task = QATask(planner=planner, llm=llm)

    svc = _context_service_stub(history=())
    conversation = _make_conversation()

    # Act
    result = await task.answer_in_conversation(
        library_id="lib-a",
        conversation=conversation,
        question="legacy?",
        context_service=svc,
        rewriter=None,
        compactor=None,
        memory=None,
        composer=None,
        settings_snapshot=_settings(),
    )

    # Assert
    assert result.answer == "From legacy [chunk-1]."
    # Legacy prompt path produced a 2-message exchange.
    sent_messages = llm.complete.call_args.args[0]
    assert len(sent_messages) == 2
    assert sent_messages[0].role == "system"
    assert sent_messages[1].role == "user"
