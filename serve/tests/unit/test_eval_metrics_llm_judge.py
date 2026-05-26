"""Unit tests for LLM-judge evaluation metrics."""

from __future__ import annotations

import pytest

from packages.core.models import Chunk
from packages.embedding.protocols import Vector
from packages.evaluation.metrics.llm_judge import (
    AnswerRelevancyMetric,
    CitationF1Metric,
    FaithfulnessMetric,
)
from packages.evaluation.protocols import EvalSample
from packages.llm.protocols import LLMResponse, Message
from packages.orchestration.protocols import AnsweredQuery
from packages.retrieval.protocols import RetrievedEvidence

# === Test fakes ===============================================================


class FakeLLM:
    def __init__(self, response_text: str = "{}", *, raise_exc: Exception | None = None) -> None:
        self._response_text = response_text
        self._raise = raise_exc
        self.call_count = 0
        self.last_messages: list[Message] | None = None

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse:
        del model, temperature, max_tokens, timeout_s
        self.call_count += 1
        self.last_messages = list(messages)
        if self._raise is not None:
            raise self._raise
        return LLMResponse(
            text=self._response_text,
            model="fake-judge",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
        )


class FakeEmbedder:
    """Returns canned vectors in order; falls back to a fixed vector after exhaustion."""

    def __init__(
        self,
        vectors: list[Vector] | None = None,
        *,
        raise_exc: Exception | None = None,
    ) -> None:
        self._vectors = vectors or []
        self._raise = raise_exc

    @property
    def dim(self) -> int:
        return 3

    async def embed(self, texts: list[str]) -> list[Vector]:
        if self._raise is not None:
            raise self._raise
        if self._vectors:
            return self._vectors[: len(texts)]
        return [[1.0, 0.0, 0.0] for _ in texts]


# === Test helpers =============================================================


def _sample() -> EvalSample:
    return EvalSample(
        sample_id="s1", library_id="lib", suite="qa", suite_version="v1", question="q?"
    )


def _evidence(chunk_id: str, text: str = "x") -> RetrievedEvidence:
    return RetrievedEvidence(
        chunk=Chunk(library_id="lib", chunk_id=chunk_id, doc_id="d1", text=text),
        score=0.9,
        source="vector",
    )


def _answered(
    *,
    answer: str = "",
    question: str = "what is X?",
    retrieved: tuple[RetrievedEvidence, ...] = (),
) -> AnsweredQuery:
    return AnsweredQuery(
        library_id="lib",
        question=question,
        answer=answer,
        retrieved=retrieved,
    )


# === CitationF1Metric =========================================================


class TestCitationF1Metric:
    @pytest.mark.asyncio
    async def test_perfect_f1(self) -> None:
        llm = FakeLLM(
            response_text='{"judgements": [{"chunk_id": "c1", "supports": true},'
            ' {"chunk_id": "c2", "supports": true}]}'
        )
        metric = CitationF1Metric(llm=llm)
        answered = _answered(
            answer="Claim one [c1]. Claim two [c2].",
            retrieved=(_evidence("c1"), _evidence("c2")),
        )
        result = await metric.score(_sample(), answered)
        assert result.score == pytest.approx(1.0)
        assert result.metric_name == "citation_f1"
        assert result.judge_model == "judge"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_partial_f1(self) -> None:
        llm = FakeLLM(
            response_text='{"judgements": [{"chunk_id": "c1", "supports": true},'
            ' {"chunk_id": "c2", "supports": false}]}'
        )
        metric = CitationF1Metric(llm=llm)
        answered = _answered(
            answer="A [c1] and B [c2].",
            retrieved=(_evidence("c1"), _evidence("c2")),
        )
        result = await metric.score(_sample(), answered)
        # precision = 1/2 = 0.5; recall = 1/2 = 0.5; f1 = 0.5
        assert result.score == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_no_citations(self) -> None:
        llm = FakeLLM(response_text='{"judgements": []}')
        metric = CitationF1Metric(llm=llm)
        answered = _answered(answer="No citations here.")
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert llm.call_count == 0  # short-circuits before LLM

    @pytest.mark.asyncio
    async def test_dangling_citations(self) -> None:
        llm = FakeLLM(response_text='{"judgements": []}')
        metric = CitationF1Metric(llm=llm)
        answered = _answered(answer="Claim [missing].")
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert llm.call_count == 0

    @pytest.mark.asyncio
    async def test_llm_error_returns_zero_with_error_field(self) -> None:
        llm = FakeLLM(raise_exc=RuntimeError("boom"))
        metric = CitationF1Metric(llm=llm)
        answered = _answered(answer="A [c1].", retrieved=(_evidence("c1"),))
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert result.error is not None
        assert "boom" in result.error
        assert result.judge_model == "judge"

    @pytest.mark.asyncio
    async def test_invalid_json_response(self) -> None:
        llm = FakeLLM(response_text="not json at all")
        metric = CitationF1Metric(llm=llm)
        answered = _answered(answer="A [c1].", retrieved=(_evidence("c1"),))
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert result.error is not None

    def test_protocol_attrs(self) -> None:
        m = CitationF1Metric(llm=FakeLLM())
        assert m.name == "citation_f1"
        assert m.requires_judge is True


