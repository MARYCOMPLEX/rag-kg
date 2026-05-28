"""Tests for ReviewGenerationTask — outline → sections → abstract."""

from __future__ import annotations

import pytest

from packages.core.models import Chunk, Query
from packages.llm.protocols import LLMResponse, Message
from packages.orchestration.protocols import TaskBudget
from packages.orchestration.tasks.review_task import (
    ReviewGenerationTask,
    ReviewGenerationTaskConfig,
)
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
    """Returns a fixed evidence tuple per heading.

    If `per_heading` is provided, look up evidence by Query.text; otherwise
    fall back to `default_evidence` for every call.
    """

    def __init__(
        self,
        default_evidence: tuple[RetrievedEvidence, ...] = (),
        per_heading: dict[str, tuple[RetrievedEvidence, ...]] | None = None,
    ) -> None:
        self._default = default_evidence
        self._per_heading = per_heading or {}
        self.calls: list[str] = []

    async def plan_and_retrieve(self, library_id: str, query: Query) -> RetrievalResult:
        self.calls.append(query.text)
        evidence = self._per_heading.get(query.text, self._default)
        return RetrievalResult(
            library_id=library_id,
            query=query.text,
            evidence=evidence,
        )


class FakeLLM:
    """Scripted LLM: returns the next text from `responses` per call.

    If a response is the special string `"__RAISE__"`, the call raises.
    """

    RAISE = "__RAISE__"

    def __init__(self, responses: list[str]) -> None:
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
            raise RuntimeError("FakeLLM: out of scripted responses")
        text = self._responses.pop(0)
        if text == FakeLLM.RAISE:
            raise RuntimeError("FakeLLM: scripted failure")
        return LLMResponse(
            text=text,
            model="fake",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
        )


_OUTLINE_4 = (
    '{"headings": ['
    '"Hybrid retrieval methods", '
    '"Graph-based RAG variants", '
    '"Self-RAG and CRAG", '
    '"Evaluation benchmarks"'
    "]}"
)


class TestReviewGenerationTaskHappyPath:
    @pytest.mark.asyncio
    async def test_returns_four_sections_and_abstract(self) -> None:
        planner = FakePlanner(default_evidence=(_ev("d::p1::0"), _ev("d::p2::1")))
        llm = FakeLLM(
            responses=[
                _OUTLINE_4,
                "Section A body [d::p1::0].",
                "Section B body [d::p2::1].",
                "Section C body [d::p1::0].",
                "Section D body [d::p2::1].",
                "This review summarizes the four themes.",
            ]
        )
        task = ReviewGenerationTask(planner=planner, llm=llm)

        result = await task.run("test-lib", "Retrieval-augmented generation")

        assert len(result.sections) == 4
        assert {s.heading for s in result.sections} == {
            "Hybrid retrieval methods",
            "Graph-based RAG variants",
            "Self-RAG and CRAG",
            "Evaluation benchmarks",
        }
        assert result.abstract == "This review summarizes the four themes."
        # 1 outline + 4 sections + 1 abstract
        assert result.cost.llm_calls == 6
        assert result.cost.input_tokens == 60
        assert result.cost.output_tokens == 30
        assert result.cost.cost_usd == pytest.approx(0.006)

    @pytest.mark.asyncio
    async def test_accepts_outline_json_array(self) -> None:
        planner = FakePlanner(default_evidence=(_ev("d::p1::0"),))
        llm = FakeLLM(
            responses=[
                '["Retrieval planning", "Global synthesis"]',
                "Planning body [d::p1::0].",
                "Synthesis body [d::p1::0].",
            ]
        )
        task = ReviewGenerationTask(
            planner=planner,
            llm=llm,
            config=ReviewGenerationTaskConfig(max_sections=2, write_abstract=False),
        )

        result = await task.run("test-lib", "GraphRAG")

        assert [section.heading for section in result.sections] == [
            "Retrieval planning",
            "Global synthesis",
        ]

    @pytest.mark.asyncio
    async def test_accepts_numbered_outline_list(self) -> None:
        planner = FakePlanner(default_evidence=(_ev("d::p1::0"),))
        llm = FakeLLM(
            responses=[
                "1. Retrieval planning\n2. Global synthesis",
                "Planning body [d::p1::0].",
                "Synthesis body [d::p1::0].",
            ]
        )
        task = ReviewGenerationTask(
            planner=planner,
            llm=llm,
            config=ReviewGenerationTaskConfig(max_sections=2, write_abstract=False),
        )

        result = await task.run("test-lib", "GraphRAG")

        assert len(result.sections) == 2
        assert planner.calls == ["Retrieval planning", "Global synthesis"]


