"""OpenTelemetry tracing helpers.

Idempotent ``TracerProvider`` setup, a typed ``traced_async`` decorator, and a
small ``with_span`` async context manager. Adapters call these helpers without
binding to OTel internals, so they degrade to no-ops when tracing is disabled.

Design notes:
- ``setup_tracing`` is idempotent: calling it again with tracing disabled does
  nothing; calling it again with tracing enabled keeps the original provider.
- The OTLP HTTP exporter is imported lazily so the dependency stays optional.
- ``traced_async`` introspects the wrapped function's signature once and, if a
  ``library_id: str`` parameter exists, propagates its runtime value as a span
  attribute on every invocation.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import wraps
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
)
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

P = ParamSpec("P")
R = TypeVar("R")

_LIBRARY_ID_ATTR = "library_id"
_SERVICE_NAME_ATTR = "service.name"
_EMPTY_RESOURCE_ATTRS: Mapping[str, str] = MappingProxyType({})

# Module-level marker so we never replace an SDK provider we already installed.
# Mutated by `setup_tracing`; spelled lowercase to satisfy pyright's
# constant-redefinition check.
_provider_installed: bool = False


@dataclass(frozen=True, slots=True)
class TracingConfig:
    """Tracing configuration.

    - ``enabled``: master switch. When ``False``, ``setup_tracing`` is a no-op
      and a NoOp tracer is used everywhere.
    - ``otlp_endpoint``: when empty, no OTLP exporter is registered. The
      provider still works (spans are dropped); a console exporter can be
      attached by setting ``console_exporter=True``.
    - ``sample_rate``: 0.0 disables sampling, 1.0 samples every trace.
    """

    enabled: bool = False
    service_name: str = "rag-kg-copilot"
    otlp_endpoint: str = ""
    sample_rate: float = 1.0
    console_exporter: bool = False
    resource_attributes: Mapping[str, str] = field(default_factory=lambda: _EMPTY_RESOURCE_ATTRS)


def _build_sampler(sample_rate: float) -> Sampler:
    if sample_rate <= 0.0:
        return ALWAYS_OFF
    if sample_rate >= 1.0:
        return ALWAYS_ON
    return ParentBased(root=TraceIdRatioBased(sample_rate))


def _build_resource(config: TracingConfig) -> Resource:
    attrs: dict[str, Any] = {_SERVICE_NAME_ATTR: config.service_name}
    attrs.update(config.resource_attributes)
    return Resource.create(attrs)


def _build_otlp_exporter(endpoint: str) -> SpanExporter | None:
    """Lazily import the OTLP HTTP exporter; return ``None`` if unavailable."""
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: PLC0415
            OTLPSpanExporter,
        )
    except ImportError:
        return None
    return OTLPSpanExporter(endpoint=endpoint)


def setup_tracing(config: TracingConfig) -> None:
    """Install the global ``TracerProvider``.

    Idempotent: subsequent calls are no-ops once a provider has been installed
    by this function. Disabled config is a true no-op (callers will fall back
    to OTel's built-in ProxyTracer / NoOp behaviour).
    """
    global _provider_installed  # noqa: PLW0603
    if not config.enabled:
        return
    if _provider_installed:
        return

    provider = TracerProvider(
        resource=_build_resource(config),
        sampler=_build_sampler(config.sample_rate),
    )

    if config.otlp_endpoint:
        exporter = _build_otlp_exporter(config.otlp_endpoint)
        if exporter is not None:
            provider.add_span_processor(BatchSpanProcessor(exporter))

    if config.console_exporter:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _provider_installed = True


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer; safe to call before or after ``setup_tracing``."""
    return trace.get_tracer(name)


def _resolve_library_id(
    sig: inspect.Signature,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str | None:
    if _LIBRARY_ID_ATTR not in sig.parameters:
        return None
    try:
        bound = sig.bind_partial(*args, **kwargs)
    except TypeError:
        return None
    value = bound.arguments.get(_LIBRARY_ID_ATTR)
    if isinstance(value, str):
        return value
    return None


def _apply_attributes(
    span: trace.Span,
    attributes: dict[str, str] | None,
) -> None:
    if not attributes:
        return
    for key, value in attributes.items():
        span.set_attribute(key, value)


def traced_async(
    span_name: str,
    *,
    attributes: dict[str, str] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Wrap an async function in a span.

    If the wrapped function declares a ``library_id: str`` parameter, the
    runtime value is attached as a span attribute automatically.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        sig = inspect.signature(func)
        tracer = get_tracer(func.__module__)

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with tracer.start_as_current_span(span_name) as span:
                _apply_attributes(span, attributes)
                library_id = _resolve_library_id(sig, args, kwargs)
                if library_id is not None:
                    span.set_attribute(_LIBRARY_ID_ATTR, library_id)
                return await func(*args, **kwargs)

        return cast(Callable[P, Awaitable[R]], wrapper)

    return decorator


@asynccontextmanager
async def with_span(
    name: str,
    library_id: str | None = None,
    **attrs: str | int | float | bool,
) -> AsyncGenerator[trace.Span]:
    """Async context manager that opens a span for ad-hoc instrumentation."""
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span(name) as span:
        if library_id is not None:
            span.set_attribute(_LIBRARY_ID_ATTR, library_id)
        for key, value in attrs.items():
            span.set_attribute(key, value)
        yield span
