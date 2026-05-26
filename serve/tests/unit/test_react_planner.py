"""Tests for ReActPlanner — Thought-Action-Observation loop."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError

import pytest

from packages.core.models import Chunk, Entity, Query, Triple
from packages.llm.protocols import LLMResponse, Message
from packages.retrieval.protocols import RetrievalBudget
from packages.retrieval.strategies.react_rag import (
    PLANNER_NAME,
    ReActPlanner,
    ReActPlannerConfig,
)

LIBRARY_ID: str = "test-lib"


def _chunk(idx: int) -> Chunk:
    return Chunk(
        library_id=LIBRARY_ID,
        chunk_id=f"d::p1::{idx}",
        doc_id="d",
        text=f"chunk text {idx}",
    )


def _triple(head: str, relation: str, tail: str) -> Triple:
    return Triple(
        library_id=LIBRARY_ID,
        head=head,
        relation=relation,
        tail=tail,
        confidence=0.9,
    )


class FakeLLM:
    """LLM that returns scripted responses in order."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
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
        if not self._replies:
            text = "Thought: done\nAction: finish[fallback]"
        else:
            text = self._replies.pop(0)
        return LLMResponse(text=text, model="fake", input_tokens=10, output_tokens=5)


class FakeEmbedder:
    @property
    def dim(self) -> int:
        return 4

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


class FakeVectorIndex:
    def __init__(self, results: list[tuple[Chunk, float]] | None = None) -> None:
        self._results = results or []
        self.search_calls: list[tuple[str, int]] = []

    async def init_library(self, library_id: str) -> None:
        pass

    async def purge_library(self, library_id: str) -> None:
        pass

    async def upsert(self, library_id: str, items: list[tuple[Chunk, list[float]]]) -> None:
        pass

    async def search(
        self,
        library_id: str,
        vector: list[float],
        k: int,
        *,
        filter: Mapping[str, object] | None = None,
    ) -> list[tuple[Chunk, float]]:
        self.search_calls.append((library_id, k))
        return self._results[:k]


class FakeBM25Index:
    def __init__(self, results: list[tuple[Chunk, float]] | None = None) -> None:
        self._results = results or []
        self.search_queries: list[str] = []

    async def init_library(self, library_id: str) -> None:
        pass

    async def purge_library(self, library_id: str) -> None:
        pass

    async def upsert(self, library_id: str, chunks: list[Chunk]) -> None:
        pass

    async def search(self, library_id: str, query: str, k: int) -> list[tuple[Chunk, float]]:
        self.search_queries.append(query)
        return self._results[:k]


class FakeGraphIndex:
    def __init__(self, triples: list[Triple] | None = None) -> None:
        self._triples = triples or []
        self.neighbor_calls: list[tuple[str, int]] = []

    async def init_library(self, library_id: str) -> None:
        pass

    async def purge_library(self, library_id: str) -> None:
        pass

    async def upsert_entities(self, library_id: str, entities: list[Entity]) -> None:
        pass

    async def upsert_triples(self, library_id: str, triples: list[Triple]) -> None:
        pass

    async def get_neighbors(self, library_id: str, entity_id: str, depth: int = 1) -> list[Triple]:
        self.neighbor_calls.append((entity_id, depth))
        return list(self._triples)


def _build_planner(
    *,
    llm: FakeLLM,
    vector_results: list[tuple[Chunk, float]] | None = None,
    bm25_results: list[tuple[Chunk, float]] | None = None,
    triples: list[Triple] | None = None,
    budget: RetrievalBudget | None = None,
    config: ReActPlannerConfig | None = None,
) -> tuple[ReActPlanner, FakeVectorIndex, FakeBM25Index, FakeGraphIndex]:
    vector_index = FakeVectorIndex(results=vector_results)
    bm25_index = FakeBM25Index(results=bm25_results)
    graph_index = FakeGraphIndex(triples=triples)
    planner = ReActPlanner(
        llm=llm,
        embedder=FakeEmbedder(),
        vector_index=vector_index,
        bm25_index=bm25_index,
        graph_index=graph_index,
        budget=budget,
        config=config,
    )
    return planner, vector_index, bm25_index, graph_index


class TestReActPlannerConfig:
    def test_defaults(self) -> None:
        cfg = ReActPlannerConfig()
        assert cfg.vector_k == 5
        assert cfg.bm25_k == 5
        assert cfg.kg_depth == 1
        assert cfg.llm_temperature == 0.0
        assert cfg.llm_max_tokens == 400

    def test_is_frozen(self) -> None:
        cfg = ReActPlannerConfig()
        with pytest.raises(FrozenInstanceError):
            cfg.vector_k = 99  # type: ignore[misc]


