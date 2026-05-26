"""Tests for the LLM-based community summarizer."""

from __future__ import annotations

import pytest

from packages.core.models import Community, Entity, Triple
from packages.llm.protocols import LLMResponse, Message
from packages.structuring.adapters.llm_community_summarizer import (
    SUMMARY_FAILED_MARKER,
    LLMCommunitySummarizer,
    LLMCommunitySummarizerConfig,
    _extract_json_block,
)

LIBRARY_ID = "test-lib"
MODEL_NAME = "fake-model"


class FakeLLM:
    """Minimal LLMClient stub that records prompts and replays a response."""

    def __init__(self, response: str, *, raise_exc: Exception | None = None) -> None:
        self._response = response
        self._raise_exc = raise_exc
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
        self.calls.append(messages)
        if self._raise_exc is not None:
            raise self._raise_exc
        return LLMResponse(text=self._response, model="fake")


def _entity(entity_id: str, name: str, type_: str = "Method") -> Entity:
    return Entity(
        library_id=LIBRARY_ID,
        entity_id=entity_id,
        name=name,
        type=type_,
    )


def _triple(head: str, relation: str, tail: str) -> Triple:
    return Triple(
        library_id=LIBRARY_ID,
        head=head,
        relation=relation,
        tail=tail,
        evidence=("c1",),
        confidence=0.8,
        source_model="llm",
    )


def _community(member_ids: tuple[str, ...]) -> Community:
    return Community(
        library_id=LIBRARY_ID,
        community_id="comm-1",
        level=0,
        member_entity_ids=member_ids,
    )