class TestReviewGenerationTaskOutlineFailure:
    @pytest.mark.asyncio
    async def test_outline_llm_exception_yields_empty_result(self) -> None:
        planner = FakePlanner(default_evidence=(_ev("d::p1::0"),))
        llm = FakeLLM(responses=[FakeLLM.RAISE])
        task = ReviewGenerationTask(planner=planner, llm=llm)

        result = await task.run("test-lib", "Topic")

        assert result.sections == ()
        assert result.abstract == ""
        # outline call failed → no LLMResponse recorded
        assert result.cost.llm_calls == 0
        # planner never invoked
        assert planner.calls == []

    @pytest.mark.asyncio
    async def test_outline_invalid_json_yields_empty_result(self) -> None:
        planner = FakePlanner(default_evidence=(_ev("d::p1::0"),))
        llm = FakeLLM(responses=["not json at all"])
        task = ReviewGenerationTask(planner=planner, llm=llm)

        result = await task.run("test-lib", "Topic")

        assert result.sections == ()
        assert result.abstract == ""
        # Outline call still happened (and counts toward cost), but no headings.
        assert result.cost.llm_calls == 1


class TestReviewGenerationTaskSectionFailure:
    @pytest.mark.asyncio
    async def test_section_llm_failure_keeps_other_sections(self) -> None:
        planner = FakePlanner(default_evidence=(_ev("d::p1::0"),))
        # 4 headings; 2nd section LLM call raises.
        llm = FakeLLM(
            responses=[
                _OUTLINE_4,
                "Body A [d::p1::0].",
                FakeLLM.RAISE,
                "Body C [d::p1::0].",
                "Body D [d::p1::0].",
                "Abstract text.",
            ]
        )
        task = ReviewGenerationTask(planner=planner, llm=llm)

        result = await task.run("test-lib", "Topic")

        # 1 section dropped.
        assert len(result.sections) == 3
        # Abstract still produced from surviving sections.
        assert result.abstract == "Abstract text."

    @pytest.mark.asyncio
    async def test_planner_failure_for_section_drops_only_that_section(
        self,
    ) -> None:
        class FlakyPlanner:
            def __init__(self) -> None:
                self.calls: list[str] = []

            async def plan_and_retrieve(self, library_id: str, query: Query) -> RetrievalResult:
                self.calls.append(query.text)
                if query.text == "Graph-based RAG variants":
                    raise RuntimeError("planner boom")
                return RetrievalResult(
                    library_id=library_id,
                    query=query.text,
                    evidence=(_ev("d::p1::0"),),
                )

        planner = FlakyPlanner()
        llm = FakeLLM(
            responses=[
                _OUTLINE_4,
                "Body A [d::p1::0].",
                "Body C [d::p1::0].",
                "Body D [d::p1::0].",
                "Abstract.",
            ]
        )
        task = ReviewGenerationTask(planner=planner, llm=llm)

        result = await task.run("test-lib", "Topic")

        # 3 sections survived, abstract written from them.
        assert len(result.sections) == 3
        assert "Graph-based RAG variants" not in {s.heading for s in result.sections}
        assert result.abstract == "Abstract."


