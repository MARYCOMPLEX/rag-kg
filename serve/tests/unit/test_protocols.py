"""Tests that all package protocols are importable and well-formed.

Verifies that protocol skeletons compile, are runtime-checkable,
and that library-scoped methods have library_id as first parameter.
"""

from __future__ import annotations

import inspect
from typing import Protocol

import pytest
from pydantic import ValidationError

from packages.embedding.protocols import Embedder, Reranker
from packages.evaluation.protocols import EvalSample, Metric, MetricScore, SampleLoader
from packages.indexing.protocols import BM25Index, GraphIndex, RetrievalCoordinator, VectorIndex
from packages.ingestion.protocols import Chunker, Deduper, Parser
from packages.llm.protocols import LLMClient, LLMResponse, Message
from packages.orchestration.protocols import TaskRunner
from packages.retrieval.protocols import RetrievalPlanner
from packages.structuring.protocols import EntityExtractor, EntityLinker, RelationExtractor

ALL_PROTOCOLS: list[type[object]] = [
    Embedder,
    Reranker,
    Metric,
    SampleLoader,
    BM25Index,
    GraphIndex,
    RetrievalCoordinator,
    VectorIndex,
    Parser,
    Chunker,
    Deduper,
    LLMClient,
    TaskRunner,
    RetrievalPlanner,
    EntityExtractor,
    EntityLinker,
    RelationExtractor,
]

LIBRARY_SCOPED_PROTOCOLS: list[type[object]] = [
    BM25Index,
    GraphIndex,
    VectorIndex,
    RetrievalCoordinator,
    Parser,
    Chunker,
    Deduper,
    TaskRunner,
    RetrievalPlanner,
    EntityExtractor,
    EntityLinker,
    RelationExtractor,
]

STATELESS_PROTOCOLS: list[type[object]] = [
    Embedder,
    Reranker,
    LLMClient,
]


class TestProtocolsAreWellFormed:
    def test_all_protocols_are_importable_and_are_protocol_subclasses(self) -> None:
        for proto in ALL_PROTOCOLS:
            assert issubclass(proto, Protocol), f"{proto.__name__} is not a Protocol"


class TestLibraryScopedProtocols:
    def test_library_scoped_methods_have_library_id_first(self) -> None:
        for proto in LIBRARY_SCOPED_PROTOCOLS:
            for name, method in inspect.getmembers(proto, predicate=inspect.isfunction):
                if name.startswith("_"):
                    continue
                params = list(inspect.signature(method).parameters.keys())
                if len(params) <= 1:
                    continue
                assert params[1] == "library_id", (
                    f"{proto.__name__}.{name}: first param after self should be "
                    f"'library_id', got '{params[1]}'"
                )


class TestIndexProtocolsHaveLifecycleMethods:
    def test_vector_index_has_init_and_purge(self) -> None:
        assert hasattr(VectorIndex, "init_library")
        assert hasattr(VectorIndex, "purge_library")

    def test_graph_index_has_init_and_purge(self) -> None:
        assert hasattr(GraphIndex, "init_library")
        assert hasattr(GraphIndex, "purge_library")

    def test_bm25_index_has_init_and_purge(self) -> None:
        assert hasattr(BM25Index, "init_library")
        assert hasattr(BM25Index, "purge_library")


class TestStatelessProtocolsNoLibraryId:
    def test_embedder_embed_has_no_library_id(self) -> None:
        sig = inspect.signature(Embedder.embed)
        params = list(sig.parameters.keys())
        assert "library_id" not in params

    def test_llm_client_complete_has_no_library_id(self) -> None:
        sig = inspect.signature(LLMClient.complete)
        params = list(sig.parameters.keys())
        assert "library_id" not in params

    def test_reranker_rerank_has_no_library_id(self) -> None:
        sig = inspect.signature(Reranker.rerank)
        params = list(sig.parameters.keys())
        assert "library_id" not in params


class TestLLMModels:
    def test_message_creation(self) -> None:
        msg = Message(role="user", content="hello")
        assert msg.role == "user"

    def test_message_is_frozen(self) -> None:
        msg = Message(role="user", content="hello")
        with pytest.raises(ValidationError):
            msg.content = "changed"  # type: ignore[misc]

    def test_llm_response_creation(self) -> None:
        resp = LLMResponse(
            text="answer",
            model="gpt-4",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
        )
        assert resp.model == "gpt-4"


class TestEvalModels:
    def test_eval_sample_creation(self) -> None:
        sample = EvalSample(
            sample_id="qa-001",
            library_id="test-lib",
            suite="qa.smoke",
            suite_version="v1",
            question="What is RAG?",
            difficulty="easy",
            type="single-hop",
        )
        assert sample.sample_id == "qa-001"

    def test_metric_score_creation(self) -> None:
        score = MetricScore(
            metric_name="recall_at_10",
            score=0.85,
        )
        assert score.score == 0.85
