"""Tests for the Prometheus metric registry definitions."""

from __future__ import annotations

from packages.observability.metrics import (
    EMBEDDING_CACHE_TOTAL,
    LLM_COST_USD_TOTAL,
    LLM_DURATION_SECONDS,
    LLM_TOKENS_TOTAL,
    RETRIEVAL_DURATION_SECONDS,
    RETRIEVAL_HITS_TOTAL,
    TASK_DURATION_SECONDS,
    get_registry,
)


class TestMetricNames:
    """Verify metric names match the Grafana dashboard contract."""

    def test_llm_metrics_named_correctly(self) -> None:
        assert LLM_DURATION_SECONDS._name == "rag_llm_duration_seconds"
        assert LLM_TOKENS_TOTAL._name == "rag_llm_tokens"
        assert LLM_COST_USD_TOTAL._name == "rag_llm_cost_usd"

    def test_retrieval_metrics_named_correctly(self) -> None:
        assert RETRIEVAL_DURATION_SECONDS._name == "rag_retrieval_duration_seconds"
        assert RETRIEVAL_HITS_TOTAL._name == "rag_retrieval_hits"

    def test_task_metric_named_correctly(self) -> None:
        assert TASK_DURATION_SECONDS._name == "rag_task_duration_seconds"

    def test_embedding_cache_named_correctly(self) -> None:
        assert EMBEDDING_CACHE_TOTAL._name == "rag_embedding_cache"


class TestMetricLabels:
    def test_llm_labels(self) -> None:
        # Histogram gets a per-label child via .labels()
        child = LLM_DURATION_SECONDS.labels(model="m", library_id="lib")
        child.observe(0.5)  # smoke

    def test_counter_labels(self) -> None:
        LLM_TOKENS_TOTAL.labels(model="m", kind="input", library_id="lib").inc(100)
        LLM_TOKENS_TOTAL.labels(model="m", kind="output", library_id="lib").inc(50)


class TestRegistry:
    def test_get_registry_returns_default(self) -> None:
        reg = get_registry()
        assert reg is not None
