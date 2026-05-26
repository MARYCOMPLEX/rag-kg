"""Integration test for the Prometheus /metrics endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from packages.observability.metrics import LLM_TOKENS_TOTAL


@pytest.mark.asyncio
async def test_metrics_returns_prometheus_exposition() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    # Prometheus text exposition format uses this content-type prefix
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    # HELP/TYPE lines for any of our registered metrics must appear
    assert "# HELP rag_llm_duration_seconds" in body
    assert "# TYPE rag_llm_duration_seconds histogram" in body


@pytest.mark.asyncio
async def test_metrics_reflects_counter_increments() -> None:
    LLM_TOKENS_TOTAL.labels(model="metrics-test", kind="input", library_id="lib-metrics-test").inc(
        7
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")

    body = response.text
    assert 'model="metrics-test"' in body
    assert 'library_id="lib-metrics-test"' in body
