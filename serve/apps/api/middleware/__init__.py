"""HTTP middleware + exception-handler registration."""

from apps.api.middleware.error_handler import register_exception_handlers
from apps.api.middleware.rate_limit import RateLimitMiddleware
from apps.api.middleware.request_id import RequestIdMiddleware

__all__ = [
    "RateLimitMiddleware",
    "RequestIdMiddleware",
    "register_exception_handlers",
]
