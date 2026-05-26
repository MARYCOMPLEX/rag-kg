"""End-to-end tests for the unified error envelope and request-id middleware."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app


@pytest.mark.asyncio
async def test_404_envelope_carries_request_id() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/v1/libraries/does-not-exist-zzz")
    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "LIBRARY_NOT_FOUND"
    assert body["request_id"]
    assert res.headers.get("x-request-id") == body["request_id"]
    assert body["details"] == {"library_id": "does-not-exist-zzz"}


@pytest.mark.asyncio
async def test_request_id_is_echoed_when_provided() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/healthz", headers={"X-Request-Id": "fixed-rid-123"})
    assert res.status_code == 200
    assert res.headers.get("x-request-id") == "fixed-rid-123"


@pytest.mark.asyncio
async def test_validation_error_envelope() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # POST /v1/libraries with missing required fields
        res = await client.post("/v1/libraries", json={})
    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["request_id"]
    assert isinstance(body["details"], list)
