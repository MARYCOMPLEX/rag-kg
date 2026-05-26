"""Unit tests for ``packages.observability.tracing``.

Verifies idempotent setup, decorator/context-manager wrapping, library_id
auto-attachment, and graceful behaviour when the SDK is disabled.
"""

from __future__ import annotations

from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.util._once import Once

from packages.observability import tracing as tracing_module
from packages.observability.tracing import (
    TracingConfig,
    get_tracer,
    setup_tracing,
    traced_async,
    with_span,
)


class _RecordingExporter(SpanExporter):
    """In-memory span sink for assertions."""

    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []

    def export(self, spans: Any) -> SpanExportResult:  # type: ignore[override]
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def _reset_global_otel_state() -> None:
    """OTel guards ``set_tracer_provider`` with a one-shot ``Once`` lock.

    Tests need a clean slate, so we punch through both the slot and the lock.
    """
    tracing_module._provider_installed = False
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    trace._TRACER_PROVIDER_SET_ONCE = Once()  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _reset_tracer_provider() -> Any:
    """Each test starts with a clean global TracerProvider."""
    _reset_global_otel_state()
    yield
    _reset_global_otel_state()


@pytest.fixture
def recording_provider() -> tuple[TracerProvider, _RecordingExporter]:
    """A fresh TracerProvider with an in-memory exporter for assertions."""
    exporter = _RecordingExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    tracing_module._provider_installed = True
    return provider, exporter


class TestSetupTracing:
    def test_disabled_setup_is_noop(self) -> None:
        before = trace.get_tracer_provider()
        setup_tracing(TracingConfig(enabled=False))
        assert trace.get_tracer_provider() is before

    def test_enabled_setup_without_endpoint_installs_provider(self) -> None:
        setup_tracing(TracingConfig(enabled=True, otlp_endpoint=""))
        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)

    def test_enabled_setup_is_idempotent(self) -> None:
        setup_tracing(TracingConfig(enabled=True))
        first = trace.get_tracer_provider()
        setup_tracing(TracingConfig(enabled=True))
        second = trace.get_tracer_provider()
        assert first is second


class TestGetTracer:
    def test_returns_tracer_when_disabled(self) -> None:
        tracer = get_tracer("test.module")
        assert tracer is not None

    def test_returns_tracer_when_enabled(self) -> None:
        setup_tracing(TracingConfig(enabled=True))
        tracer = get_tracer("test.module")
        assert tracer is not None


class TestTracedAsyncDecorator:
    @pytest.mark.asyncio
    async def test_wraps_function_with_span_name(
        self,
        recording_provider: tuple[TracerProvider, _RecordingExporter],
    ) -> None:
        _, exporter = recording_provider

        @traced_async("custom.span.name")
        async def work() -> int:
            return 42

        result = await work()

        assert result == 42
        assert len(exporter.spans) == 1
        assert exporter.spans[0].name == "custom.span.name"

    @pytest.mark.asyncio
    async def test_extracts_library_id_from_kwargs(
        self,
        recording_provider: tuple[TracerProvider, _RecordingExporter],
    ) -> None:
        _, exporter = recording_provider

        @traced_async("op")
        async def op(library_id: str, query: str) -> str:
            return f"{library_id}:{query}"

        await op(library_id="lib-42", query="hello")

        span_attrs = dict(exporter.spans[0].attributes or {})
        assert span_attrs["library_id"] == "lib-42"

    @pytest.mark.asyncio
    async def test_extracts_library_id_from_positional_arg(
        self,
        recording_provider: tuple[TracerProvider, _RecordingExporter],
    ) -> None:
        _, exporter = recording_provider

        @traced_async("op")
        async def op(library_id: str) -> str:
            return library_id

        await op("lib-positional")

        span_attrs = dict(exporter.spans[0].attributes or {})
        assert span_attrs["library_id"] == "lib-positional"

    @pytest.mark.asyncio
    async def test_no_library_id_attribute_when_param_absent(
        self,
        recording_provider: tuple[TracerProvider, _RecordingExporter],
    ) -> None:
        _, exporter = recording_provider

        @traced_async("op")
        async def op(payload: str) -> str:
            return payload

        await op("data")

        span_attrs = dict(exporter.spans[0].attributes or {})
        assert "library_id" not in span_attrs

    @pytest.mark.asyncio
    async def test_static_attributes_applied(
        self,
        recording_provider: tuple[TracerProvider, _RecordingExporter],
    ) -> None:
        _, exporter = recording_provider

        @traced_async("op", attributes={"adapter": "qdrant", "kind": "search"})
        async def op() -> None:
            return None

        await op()

        span_attrs = dict(exporter.spans[0].attributes or {})
        assert span_attrs["adapter"] == "qdrant"
        assert span_attrs["kind"] == "search"


class TestWithSpan:
    @pytest.mark.asyncio
    async def test_attributes_set_correctly(
        self,
        recording_provider: tuple[TracerProvider, _RecordingExporter],
    ) -> None:
        _, exporter = recording_provider

        async with with_span("manual", library_id="lib-x", k=10, mode="vector"):
            pass

        assert len(exporter.spans) == 1
        recorded = exporter.spans[0]
        assert recorded.name == "manual"
        attrs = dict(recorded.attributes or {})
        assert attrs["library_id"] == "lib-x"
        assert attrs["k"] == 10
        assert attrs["mode"] == "vector"

    @pytest.mark.asyncio
    async def test_omits_library_id_when_none(
        self,
        recording_provider: tuple[TracerProvider, _RecordingExporter],
    ) -> None:
        _, exporter = recording_provider

        async with with_span("manual"):
            pass

        attrs = dict(exporter.spans[0].attributes or {})
        assert "library_id" not in attrs
