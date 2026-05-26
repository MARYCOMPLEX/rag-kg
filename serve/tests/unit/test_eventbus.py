"""Tests for the in-memory event bus."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.core.models import DomainEvent
from packages.eventbus.protocols import EventBus
from packages.eventbus.service import InMemoryEventBus


def _make_event(library_id: str = "test-lib") -> DomainEvent:
    return DomainEvent(
        library_id=library_id,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        event_type="test.event",
    )


class TestInMemoryEventBus:
    def test_implements_protocol(self) -> None:
        bus = InMemoryEventBus()
        assert isinstance(bus, EventBus)

    @pytest.mark.asyncio
    async def test_publish_to_subscribed_handler(self) -> None:
        bus = InMemoryEventBus()
        received: list[DomainEvent] = []

        async def handler(event: DomainEvent) -> None:
            received.append(event)

        bus.subscribe("test.event", handler)
        event = _make_event()
        await bus.publish("test.event", event)

        assert len(received) == 1
        assert received[0] == event

    @pytest.mark.asyncio
    async def test_publish_to_no_subscribers_is_noop(self) -> None:
        bus = InMemoryEventBus()
        event = _make_event()
        await bus.publish("nonexistent.topic", event)

    @pytest.mark.asyncio
    async def test_multiple_handlers_all_receive_event(self) -> None:
        bus = InMemoryEventBus()
        results: list[str] = []

        async def handler_a(event: DomainEvent) -> None:
            results.append("a")

        async def handler_b(event: DomainEvent) -> None:
            results.append("b")

        bus.subscribe("test.event", handler_a)
        bus.subscribe("test.event", handler_b)
        await bus.publish("test.event", _make_event())

        assert results == ["a", "b"]

    @pytest.mark.asyncio
    async def test_different_topics_are_isolated(self) -> None:
        bus = InMemoryEventBus()
        received_a: list[DomainEvent] = []
        received_b: list[DomainEvent] = []

        async def handler_a(event: DomainEvent) -> None:
            received_a.append(event)

        async def handler_b(event: DomainEvent) -> None:
            received_b.append(event)

        bus.subscribe("topic.a", handler_a)
        bus.subscribe("topic.b", handler_b)

        await bus.publish("topic.a", _make_event())

        assert len(received_a) == 1
        assert len(received_b) == 0
