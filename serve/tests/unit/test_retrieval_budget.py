"""Tests for RetrievalBudget + RetrievalTrace models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.retrieval.protocols import (
    BudgetUsage,
    RetrievalBudget,
    RetrievalStep,
    RetrievalTrace,
    StepCost,
)


class TestRetrievalBudget:
    def test_defaults_are_safe(self) -> None:
        b = RetrievalBudget()
        assert b.max_steps == 8
        assert b.max_llm_calls == 20
        assert b.max_input_tokens == 32000
        assert b.timeout_s == 120.0

    def test_is_frozen(self) -> None:
        b = RetrievalBudget()
        with pytest.raises(ValidationError):
            b.max_steps = 10  # type: ignore[misc]

    def test_min_caps_enforced(self) -> None:
        with pytest.raises(ValidationError):
            RetrievalBudget(max_steps=0)
        with pytest.raises(ValidationError):
            RetrievalBudget(max_llm_calls=0)
        with pytest.raises(ValidationError):
            RetrievalBudget(timeout_s=0)


class TestStepCost:
    def test_defaults_zero(self) -> None:
        c = StepCost()
        assert c.llm_calls == 0
        assert c.input_tokens == 0
        assert c.cost_usd == 0.0


class TestRetrievalStep:
    def test_basic_step(self) -> None:
        s = RetrievalStep(
            step_idx=0,
            thought="I should search for X",
            action="vector_search",
            action_input="X",
            observation="Found 5 chunks",
        )
        assert s.step_idx == 0
        assert s.action == "vector_search"

    def test_step_idx_validated(self) -> None:
        with pytest.raises(ValidationError):
            RetrievalStep(step_idx=-1)


class TestRetrievalTrace:
    def test_minimal_trace(self) -> None:
        t = RetrievalTrace(library_id="test-lib", query="hello")
        assert t.library_id == "test-lib"
        assert t.terminated_reason == "answer_ready"
        assert len(t.steps) == 0

    def test_trace_with_steps(self) -> None:
        steps = (
            RetrievalStep(step_idx=0, thought="t0", action="vector_search"),
            RetrievalStep(step_idx=1, thought="t1", action="kg_neighborhood"),
        )
        t = RetrievalTrace(
            library_id="test-lib",
            query="hello",
            planner="react",
            steps=steps,
            budget_used=BudgetUsage(steps=2, llm_calls=2),
        )
        assert len(t.steps) == 2
        assert t.budget_used.steps == 2

    def test_terminated_reason_literal(self) -> None:
        with pytest.raises(ValidationError):
            RetrievalTrace(
                library_id="test-lib",
                query="x",
                terminated_reason="invalid",  # type: ignore[arg-type]
            )

    def test_serialization_roundtrip(self) -> None:
        t = RetrievalTrace(
            library_id="test-lib",
            query="hello",
            steps=(
                RetrievalStep(
                    step_idx=0,
                    thought="t",
                    action="a",
                    cost=StepCost(llm_calls=1, input_tokens=100),
                ),
            ),
        )
        data = t.model_dump()
        restored = RetrievalTrace.model_validate(data)
        assert restored == t
