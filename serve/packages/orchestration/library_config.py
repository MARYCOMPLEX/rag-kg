"""Per-library configuration overrides (ADR-0012).

Each Library may independently override LLM router / embedder / retrieval
budget / daily cost cap. Unset fields fall through to global defaults.

Storage: Postgres `library_config` table with JSONB columns (ADR-0012
§schema). Reads are inline in the LLM gateway and embedder service; writes
go through `LibraryConfigStore`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from packages.retrieval.protocols import RetrievalBudget


class LLMRouterSpec(BaseModel):
    """Override for LLM Gateway routing (ADR-0012)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    primary: str = Field(min_length=1)
    fallback: tuple[str, ...] = ()
    prefer_local: bool = False
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class EmbedderSpec(BaseModel):
    """Override for embedder model (ADR-0012)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    dim: int = Field(ge=64, le=8192)
    api_url: str | None = None  # None = use default


class RerankerSpec(BaseModel):
    """Override for reranker (ADR-0012 + ADR-0018)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    timeout_ms: int = Field(default=200, ge=10, le=5000)
    enabled: bool = True


class LibraryConfig(BaseModel):
    """Per-library overrides + metadata.

    `None` on any field means "inherit global default" (ADR-0012 §override-semantics).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    llm_router_override: LLMRouterSpec | None = None
    embedder_override: EmbedderSpec | None = None
    reranker_override: RerankerSpec | None = None
    retrieval_budget_override: RetrievalBudget | None = None
    daily_cost_cap_usd: Decimal | None = None
    cost_cap_warn_pct: float = Field(default=0.8, ge=0.0, le=1.0)
    schema_yaml_path: str | None = None
    timezone: str = "UTC"
    updated_at: datetime
    updated_by: str = "system"


class LibraryConfigPatch(BaseModel):
    """Partial update payload — None = leave unchanged, sentinel = clear."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    llm_router_override: LLMRouterSpec | None = None
    embedder_override: EmbedderSpec | None = None
    reranker_override: RerankerSpec | None = None
    retrieval_budget_override: RetrievalBudget | None = None
    daily_cost_cap_usd: Decimal | None = None
    cost_cap_warn_pct: float | None = None
    schema_yaml_path: str | None = None
    timezone: str | None = None


@runtime_checkable
class LibraryConfigStore(Protocol):
    """Per-library config persistence (ADR-0012)."""

    async def get(self, library_id: str) -> LibraryConfig: ...

    async def update(
        self,
        library_id: str,
        patch: LibraryConfigPatch,
        *,
        updated_by: str,
    ) -> LibraryConfig: ...

    async def init_library(self, library_id: str) -> None:
        """Insert empty config row when a Library is created."""
        ...

    async def purge_library(self, library_id: str) -> None: ...
