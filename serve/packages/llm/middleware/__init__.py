"""LLM Gateway middleware (composition pattern, ADR_REVIEW §10.2).

Wraps an inner ``LLMClient`` with cross-cutting policies (cost cap,
retry, observability). Each middleware stays a pure decorator: it does
NOT mutate ``LLMClient.complete`` itself.
"""

from packages.llm.middleware.cost_cap import (
    CostCapBlockedError,
    CostCapMiddleware,
)

__all__ = [
    "CostCapBlockedError",
    "CostCapMiddleware",
]
