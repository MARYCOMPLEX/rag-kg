"""FastAPI application entry point.

M1: /healthz, /readyz, /v1/libraries CRUD + ingest + QA.
M6: /metrics for Prometheus scraping.
M7: unified error envelope, request-id middleware, optional rate-limit and
    bearer-token auth (gated by Settings).
"""

from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, ConfigDict

from apps.api.deps import get_container
from apps.api.middleware import (
    RateLimitMiddleware,
    RequestIdMiddleware,
    register_exception_handlers,
)
from apps.api.routes import collect_routers
from packages.observability.metrics import get_registry


class HealthResponse(BaseModel):
    """Health check response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str
    version: str


def create_app() -> FastAPI:
    """Application factory — keeps test harness composable."""
    settings = get_container().settings
    application = FastAPI(
        title="RAG-KG Copilot",
        version="0.1.0",
        docs_url="/docs",
    )
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    application.add_middleware(
        RateLimitMiddleware,
        enabled=settings.rate_limit_enabled,
        rpm=settings.rate_limit_rpm,
        burst=settings.rate_limit_burst,
        redis_url=settings.redis_url,
        api_key=settings.api_key,
    )
    application.add_middleware(RequestIdMiddleware)
    register_exception_handlers(application)
    for router in collect_routers():
        application.include_router(router)

    application.add_api_route("/metrics", _metrics, methods=["GET"])
    application.add_api_route("/healthz", _healthz, methods=["GET"], response_model=HealthResponse)
    application.add_api_route("/readyz", _readyz, methods=["GET"], response_model=HealthResponse)
    return application


async def _metrics() -> Response:
    payload = generate_latest(get_registry())
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


async def _healthz() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


async def _readyz() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


app = create_app()
