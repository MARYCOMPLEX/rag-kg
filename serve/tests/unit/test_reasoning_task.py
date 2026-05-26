"""Tests for CrossPaperReasoningTask — decompose / per-sub / aggregate pipeline."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from packages.core.models import Chunk, Query
from packages.llm.protocols import LLMResponse, Message
from packages.orchestration.tasks.reasoning_task import (
    CrossPaperReasoningTask,
    CrossPaperReasoningTaskConfig,
)
from packages.retrieval.protocols import RetrievalResult, RetrievedEvidence


def _ev(chunk_id: str, doc_id: str = "doc-a", page: int = 1) -> RetrievedEvidence:
    return RetrievedEvidence(
        chunk=Chunk(
            library_id="test-lib",
            chunk_id=chunk_id,
            doc_id=doc_id,
            text=f"text for {chunk_id}",
            page=page,
        ),
        score=0.9,
        source="vector",
    )


class FakePlanner:
    """Returns canned evidence per query.text. Configurable to raise on demand."""

    def __init__(
        self,
        evidence_by_question: dict[str, tuple[RetrievedEvidence, ...]] | None = None,
        default_evidence: tuple[RetrievedEvidence, ...] = (),
        raise_for: Iterable[str] = (),
    ) -> None:
        self._evidence_by_question = evidence_by_question or {}
        self._default = default_evidence
        self._raise_for = set(raise_for)
        self.questions_seen: list[str] = []

    async def plan_and_retrieve(self, library_id: str, query: Query) -> RetrievalResult:
        self.questions_seen.append(query.text)
        if query.text in self._raise_for:
            raise RuntimeError(f"planner failed for {query.text}")
        evidence = self._evidence_by_question.get(query.text, self._default)
        return RetrievalResult(
            library_id=library_id,
            query=query.text,
            evidence=evidence,
        )


class FakeLLM:
    """Scripted LLM. Each call pops the next response (or raises)."""

    def __init__(self, responses: list[str | Exception]) -> None:
        self._responses = list(responses)
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
        self.calls.append(list(messages))
        if not self._responses:
            raise AssertionError("FakeLLM out of scripted responses")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return LLMResponse(
            text=nxt,
            model="fake",
            input_tokens=10,
            output_tokens=5,
        )


class TestCrossPaperReasoningTaskHappyPath:
    @pytest.mark.asyncio
    async def test_decomposes_into_three_sub_questions_and_aggregates(self) -> None:
        # Arrange
        decompose_resp = '{"sub_questions": ["What is A?", "What is B?", "How do A and B relate?"]}'
        evidence_a = (_ev("doc-a::p1::0"),)
        evidence_b = (_ev("doc-b::p1::0", doc_id="doc-b"),)
        evidence_rel = (_ev("doc-c::p1::0", doc_id="doc-c"),)
        planner = FakePlanner(
            evidence_by_question={
                "What is A?": evidence_a,
                "What is B?": evidence_b,
                "How do A and B relate?": evidence_rel,
            }
        )
        llm = FakeLLM(
            responses=[
                decompose_resp,
                "A is foo [doc-a::p1::0].",
                "B is bar [doc-b::p1::0].",
                "They relate via X [doc-c::p1::0].",
                "Final: A is foo [doc-a::p1::0]; B is bar [doc-b::p1::0]; "
                "they relate via X [doc-c::p1::0].",
            ]
        )
        task = CrossPaperReasoningTask(planner=planner, llm=llm)

        # Act
        result = await task.run("test-lib", "How do A and B relate?")

        # Assert
        assert result.library_id == "test-lib"
        assert len(result.sub_steps) == 3
        sub_qs = [s.sub_question for s in result.sub_steps]
        assert sub_qs == ["What is A?", "What is B?", "How do A and B relate?"]
        assert "Final:" in result.final_answer
        cited = {c.chunk_id for c in result.citations}
        assert cited == {"doc-a::p1::0", "doc-b::p1::0", "doc-c::p1::0"}
        # 1 decompose + 3 sub + 1 final = 5 LLM calls
        assert result.cost.llm_calls == 5
        assert result.cost.input_tokens == 50
        assert result.cost.output_tokens == 25


class TestCrossPaperReasoningTaskDecomposeFallback:
    @pytest.mark.asyncio
    async def test_decompose_failure_falls_back_to_single_step(self) -> None:
        # Arrange — decompose call raises; pipeline must still run with original Q
        evidence = (_ev("doc-a::p1::0"),)
        planner = FakePlanner(default_evidence=evidence)
        llm = FakeLLM(
            responses=[
                RuntimeError("decompose boom"),
                "Direct answer about X [doc-a::p1::0].",
                "Final: Direct answer [doc-a::p1::0].",
            ]
        )
        task = CrossPaperReasoningTask(planner=planner, llm=llm)

        # Act
        result = await task.run("test-lib", "What is X?")

        # Assert — single sub-step using the original question
        assert len(result.sub_steps) == 1
        assert result.sub_steps[0].sub_question == "What is X?"
        assert "Final" in result.final_answer
        # Decompose was not counted (it raised)
        assert result.cost.llm_calls == 2

    @pytest.mark.asyncio
    async def test_decompose_invalid_json_falls_back_to_single_step(self) -> None:
        # Arrange — decompose returns garbage that can't be parsed
        evidence = (_ev("doc-a::p1::0"),)
        planner = FakePlanner(default_evidence=evidence)
        llm = FakeLLM(
            responses=[
                "not json at all, sorry",
                "Direct answer [doc-a::p1::0].",
                "Final answer [doc-a::p1::0].",
            ]
        )
        task = CrossPaperReasoningTask(planner=planner, llm=llm)

        # Act
        result = await task.run("test-lib", "What is X?")

        # Assert
        assert len(result.sub_steps) == 1
        assert result.sub_steps[0].sub_question == "What is X?"

    @pytest.mark.asyncio
    async def test_decompose_too_few_sub_questions_falls_back(self) -> None:
        # Arrange — only 1 sub-question returned (below MIN of 2) → fallback
        evidence = (_ev("doc-a::p1::0"),)
        planner = FakePlanner(default_evidence=evidence)
        llm = FakeLLM(
            responses=[
                '{"sub_questions": ["only one sub"]}',
                "Direct answer [doc-a::p1::0].",
                "Final answer [doc-a::p1::0].",
            ]
        )
        task = CrossPaperReasoningTask(planner=planner, llm=llm)

        # Act
        result = await task.run("test-lib", "What is X?")

        # Assert
        assert len(result.sub_steps) == 1
        assert result.sub_steps[0].sub_question == "What is X?"


class TestCrossPaperReasoningTaskSubStepFailure:
    @pytest.mark.asyncio
    async def test_sub_step_llm_failure_preserves_other_steps(self) -> None:
        # Arrange — middle sub-question's LLM call raises
        decompose_resp = '{"sub_questions": ["Q1", "Q2", "Q3"]}'
        evidence_q1 = (_ev("c1"),)
        evidence_q2 = (_ev("c2", doc_id="doc-b"),)
        evidence_q3 = (_ev("c3", doc_id="doc-c"),)
        planner = FakePlanner(
            evidence_by_question={"Q1": evidence_q1, "Q2": evidence_q2, "Q3": evidence_q3}
        )
        # Force concurrency=1 so script order is deterministic
        config = CrossPaperReasoningTaskConfig(sub_concurrency=1)
        llm = FakeLLM(
            responses=[
                decompose_resp,
                "A1 [c1].",
                RuntimeError("sub2 boom"),
                "A3 [c3].",
                "Final combining [c1] and [c3].",
            ]
        )
        task = CrossPaperReasoningTask(planner=planner, llm=llm, config=config)

        # Act
        result = await task.run("test-lib", "compound Q?")

        # Assert
        assert len(result.sub_steps) == 3
        assert result.sub_steps[0].answer == "A1 [c1]."
        assert result.sub_steps[1].answer == ""  # failed sub kept w/ empty answer
        assert result.sub_steps[1].evidence == evidence_q2  # evidence preserved
        assert result.sub_steps[2].answer == "A3 [c3]."
        assert "Final" in result.final_answer
        cited = {c.chunk_id for c in result.citations}
        assert cited == {"c1", "c3"}

    @pytest.mark.asyncio
    async def test_planner_failure_for_one_sub_preserves_others(self) -> None:
        # Arrange — planner raises for Q2 only
        decompose_resp = '{"sub_questions": ["Q1", "Q2"]}'
        planner = FakePlanner(
            evidence_by_question={"Q1": (_ev("c1"),)},
            raise_for=("Q2",),
        )
        config = CrossPaperReasoningTaskConfig(sub_concurrency=1)
        llm = FakeLLM(
            responses=[
                decompose_resp,
                "A1 [c1].",
                "Final [c1].",
            ]
        )
        task = CrossPaperReasoningTask(planner=planner, llm=llm, config=config)

        # Act
        result = await task.run("test-lib", "Q")

        # Assert
        assert len(result.sub_steps) == 2
        assert result.sub_steps[1].answer == ""
        assert result.sub_steps[1].evidence == ()
        assert "Final" in result.final_answer

    @pytest.mark.asyncio
    async def test_aggregate_failure_falls_back_to_concatenation(self) -> None:
        # Arrange — final aggregate LLM call raises
        decompose_resp = '{"sub_questions": ["Q1", "Q2"]}'
        planner = FakePlanner(
            evidence_by_question={"Q1": (_ev("c1"),), "Q2": (_ev("c2", doc_id="doc-b"),)}
        )
        config = CrossPaperReasoningTaskConfig(sub_concurrency=1)
        llm = FakeLLM(
            responses=[
                decompose_resp,
                "Answer one [c1].",
                "Answer two [c2].",
                RuntimeError("aggregate boom"),
            ]
        )
        task = CrossPaperReasoningTask(planner=planner, llm=llm, config=config)

        # Act
        result = await task.run("test-lib", "Q")

        # Assert — final answer is concatenation, citations still extracted
        assert "Answer one [c1]." in result.final_answer
        assert "Answer two [c2]." in result.final_answer
        cited = {c.chunk_id for c in result.citations}
        assert cited == {"c1", "c2"}


class TestCrossPaperReasoningTaskCitations:
    @pytest.mark.asyncio
    async def test_citation_aggregation_union_across_sub_steps(self) -> None:
        # Arrange — final answer cites chunks from multiple sub-steps
        decompose_resp = '{"sub_questions": ["Q1", "Q2", "Q3"]}'
        planner = FakePlanner(
            evidence_by_question={
                "Q1": (_ev("c1"), _ev("c1b", doc_id="doc-a2")),
                "Q2": (_ev("c2", doc_id="doc-b"),),
                "Q3": (_ev("c3", doc_id="doc-c"),),
            }
        )
        llm = FakeLLM(
            responses=[
                decompose_resp,
                "A1 [c1] [c1b].",
                "A2 [c2].",
                "A3 [c3].",
                # Final cites a subset + one unknown id (must be dropped)
                "Combined [c1] [c2] [c3] [unknown::xyz].",
            ]
        )
        task = CrossPaperReasoningTask(planner=planner, llm=llm)

        # Act
        result = await task.run("test-lib", "compound?")

        # Assert
        cited = {c.chunk_id for c in result.citations}
        assert cited == {"c1", "c2", "c3"}  # unknown::xyz dropped, c1b not cited
        # And per-citation metadata (doc_id) is correct
        by_id = {c.chunk_id: c for c in result.citations}
        assert by_id["c2"].doc_id == "doc-b"
        assert by_id["c3"].doc_id == "doc-c"

    @pytest.mark.asyncio
    async def test_no_citations_when_final_has_none(self) -> None:
        # Arrange
        decompose_resp = '{"sub_questions": ["Q1", "Q2"]}'
        planner = FakePlanner(evidence_by_question={"Q1": (_ev("c1"),), "Q2": (_ev("c2"),)})
        llm = FakeLLM(
            responses=[
                decompose_resp,
                "A1 [c1].",
                "A2 [c2].",
                "Final answer with no inline citations.",
            ]
        )
        task = CrossPaperReasoningTask(planner=planner, llm=llm)

        # Act
        result = await task.run("test-lib", "Q?")

        # Assert
        assert result.citations == ()
