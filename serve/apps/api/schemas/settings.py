"""HTTP wire schemas for per-library settings endpoints (ADR-0012, ADR-0015).

API-layer Pydantic models — separate from the domain
`packages.orchestration.library_config.LibraryConfig` so the wire contract
can evolve without forcing core schema migrations (CODING_STANDARDS §13.1).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LLMRouterSpecPayload(BaseModel):
    """Wire shape for `LLMRouterSpec` overrides (ADR-0012)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    primary: str = Field(min_length=1)
    fallback: tuple[str, ...] = ()
    prefer_local: bool = False
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class EmbedderSpecPayload(BaseModel):
    """Wire shape for `EmbedderSpec` overrides (ADR-0012)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    dim: int = Field(ge=64, le=8192)
    api_url: str | None = None


class RerankerSpecPayload(BaseModel):
    """Wire shape for `RerankerSpec` overrides (ADR-0012 + ADR-0018)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    timeout_ms: int = Field(default=200, ge=10, le=5000)
    enabled: bool = True


class RetrievalBudgetPayload(BaseModel):
    """Wire shape for `RetrievalBudget` overrides (ADR-0012)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_steps: int = Field(default=8, ge=1, le=50)
    max_llm_calls: int = Field(default=12, ge=1, le=100)
    max_input_tokens: int = Field(default=8000, ge=512, le=200_000)
    max_output_tokens: int = Field(default=2000, ge=64, le=32_000)
    timeout_s: float = Field(default=60.0, ge=1.0, le=600.0)


class LibrarySettingsResponse(BaseModel):
    """`GET /v1/libraries/{lib}/settings` — full effective overrides view."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    llm_router_override: LLMRouterSpecPayload | None = None
    embedder_override: EmbedderSpecPayload | None = None
    reranker_override: RerankerSpecPayload | None = None
    retrieval_budget_override: RetrievalBudgetPayload | None = None
    daily_cost_cap_usd: Decimal | None = None
    cost_cap_warn_pct: float = Field(ge=0.0, le=1.0)
    schema_yaml_path: str | None = None
    timezone: str = "UTC"
    updated_at: datetime
    updated_by: str = "system"


class LibrarySettingsPatchRequest(BaseModel):
    """`PUT /v1/libraries/{lib}/settings` — partial update payload (ADR-0012 §2)."""

    model_config = ConfigDict(extra="forbid")

    llm_router_override: LLMRouterSpecPayload | None = None
    embedder_override: EmbedderSpecPayload | None = None
    reranker_override: RerankerSpecPayload | None = None
    retrieval_budget_override: RetrievalBudgetPayload | None = None
    daily_cost_cap_usd: Decimal | None = None
    cost_cap_warn_pct: float | None = Field(default=None, ge=0.0, le=1.0)
    schema_yaml_path: str | None = None
    timezone: str | None = None


class DailyCostEntry(BaseModel):
    """One historical day's cost row (ADR-0015 §8)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    date: date
    cost_usd: Decimal
    request_count: int = Field(ge=0)


class LibraryCostResponse(BaseModel):
    """`GET /v1/libraries/{lib}/cost?days=30` — cost trend payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str
    cap_usd: Decimal | None = None
    today: DailyCostEntry
    history: tuple[DailyCostEntry, ...] = ()
