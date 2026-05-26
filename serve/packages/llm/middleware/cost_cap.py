"""Cost-cap middleware around any ``LLMClient`` (ADR-0015 §3 / ADR_REVIEW §10.2).

Composition pattern: the middleware wraps an inner client and adds two
gates:

- **Pre-call**: refuse the request when the per-Library daily counter is
  ≥ ``cap_usd``. Raises ``CostCapBlockedError`` (mapped to HTTP 402 by
  the API error envelope).
- **Post-call**: increment the counter atomically and emit edge-triggered
  warnings via the wired notifier (handled inside ``CostCapEnforcer``).

This stays out of ``packages.llm.adapters.*`` on purpose — those are pure
LLM providers; cost discipline is a cross-cutting policy that belongs in
the middleware layer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

import structlog

from packages.llm.protocols import LLMClient, LLMResponse, Message
from packages.observability import with_span

logger = structlog.get_logger(__name__)


class CostCapBlockedError(Exception):
    """Raised when a per-Library daily cap is exhausted before a call.

    Local to the LLM package so callers can catch it without depending on
    ``packages.orchestration.errors``. Mapped to HTTP 402 (ADR-0015 §9).
    """

    def __init__(
        self,
        library_id: str,
        spent_usd: Decimal,
        cap_usd: Decimal | None,
    ) -> None:
        self.library_id = library_id
        self.spent_usd = spent_usd
        self.cap_usd = cap_usd
        super().__init__(
            f"Daily cost cap reached: library_id={library_id!r} spent={spent_usd} cap={cap_usd}"
        )


@runtime_checkable
class _CostCapPort(Protocol):
    """Minimal contract this middleware needs from the cost enforcer.

    Defined locally so we can inject a fake in tests without importing
    the orchestration package (which would create a layering violation).
    """

    async def check(self, library_id: str) -> _CostCheckLike: ...

    async def record(
        self,
        library_id: str,
        cost_usd: Decimal,
        llm_calls: int = 1,
    ) -> _CostCheckLike: ...


@runtime_checkable
class _CostCheckLike(Protocol):
    decision: str
    spent_usd: Decimal
    cap_usd: Decimal | None
    pct_used: float


class CostCapMiddleware:
    """``LLMClient`` decorator that enforces a per-Library daily cost cap.

    Constructor takes the inner client (typed against the
    ``LLMClient`` Protocol — any adapter works) and a ``CostCapPort``.
    The middleware exposes the same ``complete`` signature plus a
    library-scoped ``call(library_id, messages, ...)`` that does the
    pre-/post-checks. The plain ``complete`` raises ``RuntimeError`` to
    forbid library-less calls — a deliberate fail-fast.
    """

    def __init__(
        self,
        *,
        inner: LLMClient,
        enforcer: _CostCapPort,
    ) -> None:
        self._inner = inner
        self._enforcer = enforcer

    async def call(
        self,
        library_id: str,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse:
        """Library-scoped variant of ``complete`` with cap enforcement."""
        async with with_span("llm.cost_cap_middleware", library_id=library_id):
            pre = await self._enforcer.check(library_id)
            if pre.decision == "blocked":
                await logger.awarning(
                    "llm_cost_cap_blocked",
                    library_id=library_id,
                    spent_usd=str(pre.spent_usd),
                    cap_usd=str(pre.cap_usd) if pre.cap_usd is not None else None,
                )
                raise CostCapBlockedError(
                    library_id=library_id,
                    spent_usd=pre.spent_usd,
                    cap_usd=pre.cap_usd,
                )
            response = await self._inner.complete(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
            )
            try:
                await self._enforcer.record(
                    library_id, Decimal(str(response.cost_usd)), llm_calls=1
                )
            except Exception as exc:
                await logger.aerror(
                    "llm_cost_cap_record_failed",
                    library_id=library_id,
                    error=repr(exc),
                )
            return response

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse:
        """Forwarder for the bare ``LLMClient`` Protocol (no library scope).

        Raises ``RuntimeError`` — every callsite that owns a library_id
        must use ``call(library_id, ...)`` instead. Keeping this method
        present preserves Protocol compatibility for places that pass the
        wrapped client around as a generic ``LLMClient``.
        """
        raise RuntimeError(
            "CostCapMiddleware.complete: use call(library_id, ...) for library-scoped LLM access"
        )
