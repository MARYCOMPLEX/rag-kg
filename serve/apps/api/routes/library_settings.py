"""Per-library settings endpoints (ADR-0012, ADR-0015).

| Method | Path                                              | Purpose                          |
|--------|---------------------------------------------------|----------------------------------|
| GET    | /v1/libraries/{library_id}/settings               | read effective overrides         |
| PUT    | /v1/libraries/{library_id}/settings               | partial update (PATCH semantics) |
| GET    | /v1/libraries/{library_id}/cost?days=30           | today + cost trend               |

Refs:
- ADR-0012 §2 — `LibraryConfigPatch` semantics (None field = clear override).
- ADR-0015 §8 — daily cost endpoint payload.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import structlog
from fastapi import APIRouter, Depends, Path, Query

from apps._shared.factories import AppContainer
from apps.api._orchestration_deps import (
    get_cost_enforcer,
    get_library_config_store,
)
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from apps.api.schemas.settings import (
    DailyCostEntry,
    EmbedderSpecPayload,
    LibraryCostResponse,
    LibrarySettingsPatchRequest,
    LibrarySettingsResponse,
    LLMRouterSpecPayload,
    RerankerSpecPayload,
    RetrievalBudgetPayload,
)
from packages.core.errors import LibraryNotFoundError
from packages.observability import with_span
from packages.orchestration.adapters.postgres_cost import PostgresCostCapEnforcer
from packages.orchestration.adapters.postgres_library_config import (
    PostgresLibraryConfigStore,
)
from packages.orchestration.cost import LibraryDailyCost
from packages.orchestration.library_config import (
    EmbedderSpec,
    LibraryConfig,
    LibraryConfigPatch,
    LLMRouterSpec,
    RerankerSpec,
)
from packages.retrieval.protocols import RetrievalBudget

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["library_settings"])

_DEFAULT_HISTORY_DAYS = 30
_MAX_HISTORY_DAYS = 365


# ---------- domain ↔ wire conversion helpers ----------------------------


def _llm_router_to_payload(spec: LLMRouterSpec | None) -> LLMRouterSpecPayload | None:
    if spec is None:
        return None
    return LLMRouterSpecPayload(
        primary=spec.primary,
        fallback=spec.fallback,
        prefer_local=spec.prefer_local,
        temperature=spec.temperature,
    )


def _embedder_to_payload(spec: EmbedderSpec | None) -> EmbedderSpecPayload | None:
    if spec is None:
        return None
    return EmbedderSpecPayload(name=spec.name, dim=spec.dim, api_url=spec.api_url)


def _reranker_to_payload(spec: RerankerSpec | None) -> RerankerSpecPayload | None:
    if spec is None:
        return None
    return RerankerSpecPayload(
        name=spec.name,
        timeout_ms=spec.timeout_ms,
        enabled=spec.enabled,
    )


def _budget_to_payload(
    budget: RetrievalBudget | None,
) -> RetrievalBudgetPayload | None:
    if budget is None:
        return None
    return RetrievalBudgetPayload(
        max_steps=budget.max_steps,
        max_llm_calls=budget.max_llm_calls,
        max_input_tokens=budget.max_input_tokens,
        max_output_tokens=budget.max_output_tokens,
        timeout_s=budget.timeout_s,
    )


def _config_to_response(config: LibraryConfig) -> LibrarySettingsResponse:
    return LibrarySettingsResponse(
        library_id=config.library_id,
        llm_router_override=_llm_router_to_payload(config.llm_router_override),
        embedder_override=_embedder_to_payload(config.embedder_override),
        reranker_override=_reranker_to_payload(config.reranker_override),
        retrieval_budget_override=_budget_to_payload(config.retrieval_budget_override),
        daily_cost_cap_usd=config.daily_cost_cap_usd,
        cost_cap_warn_pct=config.cost_cap_warn_pct,
        schema_yaml_path=config.schema_yaml_path,
        timezone=config.timezone,
        updated_at=config.updated_at,
        updated_by=config.updated_by,
    )


def _payload_to_llm_router(
    payload: LLMRouterSpecPayload | None,
) -> LLMRouterSpec | None:
    if payload is None:
        return None
    return LLMRouterSpec(
        primary=payload.primary,
        fallback=payload.fallback,
        prefer_local=payload.prefer_local,
        temperature=payload.temperature,
    )


def _payload_to_embedder(payload: EmbedderSpecPayload | None) -> EmbedderSpec | None:
    if payload is None:
        return None
    return EmbedderSpec(name=payload.name, dim=payload.dim, api_url=payload.api_url)


def _payload_to_reranker(payload: RerankerSpecPayload | None) -> RerankerSpec | None:
    if payload is None:
        return None
    return RerankerSpec(
        name=payload.name,
        timeout_ms=payload.timeout_ms,
        enabled=payload.enabled,
    )


def _payload_to_budget(
    payload: RetrievalBudgetPayload | None,
) -> RetrievalBudget | None:
    if payload is None:
        return None
    return RetrievalBudget(
        max_steps=payload.max_steps,
        max_llm_calls=payload.max_llm_calls,
        max_input_tokens=payload.max_input_tokens,
        max_output_tokens=payload.max_output_tokens,
        timeout_s=payload.timeout_s,
    )


def _request_to_patch(req: LibrarySettingsPatchRequest) -> LibraryConfigPatch:
    """Convert wire payload to domain patch — preserving `model_fields_set`.

    Per ADR-0012 §2, a field absent from the payload means "leave alone";
    a field set to `None` explicitly means "clear the override". Pydantic
    keeps that distinction in `model_fields_set`; we rebuild the patch by
    constructing it with all defaults then overlaying only the explicitly
    set fields via `model_copy`.
    """
    fields = req.model_fields_set
    patch = LibraryConfigPatch()
    updates: dict[str, object] = {}
    if "llm_router_override" in fields:
        updates["llm_router_override"] = _payload_to_llm_router(req.llm_router_override)
    if "embedder_override" in fields:
        updates["embedder_override"] = _payload_to_embedder(req.embedder_override)
    if "reranker_override" in fields:
        updates["reranker_override"] = _payload_to_reranker(req.reranker_override)
    if "retrieval_budget_override" in fields:
        updates["retrieval_budget_override"] = _payload_to_budget(req.retrieval_budget_override)
    if "daily_cost_cap_usd" in fields:
        updates["daily_cost_cap_usd"] = req.daily_cost_cap_usd
    if "cost_cap_warn_pct" in fields:
        updates["cost_cap_warn_pct"] = req.cost_cap_warn_pct
    if "schema_yaml_path" in fields:
        updates["schema_yaml_path"] = req.schema_yaml_path
    if "timezone" in fields:
        updates["timezone"] = req.timezone
    if not updates:
        return patch
    # `model_copy(update=...)` re-validates field types and preserves the
    # `model_fields_set` markers we care about — see Pydantic v2 docs.
    return patch.model_copy(update=updates)


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


# ---------- routes -----------------------------------------------------


@router.get(
    "/v1/libraries/{library_id}/settings",
    response_model=LibrarySettingsResponse,
    summary="Read effective per-library configuration overrides",
)
async def get_library_settings(
    library_id: str = Path(..., description="Library slug"),
    container: AppContainer = Depends(get_container),
    store: PostgresLibraryConfigStore = Depends(get_library_config_store),
    _principal: Principal = Depends(get_current_principal),
) -> LibrarySettingsResponse:
    await _ensure_library(container, library_id)
    config = await store.get(library_id)
    return _config_to_response(config)


@router.put(
    "/v1/libraries/{library_id}/settings",
    response_model=LibrarySettingsResponse,
    summary="Partial update of per-library overrides (PATCH semantics)",
)
async def update_library_settings(
    body: LibrarySettingsPatchRequest,
    library_id: str = Path(..., description="Library slug"),
    container: AppContainer = Depends(get_container),
    store: PostgresLibraryConfigStore = Depends(get_library_config_store),
    principal: Principal = Depends(get_current_principal),
) -> LibrarySettingsResponse:
    await _ensure_library(container, library_id)
    patch = _request_to_patch(body)
    async with with_span(
        "api.library_settings.update",
        library_id=library_id,
        actor=principal.id,
    ):
        config = await store.update(library_id, patch, updated_by=principal.id)
    await logger.ainfo(
        "library_settings_updated",
        library_id=library_id,
        actor=principal.id,
        changed_fields=sorted(patch.model_fields_set),
    )
    return _config_to_response(config)


def _to_cost_entry(row: LibraryDailyCost) -> DailyCostEntry:
    return DailyCostEntry(
        date=row.date,
        cost_usd=row.cost_usd,
        request_count=row.llm_calls,
    )


def _empty_today(today: date) -> DailyCostEntry:
    return DailyCostEntry(date=today, cost_usd=Decimal("0"), request_count=0)


@router.get(
    "/v1/libraries/{library_id}/cost",
    response_model=LibraryCostResponse,
    summary="Today's cost + recent daily history (ADR-0015 §8)",
)
async def get_library_cost(
    library_id: str = Path(..., description="Library slug"),
    days: int = Query(
        default=_DEFAULT_HISTORY_DAYS,
        ge=1,
        le=_MAX_HISTORY_DAYS,
        description="Number of days of history to include (incl. today).",
    ),
    container: AppContainer = Depends(get_container),
    store: PostgresLibraryConfigStore = Depends(get_library_config_store),
    enforcer: PostgresCostCapEnforcer = Depends(get_cost_enforcer),
    _principal: Principal = Depends(get_current_principal),
) -> LibraryCostResponse:
    await _ensure_library(container, library_id)
    config = await store.get(library_id)
    cap = config.daily_cost_cap_usd
    history_rows = await enforcer.history(library_id, days=days)
    history = tuple(_to_cost_entry(r) for r in history_rows)
    today = max(row.date for row in history_rows) if history_rows else datetime.now(tz=UTC).date()
    today_entry = next(
        (entry for entry in history if entry.date == today),
        _empty_today(today),
    )
    older = tuple(entry for entry in history if entry.date != today)
    return LibraryCostResponse(
        library_id=library_id,
        cap_usd=cap,
        today=today_entry,
        history=older,
    )
