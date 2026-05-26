"""Lightweight bearer-token authentication.

When `Settings.api_key` is empty (the default for dev), every request resolves
as the anonymous principal. When it is set, the `Authorization: Bearer <token>`
header must match exactly (constant-time compare).
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from apps._shared.factories import AppContainer
from apps.api.deps import get_container


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated caller. `kind` is one of 'anonymous' | 'api_key'."""

    kind: str
    id: str


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    return token or None


async def get_current_principal(
    request: Request,
    container: AppContainer = Depends(get_container),
) -> Principal:
    expected = container.settings.api_key
    if not expected:
        return Principal(kind="anonymous", id="dev")

    provided = _extract_bearer(request)
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Principal(kind="api_key", id=f"key:{provided[:8]}")
