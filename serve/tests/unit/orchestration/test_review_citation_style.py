"""Tests for the `citation_style` parameter on `ReviewGenerationTask.run`.

The task body's `[chunk_id]` markers are post-processed into either
`[1]` (numeric) or `(Author Year)` (author_year) form. Citations are
left structurally identical — only the rendered body changes.
"""

from __future__ import annotations

import re

import pytest

from packages.core.models import Chunk, Query
from packages.llm.protocols import LLMResponse, Message
from packages.orchestration.tasks.review_task import (
    ReviewGenerationTask,
    ReviewGenerationTaskConfig,
)
from packages.retrieval.protocols import RetrievalResult, RetrievedEvidence

LIBRARY_ID = "test-lib"


def _ev(chunk_id: str, doc_id: str) -> RetrievedEvidence:
    return RetrievedEvidence(
        chunk=Chunk(
            library_id=LIBRARY_ID,
            chunk_id=chunk_id,
            doc_id=doc_id,
            text=f"text for {chunk_id}",
            page=1,
        ),
        score=0.9,
        source="vector",
    )


class _StaticPlanner:
    """Returns the same evidence tuple for every heading."""

    def __init__(self, evidence: tuple[RetrievedEvidence, ...]) -> None:
        self._evidence = evidence

    async def plan_and_retrieve(self, library_id: str, query: Query) -> RetrievalResult:
        return RetrievalResult(
            library_id=library_id,
            query=query.text,
            evidence=self._evidence,
        )


class _ScriptedLLM:
    """Yields the next text from `responses` per call."""

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
        text = self._responses.pop(0)
        return LLMResponse(
            text=text,
            model="fake",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0,
        )


_OUTLINE_2 = '{"headings": ["Topic A", "Topic B"]}'


@pytest.mark.asyncio
async def test_default_citation_style_is_numeric() -> None:
    # Arrange — every cite [d::p1::0] should render as [1].
    evidence = (_ev("d::p1::0", doc_id="smith2024"),)
    planner = _StaticPlanner(evidence)
    llm = _ScriptedLLM(
        [
            _OUTLINE_2,
            "Body A discusses X [d::p1::0] and again [d::p1::0].",
            "Body B repeats [d::p1::0].",
            "Abstract for both topics.",
        ]
    )
    task = ReviewGenerationTask(
        planner=planner,
        llm=llm,
        config=ReviewGenerationTaskConfig(max_sections=2),
    )

    # Act
    result = await task.run(LIBRARY_ID, "Topic")

    # Assert
    bodies = " | ".join(s.body for s in result.sections)
    assert "[1]" in bodies
    assert "[d::p1::0]" not in bodies


@pytest.mark.asyncio
async def test_author_year_citation_style_renders_parenthetical_form() -> None:
    # Arrange — doc_id `smith2024` should render as (Smith 2024).
    evidence = (_ev("d::p1::0", doc_id="smith2024"),)
    planner = _StaticPlanner(evidence)
    llm = _ScriptedLLM(
        [
            _OUTLINE_2,
            "Method comes from [d::p1::0].",
            "Confirmed by [d::p1::0].",
            "Abstract.",
        ]
    )
    task = ReviewGenerationTask(
        planner=planner,
        llm=llm,
        config=ReviewGenerationTaskConfig(max_sections=2),
    )

    # Act
    result = await task.run(LIBRARY_ID, "Topic", citation_style="author_year")

    # Assert
    bodies = " | ".join(s.body for s in result.sections)
    assert "(Smith 2024)" in bodies
    assert "[d::p1::0]" not in bodies


@pytest.mark.asyncio
async def test_citation_style_does_not_drop_citations() -> None:
    # Arrange
    evidence = (_ev("d::p1::0", doc_id="smith2024"),)
    planner = _StaticPlanner(evidence)
    llm = _ScriptedLLM(
        [
            _OUTLINE_2,
            "Body A [d::p1::0].",
            "Body B [d::p1::0].",
            "Abstract.",
        ]
    )
    task = ReviewGenerationTask(
        planner=planner,
        llm=llm,
        config=ReviewGenerationTaskConfig(max_sections=2),
    )

    # Act
    result = await task.run(LIBRARY_ID, "Topic", citation_style="numeric")

    # Assert — Citation objects untouched, only body rewritten.
    assert all(any(c.chunk_id == "d::p1::0" for c in s.citations) for s in result.sections)


@pytest.mark.asyncio
async def test_unknown_chunk_id_in_body_is_left_intact() -> None:
    # Arrange — LLM cites a chunk_id we never retrieved; must stay as-is.
    evidence = (_ev("d::p1::0", doc_id="smith2024"),)
    planner = _StaticPlanner(evidence)
    llm = _ScriptedLLM(
        [
            _OUTLINE_2,
            "Real cite [d::p1::0] then a fake [d::p99::99].",
            "Body B [d::p1::0].",
            "Abstract.",
        ]
    )
    task = ReviewGenerationTask(
        planner=planner,
        llm=llm,
        config=ReviewGenerationTaskConfig(max_sections=2),
    )

    # Act
    result = await task.run(LIBRARY_ID, "Topic")

    # Assert — fake cite preserved verbatim; real cite renumbered.
    section_a = next(s for s in result.sections if s.heading == "Topic A")
    assert "[d::p99::99]" in section_a.body
    assert re.search(r"\[1\]", section_a.body) is not None