class TestSingleStepFinish:
    @pytest.mark.asyncio
    async def test_immediate_finish_returns_no_evidence(self) -> None:
        llm = FakeLLM(["Thought: I already know.\nAction: finish[answer ready]"])
        planner, _v, _b, _g = _build_planner(llm=llm)
        query = Query(library_id=LIBRARY_ID, text="What is X?")

        result = await planner.plan_and_retrieve(LIBRARY_ID, query)

        assert result.evidence == ()
        assert result.trace is not None
        assert result.trace.terminated_reason == "answer_ready"
        assert result.trace.planner == PLANNER_NAME
        assert len(result.trace.steps) == 1
        assert result.trace.steps[0].action.lower() == "finish"
        assert result.trace.steps[0].action_input == "answer ready"


class TestMultiStep:
    @pytest.mark.asyncio
    async def test_vector_then_bm25_then_finish(self) -> None:
        llm = FakeLLM(
            [
                "Thought: try semantic search\nAction: vector_search[react paper]",
                "Thought: try keywords\nAction: bm25_search[react reasoning]",
                "Thought: done\nAction: finish[gathered evidence]",
            ]
        )
        v_chunk = _chunk(0)
        b_chunk = _chunk(1)
        planner, vidx, bidx, _g = _build_planner(
            llm=llm,
            vector_results=[(v_chunk, 0.9)],
            bm25_results=[(b_chunk, 0.7)],
        )
        query = Query(library_id=LIBRARY_ID, text="What is ReAct?")

        result = await planner.plan_and_retrieve(LIBRARY_ID, query)

        assert result.trace is not None
        assert result.trace.terminated_reason == "answer_ready"
        assert len(result.trace.steps) == 3
        chunk_ids = {ev.chunk.chunk_id for ev in result.evidence}
        assert chunk_ids == {v_chunk.chunk_id, b_chunk.chunk_id}
        assert result.evidence[0].score == 0.9  # sorted desc
        assert vidx.search_calls == [(LIBRARY_ID, 5)]
        assert bidx.search_queries == ["react reasoning"]

    @pytest.mark.asyncio
    async def test_dedupes_by_chunk_id_keeping_max_score(self) -> None:
        chunk = _chunk(0)
        llm = FakeLLM(
            [
                "Thought: t1\nAction: vector_search[q]",
                "Thought: t2\nAction: bm25_search[q]",
                "Thought: done\nAction: finish[ok]",
            ]
        )
        planner, _v, _b, _g = _build_planner(
            llm=llm,
            vector_results=[(chunk, 0.4)],
            bm25_results=[(chunk, 0.95)],
        )
        query = Query(library_id=LIBRARY_ID, text="q")

        result = await planner.plan_and_retrieve(LIBRARY_ID, query)

        assert len(result.evidence) == 1
        assert result.evidence[0].score == 0.95


class TestBudget:
    @pytest.mark.asyncio
    async def test_max_steps_one_terminates_with_budget_exceeded(self) -> None:
        llm = FakeLLM(
            [
                "Thought: search\nAction: vector_search[q]",
                "Thought: more\nAction: vector_search[q2]",
            ]
        )
        budget = RetrievalBudget(max_steps=1)
        planner, _v, _b, _g = _build_planner(
            llm=llm,
            vector_results=[(_chunk(0), 0.5)],
            budget=budget,
        )
        query = Query(library_id=LIBRARY_ID, text="q")

        result = await planner.plan_and_retrieve(LIBRARY_ID, query)

        assert result.trace is not None
        assert result.trace.terminated_reason == "budget_exceeded"
        assert len(result.trace.steps) == 1
        assert result.trace.budget_used.steps == 1
        assert result.trace.budget_used.llm_calls == 1


