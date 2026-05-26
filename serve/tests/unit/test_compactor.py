"""Tests for TurnCompactor — suffix selection + summarization fallback."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from packages.context.compactor import CompactionResult, TurnCompactor
from packages.context.protocols import ContextBudget, Turn
from packages.llm.protocols import LLMResponse
from packages.orchestration.protocols import Citation


class _LenCounter:
    """Stub TokenCounter where 1 char = 1 token. Predictable test math."""

    def count(self, text: str) -> int:
        return len(text)


def _turn(turn_id: str, role: str, content: str, *, snippet: str = "") -> Turn:
    citations: tuple[Citation, ...] = ()
    if snippet:
        citations = (
            Citation(
                chunk_id=f"chunk::{turn_id}",
                doc_id="doc1",
                snippet=snippet,
            ),
        )
    return Turn(
        conversation_id="conv1",
        turn_id=turn_id,
        role=role,  # type: ignore[arg-type]
        content=content,
        citations=citations,
        created_at=datetime(2026, 4, 28, tzinfo=UTC),
    )


def _llm_with_text(text: str) -> AsyncMock:
    mock = AsyncMock()
    mock.complete.return_value = LLMResponse(
        text=text, model="m", input_tokens=10, output_tokens=20, cost_usd=0.0
    )
    return mock


def _budget(*, recent_turns_max: int = 100, summary_max: int = 100) -> ContextBudget:
    return ContextBudget(
        max_input_tokens=4096,
        recent_turns_max=recent_turns_max,
        summary_max=summary_max,
    )


class TestTurnCompactor:
    @pytest.mark.asyncio
    async def test_empty_turns_returns_empty_no_llm_call(self) -> None:
        # Arrange
        llm = _llm_with_text("never used")
        compactor = TurnCompactor(llm=llm, counter=_LenCounter(), budget=_budget())

        # Act
        result = await compactor.fit_auto(prior_summary="", turns=())

        # Assert
        assert isinstance(result, CompactionResult)
        assert result.kept_turns == ()
        assert result.dropped_turns == 0
        assert result.summary == ""
        llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_fit_auto_skips_llm_when_within_budget(self) -> None:
        # Arrange
        llm = _llm_with_text("never used")
        budget = _budget(recent_turns_max=100, summary_max=100)
        compactor = TurnCompactor(llm=llm, counter=_LenCounter(), budget=budget)
        turns = (
            _turn("t1", "user", "hi"),
            _turn("t2", "assistant", "hello"),
        )

        # Act
        result = await compactor.fit_auto(prior_summary="", turns=turns)

        # Assert
        assert result.kept_turns == turns
        assert result.dropped_turns == 0
        llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_fit_auto_passes_prior_summary_through_when_no_compaction(
        self,
    ) -> None:
        # Arrange
        llm = _llm_with_text("never used")
        compactor = TurnCompactor(llm=llm, counter=_LenCounter(), budget=_budget())
        turns = (_turn("t1", "user", "ok"),)

        # Act
        result = await compactor.fit_auto(prior_summary="prior history summary here", turns=turns)

        # Assert
        assert result.summary == "prior history summary here"
        assert result.kept_turns == turns
        llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_many_turns_over_budget_keeps_suffix_and_calls_llm_once(
        self,
    ) -> None:
        # Arrange — recent_turns_max=20, each turn ~10 tokens of content
        llm = _llm_with_text("compacted summary")
        budget = _budget(recent_turns_max=20, summary_max=200)
        compactor = TurnCompactor(llm=llm, counter=_LenCounter(), budget=budget)
        # 5 turns, each 10 tokens — only the last 2 fit (20 tokens budget).
        turns = tuple(
            _turn(f"t{i}", "user" if i % 2 == 0 else "assistant", "x" * 10) for i in range(5)
        )

        # Act
        result = await compactor.fit(prior_summary="", turns=turns)

        # Assert
        assert llm.complete.call_count == 1
        assert len(result.kept_turns) == 2
        assert result.kept_turns[0].turn_id == "t3"
        assert result.kept_turns[1].turn_id == "t4"
        assert result.dropped_turns == 3
        assert result.summary == "compacted summary"
        assert result.kept_tokens == 20

    @pytest.mark.asyncio
    async def test_kept_turns_preserve_chronological_order(self) -> None:
        # Arrange
        llm = _llm_with_text("ok")
        budget = _budget(recent_turns_max=15, summary_max=200)
        compactor = TurnCompactor(llm=llm, counter=_LenCounter(), budget=budget)
        turns = tuple(_turn(f"t{i}", "user", "x" * 5) for i in range(5))

        # Act
        result = await compactor.fit(prior_summary="", turns=turns)

        # Assert — last 3 turns kept (5+5+5=15), order oldest-of-kept first
        ids = [t.turn_id for t in result.kept_turns]
        assert ids == ["t2", "t3", "t4"]

    @pytest.mark.asyncio
    async def test_prior_summary_merged_into_new_summary_body(self) -> None:
        # Arrange
        llm = _llm_with_text("merged result")
        budget = _budget(recent_turns_max=5, summary_max=200)
        compactor = TurnCompactor(llm=llm, counter=_LenCounter(), budget=budget)
        turns = (
            _turn("t1", "user", "first question about RAG"),
            _turn("t2", "assistant", "answer mentioning Leiden"),
            _turn("t3", "user", "ok"),
        )

        # Act
        result = await compactor.fit(prior_summary="EARLIER_SUMMARY", turns=turns)

        # Assert
        llm.complete.assert_called_once()
        call_args = llm.complete.call_args
        messages = call_args.args[0]
        # The body should include both prior summary + the dropped turns
        user_msg = messages[1].content
        assert "EARLIER_SUMMARY" in user_msg
        assert "first question about RAG" in user_msg
        assert result.summary == "merged result"

    @pytest.mark.asyncio
    async def test_llm_error_falls_back_to_prior_summary(self) -> None:
        # Arrange
        llm = AsyncMock()
        llm.complete.side_effect = RuntimeError("llm down")
        budget = _budget(recent_turns_max=5, summary_max=200)
        compactor = TurnCompactor(llm=llm, counter=_LenCounter(), budget=budget)
        turns = (
            _turn("t1", "user", "old turn content here"),
            _turn("t2", "assistant", "old answer"),
            _turn("t3", "user", "ok"),
        )

        # Act
        result = await compactor.fit(prior_summary="SAFE_PRIOR", turns=turns)

        # Assert — never lose data: prior summary preserved, kept_turns intact
        assert result.summary == "SAFE_PRIOR"
        assert len(result.kept_turns) == 1
        assert result.kept_turns[0].turn_id == "t3"
        assert result.dropped_turns == 2

    @pytest.mark.asyncio
    async def test_citation_metadata_counted_in_turn_tokens(self) -> None:
        # Arrange — citation snippet adds tokens that count toward budget
        llm = _llm_with_text("summary")
        budget = _budget(recent_turns_max=10, summary_max=200)
        compactor = TurnCompactor(llm=llm, counter=_LenCounter(), budget=budget)
        # Content = 5 chars; snippet = 10 chars; chunk_id = "chunk::tX" 9 chars
        # Total per turn ≈ 24 tokens > 10 → only 0 turns should fit.
        turn = _turn("tX", "user", "abcde", snippet="x" * 10)

        # Act
        result = await compactor.fit(prior_summary="", turns=(turn,))

        # Assert
        assert result.kept_turns == ()
        assert result.dropped_turns == 1

    @pytest.mark.asyncio
    async def test_llm_called_with_temperature_zero(self) -> None:
        # Arrange
        llm = _llm_with_text("s")
        budget = _budget(recent_turns_max=2, summary_max=200)
        compactor = TurnCompactor(llm=llm, counter=_LenCounter(), budget=budget)
        turns = (_turn("t1", "user", "old"), _turn("t2", "user", "new"))

        # Act
        await compactor.fit(prior_summary="", turns=turns)

        # Assert
        kwargs = llm.complete.call_args.kwargs
        assert kwargs["temperature"] == 0.0
