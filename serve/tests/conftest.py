"""Shared test fixtures."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.core.models import Chunk, Document, Entity, Library, Query, Triple


@pytest.fixture
def sample_library() -> Library:
    return Library(
        library_id="test-lib",
        name="Test Library",
        description="A test library",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def sample_document() -> Document:
    return Document(
        library_id="test-lib",
        doc_id="doc-001",
        title="Test Paper",
        authors=("Alice", "Bob"),
        year=2025,
        venue="NeurIPS",
        source_url="https://arxiv.org/abs/0000.00000",
        doi="10.1234/test",
        content_hash="abc123def456",
        ingest_ts=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def sample_chunk() -> Chunk:
    return Chunk(
        library_id="test-lib",
        chunk_id="doc-001::intro::0",
        doc_id="doc-001",
        text="This is a test chunk about knowledge graphs.",
        page=1,
        section="Introduction",
        kind="text",
        offset=(0, 45),
    )


@pytest.fixture
def sample_entity() -> Entity:
    return Entity(
        library_id="test-lib",
        entity_id="ent-graphrag",
        name="GraphRAG",
        aliases=("Graph-RAG", "graph rag"),
        type="Method",
        description="A graph-based RAG approach",
    )


@pytest.fixture
def sample_triple() -> Triple:
    return Triple(
        library_id="test-lib",
        head="ent-graphrag",
        relation="improves_upon",
        tail="ent-naive-rag",
        evidence=("doc-001::intro::0",),
        confidence=0.95,
        source_model="gpt-4",
    )


@pytest.fixture
def sample_query() -> Query:
    return Query(
        library_id="test-lib",
        text="What is GraphRAG?",
        type="single-hop",
        max_results=10,
    )
