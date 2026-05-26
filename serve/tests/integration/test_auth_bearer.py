"""Tests for the optional bearer-token auth dep."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from apps.api.auth import Principal, get_current_principal


def _request_with_auth(header: str | None) -> Request:
    headers = []
    if header is not None:
        headers.append((b"authorization", header.encode("ascii")))
    scope = {
        "type": "http",
        "headers": headers,
        "method": "GET",
        "path": "/",
        "query_string": b"",
    }
    return Request(scope)


def _container_with_key(key: str) -> object:
    container = MagicMock()
    container.settings = MagicMock()
    container.settings.api_key = key
    return container


@pytest.mark.asyncio
async def test_anonymous_when_api_key_empty() -> None:
    request = _request_with_auth(None)
    principal = await get_current_principal(request, _container_with_key(""))  # type: ignore[arg-type]
    assert isinstance(principal, Principal)
    assert principal.kind == "anonymous"


@pytest.mark.asyncio
async def test_missing_bearer_when_required_raises_401() -> None:
    request = _request_with_auth(None)
    with pytest.raises(HTTPException) as ctx:
        await get_current_principal(request, _container_with_key("secret"))  # type: ignore[arg-type]
    assert ctx.value.status_code == 401


@pytest.mark.asyncio
async def test_wrong_bearer_raises_401() -> None:
    request = _request_with_auth("Bearer wrong-token")
    with pytest.raises(HTTPException) as ctx:
        await get_current_principal(request, _container_with_key("secret"))  # type: ignore[arg-type]
    assert ctx.value.status_code == 401


@pytest.mark.asyncio
async def test_correct_bearer_resolves_principal() -> None:
    request = _request_with_auth("Bearer secret")
    principal = await get_current_principal(request, _container_with_key("secret"))  # type: ignore[arg-type]
    assert principal.kind == "api_key"
    assert principal.id.startswith("key:")


@pytest.mark.asyncio
async def test_async_mock_call_pattern() -> None:
    """Sanity check — get_current_principal does not await the container."""
    container = _container_with_key("")
    container.refresh = AsyncMock()  # type: ignore[attr-defined]
    request = _request_with_auth(None)
    p = await get_current_principal(request, container)  # type: ignore[arg-type]
    container.refresh.assert_not_called()  # type: ignore[attr-defined]
    assert p.kind == "anonymous"