# === FaithfulnessMetric =======================================================


class TestFaithfulnessMetric:
    @pytest.mark.asyncio
    async def test_all_supported(self) -> None:
        llm = FakeLLM(
            response_text='{"claims": [{"claim": "X", "supported": true},'
            ' {"claim": "Y", "supported": true}]}'
        )
        metric = FaithfulnessMetric(llm=llm)
        answered = _answered(
            answer="X happened. Y too.",
            retrieved=(_evidence("c1", "X happened. Y followed."),),
        )
        result = await metric.score(_sample(), answered)
        assert result.score == pytest.approx(1.0)
        assert result.metric_name == "faithfulness"

    @pytest.mark.asyncio
    async def test_partial_supported(self) -> None:
        llm = FakeLLM(
            response_text='{"claims": [{"claim": "X", "supported": true},'
            ' {"claim": "Y", "supported": false},'
            ' {"claim": "Z", "supported": false}]}'
        )
        metric = FaithfulnessMetric(llm=llm)
        answered = _answered(
            answer="big claim",
            retrieved=(_evidence("c1", "evidence text"),),
        )
        result = await metric.score(_sample(), answered)
        assert result.score == pytest.approx(1 / 3)

    @pytest.mark.asyncio
    async def test_no_evidence_short_circuits(self) -> None:
        llm = FakeLLM(response_text='{"claims": []}')
        metric = FaithfulnessMetric(llm=llm)
        answered = _answered(answer="something")
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert llm.call_count == 0

    @pytest.mark.asyncio
    async def test_empty_answer_short_circuits(self) -> None:
        llm = FakeLLM(response_text='{"claims": []}')
        metric = FaithfulnessMetric(llm=llm)
        answered = _answered(answer="   ", retrieved=(_evidence("c1"),))
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert llm.call_count == 0

    @pytest.mark.asyncio
    async def test_zero_claims_returns_zero(self) -> None:
        llm = FakeLLM(response_text='{"claims": []}')
        metric = FaithfulnessMetric(llm=llm)
        answered = _answered(
            answer="answer text",
            retrieved=(_evidence("c1", "evidence"),),
        )
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_llm_error_returns_zero_with_error(self) -> None:
        llm = FakeLLM(raise_exc=RuntimeError("judge down"))
        metric = FaithfulnessMetric(llm=llm)
        answered = _answered(
            answer="claim",
            retrieved=(_evidence("c1", "ev"),),
        )
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert result.error is not None
        assert "judge down" in result.error

    @pytest.mark.asyncio
    async def test_invalid_json_returns_zero_with_error(self) -> None:
        llm = FakeLLM(response_text="garbage")
        metric = FaithfulnessMetric(llm=llm)
        answered = _answered(
            answer="claim",
            retrieved=(_evidence("c1", "ev"),),
        )
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert result.error is not None

    def test_protocol_attrs(self) -> None:
        m = FaithfulnessMetric(llm=FakeLLM())
        assert m.name == "faithfulness"
        assert m.requires_judge is True