class TestReviewGenerationTaskBudget:
    @pytest.mark.asyncio
    async def test_max_sections_cap_via_config(self) -> None:
        planner = FakePlanner(default_evidence=(_ev("d::p1::0"),))
        llm = FakeLLM(
            responses=[
                _OUTLINE_4,
                "Body 1 [d::p1::0].",
                "Body 2 [d::p1::0].",
                "Abstract.",
            ]
        )
        task = ReviewGenerationTask(
            planner=planner,
            llm=llm,
            config=ReviewGenerationTaskConfig(max_sections=2),
        )

        result = await task.run("test-lib", "Topic")

        assert len(result.sections) == 2
        # Only 2 of the 4 headings were retrieved on.
        assert len(planner.calls) == 2

    @pytest.mark.asyncio
    async def test_max_subtopics_cap_via_budget(self) -> None:
        planner = FakePlanner(default_evidence=(_ev("d::p1::0"),))
        llm = FakeLLM(
            responses=[
                _OUTLINE_4,
                "Body 1 [d::p1::0].",
                "Abstract.",
            ]
        )
        task = ReviewGenerationTask(
            planner=planner,
            llm=llm,
            budget=TaskBudget(max_subtopics=1),
        )

        result = await task.run("test-lib", "Topic")

        assert len(result.sections) == 1
        assert len(planner.calls) == 1


class TestReviewGenerationTaskCitations:
    @pytest.mark.asyncio
    async def test_citations_match_retrieved_chunk_ids(self) -> None:
        # Each heading has its own evidence pool; the LLM cites a mix of
        # real and fake chunk_ids and only real ones should survive.
        per_heading = {
            "Hybrid retrieval methods": (_ev("d::p1::0"), _ev("d::p1::1")),
            "Graph-based RAG variants": (_ev("d::p2::0"),),
            "Self-RAG and CRAG": (_ev("d::p3::0"),),
            "Evaluation benchmarks": (_ev("d::p4::0"),),
        }
        planner = FakePlanner(per_heading=per_heading)
        llm = FakeLLM(
            responses=[
                _OUTLINE_4,
                "Two cites [d::p1::0] and [d::p1::1] plus a fake [d::p99::99].",
                "One cite [d::p2::0].",
                "One cite [d::p3::0].",
                "One cite [d::p4::0].",
                "Abstract text.",
            ]
        )
        task = ReviewGenerationTask(planner=planner, llm=llm)

        result = await task.run("test-lib", "Topic")

        by_heading = {s.heading: s for s in result.sections}

        hybrid = by_heading["Hybrid retrieval methods"]
        assert {c.chunk_id for c in hybrid.citations} == {"d::p1::0", "d::p1::1"}

        graph = by_heading["Graph-based RAG variants"]
        assert {c.chunk_id for c in graph.citations} == {"d::p2::0"}

    @pytest.mark.asyncio
    async def test_section_with_empty_evidence_skips_llm_call(self) -> None:
        per_heading: dict[str, tuple[RetrievedEvidence, ...]] = {
            "Hybrid retrieval methods": (),
            "Graph-based RAG variants": (_ev("d::p2::0"),),
            "Self-RAG and CRAG": (_ev("d::p3::0"),),
            "Evaluation benchmarks": (_ev("d::p4::0"),),
        }
        planner = FakePlanner(per_heading=per_heading)
        llm = FakeLLM(
            responses=[
                _OUTLINE_4,
                # NOTE: only 3 section bodies — empty-evidence section skips LLM.
                "Body B [d::p2::0].",
                "Body C [d::p3::0].",
                "Body D [d::p4::0].",
                "Abstract.",
            ]
        )
        task = ReviewGenerationTask(planner=planner, llm=llm)

        result = await task.run("test-lib", "Topic")

        # All 4 sections present; one has the no-evidence sentinel body.
        assert len(result.sections) == 4
        empty_section = next(s for s in result.sections if s.heading == "Hybrid retrieval methods")
        assert "No evidence" in empty_section.body
        assert empty_section.citations == ()
        assert empty_section.evidence == ()


class TestReviewGenerationTaskAbstractDisabled:
    @pytest.mark.asyncio
    async def test_disabling_abstract_skips_call(self) -> None:
        planner = FakePlanner(default_evidence=(_ev("d::p1::0"),))
        llm = FakeLLM(
            responses=[
                _OUTLINE_4,
                "Body 1 [d::p1::0].",
                "Body 2 [d::p1::0].",
                "Body 3 [d::p1::0].",
                "Body 4 [d::p1::0].",
            ]
        )
        task = ReviewGenerationTask(
            planner=planner,
            llm=llm,
            config=ReviewGenerationTaskConfig(write_abstract=False),
        )

        result = await task.run("test-lib", "Topic")

        assert result.abstract == ""
        assert result.cost.llm_calls == 5  # 1 outline + 4 sections, no abstract
