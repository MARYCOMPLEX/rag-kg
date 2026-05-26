"""Tests for `packages.context.query_rewriter.QueryRewriter`.

NOTE: M8.A3 contract requested `tests/unit/test_query_rewriter.py`, but that
filename is already taken by tests for `packages.retrieval.rewriter.LLMQueryRewriter`
(a different HyDE/decompose rewriter). We therefore land these tests under
`test_context_query_rewriter.py` to avoid a pytest collection collision.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from packages.context.protocols import Turn
from packages.context.query_rewriter import QueryRewriter
from packages.llm.protocols import LLMClient, LLMResponse


def _user_turn(content: str, idx: int = 0) -> Turn:
    return Turn(
        conversation_id="conv-1",
        turn_id=f"turn-u{idx}",
        role="user",
        content=content,
        created_at=datetime(2026, 4, 28, 12, 0, idx, tzinfo=UTC),
    )


def _assistant_turn(content: str, idx: int = 0) -> Turn:
    return Turn(
        conversation_id="conv-1",
        turn_id=f"turn-a{idx}",
        role="assistant",
        content=content,
        created_at=datetime(2026, 4, 28, 12, 0, idx, tzinfo=UTC),
    )


def _llm_response(text: str) -> LLMResponse:
    return LLMResponse(text=text, model="fake-model", input_tokens=10, output_tokens=5)


def _make_mock_llm(text: str) -> AsyncMock:
    mock = AsyncMock(spec=LLMClient)
    mock.complete = AsyncMock(return_value=_llm_response(text))
    return mock


class TestPassthroughHeuristics:
    async def test_empty_history_returns_original_no_llm_call(self) -> None:
        # Arrange
        llm = _make_mock_llm("ignored")
        rewriter = QueryRewriter(llm=llm)

        # Act
        result = await rewriter.rewrite(question="What is GraphRAG?", recent_turns=())

        # Assert
        assert result.rewritten == "What is GraphRAG?"
        assert result.original == "What is GraphRAG?"
        assert result.used_history is False
        assert result.confidence == 1.0
        llm.complete.assert_not_called()

    async def test_no_anaphor_with_single_turn_skips_llm(self) -> None:
        # Arrange
        llm = _make_mock_llm("ignored")
        rewriter = QueryRewriter(llm=llm)
        history = (_user_turn("Hello there", idx=0),)

        # Act
        result = await rewriter.rewrite(
            question="Explain Leiden clustering in detail.",
            recent_turns=history,
        )

        # Assert
        assert result.rewritten == "Explain Leiden clustering in detail."
        assert result.used_history is False
        assert result.confidence == 1.0
        llm.complete.assert_not_called()


class TestRewriteFlow:
    async def test_anaphor_with_history_triggers_llm_rewrite(self) -> None:
        # Arrange
        payload = json.dumps(
            {
                "rewritten": "How does GraphRAG perform community detection?",
                "confidence": 0.92,
                "explanation": "'it' refers to GraphRAG from prior turn.",
            }
        )
        llm = _make_mock_llm(payload)
        rewriter = QueryRewriter(llm=llm)
        history = (
            _user_turn("Tell me about GraphRAG.", idx=0),
            _assistant_turn("GraphRAG indexes via Leiden clustering.", idx=1),
        )

        # Act
        result = await rewriter.rewrite(question="How does it do that?", recent_turns=history)

        # Assert
        assert result.used_history is True
        assert result.rewritten == "How does GraphRAG perform community detection?"
        assert result.original == "How does it do that?"
        assert result.confidence == pytest.approx(0.92)
        llm.complete.assert_awaited_once()

    async def test_two_turns_without_anaphor_still_calls_llm(self) -> None:
        # Implicit ellipsis: ≥ 2 prior turns → LLM consulted even without
        # an explicit pronoun.
        # Arrange
        payload = json.dumps({"rewritten": "Compare HyDE versus step-back.", "confidence": 0.8})
        llm = _make_mock_llm(payload)
        rewriter = QueryRewriter(llm=llm)
        history = (
            _user_turn("Tell me about HyDE.", idx=0),
            _assistant_turn("HyDE generates a hypothetical answer.", idx=1),
        )

        # Act
        result = await rewriter.rewrite(question="Compare with step-back.", recent_turns=history)

        # Assert
        assert result.used_history is True
        assert result.rewritten == "Compare HyDE versus step-back."
        llm.complete.assert_awaited_once()


class TestFallbacks:
    async def test_malformed_json_falls_back_to_original(self) -> None:
        # Arrange
        llm = _make_mock_llm("not json at all { broken")
        rewriter = QueryRewriter(llm=llm)
        history = (_user_turn("Tell me about GraphRAG.", idx=0),)

        # Act
        result = await rewriter.rewrite(question="What about it?", recent_turns=history)

        # Assert
        assert result.rewritten == "What about it?"
        assert result.used_history is False
        assert result.confidence == 0.0
        llm.complete.assert_awaited_once()

    async def test_low_confidence_falls_back_to_original(self) -> None:
        # Arrange
        payload = json.dumps(
            {
                "rewritten": "wild guess",
                "confidence": 0.4,
                "explanation": "not sure",
            }
        )
        llm = _make_mock_llm(payload)
        rewriter = QueryRewriter(llm=llm, min_confidence=0.6)
        history = (_user_turn("Tell me about GraphRAG.", idx=0),)

        # Act
        result = await rewriter.rewrite(question="What about it?", recent_turns=history)

        # Assert
        assert result.rewritten == "What about it?"
        assert result.used_history is False
        assert result.confidence == pytest.approx(0.4)

    async def test_high_confidence_uses_rewrite(self) -> None:
        # Arrange
        payload = json.dumps(
            {
                "rewritten": "What is GraphRAG's indexing pipeline?",
                "confidence": 0.85,
                "explanation": "resolves 'it' to GraphRAG",
            }
        )
        llm = _make_mock_llm(payload)
        rewriter = QueryRewriter(llm=llm, min_confidence=0.6)
        history = (_user_turn("Tell me about GraphRAG.", idx=0),)

        # Act
        result = await rewriter.rewrite(
            question="What is its indexing pipeline?",
            recent_turns=history,
        )

        # Assert
        assert result.used_history is True
        assert result.rewritten == "What is GraphRAG's indexing pipeline?"
        assert result.confidence == pytest.approx(0.85)

    async def test_llm_transport_error_falls_back_to_original(self) -> None:
        # Arrange
        llm = AsyncMock(spec=LLMClient)
        llm.complete = AsyncMock(side_effect=RuntimeError("network down"))
        rewriter = QueryRewriter(llm=llm)
        history = (_user_turn("Tell me about HyDE.", idx=0),)

        # Act
        result = await rewriter.rewrite(question="How does it work?", recent_turns=history)

        # Assert
        assert result.rewritten == "How does it work?"
        assert result.used_history is False
        assert result.confidence == 0.0


class TestChineseAnaphor:
    async def test_chinese_anaphor_triggers_rewrite(self) -> None:
        # Arrange
        payload = json.dumps(
            {
                "rewritten": "再讲讲 GraphRAG 的索引流程。",
                "confidence": 0.9,
                "explanation": "解析“它”为 GraphRAG",
            }
        )
        llm = _make_mock_llm(payload)
        rewriter = QueryRewriter(llm=llm)
        history = (_user_turn("讲一下 GraphRAG。", idx=0),)

        # Act
        result = await rewriter.rewrite(question="再讲讲它的索引流程。", recent_turns=history)

        # Assert
        assert result.used_history is True
        assert "GraphRAG" in result.rewritten
        llm.complete.assert_awaited_once()


class TestProperties:
    def test_is_disabled_property_is_false(self) -> None:
        # Arrange / Act
        rewriter = QueryRewriter(llm=_make_mock_llm(""))

        # Assert
        assert rewriter.is_disabled is False
