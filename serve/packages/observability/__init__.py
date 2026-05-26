"""Cross-cutting observability helpers.

Exposes OpenTelemetry tracing primitives + Langfuse LLM trace wrapper +
Prometheus metric definitions + combined @instrumented decorator.
Adapters and orchestrators stay decoupled from SDKs by going through these.
"""

from packages.observability.instrumentation import instrumented
from packages.observability.langfuse_client import (
    LangfuseConfig,
    LangfuseTracedLLM,
    update_config,
    with_library_tag,
)
from packages.observability.metrics import (
    EMBEDDING_CACHE_TOTAL,
    EMBEDDING_DURATION_SECONDS,
    INGESTION_DOCUMENTS_TOTAL,
    LLM_COST_USD_TOTAL,
    LLM_DURATION_SECONDS,
    LLM_ERRORS_TOTAL,
    LLM_TOKENS_TOTAL,
    RETRIEVAL_DURATION_SECONDS,
    RETRIEVAL_HITS_TOTAL,
    TASK_DURATION_SECONDS,
    TASK_RESULTS_TOTAL,
    get_registry,
)
from packages.observability.tracing import (
    TracingConfig,
    get_tracer,
    setup_tracing,
    traced_async,
    with_span,
)

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
    "LangfuseConfig",
    "LangfuseTracedLLM",
    "TracingConfig",
    "get_registry",
    "get_tracer",
    "instrumented",
    "setup_tracing",
    "traced_async",
    "update_config",
    "with_library_tag",
    "with_span",
]
