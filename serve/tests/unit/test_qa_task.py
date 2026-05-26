"""Tests for QATask — citation extraction and prompt assembly."""

from __future__ import annotations

import pytest

from packages.core.models import Chunk, Query
from packages.llm.protocols import LLMResponse, Message
from packages.orchestration.tasks.qa_task import QATask
from packages.retrieval.protocols import RetrievalResult, RetrievedEvidence


def _ev(chunk_id: str, doc_id: str = "d", page: int = 1) -> RetrievedEvidence:
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
    def __init__(self, evidence: tuple[RetrievedEvidence, ...]) -> None:
        self._evidence = evidence
        self.last_question: str | None = None

    async def plan_and_retrieve(self, library_id: str, query: Query) -> RetrievalResult:
        self.last_question = query.text
        return RetrievalResult(
            library_id=library_id,
            query=query.text,
            evidence=self._evidence,
        )


class FakeLLM:
    def __init__(self, response_text: str = "answer") -> None:
        self._response_text = response_text
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
        self.last_messages = list(messages)
        return LLMResponse(
            text=self._response_text,
            model="fake",
            input_tokens=42,
            output_tokens=7,
        )


class TestQATask:
    @pytest.mark.asyncio
    async def test_no_evidence_returns_no_answer_message(self) -> None:
        planner = FakePlanner(evidence=())
        llm = FakeLLM()
        task = QATask(planner=planner, llm=llm)
        result = await task.answer("test-lib", "What?")
        assert "could not find" in result.answer.lower()
        assert llm.last_messages is None  # LLM never called

    @pytest.mark.asyncio
    async def test_calls_llm_with_evidence(self) -> None:
        planner = FakePlanner(evidence=(_ev("d::p1::0"),))
        llm = FakeLLM(response_text="Some answer.")
        task = QATask(planner=planner, llm=llm)
        result = await task.answer("test-lib", "What?")
        assert result.answer == "Some answer."
        assert llm.last_messages is not None
        assert len(llm.last_messages) == 2
        assert "d::p1::0" in llm.last_messages[1].content

    @pytest.mark.asyncio
    async def test_extracts_citations_from_answer(self) -> None:
        planner = FakePlanner(evidence=(_ev("d::p1::0"), _ev("d::p2::1")))
        llm = FakeLLM(response_text="X is true [d::p1::0] and Y is also true [d::p2::1].")
        task = QATask(planner=planner, llm=llm)
        result = await task.answer("test-lib", "What?")
        cited = {c.chunk_id for c in result.citations}
        assert cited == {"d::p1::0", "d::p2::1"}

    @pytest.mark.asyncio
    async def test_unknown_citation_ids_are_dropped(self) -> None:
        planner = FakePlanner(evidence=(_ev("d::p1::0"),))
        llm = FakeLLM(response_text="See [d::p1::0] and [d::p99::99].")
        task = QATask(planner=planner, llm=llm)
        result = await task.answer("test-lib", "What?")
        cited = {c.chunk_id for c in result.citations}
        assert cited == {"d::p1::0"}

    @pytest.mark.asyncio
    async def test_token_usage_propagated(self) -> None:
        planner = FakePlanner(evidence=(_ev("d::p1::0"),))
        llm = FakeLLM()
        task = QATask(planner=planner, llm=llm)
        result = await task.answer("test-lib", "What?")
        assert result.tokens.input_tokens == 42
        assert result.tokens.output_tokens == 7

    @pytest.mark.asyncio
    async def test_max_context_chunks_respected(self) -> None:
        evidence = tuple(_ev(f"d::p1::{i}") for i in range(20))
        planner = FakePlanner(evidence=evidence)
        llm = FakeLLM()
        task = QATask(planner=planner, llm=llm, max_context_chunks=3)
        await task.answer("test-lib", "What?")
        assert llm.last_messages is not None
        # only first 3 chunks in context
        assert "d::p1::3" not in llm.last_messages[1].content
        assert "d::p1::0" in llm.last_messages[1].content

    @pytest.mark.asyncio
    async def test_extracts_community_level_citations(self) -> None:
        """Global mode emits chunk_ids like 'community::c0:5' — must still cite."""
        community_evidence = RetrievedEvidence(
            chunk=Chunk(
                library_id="test-lib",
                chunk_id="community::c0:5",
                doc_id="community",
                text="Community summary about RAG variants.",
            ),
            score=0.9,
            source="community",
        )
        chunk_evidence = _ev("d::p1::0")
        planner = FakePlanner(evidence=(community_evidence, chunk_evidence))
        llm = FakeLLM(response_text="See [community::c0:5] and [d::p1::0] for details.")
        task = QATask(planner=planner, llm=llm)
        result = await task.answer("test-lib", "What?")
        cited = {c.chunk_id for c in result.citations}
        assert cited == {"community::c0:5", "d::p1::0"}

    @pytest.mark.asyncio
    async def test_community_only_evidence_extracts_citation(self) -> None:
        """Pure-global response with only community evidence still extracts citation."""
        community_evidence = RetrievedEvidence(
            chunk=Chunk(
                library_id="test-lib",
                chunk_id="community::c1:2",
                doc_id="community",
                text="High-level theme summary.",
            ),
            score=0.9,
            source="community",
        )
        planner = FakePlanner(evidence=(community_evidence,))
        llm = FakeLLM(response_text="The corpus covers RAG [community::c1:2].")
        task = QATask(planner=planner, llm=llm)
        result = await task.answer("test-lib", "What themes?")
        assert len(result.citations) == 1
        assert result.citations[0].chunk_id == "community::c1:2"
        assert result.citations[0].doc_id == "community"
