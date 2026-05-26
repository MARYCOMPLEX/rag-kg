"""Retry policy for transient LLM/embedding HTTP failures.

Retries on:
- ReadTimeout / WriteTimeout / PoolTimeout
- ConnectError / RemoteProtocolError
- HTTPStatusError 5xx and 429

Does NOT retry on:
- 4xx (auth, bad request — fixing the request matters)
- Non-network exceptions
"""

from __future__ import annotations

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

_HTTP_SERVER_ERROR_MIN = 500
_HTTP_TOO_MANY_REQUESTS = 429


def _is_transient(exc: BaseException) -> bool:
    if isinstance(
        exc,
        httpx.ReadTimeout | httpx.WriteTimeout | httpx.PoolTimeout | httpx.ConnectTimeout,
    ):
        return True
    if isinstance(exc, httpx.RemoteProtocolError | httpx.ConnectError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status >= _HTTP_SERVER_ERROR_MIN or status == _HTTP_TOO_MANY_REQUESTS
    return False


def make_retrying(*, max_attempts: int = 3, initial_wait: float = 2.0) -> AsyncRetrying:
    """Build an AsyncRetrying for transient HTTP failures."""
    return AsyncRetrying(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=initial_wait, min=initial_wait, max=30.0),
        reraise=True,
        before_sleep=lambda rs: logger.warning(
            "llm_retry",
            attempt=rs.attempt_number,
            error=type(rs.outcome.exception()).__name__ if rs.outcome else None,
            wait_seconds=rs.next_action.sleep if rs.next_action else None,
        ),
    )
