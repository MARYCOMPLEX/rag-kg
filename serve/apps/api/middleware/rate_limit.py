"""Redis-backed token-bucket rate limiter.

Disabled by default (`Settings.rate_limit_enabled = False`) so existing tests
keep their hot-path. When enabled, throttles per (principal, route) with
configurable rpm + burst.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastapi.responses import JSONResponse
from redis.asyncio import from_url as _redis_from_url  # pyright: ignore[reportUnknownVariableType]
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from apps.api.middleware.request_id import get_request_id
from packages.core.api_errors import ErrorCode, ErrorEnvelope

_log = logging.getLogger(__name__)

_BYPASS_PATHS: frozenset[str] = frozenset(
    {"/healthz", "/readyz", "/metrics", "/docs", "/openapi.json", "/redoc"}
)

# Atomic Lua: refill bucket then consume one token; returns
# (allowed, remaining_tokens, retry_after_seconds).
_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_per_sec = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'updated')
local tokens = tonumber(data[1])
local updated = tonumber(data[2])
if tokens == nil then tokens = capacity end
if updated == nil then updated = now end

local elapsed = math.max(0, now - updated)
tokens = math.min(capacity, tokens + elapsed * refill_per_sec)

local allowed = 0
local retry_after = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  retry_after = (cost - tokens) / refill_per_sec
end

redis.call('HMSET', key, 'tokens', tokens, 'updated', now)
redis.call('EXPIRE', key, 3600)
return {allowed, tokens, retry_after}
"""


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter that gracefully degrades if Redis is unreachable."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool,
        rpm: int,
        burst: int,
        redis_url: str,
        api_key: str = "",
    ) -> None:
        super().__init__(app)
        self._enabled = enabled
        self._rpm = max(1, rpm)
        self._burst = max(1, burst)
        self._refill_per_sec = self._rpm / 60.0
        self._redis_url = redis_url
        self._api_key = api_key
        self._redis: Any = None
        self._script_sha: str | None = None

    async def _ensure_redis(self) -> Any:
        if self._redis is None:
            self._redis = _redis_from_url(self._redis_url, decode_responses=True)  # pyright: ignore[reportUnknownMemberType]
        return self._redis

    def _principal(self, request: Request) -> tuple[str, str]:
        """Returns (principal_id, principal_kind)."""
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
            if token:
                return (f"key:{token[:8]}", "api_key")
        client = request.client
        ip = client.host if client else "unknown"
        return (f"ip:{ip}", "ip")

    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not self._enabled or request.url.path in _BYPASS_PATHS:
            return await call_next(request)

        principal_id, principal_kind = self._principal(request)
        route = request.url.path
        key = f"rl:{principal_id}:{route}"
        try:
            redis = await self._ensure_redis()
            result = await redis.eval(
                _LUA,
                1,
                key,
                str(self._burst),
                str(self._refill_per_sec),
                str(time.time()),
                "1",
            )
        except Exception:
            _log.warning("rate-limit fail-open: redis unreachable", exc_info=True)
            return await call_next(request)

        result_list = cast(list[Any], result)
        allowed = int(result_list[0])
        retry_after_value = float(result_list[2])
        if allowed == 1:
            return await call_next(request)

        rid = get_request_id(request)
        body = ErrorEnvelope(
            code=ErrorCode.RATE_LIMITED,
            message="Too many requests — please retry after the indicated delay",
            request_id=rid,
            details={"principal_kind": principal_kind, "route": route},
        ).model_dump(mode="json")
        retry = max(1, int(retry_after_value + 0.999))
        headers = {"Retry-After": str(retry)}
        return JSONResponse(status_code=429, content=body, headers=headers)
