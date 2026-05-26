"""Tests for the LLM-based entity + relation extractor."""

from __future__ import annotations

import pytest

from packages.core.models import Chunk
from packages.llm.protocols import LLMResponse, Message
from packages.structuring.adapters.llm_extractor import (
    LLMEntityRelationExtractor,
    LLMExtractorConfig,
    _canonical_entity_id,
    _extract_json_block,
)
from packages.structuring.schema import EntityType, KGSchema, RelationType


def _schema() -> KGSchema:
    return KGSchema(
        library_id="test-lib",
        entity_types=(EntityType(id="Method"), EntityType(id="Dataset")),
        relation_types=(
            RelationType(
                id="evaluated_on",
                head_types=("Method",),
                tail_types=("Dataset",),
            ),
        ),
    )


def _chunk(chunk_id: str, text: str = "x") -> Chunk:
    return Chunk(library_id="test-lib", chunk_id=chunk_id, doc_id="d", text=text)


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse:
        return LLMResponse(text=self._response, model="fake")


class TestCanonicalEntityId:
    def test_basic_slug(self) -> None:
        assert _canonical_entity_id("GraphRAG", "Method") == "method:graphrag"

    def test_unicode_chars(self) -> None:
        # Should hash-fallback when no ASCII chars remain
        result = _canonical_entity_id("中文", "Method")
        assert result.startswith("method:")
        assert len(result) > len("method:")


class TestExtractJsonBlock:
    def test_plain_json(self) -> None:
        assert _extract_json_block('{"a": 1}') == '{"a": 1}'

    def test_with_code_fence(self) -> None:
        assert _extract_json_block('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_with_prose_around(self) -> None:
        result = _extract_json_block('Here is the JSON:\n{"a": 1}\n')
        assert result == '{"a": 1}'

    def test_no_json_returns_none(self) -> None:
        assert _extract_json_block("no json here") is None


class TestLLMExtractor:
    @pytest.mark.asyncio
    async def test_empty_chunks(self) -> None:
        extractor = LLMEntityRelationExtractor(llm=FakeLLM("{}"), schema=_schema())
        result = await extractor.extract("test-lib", [])
        assert result.entities == ()
        assert result.triples == ()

    @pytest.mark.asyncio
    async def test_parses_valid_response(self) -> None:
        json_payload = """{
            "entities": [
                {"name": "GraphRAG", "type": "Method"},
                {"name": "HotpotQA", "type": "Dataset"}
            ],
            "triples": [
                {
                    "head": "GraphRAG",
                    "head_type": "Method",
                    "relation": "evaluated_on",
                    "tail": "HotpotQA",
                    "tail_type": "Dataset",
                    "evidence_chunk_ids": ["d::p1::0"],
                    "confidence": 0.9
                }
            ]
        }"""
        extractor = LLMEntityRelationExtractor(
            llm=FakeLLM(json_payload),
            schema=_schema(),
            config=LLMExtractorConfig(chunks_per_call=10),
        )
        result = await extractor.extract("test-lib", [_chunk("d::p1::0")])
        assert len(result.entities) == 2
        assert len(result.triples) == 1
        triple = result.triples[0]
        assert triple.head == "method:graphrag"
        assert triple.tail == "dataset:hotpotqa"
        assert triple.evidence == ("d::p1::0",)

    @pytest.mark.asyncio
    async def test_drops_triple_with_invalid_relation(self) -> None:
        json_payload = """{
            "entities": [],
            "triples": [
                {
                    "head": "X", "head_type": "Method",
                    "relation": "BOGUS",
                    "tail": "Y", "tail_type": "Dataset",
                    "evidence_chunk_ids": ["d::p1::0"]
                }
            ]
        }"""
        extractor = LLMEntityRelationExtractor(llm=FakeLLM(json_payload), schema=_schema())
        result = await extractor.extract("test-lib", [_chunk("d::p1::0")])
        assert result.triples == ()

    @pytest.mark.asyncio
    async def test_drops_triple_with_unknown_evidence_chunk(self) -> None:
        json_payload = """{
            "entities": [],
            "triples": [
                {
                    "head": "X", "head_type": "Method",
                    "relation": "evaluated_on",
                    "tail": "Y", "tail_type": "Dataset",
                    "evidence_chunk_ids": ["bogus_chunk"]
                }
            ]
        }"""
        extractor = LLMEntityRelationExtractor(llm=FakeLLM(json_payload), schema=_schema())
        result = await extractor.extract("test-lib", [_chunk("d::p1::0")])
        assert result.triples == ()

    @pytest.mark.asyncio
    async def test_invalid_json_returns_empty(self) -> None:
        extractor = LLMEntityRelationExtractor(llm=FakeLLM("not json"), schema=_schema())
        result = await extractor.extract("test-lib", [_chunk("d::p1::0")])
        assert result.entities == ()
        assert result.triples == ()
