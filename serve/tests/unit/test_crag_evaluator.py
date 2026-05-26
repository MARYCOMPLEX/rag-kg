"""Tests for CRAGEvaluator — the M4.3 corrective-RAG relevance grader."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.core.models import Chunk
from packages.llm.protocols import LLMResponse, Message
from packages.retrieval.critics import (
    CRAGAssessment,
    CRAGEvaluator,
    CRAGEvaluatorConfig,
    EvidenceGrade,
    GradeLabel,
    _extract_json_block,
)
from packages.retrieval.protocols import RetrievedEvidence


def _evidence(chunk_id: str, text: str = "x") -> RetrievedEvidence:
    return RetrievedEvidence(
        chunk=Chunk(library_id="lib", chunk_id=chunk_id, doc_id="d", text=text),
        score=0.5,
        source="vector",
    )


class FakeLLM:
    """Returns a single canned response for every call."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls = 0

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse:
        self.calls += 1
        return LLMResponse(text=self._response, model="fake")


class FailingLLM:
    """Always raises — used to test fail-open behaviour."""

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse:
        raise RuntimeError("boom")


class TestExtractJsonBlock:
    def test_plain_array(self) -> None:
        assert _extract_json_block('[{"a": 1}]') == '[{"a": 1}]'

    def test_with_code_fence(self) -> None:
        assert _extract_json_block('```json\n[{"a": 1}]\n```') == '[{"a": 1}]'

    def test_with_prose_around(self) -> None:
        assert _extract_json_block('Here:\n[{"a": 1}]\ndone') == '[{"a": 1}]'

    def test_no_array_returns_none(self) -> None:
        assert _extract_json_block("no json here") is None


