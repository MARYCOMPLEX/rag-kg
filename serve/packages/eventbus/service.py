"""In-memory event bus implementation."""

from __future__ import annotations

from collections import defaultdict

from packages.core.models import DomainEvent
from packages.eventbus.protocols import EventHandler


class InMemoryEventBus:
    """Simple in-memory pub/sub for domain events.

    Handlers are called sequentially in subscription order.
    Suitable for single-process deployments; swap to Kafka/Redis
    adapter when scaling out.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Register a handler for a topic."""
        self._handlers[topic].append(handler)

    async def publish(self, topic: str, event: DomainEvent) -> None:
        """Dispatch event to all handlers for the topic."""
        for handler in self._handlers.get(topic, []):
            await handler(event)
