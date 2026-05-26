"""Unit tests for deterministic (LLM-free) evaluation metrics."""

from __future__ import annotations

import pytest

from packages.core.models import Chunk
from packages.evaluation.metrics.deterministic import (
    CitationPresentMetric,
    KeyPointCoverageMetric,
    LatencyConfig,
    LatencyMetric,
    MustNotContainMetric,
    RecallAtKMetric,
)
from packages.evaluation.protocols import EvalSample
from packages.orchestration.protocols import AnsweredQuery
from packages.retrieval.protocols import RetrievedEvidence


def _sample(
    *,
    expected_evidence_doc_ids: tuple[str, ...] = (),
    expected_key_points: tuple[str, ...] = (),
    must_not_contain: tuple[str, ...] = (),
) -> EvalSample:
    return EvalSample(
        sample_id="s1",
        library_id="lib",
        suite="qa",
        suite_version="v1",
        question="q?",
        expected_evidence_doc_ids=expected_evidence_doc_ids,
        expected_key_points=expected_key_points,
        must_not_contain=must_not_contain,
    )


def _evidence(doc_id: str, chunk_id: str = "c") -> RetrievedEvidence:
    return RetrievedEvidence(
        chunk=Chunk(
            library_id="lib",
            chunk_id=chunk_id,
            doc_id=doc_id,
            text="t",
        ),
        score=0.9,
        source="vector",
    )


def _answered(
    *,
    answer: str = "",
    retrieved: tuple[RetrievedEvidence, ...] = (),
    duration_ms: int = 0,
    question: str = "q?",
) -> AnsweredQuery:
    return AnsweredQuery(
        library_id="lib",
        question=question,
        answer=answer,
        retrieved=retrieved,
        duration_ms=duration_ms,
    )


# === RecallAtKMetric ==========================================================


class TestRecallAtKMetric:
    @pytest.mark.asyncio
    async def test_perfect_recall(self) -> None:
        metric = RecallAtKMetric()
        sample = _sample(expected_evidence_doc_ids=("d1", "d2"))
        answered = _answered(retrieved=(_evidence("d1", "c1"), _evidence("d2", "c2")))
        result = await metric.score(sample, answered)
        assert result.score == 1.0
        assert result.metric_name == "recall_at_k"

    @pytest.mark.asyncio
    async def test_partial_recall(self) -> None:
        metric = RecallAtKMetric()
        sample = _sample(expected_evidence_doc_ids=("d1", "d2", "d3"))
        answered = _answered(retrieved=(_evidence("d1", "c1"),))
        result = await metric.score(sample, answered)
        assert result.score == pytest.approx(1 / 3)

    @pytest.mark.asyncio
    async def test_zero_recall(self) -> None:
        metric = RecallAtKMetric()
        sample = _sample(expected_evidence_doc_ids=("d1",))
        answered = _answered(retrieved=(_evidence("d2", "c2"),))
        result = await metric.score(sample, answered)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_no_expected_returns_one(self) -> None:
        metric = RecallAtKMetric()
        sample = _sample()  # no expected evidence
        answered = _answered()
        result = await metric.score(sample, answered)
        assert result.score == 1.0

    def test_protocol_attrs(self) -> None:
        m = RecallAtKMetric()
        assert m.name == "recall_at_k"
        assert m.requires_judge is False


# === KeyPointCoverageMetric ===================================================


class TestKeyPointCoverageMetric:
    @pytest.mark.asyncio
    async def test_perfect_coverage(self) -> None:
        metric = KeyPointCoverageMetric()
        sample = _sample(expected_key_points=("alpha", "beta"))
        answered = _answered(answer="The Alpha and Beta variants are documented.")
        result = await metric.score(sample, answered)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_partial_case_insensitive(self) -> None:
        metric = KeyPointCoverageMetric()
        sample = _sample(expected_key_points=("ALPHA", "beta", "gamma"))
        answered = _answered(answer="alpha and BETA are present.")
        result = await metric.score(sample, answered)
        assert result.score == pytest.approx(2 / 3)

    @pytest.mark.asyncio
    async def test_zero_coverage(self) -> None:
        metric = KeyPointCoverageMetric()
        sample = _sample(expected_key_points=("xyz",))
        answered = _answered(answer="something else entirely")
        result = await metric.score(sample, answered)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_empty_expected_returns_one(self) -> None:
        metric = KeyPointCoverageMetric()
        sample = _sample()
        answered = _answered(answer="anything")
        result = await metric.score(sample, answered)
        assert result.score == 1.0

    def test_protocol_attrs(self) -> None:
        m = KeyPointCoverageMetric()
        assert m.name == "key_point_coverage"
        assert m.requires_judge is False