class TestExtractJsonBlock:
    def test_plain_json(self) -> None:
        assert _extract_json_block('{"a": 1}') == '{"a": 1}'

    def test_with_code_fence(self) -> None:
        assert _extract_json_block('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_no_json_returns_none(self) -> None:
        assert _extract_json_block("no braces here") is None


class TestLLMCommunitySummarizer:
    @pytest.mark.asyncio
    async def test_populates_title_summary_and_reps_on_valid_response(self) -> None:
        # Arrange
        entities = [
            _entity("method:graphrag", "GraphRAG"),
            _entity("method:naive_rag", "Naive RAG"),
            _entity("dataset:hotpotqa", "HotpotQA", type_="Dataset"),
        ]
        triples = [
            _triple("method:graphrag", "improves_upon", "method:naive_rag"),
            _triple("method:graphrag", "evaluated_on", "dataset:hotpotqa"),
        ]
        community = _community(("method:graphrag", "method:naive_rag", "dataset:hotpotqa"))
        response = """{
            "title": "GraphRAG over HotpotQA",
            "summary": "GraphRAG improves on naive RAG. It is evaluated on HotpotQA.",
            "representative_entities": ["method:graphrag", "dataset:hotpotqa"]
        }"""
        summarizer = LLMCommunitySummarizer(llm=FakeLLM(response), model_name=MODEL_NAME)

        # Act
        result = await summarizer.summarize(LIBRARY_ID, community, entities, triples)

        # Assert
        assert result.title == "GraphRAG over HotpotQA"
        assert "GraphRAG improves on naive RAG" in result.summary
        assert result.summary_model == MODEL_NAME
        assert result.representative_entities == (
            "method:graphrag",
            "dataset:hotpotqa",
        )

    @pytest.mark.asyncio
    async def test_returns_summary_failed_on_malformed_response(self) -> None:
        # Arrange
        entities = [_entity("method:graphrag", "GraphRAG")]
        community = _community(("method:graphrag",))
        summarizer = LLMCommunitySummarizer(
            llm=FakeLLM("definitely not json"), model_name=MODEL_NAME
        )

        # Act
        result = await summarizer.summarize(LIBRARY_ID, community, entities, [])

        # Assert
        assert result.summary == SUMMARY_FAILED_MARKER
        assert result.title == ""
        assert result.representative_entities == ()
        assert result.summary_model == MODEL_NAME

    @pytest.mark.asyncio
    async def test_returns_summary_failed_on_llm_exception(self) -> None:
        entities = [_entity("method:graphrag", "GraphRAG")]
        community = _community(("method:graphrag",))
        summarizer = LLMCommunitySummarizer(
            llm=FakeLLM("", raise_exc=TimeoutError("upstream timeout")),
            model_name=MODEL_NAME,
        )

        result = await summarizer.summarize(LIBRARY_ID, community, entities, [])

        assert result.summary == SUMMARY_FAILED_MARKER
        assert result.summary_model == MODEL_NAME

    @pytest.mark.asyncio
    async def test_filters_representatives_to_input_entities(self) -> None:
        entities = [_entity("method:graphrag", "GraphRAG")]
        community = _community(("method:graphrag",))
        # LLM hallucinates two entity_ids that aren't in the input
        response = """{
            "title": "Made-up Title",
            "summary": "Some summary text. Another sentence.",
            "representative_entities": [
                "method:graphrag",
                "method:hallucinated",
                "dataset:nope"
            ]
        }"""
        summarizer = LLMCommunitySummarizer(llm=FakeLLM(response), model_name=MODEL_NAME)

        result = await summarizer.summarize(LIBRARY_ID, community, entities, [])

        assert result.representative_entities == ("method:graphrag",)

    @pytest.mark.asyncio
    async def test_truncates_entities_and_triples_over_limit(self) -> None:
        # Arrange: 5 entities, 4 triples, limits set to 2 + 2.
        entities = [_entity(f"method:e{i}", f"E{i}") for i in range(5)]
        triples = [
            _triple("method:e0", "improves_upon", "method:e1"),
            _triple("method:e0", "improves_upon", "method:e2"),
            _triple("method:e0", "improves_upon", "method:e3"),
            _triple("method:e0", "improves_upon", "method:e4"),
        ]
        community = _community(tuple(e.entity_id for e in entities))
        response = """{
            "title": "Trunc Test",
            "summary": "Short summary. Another sentence.",
            "representative_entities": ["method:e0"]
        }"""
        fake = FakeLLM(response)
        summarizer = LLMCommunitySummarizer(
            llm=fake,
            model_name=MODEL_NAME,
            config=LLMCommunitySummarizerConfig(
                max_entities_in_prompt=2,
                max_triples_in_prompt=2,
            ),
        )

        # Act
        result = await summarizer.summarize(LIBRARY_ID, community, entities, triples)

        # Assert: prompt should only mention the first 2 sorted entity_ids
        # (method:e0, method:e1) and at most 2 triples.
        assert result.title == "Trunc Test"
        assert len(fake.calls) == 1
        user_prompt = fake.calls[0][1].content
        assert "method:e0" in user_prompt
        assert "method:e1" in user_prompt
        # Truncated entries must NOT appear
        assert "method:e2" not in user_prompt
        assert "method:e3" not in user_prompt
        assert "method:e4" not in user_prompt
        # Only triples whose endpoints survived truncation can appear,
        # and at most max_triples_in_prompt of them.
        triple_lines = [line for line in user_prompt.splitlines() if "->" in line]
        assert len(triple_lines) <= 2

    @pytest.mark.asyncio
    async def test_returns_failure_when_no_entities_in_community(self) -> None:
        # member_entity_ids points to ids not present in the entities list
        community = _community(("method:missing",))
        entities = [_entity("method:graphrag", "GraphRAG")]
        summarizer = LLMCommunitySummarizer(
            llm=FakeLLM('{"title":"x","summary":"y","representative_entities":[]}'),
            model_name=MODEL_NAME,
        )

        result = await summarizer.summarize(LIBRARY_ID, community, entities, [])

        assert result.summary == SUMMARY_FAILED_MARKER
        assert result.summary_model == MODEL_NAME

    @pytest.mark.asyncio
    async def test_library_id_mismatch_returns_failure(self) -> None:
        community = _community(("method:graphrag",))
        entities = [_entity("method:graphrag", "GraphRAG")]
        summarizer = LLMCommunitySummarizer(llm=FakeLLM("{}"), model_name=MODEL_NAME)

        result = await summarizer.summarize("different-lib", community, entities, [])

        assert result.summary == SUMMARY_FAILED_MARKER
        assert result.library_id == LIBRARY_ID