class TestCRAGEvaluator:
    @pytest.mark.asyncio
    async def test_empty_evidence_returns_ambiguous_no_trigger(self) -> None:
        # Arrange
        evaluator = CRAGEvaluator(llm=FakeLLM("[]"))

        # Act
        result = await evaluator.evaluate("q", [])

        # Assert
        assert isinstance(result, CRAGAssessment)
        assert result.overall == GradeLabel.AMBIGUOUS
        assert result.grades == ()
        assert result.trigger_rewrite is False

    @pytest.mark.asyncio
    async def test_empty_evidence_skips_llm_call(self) -> None:
        llm = FakeLLM("[]")
        evaluator = CRAGEvaluator(llm=llm)

        await evaluator.evaluate("q", [])

        assert llm.calls == 0

    @pytest.mark.asyncio
    async def test_high_scores_yield_correct_no_trigger(self) -> None:
        payload = (
            '[{"index": 0, "score": 0.92, "label": "CORRECT", "reason": "direct"},'
            ' {"index": 1, "score": 0.81, "label": "CORRECT", "reason": "direct"}]'
        )
        evaluator = CRAGEvaluator(llm=FakeLLM(payload))

        result = await evaluator.evaluate("q", [_evidence("c1"), _evidence("c2")])

        assert result.overall == GradeLabel.CORRECT
        assert result.trigger_rewrite is False
        assert len(result.grades) == 2
        assert result.grades[0].chunk_id == "c1"
        assert result.grades[0].label == GradeLabel.CORRECT

    @pytest.mark.asyncio
    async def test_all_low_scores_yield_incorrect_with_trigger(self) -> None:
        payload = (
            '[{"index": 0, "score": 0.10, "label": "INCORRECT", "reason": "off"},'
            ' {"index": 1, "score": 0.05, "label": "INCORRECT", "reason": "off"}]'
        )
        evaluator = CRAGEvaluator(llm=FakeLLM(payload))

        result = await evaluator.evaluate("q", [_evidence("c1"), _evidence("c2")])

        assert result.overall == GradeLabel.INCORRECT
        assert result.trigger_rewrite is True
        assert all(g.label == GradeLabel.INCORRECT for g in result.grades)

    @pytest.mark.asyncio
    async def test_mixed_scores_yield_ambiguous(self) -> None:
        # One mid-tier (0.5), one low (0.1) — neither hits CORRECT bar (0.7),
        # not all below INCORRECT bar (0.3) → AMBIGUOUS, trigger rewrite.
        payload = (
            '[{"index": 0, "score": 0.50, "label": "AMBIGUOUS", "reason": "partial"},'
            ' {"index": 1, "score": 0.10, "label": "INCORRECT", "reason": "off"}]'
        )
        evaluator = CRAGEvaluator(llm=FakeLLM(payload))

        result = await evaluator.evaluate("q", [_evidence("c1"), _evidence("c2")])

        assert result.overall == GradeLabel.AMBIGUOUS
        assert result.trigger_rewrite is True

    @pytest.mark.asyncio
    async def test_ambiguous_with_one_correct_does_not_trigger(self) -> None:
        # One CORRECT chunk → overall CORRECT, no rewrite.
        payload = (
            '[{"index": 0, "score": 0.85, "label": "CORRECT", "reason": "good"},'
            ' {"index": 1, "score": 0.10, "label": "INCORRECT", "reason": "off"}]'
        )
        evaluator = CRAGEvaluator(llm=FakeLLM(payload))

        result = await evaluator.evaluate("q", [_evidence("c1"), _evidence("c2")])

        assert result.overall == GradeLabel.CORRECT
        assert result.trigger_rewrite is False

    @pytest.mark.asyncio
    async def test_llm_failure_returns_ambiguous_fail_open(self) -> None:
        evaluator = CRAGEvaluator(llm=FailingLLM())

        result = await evaluator.evaluate("q", [_evidence("c1")])

        assert result.overall == GradeLabel.AMBIGUOUS
        assert result.grades == ()
        assert result.trigger_rewrite is False

    @pytest.mark.asyncio
    async def test_malformed_json_yields_empty_grades_ambiguous(self) -> None:
        evaluator = CRAGEvaluator(llm=FakeLLM("not json at all"))

        result = await evaluator.evaluate("q", [_evidence("c1")])

        assert result.overall == GradeLabel.AMBIGUOUS
        assert result.grades == ()

    @pytest.mark.asyncio
    async def test_partially_invalid_json_drops_bad_rows(self) -> None:
        # Second row missing required `index` → dropped; first survives.
        payload = (
            '[{"index": 0, "score": 0.9, "label": "CORRECT", "reason": "ok"},'
            ' {"score": 0.4, "label": "AMBIGUOUS"}]'
        )
        evaluator = CRAGEvaluator(llm=FakeLLM(payload))

        result = await evaluator.evaluate("q", [_evidence("c1"), _evidence("c2")])

        assert len(result.grades) == 1
        assert result.grades[0].chunk_id == "c1"
        assert result.overall == GradeLabel.CORRECT

    @pytest.mark.asyncio
    async def test_out_of_range_index_dropped(self) -> None:
        # index=5 is out of range for a single-evidence batch.
        payload = '[{"index": 5, "score": 0.9, "label": "CORRECT", "reason": "x"}]'
        evaluator = CRAGEvaluator(llm=FakeLLM(payload))

        result = await evaluator.evaluate("q", [_evidence("c1")])

        assert result.grades == ()
        assert result.overall == GradeLabel.AMBIGUOUS

    @pytest.mark.asyncio
    async def test_score_clamped_to_unit_interval(self) -> None:
        payload = (
            '[{"index": 0, "score": 1.7, "label": "CORRECT", "reason": "x"},'
            ' {"index": 1, "score": -0.4, "label": "INCORRECT", "reason": "x"}]'
        )
        evaluator = CRAGEvaluator(llm=FakeLLM(payload))

        result = await evaluator.evaluate("q", [_evidence("c1"), _evidence("c2")])

        assert result.grades[0].score == 1.0
        assert result.grades[1].score == 0.0

    @pytest.mark.asyncio
    async def test_unknown_label_falls_back_to_score_threshold(self) -> None:
        payload = '[{"index": 0, "score": 0.9, "label": "FOO", "reason": "x"}]'
        evaluator = CRAGEvaluator(llm=FakeLLM(payload))

        result = await evaluator.evaluate("q", [_evidence("c1")])

        # Score (0.9) >= correct_threshold (0.7) → CORRECT
        assert result.grades[0].label == GradeLabel.CORRECT

    @pytest.mark.asyncio
    async def test_code_fenced_response_parses(self) -> None:
        payload = '```json\n[{"index": 0, "score": 0.85, "label": "CORRECT", "reason": "x"}]\n```'
        evaluator = CRAGEvaluator(llm=FakeLLM(payload))

        result = await evaluator.evaluate("q", [_evidence("c1")])

        assert result.overall == GradeLabel.CORRECT
        assert len(result.grades) == 1

    @pytest.mark.asyncio
    async def test_non_array_json_returns_empty(self) -> None:
        # Object not array → not parseable as our list shape.
        evaluator = CRAGEvaluator(llm=FakeLLM('{"index": 0}'))

        result = await evaluator.evaluate("q", [_evidence("c1")])

        assert result.grades == ()
        assert result.overall == GradeLabel.AMBIGUOUS

    @pytest.mark.asyncio
    async def test_custom_thresholds_change_aggregate(self) -> None:
        # With correct_threshold=0.5, score=0.6 should be CORRECT.
        payload = '[{"index": 0, "score": 0.6, "label": "CORRECT", "reason": "x"}]'
        evaluator = CRAGEvaluator(
            llm=FakeLLM(payload),
            config=CRAGEvaluatorConfig(correct_threshold=0.5),
        )

        result = await evaluator.evaluate("q", [_evidence("c1")])

        assert result.overall == GradeLabel.CORRECT
        assert result.trigger_rewrite is False


class TestEvidenceGrade:
    def test_grade_is_frozen(self) -> None:
        grade = EvidenceGrade(chunk_id="c1", score=0.8, label=GradeLabel.CORRECT, reason="ok")
        with pytest.raises(ValidationError):
            grade.score = 0.1  # type: ignore[misc]

    def test_score_must_be_in_unit_interval(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceGrade(chunk_id="c1", score=1.5, label=GradeLabel.CORRECT)