# === AnswerRelevancyMetric ====================================================


class TestAnswerRelevancyMetric:
    @pytest.mark.asyncio
    async def test_high_relevancy(self) -> None:
        llm = FakeLLM(response_text='{"questions": ["q1", "q2", "q3"]}')
        # original Q embeds to [1,0,0]; all 3 hypothetical Qs identical => sim 1.0
        embedder = FakeEmbedder(
            vectors=[
                [1.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
            ]
        )
        metric = AnswerRelevancyMetric(llm=llm, embedder=embedder)
        answered = _answered(answer="some answer", question="real question")
        result = await metric.score(_sample(), answered)
        assert result.score == pytest.approx(1.0)
        assert result.metric_name == "answer_relevancy"
        assert result.judge_model == "judge"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_orthogonal_questions(self) -> None:
        llm = FakeLLM(response_text='{"questions": ["q1", "q2", "q3"]}')
        embedder = FakeEmbedder(
            vectors=[
                [1.0, 0.0, 0.0],  # original Q
                [0.0, 1.0, 0.0],  # orthogonal
                [0.0, 1.0, 0.0],  # orthogonal
                [0.0, 1.0, 0.0],  # orthogonal
            ]
        )
        metric = AnswerRelevancyMetric(llm=llm, embedder=embedder)
        answered = _answered(answer="ans", question="q")
        result = await metric.score(_sample(), answered)
        assert result.score == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_mixed_similarity(self) -> None:
        llm = FakeLLM(response_text='{"questions": ["q1", "q2"]}')
        embedder = FakeEmbedder(
            vectors=[
                [1.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],  # sim 1.0
                [0.0, 1.0, 0.0],  # sim 0.0
            ]
        )
        metric = AnswerRelevancyMetric(llm=llm, embedder=embedder)
        answered = _answered(answer="ans", question="q")
        result = await metric.score(_sample(), answered)
        assert result.score == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_empty_answer_short_circuits(self) -> None:
        llm = FakeLLM(response_text='{"questions": []}')
        embedder = FakeEmbedder()
        metric = AnswerRelevancyMetric(llm=llm, embedder=embedder)
        answered = _answered(answer="   ", question="q")
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert llm.call_count == 0

    @pytest.mark.asyncio
    async def test_llm_error_returns_zero(self) -> None:
        llm = FakeLLM(raise_exc=RuntimeError("network"))
        embedder = FakeEmbedder()
        metric = AnswerRelevancyMetric(llm=llm, embedder=embedder)
        answered = _answered(answer="ans", question="q")
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert result.error is not None
        assert "network" in result.error

    @pytest.mark.asyncio
    async def test_invalid_json_returns_zero(self) -> None:
        llm = FakeLLM(response_text="oops")
        embedder = FakeEmbedder()
        metric = AnswerRelevancyMetric(llm=llm, embedder=embedder)
        answered = _answered(answer="ans", question="q")
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_no_questions_generated(self) -> None:
        llm = FakeLLM(response_text='{"questions": []}')
        embedder = FakeEmbedder()
        metric = AnswerRelevancyMetric(llm=llm, embedder=embedder)
        answered = _answered(answer="ans", question="q")
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_embedder_error(self) -> None:
        llm = FakeLLM(response_text='{"questions": ["q1"]}')
        embedder = FakeEmbedder(raise_exc=RuntimeError("embed-fail"))
        metric = AnswerRelevancyMetric(llm=llm, embedder=embedder)
        answered = _answered(answer="ans", question="q")
        result = await metric.score(_sample(), answered)
        assert result.score == 0.0
        assert result.error is not None
        assert "embed-fail" in result.error

    def test_protocol_attrs(self) -> None:
        m = AnswerRelevancyMetric(llm=FakeLLM(), embedder=FakeEmbedder())
        assert m.name == "answer_relevancy"
        assert m.requires_judge is True
