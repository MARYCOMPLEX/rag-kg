"""Centralized application settings via pydantic-settings.

All configuration flows through this module. Business code must not
call os.getenv directly — inject the needed fields instead.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Data Layer ---
    postgres_url: str = "postgresql+asyncpg://rkb:rkb@localhost:5432/rkb"
    qdrant_url: str = "http://localhost:6333"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme"
    opensearch_url: str = "http://localhost:9200"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "kb"

    # --- LLM (OpenAI-compatible API) ---
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_s: int = Field(default=60, ge=1, le=600)

    # --- Embedding (OpenAI-compatible API) ---
    embedding_api_base: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = Field(default=1536, ge=1)
    embedding_batch_size: int = Field(default=64, ge=1, le=2048)
    embedding_timeout_s: int = Field(default=30, ge=1, le=300)

    # --- Reranker (OpenAI-compatible /v1/rerank) ---
    rerank_api_base: str = "https://api.siliconflow.cn/v1"
    rerank_api_key: str = ""
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_timeout_s: int = Field(default=30, ge=1, le=300)
    rerank_enabled: bool = True

    # --- Hybrid retrieval ---
    hybrid_enabled: bool = True
    hybrid_k_vector: int = Field(default=20, ge=1, le=200)
    hybrid_k_bm25: int = Field(default=20, ge=1, le=200)
    hybrid_rrf_k: int = Field(default=60, ge=1, le=200)
    hybrid_k_final: int = Field(default=8, ge=1, le=50)

    # --- KG extraction ---
    kg_enabled: bool = True
    kg_chunks_per_call: int = Field(default=5, ge=1, le=20)
    kg_max_concurrent: int = Field(default=2, ge=1, le=8)

    # --- Community detection / global search (M3) ---
    community_enabled: bool = True
    community_min_size: int = Field(default=3, ge=2, le=20)
    community_max_levels: int = Field(default=2, ge=1, le=5)
    community_random_seed: int = 42
    community_summary_max_entities: int = Field(default=30, ge=5, le=200)
    community_summary_max_triples: int = Field(default=80, ge=10, le=500)
    community_summary_max_concurrent: int = Field(default=2, ge=1, le=8)
    global_search_k: int = Field(default=5, ge=1, le=50)

    # --- Agentic retrieval (M4) ---
    # planner choices: routed (M3 default) | direct | hybrid | global | react
    planner: str = "routed"
    react_max_steps: int = Field(default=8, ge=1, le=50)
    react_max_llm_calls: int = Field(default=20, ge=1, le=200)
    react_max_input_tokens: int = Field(default=32000, ge=100)
    react_max_output_tokens: int = Field(default=4000, ge=100)
    react_timeout_s: float = Field(default=180.0, ge=1.0)
    react_vector_k: int = Field(default=5, ge=1, le=50)
    react_bm25_k: int = Field(default=5, ge=1, le=50)
    react_kg_depth: int = Field(default=1, ge=1, le=3)

    # --- Data Directory ---
    data_dir: str = "data"

    # --- Observability ---
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    otel_enabled: bool = False
    otel_service_name: str = "rag-kg-copilot"
    otel_otlp_endpoint: str = ""  # empty = no remote exporter
    otel_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)

    # --- API surface (M7) ---
    api_key: str = ""  # empty disables auth (dev mode)
    rate_limit_enabled: bool = False
    rate_limit_rpm: int = Field(default=60, ge=1)
    rate_limit_burst: int = Field(default=20, ge=1)

    # --- Ingestion idempotency (M7) ---
    ingest_state_dir: str = "data/state"

    # --- Context management (M8) ---
    context_db_path: str = "data/state/context.sqlite"
    context_max_input_tokens: int = Field(default=24576, ge=512)
    context_recent_turns_window: int = Field(default=4, ge=0, le=50)
    context_memory_max_entries_in_prompt: int = Field(default=5, ge=0, le=50)
    context_compact_summary_max_tokens: int = Field(default=512, ge=64, le=4096)
    rewrite_enabled: bool = True
    rewrite_min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    rewrite_max_tokens_out: int = Field(default=80, ge=16, le=512)

    # --- App ---
    log_level: str = "INFO"
    debug: bool = False


def get_settings() -> Settings:
    """Factory for settings; caching handled by caller (DI container)."""
    return Settings()
