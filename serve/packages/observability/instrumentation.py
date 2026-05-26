"""Combined OpenTelemetry + Prometheus instrumentation decorator.

Use `@instrumented(...)` on async adapter methods to emit:
  - One OpenTelemetry span (with library_id auto-extracted from kwargs/positional)
  - One Prometheus duration observation (labels resolved at call time)
"""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable, Coroutine, Mapping
from typing import Any, TypeVar, cast

from opentelemetry.trace import Status, StatusCode
from prometheus_client import Histogram

from packages.observability.tracing import get_tracer

F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, Any]])


def instrumented(
    *,
    op_name: str,
    component: str,
    histogram: Histogram | None = None,
    histogram_labels: Mapping[str, str] | None = None,
    label_from_arg: Mapping[str, str] | None = None,
    record_exceptions: bool = True,
) -> Callable[[F], F]:
    """Decorate an async method with both OTel span and Prometheus histogram.

    Args:
        op_name: span name + Prometheus `op` label value.
        component: high-level component (qdrant, neo4j, openai_llm, ...).
        histogram: Prometheus Histogram to record duration into. If None, no
            metric is recorded (OTel span only).
        histogram_labels: static label values applied on every call.
        label_from_arg: mapping from histogram label name to function argument
            name. Each named arg is read at call time and stringified into the
            label value (e.g., {"library_id": "library_id"} pulls library_id
            from the wrapped function's signature).
        record_exceptions: whether to attach exception info to the span on raise.

    Notes:
        - `library_id` is automatically extracted into the span attributes if
          present in the function signature (consistent with `traced_async`).
        - On exception the histogram is still observed so error latency is
          counted (operators want to see failed call duration too).
    """
    static_labels: dict[str, str] = dict(histogram_labels or {})
    arg_label_map: dict[str, str] = dict(label_from_arg or {})

    def _decorator(func: F) -> F:
        sig = inspect.signature(func)
        param_names = tuple(sig.parameters.keys())

        @functools.wraps(func)
        async def _wrapped(*args: Any, **kwargs: Any) -> Any:
            bound_kwargs = _bind_kwargs(param_names, args, kwargs)
            library_id = _stringify_optional(bound_kwargs.get("library_id"))

            tracer = get_tracer(__name__)
            span_attrs: dict[str, str | int | float | bool] = {
                "component": component,
                "op": op_name,
            }
            if library_id is not None:
                span_attrs["library_id"] = library_id

            label_values: dict[str, str] = dict(static_labels)
            for label_name, arg_name in arg_label_map.items():
                if arg_name in bound_kwargs:
                    label_values[label_name] = _stringify(bound_kwargs[arg_name])

            started = time.perf_counter()
            with tracer.start_as_current_span(op_name) as span:
                for k, v in span_attrs.items():
                    span.set_attribute(k, v)
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    if record_exceptions:
                        span.record_exception(exc)
                        span.set_status(_otel_error_status(exc))
                    raise
                finally:
                    if histogram is not None:
                        elapsed_s = time.perf_counter() - started
                        try:
                            histogram.labels(**label_values).observe(elapsed_s)
                        except (ValueError, KeyError):
                            histogram.observe(elapsed_s)

        return cast(F, _wrapped)

    return _decorator


def _bind_kwargs(
    param_names: tuple[str, ...],
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    bound: dict[str, Any] = dict(kwargs)
    for name, value in zip(param_names, args, strict=False):
        bound.setdefault(name, value)
    return bound


def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return type(value).__name__


def _stringify_optional(value: object) -> str | None:
    if value is None:
        return None
    return _stringify(value)


def _otel_error_status(exc: BaseException) -> Status:
    return Status(StatusCode.ERROR, description=type(exc).__name__ + ": " + str(exc))
