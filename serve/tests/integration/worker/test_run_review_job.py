"""Integration test for `apps.worker.jobs.run_review.run`.

Drives the wrapper end-to-end with stub planner + LLM so we can assert:

- The job lifecycle wraps the task call (status row updated).
- Stage events from the task layer reach the bus untouched.
- `cost_updated` event fires after the run.
- The result writer is called when wired into `ctx`.
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.worker.jobs import run_review
from packages.core.models import Chunk, Query
from packages.llm.protocols import LLMResponse, Message
from packages.retrieval.protocols import RetrievalResult, RetrievedEvidence

LIBRARY_ID = "test-lib"


def _ev(chunk_id: str) -> RetrievedEvidence:
    return RetrievedEvidence(
        chunk=Chunk(
            library_id=LIBRARY_ID,
            chunk_id=chunk_id,
            doc_id="doc",
            text=f"text for {chunk_id}",
            page=1,
        ),
        score=0.9,
        source="vector",
    )


class _StubPlanner:
    async def plan_and_retrieve(self, library_id: str, query: Query) -> RetrievalResult:
        return RetrievalResult(
            library_id=library_id,
            query=query.text,
            evidence=(_ev("doc::p1::0"),),
        )


class _StubLLM:
    def __init__(self) -> None:
        self.calls = 0
        self._responses = [
            '{"headings": ["Topic A", "Topic B"]}',
            "Section A [doc::p1::0].",
            "Section B [doc::p1::0].",
            "Abstract.",
        ]

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
        text = self._responses.pop(0)
        return LLMResponse(
            text=text,
            model="stub",
            input_tokens=20,
            output_tokens=10,
            cost_usd=0.002,
        )


class _CapturingWriter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, bytes]] = []

    async def write(self, library_id: str, task_id: str, kind: str, content: bytes) -> str:
        self.calls.append((library_id, task_id, kind, content))
        return f"s3://kb/{library_id}/reviews/{task_id}.md"


@pytest.mark.asyncio
async def test_run_review_emits_stages_and_persists_result_pointer(
    base_ctx: dict[str, Any],
    fake_event_bus: Any,
    fake_task_store: Any,
) -> None:
    # Arrange
    writer = _CapturingWriter()
    ctx = {
        **base_ctx,
        "retrieval_planner": _StubPlanner(),
        "llm_client": _StubLLM(),
        "result_writer": writer,
    }

    # Act
    result = await run_review.run(
        ctx,
        library_id=LIBRARY_ID,
        task_id="review-task-1",
        input_payload={"topic": "RAG retrieval"},
    )

    # Assert — pipeline produced sections + persisted to the writer.
    assert result["section_count"] == 2
    assert result["result_pointer"].endswith("review-task-1.md")
    assert writer.calls and writer.calls[0][2] == "review"
    assert b"# RAG retrieval" in writer.calls[0][3]

    # Stage events covering the canonical review phases.
    stages = [s for s, _ in fake_event_bus.stage_events() if s is not None]
    for expected in (
        "subtopic_decompose",
        "subtopic_local_search",
        "subtopic_draft",
        "citation_check",
        "final_compose",
    ):
        assert expected in stages

    # `cost_updated` event was emitted once.
    cost_events = [e for e in fake_event_bus.events if e.type.value == "cost_updated"]
    assert len(cost_events) == 1
    assert cost_events[0].payload["cost_usd"] > 0.0

    # Status row updated to "running" with the result pointer + cost.
    row = fake_task_store.rows[(LIBRARY_ID, "review-task-1")]
    assert row["status"] in {"running", "completed"}
    assert row["result_pointer"] == result["result_pointer"]


@pytest.mark.asyncio
async def test_run_review_runs_without_writer(
    base_ctx: dict[str, Any],
    fake_event_bus: Any,
) -> None:
    # Arrange — no `result_writer` in ctx; pointer stays empty.
    ctx = {
        **base_ctx,
        "retrieval_planner": _StubPlanner(),
        "llm_client": _StubLLM(),
    }

    # Act
    result = await run_review.run(
        ctx,
        library_id=LIBRARY_ID,
        task_id="review-task-2",
        input_payload={"topic": "Topic"},
    )

    # Assert
    assert result["result_pointer"] == ""
    assert result["section_count"] == 2
