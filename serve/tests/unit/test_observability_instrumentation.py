"""Tests for the @instrumented decorator (OTel + Prometheus)."""

from __future__ import annotations

import secrets

import pytest
from prometheus_client import Histogram

from packages.observability.instrumentation import instrumented


@pytest.fixture
def fresh_histogram() -> Histogram:
    """Create a per-test histogram so labels don't accumulate across tests."""
    name = f"test_hist_{secrets.token_hex(4)}_seconds"
    return Histogram(
        name,
        "Test histogram",
        labelnames=("library_id", "op"),
    )


class TestInstrumentedDecorator:
    @pytest.mark.asyncio
    async def test_returns_value_unchanged(self, fresh_histogram: Histogram) -> None:
        @instrumented(
            op_name="test.op",
            component="test",
            histogram=fresh_histogram,
            label_from_arg={"library_id": "library_id", "op": "op"},
        )
        async def fn(library_id: str, op: str) -> int:
            return 42

        assert await fn("lib-x", "search") == 42

    @pytest.mark.asyncio
    async def test_records_histogram_observation(self, fresh_histogram: Histogram) -> None:
        @instrumented(
            op_name="test.op",
            component="test",
            histogram=fresh_histogram,
            label_from_arg={"library_id": "library_id"},
            histogram_labels={"op": "search"},
        )
        async def fn(library_id: str) -> str:
            return "ok"

        await fn("lib-x")
        sample_count = fresh_histogram.labels(library_id="lib-x", op="search")._sum.get()
        assert sample_count > 0  # observed at least one duration

    @pytest.mark.asyncio
    async def test_observes_on_exception(self, fresh_histogram: Histogram) -> None:
        @instrumented(
            op_name="test.op",
            component="test",
            histogram=fresh_histogram,
            label_from_arg={"library_id": "library_id"},
            histogram_labels={"op": "search"},
        )
        async def fn(library_id: str) -> str:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await fn("lib-x")
        # Histogram still observes failed call duration
        sample_count = fresh_histogram.labels(library_id="lib-x", op="search")._sum.get()
        assert sample_count > 0

    @pytest.mark.asyncio
    async def test_no_histogram_still_works(self) -> None:
        @instrumented(op_name="test.op", component="test")
        async def fn(library_id: str) -> int:
            return 7

        assert await fn("lib-x") == 7

    @pytest.mark.asyncio
    async def test_extracts_library_id_from_kwargs(self, fresh_histogram: Histogram) -> None:
        @instrumented(
            op_name="test.op",
            component="test",
            histogram=fresh_histogram,
            label_from_arg={"library_id": "library_id", "op": "op"},
        )
        async def fn(*, library_id: str, op: str) -> int:
            return 1

        await fn(library_id="kw-lib", op="upsert")
        sample_count = fresh_histogram.labels(library_id="kw-lib", op="upsert")._sum.get()
        assert sample_count > 0