class TestMalformedAction:
    @pytest.mark.asyncio
    async def test_unparseable_response_records_step_and_continues(self) -> None:
        llm = FakeLLM(
            [
                "this is not a valid react reply",
                "Thought: ok\nAction: finish[recovered]",
            ]
        )
        planner, _v, _b, _g = _build_planner(llm=llm)
        query = Query(library_id=LIBRARY_ID, text="q")

        result = await planner.plan_and_retrieve(LIBRARY_ID, query)

        assert result.trace is not None
        assert len(result.trace.steps) == 2
        first = result.trace.steps[0]
        assert first.action == ""
        assert "Could not parse" in first.observation
        assert result.trace.terminated_reason == "answer_ready"

    @pytest.mark.asyncio
    async def test_unknown_action_records_helpful_observation(self) -> None:
        llm = FakeLLM(
            [
                "Thought: try unknown\nAction: do_magic[x]",
                "Thought: done\nAction: finish[ok]",
            ]
        )
        planner, _v, _b, _g = _build_planner(llm=llm)
        query = Query(library_id=LIBRARY_ID, text="q")

        result = await planner.plan_and_retrieve(LIBRARY_ID, query)

        assert result.trace is not None
        assert "Unknown action" in result.trace.steps[0].observation


class TestToolDispatch:
    @pytest.mark.asyncio
    async def test_vector_search_observation_format(self) -> None:
        llm = FakeLLM(
            [
                "Thought: t\nAction: vector_search[hello]",
                "Thought: t\nAction: finish[ok]",
            ]
        )
        planner, _v, _b, _g = _build_planner(
            llm=llm,
            vector_results=[(_chunk(0), 0.9), (_chunk(1), 0.8)],
        )
        result = await planner.plan_and_retrieve(LIBRARY_ID, Query(library_id=LIBRARY_ID, text="q"))
        assert result.trace is not None
        obs = result.trace.steps[0].observation
        assert "vector_search returned 2 results" in obs
        assert "d::p1::0" in obs

    @pytest.mark.asyncio
    async def test_bm25_search_observation_format(self) -> None:
        llm = FakeLLM(
            [
                "Thought: t\nAction: bm25_search[hello]",
                "Thought: t\nAction: finish[ok]",
            ]
        )
        planner, _v, _b, _g = _build_planner(
            llm=llm,
            bm25_results=[(_chunk(0), 0.5)],
        )
        result = await planner.plan_and_retrieve(LIBRARY_ID, Query(library_id=LIBRARY_ID, text="q"))
        assert result.trace is not None
        assert "bm25_search returned 1 results" in result.trace.steps[0].observation

    @pytest.mark.asyncio
    async def test_kg_neighborhood_observation_format(self) -> None:
        llm = FakeLLM(
            [
                "Thought: t\nAction: kg_neighborhood[method:react]",
                "Thought: t\nAction: finish[ok]",
            ]
        )
        triples = [
            _triple("method:react", "introduces", "concept:thought-action"),
            _triple("method:react", "evaluated_on", "benchmark:hotpotqa"),
        ]
        planner, _v, _b, gidx = _build_planner(llm=llm, triples=triples)
        result = await planner.plan_and_retrieve(LIBRARY_ID, Query(library_id=LIBRARY_ID, text="q"))
        assert result.trace is not None
        assert gidx.neighbor_calls == [("method:react", 1)]
        obs = result.trace.steps[0].observation
        assert "returned 2 triples" in obs
        assert "introduces" in obs

    @pytest.mark.asyncio
    async def test_empty_action_input_returns_helpful_message(self) -> None:
        llm = FakeLLM(
            [
                "Thought: t\nAction: vector_search[]",
                "Thought: t\nAction: finish[ok]",
            ]
        )
        planner, _v, _b, _g = _build_planner(llm=llm)
        result = await planner.plan_and_retrieve(LIBRARY_ID, Query(library_id=LIBRARY_ID, text="q"))
        assert result.trace is not None
        assert "non-empty" in result.trace.steps[0].observation


class TestQueryValidation:
    @pytest.mark.asyncio
    async def test_query_library_mismatch_raises(self) -> None:
        llm = FakeLLM(["Thought: t\nAction: finish[ok]"])
        planner, _v, _b, _g = _build_planner(llm=llm)
        query = Query(library_id="other-lib", text="q")
        with pytest.raises(ValueError, match="does not match"):
            await planner.plan_and_retrieve(LIBRARY_ID, query)


class TestActionInputFormats:
    @pytest.mark.asyncio
    async def test_action_input_line_form(self) -> None:
        llm = FakeLLM(
            [
                "Thought: t\nAction: vector_search\nAction Input: hello world",
                "Thought: done\nAction: finish[ok]",
            ]
        )
        planner, _v, _b, _g = _build_planner(
            llm=llm,
            vector_results=[(_chunk(0), 0.9)],
        )
        result = await planner.plan_and_retrieve(LIBRARY_ID, Query(library_id=LIBRARY_ID, text="q"))
        assert result.trace is not None
        assert result.trace.steps[0].action_input == "hello world"
        assert len(result.evidence) == 1