# === CitationPresentMetric ====================================================


class TestCitationPresentMetric:
    @pytest.mark.asyncio
    async def test_present(self) -> None:
        metric = CitationPresentMetric()
        sample = _sample()
        answered = _answered(answer="See [doc::p1::3] for details.")
        result = await metric.score(sample, answered)
        assert result.score == 1.0
        assert result.details["citation_count"] == 1

    @pytest.mark.asyncio
    async def test_multiple_citations(self) -> None:
        metric = CitationPresentMetric()
        sample = _sample()
        answered = _answered(answer="See [a/b] and [c-1] please.")
        result = await metric.score(sample, answered)
        assert result.score == 1.0
        assert result.details["citation_count"] == 2

    @pytest.mark.asyncio
    async def test_absent(self) -> None:
        metric = CitationPresentMetric()
        sample = _sample()
        answered = _answered(answer="No citation here.")
        result = await metric.score(sample, answered)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_brackets_with_invalid_chars_not_counted(self) -> None:
        metric = CitationPresentMetric()
        sample = _sample()
        answered = _answered(answer="See [hello world!] only")
        result = await metric.score(sample, answered)
        # space and ! aren't allowed in chunk_id charset
        assert result.score == 0.0

    def test_protocol_attrs(self) -> None:
        m = CitationPresentMetric()
        assert m.name == "citation_present"
        assert m.requires_judge is False


# === MustNotContainMetric =====================================================


class TestMustNotContainMetric:
    @pytest.mark.asyncio
    async def test_clean_answer(self) -> None:
        metric = MustNotContainMetric()
        sample = _sample(must_not_contain=("forbidden", "secret"))
        answered = _answered(answer="A clean and accurate answer.")
        result = await metric.score(sample, answered)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_violation_present(self) -> None:
        metric = MustNotContainMetric()
        sample = _sample(must_not_contain=("forbidden",))
        answered = _answered(answer="This contains FORBIDDEN content.")
        result = await metric.score(sample, answered)
        assert result.score == 0.0
        assert "forbidden" in result.details["violations"]  # type: ignore[operator]

    @pytest.mark.asyncio
    async def test_no_forbidden_list(self) -> None:
        metric = MustNotContainMetric()
        sample = _sample()
        answered = _answered(answer="anything goes")
        result = await metric.score(sample, answered)
        assert result.score == 1.0

    def test_protocol_attrs(self) -> None:
        m = MustNotContainMetric()
        assert m.name == "must_not_contain"
        assert m.requires_judge is False


# === LatencyMetric ============================================================


class TestLatencyMetric:
    @pytest.mark.asyncio
    async def test_within_target(self) -> None:
        metric = LatencyMetric(target_ms=10_000)
        sample = _sample()
        answered = _answered(duration_ms=5_000)
        result = await metric.score(sample, answered)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_at_target_boundary(self) -> None:
        metric = LatencyMetric(target_ms=10_000)
        answered = _answered(duration_ms=10_000)
        result = await metric.score(_sample(), answered)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_midway_decay(self) -> None:
        metric = LatencyMetric(target_ms=10_000)
        # midway between target (10k) and upper (30k) => 20k => score 0.5
        answered = _answered(duration_ms=20_000)
        result = await metric.score(_sample(), answered)
        assert result.score == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_over_budget(self) -> None:
        metric = LatencyMetric(target_ms=10_000)
        answered = _answered(duration_ms=30_001)
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_default_target(self) -> None:
        metric = LatencyMetric()
        answered = _answered(duration_ms=29_999)
        result = await metric.score(_sample(), answered)
        # 29_999 < 30_000 default target => 1.0
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_explicit_config(self) -> None:
        metric = LatencyMetric(config=LatencyConfig(target_ms=5_000, decay_factor=2))
        answered = _answered(duration_ms=10_000)
        result = await metric.score(_sample(), answered)
        # upper = 10_000 => exactly at upper => 0.0
        assert result.score == 0.0

    def test_protocol_attrs(self) -> None:
        m = LatencyMetric()
        assert m.name == "latency"
        assert m.requires_judge is False
