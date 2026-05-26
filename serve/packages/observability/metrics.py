"""Prometheus metric definitions matching the Grafana dashboards.

Naming convention (locked by infra/grafana/dashboards/*):
    rag_<component>_<metric>_<unit>
Shared labels:
    library_id, suite, model, source, kind, op, component, error_type
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram
from prometheus_client.registry import REGISTRY as DEFAULT_REGISTRY

__all__ = [
    "EMBEDDING_CACHE_TOTAL",
    "EMBEDDING_DURATION_SECONDS",
    "INGESTION_DOCUMENTS_TOTAL",
    "LLM_COST_USD_TOTAL",
    "LLM_DURATION_SECONDS",
    "LLM_ERRORS_TOTAL",
    "LLM_TOKENS_TOTAL",
    "RETRIEVAL_DURATION_SECONDS",
    "RETRIEVAL_HITS_TOTAL",
    "TASK_DURATION_SECONDS",
    "TASK_RESULTS_TOTAL",
    "get_registry",
]


_DURATION_BUCKETS_S: tuple[float, ...] = (
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    25.0,
    60.0,
    120.0,
    300.0,
)


def get_registry() -> CollectorRegistry:
    """Return the active Prometheus registry (default global)."""
    return DEFAULT_REGISTRY


# === LLM ===

LLM_DURATION_SECONDS = Histogram(
    "rag_llm_duration_seconds",
    "Wall-clock latency of an LLM chat completion call.",
    labelnames=("model", "library_id"),
    buckets=_DURATION_BUCKETS_S,
)

LLM_TOKENS_TOTAL = Counter(
    "rag_llm_tokens_total",
    "Cumulative LLM token usage by direction (input/output).",
    labelnames=("model", "kind", "library_id"),
)

LLM_COST_USD_TOTAL = Counter(
    "rag_llm_cost_usd_total",
    "Cumulative USD spent on LLM chat completion calls.",
    labelnames=("model", "library_id"),
)

LLM_ERRORS_TOTAL = Counter(
    "rag_llm_errors_total",
    "Cumulative LLM call errors.",
    labelnames=("model", "library_id", "error_type"),
)


# === Embedding (separate from LLM since cost/latency profile differs) ===

EMBEDDING_DURATION_SECONDS = Histogram(
    "rag_embedding_duration_seconds",
    "Wall-clock latency of an embedding batch.",
    labelnames=("model", "op"),  # op=embed|rerank
    buckets=_DURATION_BUCKETS_S,
)

EMBEDDING_CACHE_TOTAL = Counter(
    "rag_embedding_cache_total",
    "Embedding cache hit/miss count.",
    labelnames=("status",),  # status=hit|miss
)


# === Retrieval (vector / bm25 / graph / community) ===

RETRIEVAL_DURATION_SECONDS = Histogram(
    "rag_retrieval_duration_seconds",
    "Latency of a retrieval index operation.",
    # component=qdrant|bm25|neo4j|community; op=search|upsert|...
    labelnames=("component", "library_id", "op"),
    buckets=_DURATION_BUCKETS_S,
)

RETRIEVAL_HITS_TOTAL = Counter(
    "rag_retrieval_hits_total",
    "Number of items returned by a retrieval call.",
    labelnames=("component", "library_id", "source"),
)


# === Ingestion ===

INGESTION_DOCUMENTS_TOTAL = Counter(
    "rag_ingestion_documents_total",
    "Documents fully ingested.",
    labelnames=("library_id", "status"),  # status=ok|error
)


# === Tasks (QA / Review / Reasoning / Hypothesis / Eval) ===

TASK_DURATION_SECONDS = Histogram(
    "rag_task_duration_seconds",
    "End-to-end task latency.",
    labelnames=("task", "library_id"),
    buckets=_DURATION_BUCKETS_S,
)

TASK_RESULTS_TOTAL = Counter(
    "rag_task_results_total",
    "Cumulative task runs by outcome.",
    labelnames=("task", "library_id", "outcome"),  # outcome=ok|error
)
