"""Tests for LLMQueryRewriter — HyDE / step_back / decompose."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.llm.protocols import LLMResponse, Message
from packages.retrieval.rewriter import (
    LLMQueryRewriter,
    QueryRewriterConfig,
    RewriteSet,
    RewrittenQuery,
)


class FakeLLM:
    """LLM that picks a canned response based on a strategy keyword in the system prompt."""

    def __init__(self, replies: dict[str, str]) -> None:
        self._replies = replies
        self.calls: list[list[Message]] = []

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse:
        self.calls.append(messages)
        system = next((m.content for m in messages if m.role == "system"), "")
        for keyword, reply in self._replies.items():
            if keyword in system:
                return LLMResponse(text=reply, model="fake")
        return LLMResponse(text="", model="fake")


class FailingLLM:
    """LLM that raises a transport-style error on every call."""

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse:
        msg = "boom"
        raise RuntimeError(msg)


_HYDE_HYPOTHETICAL = (
    "GraphRAG indexes a corpus into community summaries via Leiden, "
    "then queries those summaries for global questions. "
    "It improves recall for high-level synthesis."
)


def _hyde_replies() -> dict[str, str]:
    return {
        "HyDE": _HYDE_HYPOTHETICAL,
        "step-back": "What is the general principle behind community-summary retrieval?",
        "decomposer": "What is GraphRAG's indexing pipeline?",
    }


class TestPassthrough:
    async def test_passthrough_always_first(self) -> None:
        rewriter = LLMQueryRewriter(
            FakeLLM(_hyde_replies()),
            QueryRewriterConfig(strategies=("hyde",)),
        )
        rs = await rewriter.rewrite("How does GraphRAG work?")
        assert rs.queries[0].strategy == "passthrough"
        assert rs.queries[0].rewritten == "How does GraphRAG work?"
        assert rs.queries[0].original == "How does GraphRAG work?"

    async def test_passthrough_present_when_no_strategies(self) -> None:
        rewriter = LLMQueryRewriter(
            FakeLLM({}),
            QueryRewriterConfig(strategies=()),
        )
        rs = await rewriter.rewrite("hello world")
        assert len(rs.queries) == 1
        assert rs.queries[0].strategy == "passthrough"


class TestStrategies:
    async def test_hyde_returns_hypothetical_answer(self) -> None:
        rewriter = LLMQueryRewriter(
            FakeLLM(_hyde_replies()),
            QueryRewriterConfig(strategies=("hyde",)),
        )
        rs = await rewriter.rewrite("How does GraphRAG work?")
        hyde = rs.queries[1]
        assert hyde.strategy == "hyde"
        assert "GraphRAG" in hyde.rewritten
        assert hyde.rewritten != hyde.original

    async def test_step_back_returns_general_question(self) -> None:
        rewriter = LLMQueryRewriter(
            FakeLLM(_hyde_replies()),
            QueryRewriterConfig(strategies=("step_back",)),
        )
        rs = await rewriter.rewrite("How does GraphRAG work?")
        sb = rs.queries[1]
        assert sb.strategy == "step_back"
        assert sb.rewritten.startswith("What is the general principle")

    async def test_decompose_returns_subquestion(self) -> None:
        rewriter = LLMQueryRewriter(
            FakeLLM(_hyde_replies()),
            QueryRewriterConfig(strategies=("decompose",)),
        )
        rs = await rewriter.rewrite(
            "How does GraphRAG work and how does it compare to vanilla RAG?"
        )
        dq = rs.queries[1]
        assert dq.strategy == "decompose"
        assert dq.rewritten == "What is GraphRAG's indexing pipeline?"

    async def test_multiple_strategies_one_rewrite_each(self) -> None:
        rewriter = LLMQueryRewriter(
            FakeLLM(_hyde_replies()),
            QueryRewriterConfig(strategies=("hyde", "step_back", "decompose")),
        )
        rs = await rewriter.rewrite("How does GraphRAG work?")
        # passthrough + 3 rewrites
        assert len(rs.queries) == 4
        strategies = [q.strategy for q in rs.queries]
        assert strategies == ["passthrough", "hyde", "step_back", "decompose"]


class TestFailureFallback:
    async def test_llm_failure_falls_back_to_passthrough(self) -> None:
        rewriter = LLMQueryRewriter(
            FailingLLM(),
            QueryRewriterConfig(strategies=("hyde",)),
        )
        rs = await rewriter.rewrite("What is HyDE?")
        # passthrough + 1 fallback
        assert len(rs.queries) == 2
        fallback = rs.queries[1]
        assert fallback.strategy == "passthrough"
        assert fallback.rewritten == "What is HyDE?"
        assert "hyde failed" in fallback.rationale

    async def test_empty_llm_response_falls_back(self) -> None:
        rewriter = LLMQueryRewriter(
            FakeLLM({}),  # no keywords match → empty text
            QueryRewriterConfig(strategies=("hyde",)),
        )
        rs = await rewriter.rewrite("anything")
        fallback = rs.queries[1]
        assert fallback.strategy == "passthrough"
        assert "empty" in fallback.rationale


class TestConfigValidation:
    def test_unsupported_strategy_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported strategy"):
            LLMQueryRewriter(
                FakeLLM({}),
                QueryRewriterConfig(strategies=("not_a_strategy",)),
            )

    def test_default_config_uses_hyde(self) -> None:
        config = QueryRewriterConfig()
        assert config.strategies == ("hyde",)
        assert config.temperature == 0.3
        assert config.max_tokens == 200
        assert config.timeout_s == 60.0


class TestModelImmutability:
    def test_rewritten_query_is_frozen(self) -> None:
        q = RewrittenQuery(original="x", rewritten="y", strategy="hyde", rationale="r")
        with pytest.raises(ValidationError):
            q.rewritten = "z"  # type: ignore[misc]

    def test_rewrite_set_requires_at_least_one_query(self) -> None:
        with pytest.raises(ValidationError):
            RewriteSet(original="x", queries=())

    def test_rewrite_set_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            RewriteSet.model_validate(
                {
                    "original": "x",
                    "queries": [
                        {
                            "original": "x",
                            "rewritten": "y",
                            "strategy": "hyde",
                            "rationale": "",
                        }
                    ],
                    "extra": "nope",
                }
            )
